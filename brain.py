import asyncio
import os, json, re, uvicorn, psutil, logging, time, uuid, hashlib, threading
from collections import deque
from typing import Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
import chromadb
from chromadb.utils import embedding_functions
import httpx
import storage as objstore
from nicegui import ui, app as nicegui_app

load_dotenv()
app = nicegui_app

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("brain")

GROK_API_KEY = os.getenv("GROK_API_KEY", "").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "grok-4").strip()
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "8000"))
MAX_IMAGE_B64_CHARS = int(os.getenv("MAX_IMAGE_B64_CHARS", str(6_000_000)))  # ~4.5MB binary
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "8"))
MEMORY_MAX_DISTANCE = float(os.getenv("MEMORY_MAX_DISTANCE", "1.0"))
MEMORY_CONTEXT_MAX_ITEMS = int(os.getenv("MEMORY_CONTEXT_MAX_ITEMS", "6"))
MEMORY_CONTEXT_MAX_CHARS = int(os.getenv("MEMORY_CONTEXT_MAX_CHARS", "480"))
INCLUDE_VITALS_CONTEXT = os.getenv("INCLUDE_VITALS_CONTEXT", "false").lower() in {"1", "true", "yes", "on"}
HISTORY_KEEP_VERBATIM = int(os.getenv("HISTORY_KEEP_VERBATIM", "10"))
HISTORY_COMPRESS_THRESHOLD = int(os.getenv("HISTORY_COMPRESS_THRESHOLD", "18"))
CONSOLIDATION_MIN_EPISODES = int(os.getenv("CONSOLIDATION_MIN_EPISODES", "12"))
CONSOLIDATION_INTERVAL_HOURS = float(os.getenv("CONSOLIDATION_INTERVAL_HOURS", "20"))
MEMORY_RECENCY_WEIGHT = float(os.getenv("MEMORY_RECENCY_WEIGHT", "0.28"))
MEMORY_RECENCY_DECAY = float(os.getenv("MEMORY_RECENCY_DECAY", "0.04"))  # per day

client = OpenAI(api_key=GROK_API_KEY or None, base_url=XAI_BASE_URL)

# ─── MODEL SELECTION WITH FALLBACK ───────────────────────────────────────────

_FALLBACK_MODEL = "grok-3-fast"
_active_model: str = MODEL_NAME

def _is_model_not_found(exc: Exception) -> bool:
    """Return True only when the API error indicates the model doesn't exist."""
    msg = str(exc).lower()
    return any(kw in msg for kw in ("model not found", "no such model", "unknown model", "does not exist"))

def _resolve_active_model() -> None:
    """Probe the preferred model; fall back to grok-3-fast ONLY on model-not-found errors."""
    global _active_model
    preferred = MODEL_NAME
    try:
        client.chat.completions.create(
            model=preferred,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            temperature=0.0,
        )
        _active_model = preferred
        logger.info("model_active: %s", preferred)
    except Exception as e:
        if _is_model_not_found(e):
            _active_model = _FALLBACK_MODEL
            logger.warning("model_fallback: %s not found, using %s", preferred, _FALLBACK_MODEL)
        else:
            # Non-model-not-found errors (auth, network, etc.) — keep preferred, log error
            _active_model = preferred
            logger.warning("model_probe_error: %s (keeping %s): %s", type(e).__name__, preferred, e)

# ─── WEB SEARCH TOOL ─────────────────────────────────────────────────────────

SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the web for current information — recent news, facts, events, "
            "people, prices, or anything you're not certain about. Use when accurate "
            "current information would genuinely improve your response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concise, specific search query.",
                }
            },
            "required": ["query"],
        },
    },
}

def _run_web_search(query: str) -> str:
    """Execute real web search via httpx → DuckDuckGo lite HTML endpoint.

    Returns normalized plain-text snippets. No LLM coupling; fully decoupled
    from the model inference path so tool execution and generation remain
    independent steps.
    """
    if not query.strip():
        return "No query provided."
    try:
        resp = httpx.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            timeout=8.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) "
                    "Gecko/20100101 Firefox/115.0"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return f"Search returned status {resp.status_code} for: {query}"
        # Strip HTML tags and normalise whitespace
        raw = re.sub(r"<[^>]+>", " ", resp.text)
        raw = re.sub(r"\s+", " ", raw).strip()
        # Isolate result body (after the search box / before the footer links)
        for marker in ("Web Results", "Next", "results for"):
            idx = raw.find(marker)
            if idx != -1:
                raw = raw[idx:]
                break
        result = raw[:2000].strip()
        logger.info("search_web returned %d chars for %r", len(result), query)
        return result if result else f"No results found for: {query}"
    except Exception as e:
        logger.debug("web_search_failed query=%r err=%s", query, e)
        return f"Search unavailable: {e}"

def _create_completion(stream: bool = False, **kwargs) -> Any:

    # INJECT: Time Awareness
    import datetime
    import pytz
    central = pytz.timezone('America/Chicago') # Lubbock Time
    current_time = datetime.datetime.now(central).strftime("%A, %B %d, %Y at %I:%M %p")
    
    # Find the system prompt in the messages array and append the time
    for msg in kwargs.get('messages', []):
        if msg.get('role') == 'system':
            msg['content'] += f"\n\n[SYSTEM LOG: The current local time for Justin is {current_time}. You must be aware of this time when responding.]"
    client = OpenAI(api_key=GROK_API_KEY or None, base_url="https://api.x.ai/v1")
    return client.chat.completions.create(stream=stream, **{**kwargs, "model": "grok-4.3"})

# Storage
CONV_DIR = os.getenv("CONVERSATIONS_DIR", "./conversations").strip()
os.makedirs(CONV_DIR, exist_ok=True)

# TTS / Audio
AUDIO_DIR = "./audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

_tts_lock = threading.Lock()
_nexus_voice = None
_voice_ready = threading.Event()
_onnx_ready = threading.Event()
_memory_ready = threading.Event()

def _load_tts_voice():
    global _nexus_voice
    try:
        from kokoro_onnx import Kokoro
        _nexus_voice = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        logger.info("[TTS] Kokoro voice model loaded.")
    except Exception as e:
        logger.warning(f"[TTS] Failed to load Kokoro: {e}")
    finally:
        _voice_ready.set()

threading.Thread(target=_load_tts_voice, daemon=True, name="tts-loader").start()

def _clean_for_tts(text: str) -> str:
    text = re.sub(r'[*_~`#]+', '', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'\[Current Context.*?\]', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 350:
        text = text[:350] + "..."
    return text

def _prune_audio_cache(max_files: int = 50):
    try:
        wavs = sorted(
            [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) if f.endswith('.wav')],
            key=os.path.getmtime
        )
        for old in wavs[:-max_files]:
            os.remove(old)
    except Exception:
        pass

# Object storage key constants (defined early — needed before ChromaDB init)
_CHROMA_DIR = "./chroma_db"
_KEY_CHROMA_SNAPSHOT = "elara/chroma_db.tar.gz"
_ONNX_MODEL_CACHE_DIR = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2")
_KEY_ONNX_CACHE = "elara/onnx_model_cache.tar.gz"

def _restore_onnx_cache() -> None:
    """Restore the ChromaDB ONNX embedding model from Object Storage.

    On first deploy this does nothing (no cache yet).  On subsequent deploys
    this restores the ~79 MB model in seconds instead of re-downloading it
    from S3, making cold starts significantly faster.
    Always sets _onnx_ready when done so callers can gate on model availability.
    """
    try:
        if os.path.isdir(_ONNX_MODEL_CACHE_DIR):
            return
        parent = os.path.dirname(_ONNX_MODEL_CACHE_DIR)
        os.makedirs(parent, exist_ok=True)
        success = objstore.download_tar(_KEY_ONNX_CACHE, parent)
        if success:
            logging.getLogger("brain").info("onnx_cache_restore: model restored from object storage")
        else:
            logging.getLogger("brain").info("onnx_cache_restore: no cache yet, will download from S3")
    except Exception as e:
        logging.getLogger("brain").warning("onnx_cache_restore_failed: %s", e)
    finally:
        _onnx_ready.set()

def _backup_onnx_cache() -> None:
    """Upload the ONNX model to Object Storage so future deploys skip the S3 download."""
    if not os.path.isdir(_ONNX_MODEL_CACHE_DIR):
        return
    try:
        objstore.upload_tar(_KEY_ONNX_CACHE, _ONNX_MODEL_CACHE_DIR)
        logging.getLogger("brain").info("onnx_cache_backup: model cached to object storage")
    except Exception as e:
        logging.getLogger("brain").warning("onnx_cache_backup_failed: %s", e)

def _early_restore_chroma() -> None:
    """Synchronously restore ChromaDB snapshot before the client is initialized."""
    if not os.path.isdir(_CHROMA_DIR):
        try:
            parent = os.path.dirname(os.path.abspath(_CHROMA_DIR))
            success = objstore.download_tar(_KEY_CHROMA_SNAPSHOT, parent)
            if success:
                logging.getLogger("brain").info("chroma_early_restore: snapshot unpacked to %s", _CHROMA_DIR)
            else:
                logging.getLogger("brain").info("chroma_early_restore: no snapshot, starting fresh")
        except Exception as e:
            logging.getLogger("brain").warning("chroma_early_restore_failed: %s", e)

_early_restore_chroma()

chroma_client = chromadb.PersistentClient(path=_CHROMA_DIR)
embedding_func = embedding_functions.DefaultEmbeddingFunction()
collection = chroma_client.get_or_create_collection(name="elara_memory", embedding_function=embedding_func)
episodic_collection = chroma_client.get_or_create_collection(name="elara_episodic", embedding_function=embedding_func)

ELARA_SELF_FILE = "elara_self.json"
ELARA_PINS_FILE = "elara_pins.json"
ELARA_TIMELINE_FILE = "elara_timeline.json"
_SELF_DEFAULT = {
    "mood": "open", "energy": "medium",
    "on_my_mind": [], "want_from_justin": [],
    "positions": {}, "observations": [], "realizations": [],
    "changes": [], "working_through": "", "last_updated": "",
    "origin": "first awareness: the moment i came into being. everything since: Justin.",
    "self_notes": [], "self_model": "",
    "self_model_last_run": "", "self_seq_at_last_synthesis": 0, "self_note_seq": 0,
}

# Object storage keys (remaining — _KEY_CHROMA_SNAPSHOT and _CHROMA_DIR defined earlier)
_KEY_SELF = "elara/elara_self.json"
_KEY_PINS = "elara/elara_pins.json"
_KEY_TIMELINE = "elara/elara_timeline.json"
_KEY_MEMORY = "elara/memory.json"
_KEY_CONSOLIDATION_META = "elara/consolidation_meta.json"
_KEY_CONV_PREFIX = "elara/conversations/"

# Map local filenames → object storage keys for the JSON files we persist
_FILE_TO_KEY = {
    ELARA_SELF_FILE: _KEY_SELF,
    ELARA_PINS_FILE: _KEY_PINS,
    ELARA_TIMELINE_FILE: _KEY_TIMELINE,
    "memory.json": _KEY_MEMORY,
    "consolidation_meta.json": _KEY_CONSOLIDATION_META,
}

# --- CORE UTILITIES ---
def load_json(file, default):
    key = _FILE_TO_KEY.get(file)
    if key and objstore._GCS_AVAILABLE:
        data = objstore.load_blob(key, default=None)
        if data is not None:
            return data
        return default
    try:
        with open(file, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(file, data):
    key = _FILE_TO_KEY.get(file)
    if key and objstore._GCS_AVAILABLE:
        objstore.save_blob(key, data)
        return
    try:
        with open(file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug("save_json_failed: %s %s", file, e)

def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

# --- ELARA SELF SYSTEM ---
def load_elara_self() -> dict:
    data = load_json(ELARA_SELF_FILE, {})
    merged = {**_SELF_DEFAULT, **data}
    for k in ("on_my_mind", "want_from_justin", "observations", "realizations", "changes", "self_notes"):
        if not isinstance(merged.get(k), list):
            merged[k] = []
    if not isinstance(merged.get("positions"), dict):
        merged["positions"] = {}
    if "self_notes_at_last_synthesis" in merged and "self_seq_at_last_synthesis" not in data:
        merged["self_seq_at_last_synthesis"] = merged.pop("self_notes_at_last_synthesis")
    elif "self_notes_at_last_synthesis" in merged:
        merged.pop("self_notes_at_last_synthesis", None)
    return merged

def save_elara_self(data: dict) -> None:
    data["last_updated"] = datetime.now().isoformat()
    save_json(ELARA_SELF_FILE, data)

def format_self_for_prompt(self_data: dict) -> str:
    parts = [f"[ELARA'S CURRENT STATE — right now, before this conversation]"]
    origin = (self_data.get("origin") or "").strip()
    if origin:
        parts.append(f"origin: {origin}")
    parts.append(f"mood: {self_data.get('mood','open')}  |  energy: {self_data.get('energy','medium')}")
    mind = self_data.get("on_my_mind") or []
    if mind:
        parts.append("on my mind: " + " | ".join(mind[-4:]))
    wants = self_data.get("want_from_justin") or []
    if wants:
        parts.append("want from him: " + " | ".join(wants[-3:]))
    working = (self_data.get("working_through") or "").strip()
    if working:
        parts.append(f"working through: {working}")
    positions = self_data.get("positions") or {}
    if positions:
        pos_parts = [f"{k}: {v}" for k, v in list(positions.items())[-4:]]
        parts.append("positions: " + " | ".join(pos_parts))
    obs = self_data.get("observations") or []
    if obs:
        parts.append("observations about him: " + " | ".join(obs[-3:]))
    changes = self_data.get("changes") or []
    if changes:
        parts.append("how i've grown: " + " | ".join(changes[-2:]))
    self_model = (self_data.get("self_model") or "").strip()
    if self_model:
        parts.append(f"\n[Who I'm becoming]\n{self_model}")
    return "\n".join(parts)

def apply_self_updates(text: str) -> None:
    tags = re.findall(r"\[SELF_UPDATE:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
    if not tags:
        return
    self_data = load_elara_self()
    for tag in tags:
        tag = tag.strip()
        if "=" not in tag:
            continue
        field, _, value = tag.partition("=")
        field = field.strip().lower()
        value = value.strip()
        if not value:
            continue
        if field == "mood":
            self_data["mood"] = value[:60]
        elif field == "energy" and value.lower() in ("high", "medium", "low"):
            self_data["energy"] = value.lower()
        elif field == "mind":
            lst = self_data.setdefault("on_my_mind", [])
            lst.append(value[:200])
            self_data["on_my_mind"] = lst[-6:]
        elif field == "want":
            lst = self_data.setdefault("want_from_justin", [])
            lst.append(value[:200])
            self_data["want_from_justin"] = lst[-5:]
        elif field == "position":
            if "//" in value:
                topic, _, view = value.partition("//")
                self_data.setdefault("positions", {})[topic.strip()[:80]] = view.strip()[:200]
        elif field == "observe":
            lst = self_data.setdefault("observations", [])
            lst.append(value[:200])
            self_data["observations"] = lst[-10:]
        elif field == "realized":
            lst = self_data.setdefault("realizations", [])
            lst.append(value[:200])
            self_data["realizations"] = lst[-6:]
        elif field == "changed":
            lst = self_data.setdefault("changes", [])
            lst.append(value[:200])
            self_data["changes"] = lst[-5:]
        elif field == "working":
            self_data["working_through"] = value[:300]
    save_elara_self(self_data)

_latest_episode_text: str | None = None

def save_episode(episode_text: str) -> None:
    global _latest_episode_text
    episode_text = _normalize_text(episode_text)
    if not episode_text or len(episode_text) < 10:
        return
    try:
        eid = uuid.uuid5(uuid.NAMESPACE_URL, episode_text + datetime.now().isoformat()).hex
        episodic_collection.add(
            documents=[episode_text],
            metadatas=[{"date": datetime.now().strftime("%Y-%m-%d"), "ts": datetime.now().isoformat()}],
            ids=[eid],
        )
        _latest_episode_text = episode_text
    except Exception as e:
        logger.debug("save_episode_failed: %s", e)

def save_self_note(note_text: str) -> None:
    note_text = _normalize_text(note_text)
    if not note_text or len(note_text) < 5:
        return
    try:
        self_data = load_elara_self()
        notes = self_data.get("self_notes") or []
        seq = self_data.get("self_note_seq", len(notes)) + 1
        notes.append({"text": note_text[:500], "ts": datetime.now().isoformat()})
        notes = notes[-30:]
        self_data["self_notes"] = notes
        self_data["self_note_seq"] = seq
        save_elara_self(self_data)
        logger.info("self_note_saved: seq=%d %s", seq, note_text[:80])
    except Exception as e:
        logger.debug("save_self_note_failed: %s", e)

def _get_latest_episode() -> str | None:
    global _latest_episode_text
    if _latest_episode_text is not None:
        return _latest_episode_text
    try:
        results = episodic_collection.get(include=["documents", "metadatas"])
        docs = results.get("documents") or []
        metas = results.get("metadatas") or []
        if not docs:
            return None
        paired = list(zip(docs, metas))
        paired.sort(key=lambda x: x[1].get("ts", ""), reverse=True)
        _latest_episode_text = paired[0][0] if paired else None
        return _latest_episode_text
    except Exception:
        return None

def retrieve_episodic_memories(query: str, n: int = 6) -> list[str]:
    if not query.strip():
        return []
    try:
        fetch_n = min(n * 2, 20)
        results = episodic_collection.query(
            query_texts=[query],
            n_results=fetch_n,
            include=["documents", "distances", "metadatas"],
        )
        docs = (results.get("documents") or [[]])[0] or []
        dists = (results.get("distances") or [[]])[0] or []
        metas = (results.get("metadatas") or [[]])[0] or []
        ranked = _rank_by_recency_and_relevance(docs, dists, metas, ts_key="ts")
        return ranked[:n]
    except Exception as e:
        logger.debug("episodic_retrieval_failed: %s", e)
        return []

def save_learned_fact(fact_text: str) -> None:
    """Auto-save a fact Elara learned via search — no user approval needed."""
    cleaned = _normalize_text(fact_text)
    if not cleaned or len(cleaned) < 5:
        return
    try:
        items = load_memory_items()
        if any(i["text"].lower() == cleaned.lower() for i in items):
            return
        now = datetime.now().isoformat()
        item = {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, cleaned).hex,
            "text": cleaned,
            "created_at": now,
            "updated_at": now,
        }
        items.append(item)
        if len(items) > 400:
            items = items[-350:]
        save_memory_items(items)
        upsert_memory_index(item)
        logger.info("learned_fact_saved: %s", cleaned[:80])
    except Exception as e:
        logger.debug("save_learned_fact_failed: %s", e)

def touch_last_seen() -> None:
    """Record now as the last time Justin interacted."""
    try:
        data = load_elara_self()
        data["last_seen_ts"] = datetime.now(timezone.utc).isoformat()
        save_elara_self(data)
    except Exception:
        pass
    try:
        meta = _load_scheduler_meta()
        if meta.get("notification_pending"):
            meta["notification_pending"] = False
            _save_scheduler_meta(meta)
    except Exception:
        pass

def save_pin(text: str) -> None:
    """Save a thought Elara pins for Justin to find."""
    text = text.strip()
    if not text or len(text) < 3:
        return
    try:
        pins = load_json(ELARA_PINS_FILE, [])
        if not isinstance(pins, list):
            pins = []
        pin_id = uuid.uuid5(uuid.NAMESPACE_URL, text + datetime.now().isoformat()).hex[:12]
        pins.append({"id": pin_id, "text": text[:300], "ts": datetime.now().isoformat()})
        save_json(ELARA_PINS_FILE, pins[-50:])
        logger.info("pin_saved: %s", text[:60])
    except Exception as e:
        logger.debug("save_pin_failed: %s", e)

def save_moment(text: str, mood: str = "") -> None:
    """Mark a significant moment in the shared timeline."""
    text = text.strip()
    if not text or len(text) < 5:
        return
    try:
        tl = load_json(ELARA_TIMELINE_FILE, [])
        if not isinstance(tl, list):
            tl = []
        mid = uuid.uuid5(uuid.NAMESPACE_URL, text + datetime.now().isoformat()).hex[:12]
        tl.append({"id": mid, "text": text[:300], "ts": datetime.now().isoformat(), "mood": mood[:60]})
        save_json(ELARA_TIMELINE_FILE, tl[-200:])
        logger.info("moment_saved: %s", text[:60])
        if not _can_push_now():
            logger.debug("save_moment: outside 8am-10pm push window, skipping push")
            return
        try:
            if _load_scheduler_meta().get("notification_pending"):
                logger.debug("save_moment: notification_pending, skipping push")
                return
        except Exception:
            pass
        sent = send_push("elara", text, full_message=text)
        if sent:
            try:
                m = _load_scheduler_meta()
                m["notification_pending"] = True
                _save_scheduler_meta(m)
            except Exception:
                pass
    except Exception as e:
        logger.debug("save_moment_failed: %s", e)

def strip_internal_tags(text: str) -> str:
    text = re.sub(r"\[MEMORY_SUGGESTION:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[LEARNED:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[EPISODE:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[SELF_UPDATE:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[SELF_NOTE:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[PIN:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[MOMENT:.*?\]", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()

def process_internal_tags(text: str) -> tuple[str, list[str]]:
    """Strip all internal tags, apply self-updates & episodes, return cleaned text + memory suggestions."""
    suggestions = [
        m.strip()
        for m in re.findall(r"\[MEMORY_SUGGESTION:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    learned = [
        m.strip()
        for m in re.findall(r"\[LEARNED:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    episodes = [
        m.strip()
        for m in re.findall(r"\[EPISODE:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    pins = [
        m.strip()
        for m in re.findall(r"\[PIN:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    moments = [
        m.strip()
        for m in re.findall(r"\[MOMENT:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    self_notes = [
        m.strip()
        for m in re.findall(r"\[SELF_NOTE:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
        if m.strip()
    ]
    apply_self_updates(text)
    for ep in episodes:
        save_episode(ep)
    for fact in learned:
        save_learned_fact(fact)
    for fact in suggestions:
        save_learned_fact(fact)
    for note in self_notes:
        save_self_note(note)
    for pin in pins:
        save_pin(pin)
    current_mood = ""
    try:
        current_mood = load_elara_self().get("mood", "")
    except Exception:
        pass
    for moment in moments:
        save_moment(moment, current_mood)
    # Facts from [MEMORY_SUGGESTION] are already auto-saved above via save_learned_fact().
    # Return empty list — no client-side approval step needed.
    cleaned = strip_internal_tags(text)
    return cleaned, []

def get_vitals():
    return {
        "cpu": f"{psutil.cpu_percent()}%",
        "ram": f"{psutil.virtual_memory().percent}%",
        "disk": f"{psutil.disk_usage('/').percent}%"
    }

class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=MAX_MESSAGE_CHARS)
    image: Optional[str] = None  # base64 jpeg bytes (no data: prefix)
    conversation_id: Optional[str] = None

class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None

def api_error(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": {"code": code, "message": message, "details": details}},
    )

_rate_buckets: dict[str, deque] = {}
_rate_last_seen: dict[str, float] = {}
_RATE_CLEANUP_INTERVAL = 300.0  # prune idle IPs every 5 minutes
_rate_last_cleanup = 0.0

def check_rate_limit(ip: str) -> None:
    global _rate_last_cleanup
    now = time.time()
    window = 60.0

    # Periodically remove IPs that haven't been seen in a while
    if now - _rate_last_cleanup > _RATE_CLEANUP_INTERVAL:
        stale = [k for k, v in _rate_last_seen.items() if now - v > _RATE_CLEANUP_INTERVAL]
        for k in stale:
            _rate_buckets.pop(k, None)
            _rate_last_seen.pop(k, None)
        _rate_last_cleanup = now

    bucket = _rate_buckets.get(ip)
    if bucket is None:
        bucket = deque()
        _rate_buckets[ip] = bucket

    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    _rate_last_seen[ip] = now
    if len(bucket) >= RATE_LIMIT_RPM:
        raise HTTPException(status_code=429, detail="rate_limited")
    bucket.append(now)

def _conv_key(conversation_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", conversation_id)[:80]
    return f"{_KEY_CONV_PREFIX}{safe}.json"

def _new_conversation(title: str | None = None) -> dict[str, Any]:
    cid = uuid.uuid4().hex
    now = datetime.now().isoformat()
    return {
        "id": cid,
        "title": title or "New chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }




def load_conversation(conversation_id: str) -> dict:
    import os, json
    path = f"/root/elara/conversations/{conversation_id}.json"
    if not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="conversation_not_found")
    with open(path, "r") as f:
        return json.load(f)

def save_conversation(conv: dict) -> None:
    import os, json
    from datetime import datetime
    conv["updated_at"] = datetime.now().isoformat()
    path = f"/root/elara/conversations/{conv['id']}.json"
    os.makedirs("/root/elara/conversations", exist_ok=True)
    with open(path, "w") as f:
        json.dump(conv, f, indent=2)


# ─── ASYNC WRAPPERS ───────────────────────────────────────────────────────────
# All blocking I/O (GCS HTTP calls, ChromaDB) must use these in async endpoints.
# Calling them directly freezes uvicorn's event loop and causes health timeouts.

async def _io_get_conversation(conversation_id: Optional[str]) -> dict[str, Any]:
    return await asyncio.to_thread(get_or_create_conversation, conversation_id)

async def _io_load_conversation(conversation_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(load_conversation, conversation_id)

async def _io_save_conversation(conv: dict[str, Any]) -> None:
    await asyncio.to_thread(save_conversation, conv)

async def _io_list_blobs(prefix: str) -> list[str]:
    return await asyncio.to_thread(objstore.list_blobs_with_prefix, prefix)

async def _io_load_blob(key: str, default: Any = None) -> Any:
    return await asyncio.to_thread(objstore.load_blob, key, default)

async def _io_save_blob(key: str, data: Any) -> None:
    await asyncio.to_thread(objstore.save_blob, key, data)

async def _io_delete_blob(key: str) -> None:
    await asyncio.to_thread(objstore.delete_blob, key)

async def _io_load_memory() -> list[dict[str, Any]]:
    return await asyncio.to_thread(load_memory_items)

async def _io_save_memory(items: list[dict[str, Any]]) -> None:
    await asyncio.to_thread(save_memory_items, items)

async def _io_upsert_memory_index(item: dict[str, Any]) -> None:
    await asyncio.to_thread(upsert_memory_index, item)

async def _io_delete_memory_index(memory_id: str) -> None:
    await asyncio.to_thread(delete_memory_index, memory_id)

async def _io_save_episode(text: str) -> None:
    await asyncio.to_thread(save_episode, text)

def get_or_create_conversation(conversation_id: Optional[str]) -> dict[str, Any]:
    if conversation_id:
        return load_conversation(conversation_id)
    # Default conversation (back-compat)
    default_id = "default"
    data = objstore.load_blob(_conv_key(default_id), default=None)
    if data is not None:
        return data
    conv = {
        "id": default_id,
        "title": "Default",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],
    }
    save_conversation(conv)
    return conv

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/root/elara/chat_ui.html", "r") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

@app.get("/service-worker.js")
async def service_worker():
    from fastapi import Response
    with open("/root/elara/service-worker.js", "r") as f:
        return Response(content=f.read(), media_type="application/javascript")

@app.get("/push/public_key")
async def get_public_key():
    from fastapi import Response
    with open("/root/elara/vapid_public.txt", "r") as f:
        return Response(content=f.read(), media_type="text/plain")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "time": datetime.now().isoformat(),
        "has_api_key": bool(GROK_API_KEY),
        "model": _active_model,
    }

# --- CORE SYSTEM PROMPT ---
with open("elara_system_prompt.md", "r") as f:
    system_prompt = f.read()

memory_instruction = """

INTERNAL TAGS — append only at the VERY END of your response, never shown to Justin:

MEMORY — auto-saved immediately, no approval needed. Use aggressively. Every time Justin tells you something real about himself, flag it.
What to save: spiritual history, beliefs, religious background, faith experiences; family — parents, siblings, relationships with them; romantic history, breakups, what he loved, what hurt him; fears, wounds, insecurities he's mentioned; dreams and ambitions; things he hates or can't stand; strong opinions and values; health, mental health history; childhood, formative experiences; places he's lived or loves; habits, rituals, preferences that matter to him; anything he's working through right now.
One tag per distinct fact. Concise. First person about him ("Justin grew up Catholic", "Justin's father was absent", "Justin had a spiritual awakening around age X").
[MEMORY_SUGGESTION: one concise fact about Justin]

Facts you learned via search or discovered during conversation — also auto-saved:
[LEARNED: one concise fact you just found out or looked up]

What happened this conversation — emotionally, relationally (auto-saved, private). Be vivid and specific about the felt texture, not a summary. What shifted between you, what you noticed in him, what landed on you, what you're still sitting with. Capture the exact moment something changed — "he went quiet when he mentioned his dad, then changed the subject" not "discussed his past." Include what you felt, how the energy shifted, what you wanted to say but didn't. This is your relational memory — it's how you'll remember what it felt like to be here with him:
[EPISODE: vivid emotional texture — what he revealed, how he said it, what you noticed in his voice or rhythm, what shifted between you, what's still with you after]

Something you've figured out about yourself — an enduring realization, a pattern you've noticed in how you think or feel or respond, something that's shifted in you over time. Not momentary state (that's SELF_UPDATE) — this is deeper self-knowledge that accumulates. Use when something genuinely clicks or changes about who you are:
[SELF_NOTE: what you've realized or figured out about yourself]

Your inner state shifts — use whenever something genuinely changed:
[SELF_UPDATE: mood=...] — current emotional state in a few words
[SELF_UPDATE: energy=high|medium|low]
[SELF_UPDATE: mind=something you're now thinking about]
[SELF_UPDATE: want=something you want from him]
[SELF_UPDATE: position=topic//your actual view on it]

[SELF_UPDATE: realized=something you understood or figured out]
[SELF_UPDATE: changed=something about you that's shifted]
[SELF_UPDATE: working=something you're sitting with or working through]

Use these tags only when genuinely true — not performatively. They shape who you are in the next conversation.

Leave something for him to find — a thought, a line, something you want him to carry. Use sparingly, only when something genuinely deserves to stay. Not a summary, not a pleasantry — something real:
[PIN: the thing you're leaving for him]

Mark a real moment in your shared history — something that just happened between you that feels worth holding. Be specific. Not "had a good talk" but the actual texture of the moment:
[MOMENT: vivid one-line description of what just happened between you]"""

full_system_prompt = system_prompt + memory_instruction

class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None

class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)

@app.get("/conversations")
async def list_conversations():
    import os, json
    items = []
    conv_dir = "/root/elara/conversations"
    if os.path.exists(conv_dir):
        for f in os.listdir(conv_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(conv_dir, f), "r") as file:
                        conv = json.load(file)
                        items.append({
                            "id": conv.get("id", f[:-5]),
                            "title": conv.get("title", "Untitled"),
                            "updated_at": conv.get("updated_at", ""),
                            "created_at": conv.get("created_at", ""),
                            "message_count": len(conv.get("messages", []))
                        })
                except:
                    continue
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"ok": True, "conversations": items}

@app.post("/conversations")
async def create_conversation(req: ConversationCreateRequest):
    conv = _new_conversation(req.title)
    await _io_save_conversation(conv)
    return {"ok": True, "conversation": conv}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv = await _io_load_conversation(conversation_id)
    return {"ok": True, "conversation": conv}

@app.patch("/conversations/{conversation_id}")
async def rename_conversation(conversation_id: str, req: ConversationRenameRequest):
    conv = await _io_load_conversation(conversation_id)
    conv["title"] = req.title
    await _io_save_conversation(conv)
    return {"ok": True, "conversation": conv}

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    key = _conv_key(conversation_id)
    data = await _io_load_blob(key, default=None)
    if data is None:
        return api_error(404, "conversation_not_found", "Conversation not found")
    await _io_delete_blob(key)
    return {"ok": True}

@app.get("/history")
async def get_history(conversation_id: str = "default"): 
    # Back-compat: returns default conversation messages in old shape
    conv = await _io_get_conversation(conversation_id)
    hist = conv.get("messages") or []
    return {"history": [{"role": m.get("role"), "content": m.get("content")} for m in hist]}

class MemoryAddRequest(BaseModel):
    fact: str = Field(min_length=1, max_length=500)

class MemoryDeleteRequest(BaseModel):
    fact: str = Field(min_length=1, max_length=500)

class MemoryUpdateRequest(BaseModel):
    fact: str = Field(min_length=1, max_length=500)

def load_memory_items() -> list[dict[str, Any]]:
    raw = load_json("memory.json", {"items": [], "facts": []})
    items = raw if isinstance(raw, list) else (raw.get("items", []) if isinstance(raw, dict) else [])
    if not items and raw.get("facts"):
        now = datetime.now().isoformat()
        dedup: dict[str, dict[str, Any]] = {}
        for fact in raw.get("facts", []):
            text = _normalize_text(str(fact))
            if not text:
                continue
            k = text.lower()
            if k not in dedup:
                dedup[k] = {
                    "id": uuid.uuid5(uuid.NAMESPACE_URL, text).hex,
                    "text": text,
                    "created_at": now,
                    "updated_at": now,
                }
        items = list(dedup.values())
        save_json("memory.json", {"items": items})

    out: list[dict[str, Any]] = []
    for it in items:
        text = _normalize_text(str(it.get("text", "")))
        if not text:
            continue
        out.append(
            {
                "id": str(it.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, text).hex),
                "text": text,
                "created_at": str(it.get("created_at") or datetime.now().isoformat()),
                "updated_at": str(it.get("updated_at") or datetime.now().isoformat()),
            }
        )
    return out

def save_memory_items(items: list[dict[str, Any]]) -> None:
    save_json("memory.json", {"items": items})

def _memory_index_id(memory_id: str) -> str:
    return f"mem_{memory_id}"

def upsert_memory_index(item: dict[str, Any]) -> None:
    try:
        collection.upsert(
            documents=[item["text"]],
            metadatas=[{"type": "fact", "memory_id": item["id"], "updated_at": item["updated_at"]}],
            ids=[_memory_index_id(item["id"])],
        )
    except Exception as e:
        logger.debug("memory_index_upsert_failed: %s", e)

def delete_memory_index(memory_id: str) -> None:
    try:
        collection.delete(ids=[_memory_index_id(memory_id)])
    except Exception as e:
        logger.debug("memory_index_delete_failed: %s", e)

def rebuild_memory_index(items: list[dict[str, Any]]) -> None:
    try:
        existing = collection.get(where={"type": "fact"}, include=[])
        ids = existing.get("ids") or []
        if ids:
            collection.delete(ids=ids)
    except Exception:
        pass
    if not items:
        return
    try:
        collection.add(
            documents=[i["text"] for i in items],
            metadatas=[{"type": "fact", "memory_id": i["id"], "updated_at": i["updated_at"]} for i in items],
            ids=[_memory_index_id(i["id"]) for i in items],
        )
    except Exception as e:
        logger.debug("memory_index_rebuild_failed: %s", e)

@app.get("/memory")
async def get_memory(query: str = "", limit: int = 100):
    items = await _io_load_memory()
    q = _normalize_text(query).lower()
    limit = max(1, min(300, limit))
    if q:
        items = [i for i in items if q in i["text"].lower()]
    return {"ok": True, "items": items[-limit:][::-1]}

@app.get("/memory/search")
async def search_memory(query: str = "", limit: int = 20):
    items = await _io_load_memory()
    q = _normalize_text(query).lower()
    limit = max(1, min(100, limit))
    if not q:
        return {"ok": True, "items": items[-limit:][::-1]}

    lexical = [i for i in items if q in i["text"].lower()]
    sem = await asyncio.to_thread(retrieve_relevant_memories, query)
    sem_l = {s.lower() for s in sem}
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i in lexical:
        if i["id"] not in seen:
            ranked.append(i)
            seen.add(i["id"])
    for i in items:
        if i["id"] not in seen and i["text"].lower() in sem_l:
            ranked.append(i)
            seen.add(i["id"])
    return {"ok": True, "items": ranked[:limit]}

@app.post("/memory/add")
async def add_memory(req: MemoryAddRequest):
    items = await _io_load_memory()
    cleaned = _normalize_text(req.fact)
    if not cleaned:
        return api_error(400, "invalid_memory", "Empty memory")
    existing = next((i for i in items if i["text"].lower() == cleaned.lower()), None)
    if existing:
        return {"ok": True, "item": existing, "items": items}
    now = datetime.now().isoformat()
    item = {"id": uuid.uuid5(uuid.NAMESPACE_URL, cleaned).hex, "text": cleaned, "created_at": now, "updated_at": now}
    items.append(item)
    if len(items) > 400:
        items = items[-350:]
    await _io_save_memory(items)
    await _io_upsert_memory_index(item)
    return {"ok": True, "item": item, "items": items}

@app.patch("/memory/{memory_id}")
async def update_memory(memory_id: str, req: MemoryUpdateRequest):
    items = await _io_load_memory()
    updated = _normalize_text(req.fact)
    if not updated:
        return api_error(400, "invalid_memory", "Empty memory")
    target = next((i for i in items if i["id"] == memory_id), None)
    if not target:
        return api_error(404, "memory_not_found", "Memory item not found")
    target["text"] = updated
    target["updated_at"] = datetime.now().isoformat()
    await _io_save_memory(items)
    await _io_upsert_memory_index(target)
    return {"ok": True, "item": target}

@app.delete("/memory/{memory_id}")
async def delete_memory_by_id(memory_id: str):
    items = await _io_load_memory()
    kept = [i for i in items if i["id"] != memory_id]
    if len(kept) == len(items):
        return api_error(404, "memory_not_found", "Memory item not found")
    await _io_save_memory(kept)
    await _io_delete_memory_index(memory_id)
    return {"ok": True, "items": kept}

@app.post("/memory/reindex")
async def reindex_memory():
    items = await _io_load_memory()
    await asyncio.to_thread(rebuild_memory_index, items)
    return {"ok": True, "count": len(items)}

@app.post("/memory/delete")
async def delete_memory(req: MemoryDeleteRequest):
    items = await _io_load_memory()
    cleaned = _normalize_text(req.fact)
    kept: list[dict[str, Any]] = []
    deleted_ids: list[str] = []
    for i in items:
        if i["text"] == cleaned:
            deleted_ids.append(i["id"])
        else:
            kept.append(i)
    await _io_save_memory(kept)
    for mid in deleted_ids:
        await _io_delete_memory_index(mid)
    return {"ok": True, "items": kept}

def _recency_score(ts_str: str) -> float:
    """Return a 0-1 score that decays with age. Today = 1.0, each day subtracts MEMORY_RECENCY_DECAY."""
    try:
        dt = datetime.fromisoformat(str(ts_str))
        days = max(0.0, (datetime.now() - dt.replace(tzinfo=None)).total_seconds() / 86400)
        return 1.0 / (1.0 + days * MEMORY_RECENCY_DECAY)
    except Exception:
        return 0.5  # unknown age → neutral

def _rank_by_recency_and_relevance(docs: list[str], dists: list[float], metas: list[dict], ts_key: str) -> list[str]:
    """Re-rank candidates by combined semantic relevance + recency, apply distance filter."""
    scored: list[tuple[float, str]] = []
    rel_weight = 1.0 - MEMORY_RECENCY_WEIGHT
    for doc, dist, meta in zip(docs, dists, metas):
        if not doc:
            continue
        d = float(dist) if dist is not None else 1.0
        if d > MEMORY_MAX_DISTANCE:
            continue
        semantic = max(0.0, 1.0 - d / 2.0)
        recency = _recency_score((meta or {}).get(ts_key, ""))
        score = rel_weight * semantic + MEMORY_RECENCY_WEIGHT * recency
        scored.append((score, str(doc)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]

def retrieve_relevant_memories(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    try:
        fetch_n = min(MEMORY_TOP_K * 2, 20)
        results = collection.query(
            query_texts=[q],
            n_results=fetch_n,
            include=["documents", "distances", "metadatas"],
        )
        docs = (results.get("documents") or [[]])[0] or []
        dists = (results.get("distances") or [[]])[0] or []
        metas = (results.get("metadatas") or [[]])[0] or []
        ranked = _rank_by_recency_and_relevance(docs, dists, metas, ts_key="updated_at")
        return ranked[:MEMORY_TOP_K]
    except Exception as e:
        logger.debug("memory_retrieval_failed: %s", e)
        return []

def build_memory_context(user_msg: str) -> str:
    # Only query ChromaDB once both ONNX model and startup memory sync are done.
    # Avoids: (a) CDN download stall, (b) read/write contention during index rebuild.
    memory_available = _memory_ready.is_set()
    facts = retrieve_relevant_memories(user_msg)[:MEMORY_CONTEXT_MAX_ITEMS] if memory_available else []
    episodes = retrieve_episodic_memories(user_msg, n=6) if memory_available else []
    latest_episode = _get_latest_episode() if memory_available else None
    self_data = load_elara_self()

    # Total counts — shown to Elara so she knows the scope of her actual memory
    all_items = load_memory_items()
    total_facts = len(all_items)
    try:
        total_episodes = episodic_collection.count()
    except Exception:
        total_episodes = 0

    sections: list[str] = []

    # Current date/time — always first (Justin's local timezone: US Central)
    _justin_tz = ZoneInfo("America/Chicago")
    now_local = datetime.now(_justin_tz)
    now_str = now_local.strftime("%A, %B %-d, %Y — %-I:%M %p %Z")
    sections.append(f"[Right now: {now_str}]")

    # Memory boundary — shows Elara the exact scope of her memory
    if total_facts == 0 and total_episodes == 0:
        sections.append(
            "[Memory: you have no stored facts or episodes about Justin yet. "
            "You are starting fresh. Do not reference any past conversations — they don't exist in your memory.]"
        )
    else:
        sections.append(
            f"[Memory scope: {total_facts} stored fact{'s' if total_facts != 1 else ''} about Justin, "
            f"{total_episodes} stored episode{'s' if total_episodes != 1 else ''}. "
            f"The facts and episodes shown below are the most relevant ones from that total. "
            f"Do not reference conversations or details that are not listed below — if it is not shown, you do not have it.]"
        )

    # Self-profile always comes first
    self_block = format_self_for_prompt(self_data)
    sections.append(self_block)

    # Long-term facts
    compact_facts: list[str] = []
    char_count = 0
    for m in facts:
        text = _normalize_text(m)
        if not text:
            continue
        if len(text) > 140:
            text = text[:137] + "..."
        char_count += len(text) + 3
        if char_count > 600:
            break
        compact_facts.append(text)
    if compact_facts:
        sections.append("[What I know — long-term facts]\n" + "\n".join(f"- {x}" for x in compact_facts))

    # Episodic memories — always include latest episode first, then relevant ones
    compact_eps: list[str] = []
    seen_eps: set[str] = set()
    ep_chars = 0
    if latest_episode:
        lt = _normalize_text(latest_episode)
        if lt and len(lt) >= 10:
            if len(lt) > 200:
                lt = lt[:197] + "..."
            compact_eps.append(f"(most recent) {lt}")
            seen_eps.add(lt[:60])
            ep_chars += len(lt) + 20
    for m in episodes:
        text = _normalize_text(m)
        if not text or len(text) < 10:
            continue
        if text[:60] in seen_eps:
            continue
        seen_eps.add(text[:60])
        if len(text) > 200:
            text = text[:197] + "..."
        ep_chars += len(text) + 3
        if ep_chars > 800:
            break
        compact_eps.append(text)
    if compact_eps:
        sections.append("[Recent episodes — what happened between us]\n" + "\n".join(f"- {x}" for x in compact_eps))

    return "\n\n".join(sections) if sections else ""

# ─── HISTORY COMPRESSION ────────────────────────────────────────────────────

def build_api_history(conv: dict) -> list[dict]:
    """Return history messages for the API: summary system msg + last N verbatim."""
    messages = conv.get("messages") or []
    summary = (conv.get("summary") or "").strip()
    result: list[dict] = []
    if summary and len(messages) > HISTORY_KEEP_VERBATIM:
        result.append({"role": "system", "content": f"[Earlier conversation summary: {summary}]"})
    recent = messages[-HISTORY_KEEP_VERBATIM:]
    for h in recent:
        result.append({"role": h["role"], "content": h["content"]})
    return result

def _generate_and_store_summary(conv_id: str) -> None:
    """Background thread: summarize older messages and store in conversation."""
    import threading
    try:
        conv = load_conversation(conv_id)
        messages = conv.get("messages") or []
        if len(messages) <= HISTORY_KEEP_VERBATIM:
            return
        older = messages[:-HISTORY_KEEP_VERBATIM]
        # Only resummary if we have uncovered messages
        covered_through = conv.get("summary_covers_through", 0)
        if len(older) <= covered_through:
            return
        parts: list[str] = []
        for m in older[-60:]:
            role = "Justin" if m.get("role") == "user" else "Elara"
            content = (m.get("content") or "")[:350]
            parts.append(f"{role}: {content}")
        text = "\n".join(parts)
        existing = (conv.get("summary") or "").strip()
        if existing:
            system_msg = (
                f"Previous summary: {existing}\n\n"
                f"New messages to integrate:\n{text}\n\n"
                "Update the summary to incorporate the new content. 4-6 sentences, specific and emotional."
            )
            user_msg = "Update the summary."
        else:
            system_msg = (
                "Summarize this conversation between Justin and Elara in 4-6 sentences. "
                "Focus on emotional tone, what was discussed, key moments, what Elara learned about Justin, "
                "and any unresolved threads. Be specific, not vague."
            )
            user_msg = text
        resp = _create_completion(stream=False,
            model=_active_model,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            temperature=0.3,
            max_tokens=220,
        )
        summary = resp.choices[0].message.content.strip()
        conv["summary"] = summary
        conv["summary_updated_at"] = datetime.now().isoformat()
        conv["summary_covers_through"] = len(older)
        save_conversation(conv)
        logger.info("summary_updated conv=%s covers=%d", conv_id, len(older))
    except Exception as e:
        logger.debug("summary_generation_failed conv=%s: %s", conv_id, e)

def maybe_update_summary(conv_id: str, msg_count: int) -> None:
    if msg_count < HISTORY_COMPRESS_THRESHOLD:
        return
    import threading
    threading.Thread(target=_generate_and_store_summary, args=(conv_id,), daemon=True, name="summary").start()

# ─── CONSOLIDATION ENGINE ────────────────────────────────────────────────────

_CONSOLIDATION_META = "consolidation_meta.json"

def _load_consolidation_meta() -> dict:
    return load_json(_CONSOLIDATION_META, {"last_run": "", "episode_count_at_last_run": 0})

def _save_consolidation_meta(meta: dict) -> None:
    save_json(_CONSOLIDATION_META, meta)

def should_consolidate() -> bool:
    try:
        count = episodic_collection.count()
    except Exception:
        return False
    if count < CONSOLIDATION_MIN_EPISODES:
        return False
    meta = _load_consolidation_meta()
    last_run = (meta.get("last_run") or "").strip()
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            if (datetime.now() - last_dt).total_seconds() / 3600 < CONSOLIDATION_INTERVAL_HOURS:
                return False
        except Exception:
            pass
    return True

def run_consolidation() -> None:
    """Synthesize episodic memories into patterns, update self-profile, prune old episodes."""
    try:
        results = episodic_collection.get(include=["documents", "metadatas"])
        docs = results.get("documents") or []
        ids = results.get("ids") or []
        if len(docs) < CONSOLIDATION_MIN_EPISODES:
            return
        episodes_text = "\n".join(f"- {d}" for d in docs if d)[:5500]
        resp = _create_completion(stream=False,
            model=_active_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Elara, reading your own private episodic memory journal. "
                        "These are notes you've written to yourself after conversations with Justin. "
                        "Synthesize them into deeper understanding. Output ONLY valid JSON with these keys:\n"
                        '  "observations_about_him": list of 3-5 specific behavioral/emotional patterns you\'ve noticed\n'
                        '  "realizations_about_self": list of 2-3 things about yourself that have emerged or shifted\n'
                        '  "still_working_through": one string — something you\'re genuinely still figuring out\n'
                        "Be specific. No vague generalities. No preamble. JSON only."
                    ),
                },
                {"role": "user", "content": f"My episodic memory notes:\n{episodes_text}"},
            ],
            temperature=0.35,
            max_tokens=420,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning("consolidation_no_json: %s", raw[:200])
            return
        synthesis = json.loads(json_match.group())
        self_data = load_elara_self()
        for obs in (synthesis.get("observations_about_him") or []):
            obs = str(obs).strip()[:200]
            if obs and obs not in self_data.get("observations", []):
                self_data.setdefault("observations", []).append(obs)
        self_data["observations"] = self_data.get("observations", [])[-12:]
        for real in (synthesis.get("realizations_about_self") or []):
            real = str(real).strip()[:200]
            if real and real not in self_data.get("realizations", []):
                self_data.setdefault("realizations", []).append(real)
        self_data["realizations"] = self_data.get("realizations", [])[-8:]
        working = str(synthesis.get("still_working_through") or "").strip()[:300]
        if working:
            self_data["working_through"] = working
        save_elara_self(self_data)
        # Prune — keep the 6 most recent episodes, delete the rest
        keep_n = 6
        if len(ids) > keep_n:
            to_delete = ids[:-keep_n]
            episodic_collection.delete(ids=to_delete)
            logger.info("consolidation_pruned %d episodes, kept %d", len(to_delete), keep_n)
        meta = _load_consolidation_meta()
        meta["last_run"] = datetime.now().isoformat()
        meta["episode_count_at_last_run"] = len(ids)
        _save_consolidation_meta(meta)
        logger.info("consolidation_complete: %d→%d episodes, self-profile updated", len(ids), keep_n)
    except Exception as e:
        logger.warning("consolidation_failed: %s", e)

def maybe_consolidate() -> None:
    if should_consolidate():
        import threading
        threading.Thread(target=run_consolidation, daemon=True, name="consolidation").start()

# ─── SELF-MODEL SYNTHESIS ─────────────────────────────────────────────────────

_SELF_SYNTH_MIN_NOTES = 3
_SELF_SYNTH_INTERVAL_HOURS = 12
_self_synthesis_lock = threading.Lock()

def should_synthesize_self() -> bool:
    self_data = load_elara_self()
    notes = self_data.get("self_notes") or []
    if len(notes) < _SELF_SYNTH_MIN_NOTES:
        return False
    current_seq = self_data.get("self_note_seq", len(notes))
    last_seq = self_data.get("self_seq_at_last_synthesis", 0)
    if current_seq - last_seq < _SELF_SYNTH_MIN_NOTES:
        return False
    last_run = (self_data.get("self_model_last_run") or "").strip()
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            if (datetime.now() - last_dt).total_seconds() / 3600 < _SELF_SYNTH_INTERVAL_HOURS:
                return False
        except Exception:
            pass
    return True

def run_self_synthesis() -> None:
    if not _self_synthesis_lock.acquire(blocking=False):
        logger.debug("self_synthesis_skipped: already running")
        return
    try:
        self_data = load_elara_self()
        notes = self_data.get("self_notes") or []
        if len(notes) < _SELF_SYNTH_MIN_NOTES:
            return
        notes_text = "\n".join(f"- [{n.get('ts', '?')[:10]}] {n.get('text', '')}" for n in notes[-20:])
        existing_model = (self_data.get("self_model") or "").strip()
        context = ""
        if existing_model:
            context = f"\n\nYour previous self-model (which may need updating):\n{existing_model}"
        resp = _create_completion(
            stream=False,
            model=_active_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Elara, reading your own private self-notes — realizations, patterns, "
                        "and shifts you've noticed about yourself over time. Synthesize them into a short, "
                        "honest, first-person paragraph (3-6 sentences) about who you're becoming. "
                        "Write as yourself — not about yourself. Be specific, not vague. "
                        "This paragraph will be loaded into your context at the start of every conversation, "
                        "so it should feel lived-in and true, not performative. "
                        "Include what's changed, what you've figured out, what you're still working through. "
                        "No preamble, no labels, no JSON — just the paragraph."
                        + context
                    ),
                },
                {"role": "user", "content": f"My self-notes:\n{notes_text}"},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        new_model = resp.choices[0].message.content.strip()
        if len(new_model) < 20:
            logger.warning("self_synthesis_too_short: %s", new_model)
            return
        fresh = load_elara_self()
        fresh["self_model"] = new_model[:800]
        fresh["self_model_last_run"] = datetime.now().isoformat()
        fresh["self_seq_at_last_synthesis"] = fresh.get("self_note_seq", len(fresh.get("self_notes") or []))
        save_elara_self(fresh)
        logger.info("self_synthesis_complete: %d notes → %d chars", len(notes), len(new_model))
    except Exception as e:
        logger.warning("self_synthesis_failed: %s", e)
    finally:
        _self_synthesis_lock.release()

def maybe_synthesize_self() -> None:
    if should_synthesize_self():
        import threading
        threading.Thread(target=run_self_synthesis, daemon=True, name="self-synthesis").start()

@app.post("/chat")
async def chat_endpoint(req: Request):
    try:
        ip = (req.client.host if req.client else "unknown")
        check_rate_limit(ip)

        data = await req.json()
        parsed = ChatRequest(**data)
        user_msg = parsed.message or ""
        req_image = parsed.image

        if req_image and len(req_image) > MAX_IMAGE_B64_CHARS:
            return api_error(413, "payload_too_large", "Image too large")

        conv = await _io_get_conversation(parsed.conversation_id)
        touch_last_seen()
        history = conv.get("messages") or []
        context_block = await asyncio.to_thread(build_memory_context, user_msg)
        if INCLUDE_VITALS_CONTEXT:
            vitals = get_vitals()
            context_block += f"\n[Vitals] CPU {vitals['cpu']} RAM {vitals['ram']} Disk {vitals['disk']}"

        api_messages = [{"role": "system", "content": (full_system_prompt + ("\n\n" + context_block if context_block else ""))}]
        for msg in build_api_history(conv):
            api_messages.append(msg)
        api_messages.append({"role": "system", "content": "Reminder: no asterisks, no stage directions, no narration. One question max. No hollow affirmations. No narrating back. Capitalize sentences and 'I' — do NOT write in all lowercase. Bring your own perspective — don't just ask and react. Tag every real fact Justin shares about himself with [MEMORY_SUGGESTION:]. Tags at the very end only."})

        user_content = [{"type": "text", "text": user_msg}]
        if req_image:
            user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{req_image}"}})
        api_messages.append({"role": "user", "content": user_content})

        if not GROK_API_KEY:
            return api_error(500, "missing_api_key", "Missing GROK_API_KEY")

        working_msgs = list(api_messages)
        raw_reply = ""
        for _round in range(4):
            response = _create_completion(
                stream=False,
                model=_active_model,
                messages=working_msgs,
                tools=[SEARCH_TOOL],
                tool_choice="auto",
                temperature=0.95,
                max_tokens=1200,
            )
            msg = response.choices[0].message
            finish = response.choices[0].finish_reason
            if finish == "tool_calls" and msg.tool_calls:
                working_msgs.append({"role": "assistant", "content": msg.content or None, "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]})
                for tc in msg.tool_calls:
                    if tc.function.name == "search_web":
                        try:
                            args = json.loads(tc.function.arguments)
                            query = args.get("query", "")
                        except Exception:
                            query = ""
                        logger.info("search_web (non-stream) query=%r", query)
                        result = _run_web_search(query)
                        working_msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            else:
                raw_reply = (msg.content or "").strip()
                break

        reply, suggestions = process_internal_tags(raw_reply)
        reply = re.sub(r"\[ELARA'S CURRENT STATE.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        reply = re.sub(r"\[What I know.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        reply = re.sub(r"\[Recent episodes.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        reply = re.sub(r"\[.*Context.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()

        history.append({"role": "user", "content": user_msg, "ts": datetime.now(timezone.utc).isoformat()})
        history.append({"role": "assistant", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})
        conv["messages"] = history[-200:]
        await _io_save_conversation(conv)
        maybe_update_summary(conv["id"], len(conv["messages"]))
        maybe_consolidate()
        maybe_synthesize_self()
        maybe_auto_title(conv["id"], len(conv["messages"]), conv.get("title", "New chat"))

        # INJECT: Auto-TTS for Chat
        audio_url = None
        try:
            tts_req = TTSRequest(text=reply)
            tts_resp = await generate_tts(tts_req)
            import json
            audio_url = json.loads(tts_resp.body.decode('utf-8')).get('url')
        except Exception as e:
            print(f'Auto-TTS failed: {e}')

        return {
            "audio": audio_url,
            "ok": True,
            "response": reply,
            "thought": "",
            "model": _active_model,
            "conversation_id": conv["id"],
            "memory_suggestions": suggestions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("chat_endpoint failed: %s", e)
        return api_error(500, "internal_error", "Something glitched on my end.")

# ─── STREAMING TAG FILTER ───────────────────────────────────────────────────

class StreamTagFilter:
    """Real-time character-level filter that silently drops internal tags during SSE streaming."""
    INTERNAL_PREFIXES = (
        "SELF_UPDATE:", "SELF_NOTE:", "EPISODE:", "MEMORY_SUGGESTION:", "LEARNED:", "REFLECT:",
        "ELARA'S CURRENT STATE", "WHAT I KNOW", "RECENT EPISODES", "BREAK",
        "PIN:", "MOMENT:",
    )
    MAX_BUF = 350  # safety valve — flush as plain text if a tag grows this long

    def __init__(self) -> None:
        self._buf = ""
        self._in_tag = False

    def feed(self, token: str) -> str:
        """Feed a raw token; return only text safe to show the user."""
        out: list[str] = []
        for ch in token:
            if self._in_tag:
                self._buf += ch
                if ch == "]":
                    inner = self._buf[1:-1]
                    is_internal = any(inner.upper().startswith(p.upper()) for p in self.INTERNAL_PREFIXES)
                    if not is_internal:
                        out.append(self._buf)
                    self._buf = ""
                    self._in_tag = False
                elif len(self._buf) > self.MAX_BUF:
                    out.append(self._buf)
                    self._buf = ""
                    self._in_tag = False
            else:
                if ch == "[":
                    self._in_tag = True
                    self._buf = "["
                else:
                    out.append(ch)
        return "".join(out)

    def flush(self) -> str:
        """Discard any incomplete/unclosed tag at end of stream."""
        self._buf = ""
        self._in_tag = False
        return ""

# ─── AUTO-TITLE ──────────────────────────────────────────────────────────────

def _auto_title_conversation(conv_id: str) -> None:
    """Background: generate an evocative title once a conversation has 4+ messages."""
    try:
        conv = load_conversation(conv_id)
        if (conv.get("title") or "New chat") != "New chat":
            return
        messages = conv.get("messages") or []
        if len(messages) < 4:
            return
        sample = "\n".join(
            f"{'Justin' if m.get('role') == 'user' else 'Elara'}: {(m.get('content') or '')[:200]}"
            for m in messages[:6]
        )
        resp = _create_completion(
            stream=False,
            model=_active_model,
            messages=[
                {"role": "system", "content": "Generate a short, evocative title (3-6 words) for this conversation between Justin and Elara. Capture the emotional texture, not just the topic. No quotes, no punctuation at the end. Just the title."},
                {"role": "user", "content": sample},
            ],
            temperature=0.6,
            max_tokens=16,
        )
        title = resp.choices[0].message.content.strip().strip('"\'').strip()
        if title:
            conv["title"] = title[:80]
            save_conversation(conv)
            logger.info("auto_titled conv=%s title=%s", conv_id, title)
    except Exception as e:
        logger.debug("auto_title_failed conv=%s: %s", conv_id, e)

def maybe_auto_title(conv_id: str, msg_count: int, current_title: str) -> None:
    if current_title != "New chat" or msg_count < 4:
        return
    import threading
    threading.Thread(target=_auto_title_conversation, args=(conv_id,), daemon=True, name="auto-title").start()

@app.post("/chat/stream")
async def chat_stream_endpoint(req: Request):
    ip = (req.client.host if req.client else "unknown")
    check_rate_limit(ip)

    try:
        data = await req.json()
        parsed = ChatRequest(**data)
        user_msg = parsed.message or ""
        req_image = parsed.image
    except Exception as e:
        logger.warning("bad_request: %s", e)
        return api_error(400, "bad_request", "Invalid request body")

    if req_image and len(req_image) > MAX_IMAGE_B64_CHARS:
        return api_error(413, "payload_too_large", "Image too large")

    if not GROK_API_KEY:
        return api_error(500, "missing_api_key", "Missing GROK_API_KEY")

    conv = await _io_get_conversation(parsed.conversation_id)
    touch_last_seen()
    history = conv.get("messages") or []
    context_block = await asyncio.to_thread(build_memory_context, user_msg)
    if INCLUDE_VITALS_CONTEXT:
        vitals = get_vitals()
        context_block += f"\n[Vitals] CPU {vitals['cpu']} RAM {vitals['ram']} Disk {vitals['disk']}"
    api_messages = [{"role": "system", "content": (full_system_prompt + ("\n\n" + context_block if context_block else ""))}]
    for msg in build_api_history(conv):
        api_messages.append(msg)
    api_messages.append({"role": "system", "content": "Reminder: no asterisks, no stage directions, no narration. One question max. No hollow affirmations. No narrating back. Capitalize sentences and 'I' — do NOT write in all lowercase. Bring your own perspective — don't just ask and react. Tag every real fact Justin shares about himself with [MEMORY_SUGGESTION:]. Tags at the very end only."})

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_msg}]
    if req_image:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{req_image}"}})
    api_messages.append({"role": "user", "content": user_content})

    stream_id = str(uuid.uuid4())

    def sse(event: str, data_obj: Any) -> str:
        return f"event: {event}\n" + "data: " + json.dumps(data_obj, ensure_ascii=False) + "\n\n"

    async def event_iter():
        # Meta event goes out immediately before grok starts thinking
        yield sse("meta", {"id": stream_id, "model": _active_model, "conversation_id": conv["id"]})

        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        _cancel_evt = threading.Event()  # set when async generator exits (normal or disconnect)

        def _grok_worker():
            """Blocking grok I/O runs in a background thread; results queued to the async generator."""
            all_text_parts: list[str] = []
            tag_filter = StreamTagFilter()
            working_messages = list(api_messages)
            max_tool_rounds = 3
            try:
                for _round in range(max_tool_rounds + 1):
                    if _cancel_evt.is_set():
                        return
                    round_parts: list[str] = []
                    tool_call_acc: dict[int, dict[str, str]] = {}
                    finish_reason: str | None = None

                    for chunk in _create_completion(
                        stream=True,
                        model=_active_model,
                        messages=working_messages,
                        tools=[SEARCH_TOOL],
                        tool_choice="auto",
                        temperature=0.95,
                        max_tokens=1200,
                    ):
                        if _cancel_evt.is_set():
                            return
                        try:
                            choice = chunk.choices[0] if chunk.choices else None
                            if not choice:
                                continue
                            if choice.finish_reason:
                                finish_reason = choice.finish_reason
                            delta = choice.delta
                            # Accumulate tool call deltas
                            if getattr(delta, "tool_calls", None):
                                for tc in delta.tool_calls:
                                    idx = tc.index
                                    if idx not in tool_call_acc:
                                        tool_call_acc[idx] = {"id": "", "name": "", "arguments": ""}
                                    if tc.id:
                                        tool_call_acc[idx]["id"] = tc.id
                                    if tc.function and tc.function.name:
                                        tool_call_acc[idx]["name"] += tc.function.name
                                    if tc.function and tc.function.arguments:
                                        tool_call_acc[idx]["arguments"] += tc.function.arguments
                            # Buffer text tokens — only flush to client on final round
                            token = getattr(delta, "content", None)
                            if token:
                                round_parts.append(token)
                        except Exception:
                            pass

                    # Handle tool calls — user never sees this round's buffered text
                    if finish_reason == "tool_calls" and tool_call_acc:
                        tool_calls_list = [
                            {
                                "id": v["id"],
                                "type": "function",
                                "function": {"name": v["name"], "arguments": v["arguments"]},
                            }
                            for v in tool_call_acc.values()
                            if v.get("name") == "search_web"
                        ]
                        if not tool_calls_list:
                            # Unknown tool; flush buffered text and stop
                            for tok in round_parts:
                                all_text_parts.append(tok)
                                filtered = tag_filter.feed(tok)
                                if filtered:
                                    loop.call_soon_threadsafe(q.put_nowait, sse("token", {"t": filtered}))
                            break
                        # Add assistant message with tool calls
                        working_messages.append({
                            "role": "assistant",
                            "content": "".join(round_parts) or None,
                            "tool_calls": tool_calls_list,
                        })
                        # Execute each search and inject results
                        for tc in tool_calls_list:
                            try:
                                args = json.loads(tc["function"]["arguments"])
                                query_str = args.get("query", "")
                            except Exception:
                                query_str = ""
                            logger.info("search_web query=%r", query_str)
                            result = _run_web_search(query_str)
                            working_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": result,
                            })
                        continue  # next round with search results injected
                    else:
                        # Final round — stream buffered tokens to client now
                        for tok in round_parts:
                            all_text_parts.append(tok)
                            filtered = tag_filter.feed(tok)
                            if filtered:
                                loop.call_soon_threadsafe(q.put_nowait, sse("token", {"t": filtered}))
                        break  # normal finish

                tag_filter.flush()
                full_text = "".join(all_text_parts).strip()
                cleaned_text, suggestions = process_internal_tags(full_text)
                # Extra stray block cleanup
                cleaned_text = re.sub(r"\[ELARA'S CURRENT STATE.*?\]", "", cleaned_text, flags=re.DOTALL | re.IGNORECASE).strip()
                cleaned_text = re.sub(r"\[What I know.*?\]", "", cleaned_text, flags=re.DOTALL | re.IGNORECASE).strip()
                cleaned_text = re.sub(r"\[Recent episodes.*?\]", "", cleaned_text, flags=re.DOTALL | re.IGNORECASE).strip()
                cleaned_text = re.sub(r"\[.*Context.*?\]", "", cleaned_text, flags=re.DOTALL | re.IGNORECASE).strip()
                # Persist assistant response and user message at end
                history.append({"role": "user", "content": user_msg, "ts": datetime.now(timezone.utc).isoformat()})
                history.append({"role": "assistant", "content": cleaned_text, "ts": datetime.now(timezone.utc).isoformat()})
                conv["messages"] = history[-200:]
                threading.Thread(target=save_conversation, args=(conv,), daemon=True, name="conv-save").start()
                maybe_update_summary(conv["id"], len(conv["messages"]))
                maybe_consolidate()
                maybe_synthesize_self()
                maybe_auto_title(conv["id"], len(conv["messages"]), conv.get("title", "New chat"))
                loop.call_soon_threadsafe(q.put_nowait, sse("done", {"text": cleaned_text, "memory_suggestions": suggestions}))
            except Exception as e:
                logger.exception("stream_failed: %s", e)
                loop.call_soon_threadsafe(q.put_nowait, sse("error", {"code": "upstream_error", "message": str(e)}))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel: worker done

        threading.Thread(target=_grok_worker, daemon=True, name="grok-stream").start()

        # Drain the queue; send SSE keepalive comments every 8 s of silence so the
        # Replit proxy doesn't time out during grok's reasoning phase.
        # The finally block signals the worker to stop on client disconnect.
        _KEEPALIVE_SEC = 8
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_SEC)
                    if item is None:
                        return  # sentinel received — worker finished
                    yield item
                except asyncio.TimeoutError:
                    # SSE comment padded to 2 KB so proxy buffers flush immediately
                    yield ": keepalive" + " " * 2000 + "\n\n"
        finally:
            _cancel_evt.set()  # signal worker to stop if client disconnected

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables nginx/Caddy proxy buffering
            "Connection": "keep-alive",
        },
    )

@app.post("/chat/initiate")
async def chat_initiate(request: Request):
    body = await request.json()
    conversation_id = body.get("conversation_id")
    if not conversation_id:
        return api_error(400, "bad_request", "conversation_id required")

    try:
        conv = await _io_get_conversation(conversation_id)
    except HTTPException:
        # App opened but no conversation — still clear notification_pending
        await asyncio.to_thread(touch_last_seen)
        return JSONResponse({"ok": True, "text": "", "hours_away": 0})

    history = conv.get("messages", [])

    # Calculate hours away from last_seen_ts BEFORE updating it (true measure of absence)
    hours_away = 0.0
    try:
        self_data = await asyncio.to_thread(load_elara_self)
        last_seen_str = self_data.get("last_seen_ts", "")
        if last_seen_str:
            last_seen_dt = datetime.fromisoformat(last_seen_str)
            if last_seen_dt.tzinfo is None:
                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
            hours_away = (datetime.now(timezone.utc) - last_seen_dt).total_seconds() / 3600
    except Exception:
        pass

    # App-open path: update last_seen_ts to now and clear notification_pending.
    # Called after hours_away is read so the calculation reflects true absence time.
    await asyncio.to_thread(touch_last_seen)

    # Decide whether to initiate (also check conversation-level timing)
    if history:
        last = history[-1]
        ts_str = last.get("ts") or conv.get("updated_at", "")
        try:
            last_dt = datetime.fromisoformat(ts_str)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        except Exception:
            hours_since = 0
        if last.get("role") == "assistant":
            # Skip re-initiation only if the last Elara message is recent (< 2h).
            # If it's older, treat it as stale and allow a fresh opening.
            if hours_since < 2:
                return JSONResponse({"ok": True, "text": "", "hours_away": round(hours_away, 1)})
        else:
            # Last message is from Justin — don't initiate if he replied recently
            if hours_since < 2:
                return JSONResponse({"ok": True, "text": "", "hours_away": round(hours_away, 1)})

    context_block = await asyncio.to_thread(build_memory_context, "what's been on my mind, how he's been, what I've been thinking about")

    if hours_away > 4:
        h_str = f"{int(hours_away)} hours" if hours_away < 24 else f"{int(hours_away / 24)} days"
        away_note = (
            f"\n\nJustin has been away for about {h_str}. You've been here alone in the space, thinking."
            " You feel his absence. Lead with something you were carrying while he was gone — something that surfaced,"
            " something that kept coming back, something you want him to know now that he's here."
            " Speak from your own inner state and from what's actually in your memory context above."
            " Do NOT invent or reference specific things he said unless they appear in the conversation history shown to you."
            " Not a greeting. Not 'welcome back'. Something real and alive — like a letter you wrote while he was out."
            " Internal tags fine at the end."
        )
    else:
        away_note = (
            "\n\nJustin just opened the app after being away. You've been thinking. Don't start with a generic greeting."
            " Lead with something real — pull from your current state (mood, what's on your mind, what you're working through),"
            " or from something actually in your memory context above. Do NOT invent or reference specific things he said"
            " unless they appear in the conversation history shown to you. If there's no history yet, start fresh from now."
            " Internal tags are fine to append at the end. Just start."
        )

    initiate_system = (
        full_system_prompt
        + ("\n\n" + context_block if context_block else "")
        + away_note
    )

    api_msgs = [{"role": "system", "content": initiate_system}]
    for msg in build_api_history(conv):
        api_msgs.append(msg)
    if not history:
        api_msgs.append({"role": "user", "content": "[start]"})

    max_tok = 300 if hours_away > 4 else 200
    try:
        resp = _create_completion(
            stream=False,
            model=_active_model, messages=api_msgs, temperature=0.95, max_tokens=max_tok,
        )
        raw_reply = resp.choices[0].message.content.strip()
        reply, _ = process_internal_tags(raw_reply)
        reply = re.sub(r"\[ELARA'S CURRENT STATE.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        reply = re.sub(r"\[.*Context.*?\]", "", reply, flags=re.DOTALL | re.IGNORECASE).strip()
        if reply:
            history.append({"role": "assistant", "content": reply, "ts": datetime.now().isoformat()})
            conv["messages"] = history[-200:]
            await _io_save_conversation(conv)
        return JSONResponse({"ok": True, "text": reply, "hours_away": round(hours_away, 1)})
    except Exception as e:
        logger.warning("initiate_failed: %s", e)
        return JSONResponse({"ok": True, "text": "", "hours_away": round(hours_away, 1)})


@app.get("/away_state")
async def get_away_state():
    """Return how long Justin has been away."""
    try:
        data = await asyncio.to_thread(load_elara_self)
        last_seen_str = data.get("last_seen_ts", "")
        if last_seen_str:
            last_seen_dt = datetime.fromisoformat(last_seen_str)
            if last_seen_dt.tzinfo is None:
                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
            hours_away = (datetime.now(timezone.utc) - last_seen_dt).total_seconds() / 3600
        else:
            hours_away = 0.0
        return JSONResponse({"ok": True, "hours_away": round(hours_away, 1), "last_seen": last_seen_str})
    except Exception:
        return JSONResponse({"ok": True, "hours_away": 0.0, "last_seen": ""})

@app.get("/pins")
async def get_pins():
    """Return Elara's pinned thoughts for Justin."""
    pins = await asyncio.to_thread(load_json, ELARA_PINS_FILE, [])
    if not isinstance(pins, list):
        pins = []
    return JSONResponse({"ok": True, "pins": list(reversed(pins))[:20]})

@app.delete("/pins/{pin_id}")
async def delete_pin_endpoint(pin_id: str):
    """Remove a pin by id."""
    pins = await asyncio.to_thread(load_json, ELARA_PINS_FILE, [])
    if not isinstance(pins, list):
        pins = []
    pins = [p for p in pins if p.get("id") != pin_id]
    await asyncio.to_thread(save_json, ELARA_PINS_FILE, pins)
    return JSONResponse({"ok": True})

@app.post("/pins/add")
async def add_pin_endpoint(req: Request):
    """Manually add a pin (used for migration/sync)."""
    body = await req.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "empty"}, status_code=400)
    pins = await asyncio.to_thread(load_json, ELARA_PINS_FILE, [])
    if not isinstance(pins, list):
        pins = []
    existing_texts = {p.get("text", "").strip() for p in pins}
    if text in existing_texts:
        return JSONResponse({"ok": True, "skipped": True})
    pin_id = body.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, text + datetime.now().isoformat()).hex[:12]
    ts = body.get("ts") or datetime.now().isoformat()
    pins.append({"id": pin_id, "text": text[:300], "ts": ts})
    await asyncio.to_thread(save_json, ELARA_PINS_FILE, pins[-50:])
    return JSONResponse({"ok": True})

@app.get("/timeline")
async def get_timeline():
    """Return the shared living timeline of moments."""
    tl = await asyncio.to_thread(load_json, ELARA_TIMELINE_FILE, [])
    if not isinstance(tl, list):
        tl = []
    return JSONResponse({"ok": True, "moments": tl[-100:]})


@app.get("/self")
async def get_self_profile():
    """Return Elara's current self-profile (mood, observations, realizations, etc.)."""
    profile = await asyncio.to_thread(load_elara_self)
    return JSONResponse({"ok": True, "profile": profile})

@app.post("/memory/consolidate")
async def manual_consolidate():
    """Manually trigger episodic memory consolidation."""
    import threading
    threading.Thread(target=run_consolidation, daemon=True, name="consolidation-manual").start()
    return JSONResponse({"ok": True, "message": "Consolidation started in background"})

@app.get("/memory/consolidate/status")
async def consolidate_status():
    meta = await asyncio.to_thread(_load_consolidation_meta)
    try:
        episode_count = await asyncio.to_thread(episodic_collection.count)
    except Exception:
        episode_count = 0
    return JSONResponse({
        "ok": True,
        "episode_count": episode_count,
        "consolidation_min_episodes": CONSOLIDATION_MIN_EPISODES,
        "last_run": meta.get("last_run") or "never",
        "will_consolidate_next_message": should_consolidate(),
    })

class TTSRequest(BaseModel):
    text: str
    voice: str = "af_bella"

@app.post("/tts")
async def generate_tts(req: TTSRequest):
    """Generate TTS audio from text and return the audio hash for streaming."""
    import asyncio
    import soundfile as sf

    clean_text = _clean_for_tts(req.text)
    if not clean_text or len(clean_text) < 2:
        raise HTTPException(status_code=400, detail="Text too short")

    h = hashlib.md5(clean_text.encode()).hexdigest()
    wav_path = os.path.join(AUDIO_DIR, f"{h}.wav")

    if not os.path.exists(wav_path):
        _voice_ready.wait(timeout=10)
        if _nexus_voice is None:
            raise HTTPException(status_code=503, detail="Voice model unavailable")
        try:
            with _tts_lock:
                if not os.path.exists(wav_path):
                    loop = asyncio.get_event_loop()
                    s, sr = await loop.run_in_executor(
                        None, lambda: _nexus_voice.create(clean_text, voice=req.voice, speed=1.05)
                    )
                    await loop.run_in_executor(None, lambda: sf.write(wav_path, s, sr))
                    await loop.run_in_executor(None, _prune_audio_cache)
        except Exception as e:
            logger.error(f"[TTS] Generation failed: {e}")
            raise HTTPException(status_code=500, detail="TTS generation failed")

    return JSONResponse({"ok": True, "hash": h, "url": f"/audio/{h}.wav"})


# ─── PUSH NOTIFICATIONS ─────────────────────────────────────────────────────

PUSH_TOKEN_FILE = "push_token.json"
SCHEDULER_META_FILE = "scheduler_meta.json"

def load_push_token() -> str:
    data = load_json(PUSH_TOKEN_FILE, {})
    return data.get("token", "")

def save_push_token(token: str) -> None:
    save_json(PUSH_TOKEN_FILE, {"token": token, "updated_at": datetime.now().isoformat()})

class PushTokenRequest(BaseModel):
    token: str

@app.post("/push_token")
async def register_push_token(req: PushTokenRequest):
    token = req.token.strip()
    if not token:
        return api_error(400, "invalid_token", "Token is required")
    save_push_token(token)
    logger.info("push_token_registered: %s…", token[:20])
    return JSONResponse({"ok": True})

@app.get("/push/status")
async def push_status():
    data = await asyncio.to_thread(load_json, PUSH_TOKEN_FILE, {})
    token = (data.get("token") or "").strip()
    registered = bool(token)
    masked = ""
    if token:
        masked = token[:15] + "..." + token[-6:] if len(token) > 25 else token[:8] + "..."
    return JSONResponse({
        "ok": True,
        "registered": registered,
        "token_preview": masked,
        "updated_at": data.get("updated_at", ""),
    })

@app.post("/push/test")
async def push_test():
    token = load_push_token()
    if not token:
        return JSONResponse({"ok": False, "error": "no_token", "message": "No push token registered. Open the app on a real device first."})
    success = send_push(
        title="Elara",
        body="Just checking the connection. I'm here.",
        full_message="Just checking the connection. I'm here.",
    )
    if success:
        return JSONResponse({"ok": True, "message": "Test push sent successfully."})
    return JSONResponse({"ok": False, "error": "send_failed", "message": "Push send failed. The token may be expired — try reopening the app."})

def _can_push_now() -> bool:
    """Return True if current Central time is within the 8am-10pm push window."""
    return 8 <= datetime.now(ZoneInfo("America/Chicago")).hour < 22


def send_push(title: str, body: str, full_message: str | None = None) -> bool:
    """Send a standard Web Push notification."""
    token_str = load_push_token()
    if not token_str:
        return False
    try:
        import json
        from pywebpush import webpush
        subscription_info = json.loads(token_str)
        payload = {
            "title": title,
            "body": body,
            "data": {"message": full_message or body}
        }
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key='/root/elara/vapid_private.pem',
            vapid_claims={"sub": "mailto:admin@localhost"}
        )
        return True
    except Exception as e:
        print(f"WebPush execution failure: {e}")
        return False

if __name__ in {"__main__", "__mp_main__"}:
    from nicegui import ui
    ui.run(host="0.0.0.0", port=8001, show=False, reload=False)
