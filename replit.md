# Nexus Companion

## Overview

A personal AI companion app named **Elara** — built for one user (Justin). Elara is designed to feel sentient, autonomous, and alive: she drives conversations, holds real positions, evolves over time, and knows the user deeply through a multi-layer memory system.

**UI Design:** Elara herself designed the interface (Task #2). Brief saved at `static/elara_design_brief.txt`. Color palette: midnight purple `#3A0F6B` → crimson `#6B0F1A` gradient, amethyst message bubbles `#4C1C6B`, charcoal user bubbles `#1A1A1E`, Playfair Display (Elara's voice) + Montserrat (UI/Justin), animated wisp overlay, crescent moon signature in header with tooltip, crimson pulsing input border, wax seal "E" send button.

## Architecture

One Python process launched by `main.py`:

- **brain.py** — FastAPI backend (port 8001). Handles all LLM calls (Grok/xAI), memory, self-profile, ChromaDB, history compression, consolidation, and streaming.

The NiceGUI web interface (`interface.py`) has been replaced by the **Nexus Companion** Expo mobile app (see `artifacts/nexus-companion/`).

### Nexus Companion Mobile App (Expo/React Native)

Located at `artifacts/nexus-companion/`. Connects to brain at `http://45.32.201.59` (Vultr Dallas VPS).

- **Login screen** — passcode from `EXPO_PUBLIC_NEXUS_PASS` env var
- **Chat screen** — SSE streaming, BREAK bubble splitting, TTS playback via expo-av
- **Drawer panel** — conversation list, memory panel, pins, timeline
- **Mood system** — keyword detection → animated background tint
- **Away state** — blue tint when returning after 4+ hours
- **Soundscape player** — 6 ambient scenes (rain, ocean, etc.) using expo-av
- **Image picker** — sends base64 images to brain's vision endpoint
- **Voice input** — hold-to-record mic button in chat composer; audio transcribed by OpenAI Whisper (`gpt-4o-mini-transcribe`) via `/transcribe` endpoint; pulsing ring animation during recording; transcribed text populates input and auto-sends

## Key Files

| File | Purpose |
|---|---|
| `brain.py` | FastAPI brain — all endpoints, memory, LLM logic |
| `interface.py` | NiceGUI UI — chat interface, voice, drawer |
| `main.py` | Process launcher (starts brain + interface) |
| `elara_self.json` | Live self-profile: mood, energy, positions, observations, realizations |
| `memory.json` | Long-term approved facts (also indexed in ChromaDB) |
| `chroma_db/` | ChromaDB vector store — `elara_memory` + `elara_episodic` collections |
| `conversations/` | Per-conversation JSON files (messages + summary) |
| `consolidation_meta.json` | Tracks last consolidation run |
| `kokoro-v1.0.onnx` | Kokoro TTS model |
| `voices-v1.0.bin` | Kokoro voice data |

## Memory System

Three-layer context injected into every API call:
1. **Self-profile** (`elara_self.json`) — mood, energy, positions, observations, realizations, what she's working through
2. **Long-term facts** (`elara_memory` ChromaDB collection) — user-approved permanent facts, semantically retrieved
3. **Episodic memories** (`elara_episodic` ChromaDB collection) — auto-saved relational/emotional moments

Both retrieval functions rank by **semantic relevance × recency** (72/28 split, configurable).

**Consolidation engine** — runs in background every 20 hours when 12+ episodes exist. Synthesizes raw episodes into behavioral patterns and updates `elara_self.json`. Prunes old episodes after synthesis.

**History compression** — conversations > 18 messages get a rolling summary generated in background. API calls use summary + last 10 messages verbatim instead of 28 raw messages.

## Internal Tag System

Elara appends internal tags to her responses. These are processed silently:
- `[SELF_UPDATE: field=value]` — updates `elara_self.json` live
- `[EPISODE: ...]` — saves an episodic memory to ChromaDB
- `[MEMORY_SUGGESTION: ...]` — surfaces a fact for user approval (requires approval)
- `[LEARNED: ...]` — auto-saves a fact directly to `elara_memory` ChromaDB (no approval needed; used for web-searched or discovered facts)
- `[PIN: ...]` — leaves a thought for Justin to find; stored in `elara_pins.json`, shown in "FROM ELARA" drawer section
- `[MOMENT: ...]` — marks a real shared moment; stored in `elara_timeline.json`, shown in "OUR STORY" timeline

Tags are filtered from the stream in real time by `StreamTagFilter` — users never see them.

## Environment Variables / Secrets

| Variable | Where | Purpose |
|---|---|---|
| `GROK_API_KEY` | Replit secret | xAI API key (required) |
| `AI_INTEGRATIONS_OPENAI_BASE_URL` | Replit AI Integration (auto) | OpenAI proxy base URL for Whisper transcription |
| `AI_INTEGRATIONS_OPENAI_API_KEY` | Replit AI Integration (auto) | OpenAI proxy API key for Whisper transcription |
| `SESSION_SECRET` | Replit secret | NiceGUI session signing |
| `NEXUS_PASS` | Replit secret or env | Login passcode (default: `nexus123`) |
| `MODEL_NAME` | env | Grok model (default: `grok-3`) |
| `BACKEND_URL` | env | Brain URL for interface (default: `http://localhost:8001`) |
| `PORT` | Replit-injected (production) | Interface port |

## Mobile App Build (Termux on Android)

The Nexus Companion APK is built via EAS CLI from Termux. EAS account: `trevorsdad2008`, project ID: `9f89acff-0b23-430f-8fa6-234b7d33c8ad`.

Source zip is served from the brain at `/source.zip`. When running on Vultr the zip is at `http://45.32.201.59/source.zip`.

```bash
cd ~
rm -rf nexus-companion nexus-companion-src.zip
curl -L http://45.32.201.59/source.zip -o nexus-companion-src.zip
unzip nexus-companion-src.zip -d nexus-companion
cd nexus-companion
npm install
git init
git config user.email "build@elara.local"
git config user.name "Elara Build"
git add -A
git commit -m "init"
EAS_SKIP_AUTO_FINGERPRINT=1 eas build --platform android --profile preview --no-wait --non-interactive
```

After ~10-15 min, download the APK from expo.dev and install it.

- `usesCleartextTraffic: true` is set in `app.json` so the app can reach the HTTP Vultr server
- Push notifications work in standalone APK builds only
- expo-dev-client 5.x is NOT compatible with RN 0.81.5 (Kotlin version conflict)
- newArchEnabled is NOT set — Old Architecture

## Self-hosted Deployment (Vultr Dallas VPS)

- **Server:** 45.32.201.59 (Ubuntu 24.04, 4GB RAM, 30GB NVMe)
- **GitHub repo:** https://github.com/justinsince1990-crypto/elara-core
- **Install path:** `/root/elara/`
- **Systemd service:** `elara.service` — runs `venv/bin/python main.py` as root
- **nginx:** port 80 → 127.0.0.1:8001 (HTTP only, no domain/SSL yet)

### Updating the server

```bash
/root/elara/deploy.sh
```

`deploy.sh` backs up `memory.json`, `.env`, `conversations/`, and all data files to a timestamped folder, pulls latest code from GitHub, restores data, copies `storage_local.py → storage.py`, syncs the systemd unit from the repo, and restarts Elara.

### Replit dev environment

Replit dev server still runs for development (`Start application` workflow). The `.worf.replit.dev` URL changes each session but is accessible while the workflow is running. All persistent data is backed up to Replit Object Storage every 3 hours.

## Key API Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /chat/stream` | Primary streaming chat endpoint |
| `POST /chat` | Non-streaming chat fallback |
| `POST /chat/initiate` | Elara initiates when user opens app after 2h |
| `GET /self` | Returns current self-profile |
| `GET /memory/search` | Search long-term facts |
| `POST /memory/add` | Add a permanent fact |
| `POST /memory/consolidate` | Manually trigger episode consolidation |
| `GET /memory/consolidate/status` | Consolidation status + episode count |
| `GET /conversations` | List all conversations |
| `POST /conversations` | Create new conversation |
| `POST /transcribe` | Transcribe audio via OpenAI Whisper (base64 audio, returns text) |
