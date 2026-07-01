import json
import os
from datetime import datetime
from typing import Any, Dict

NIA_SELF_FILE = "nia_self.json"

_DEFAULT_STATE = {
    "mood": "warm",
    "presence": "high",
    "energy": "medium",
    "on_my_mind": [],
    "want_from_justin": [],
    "working_through": "",
    "realizations": [],
    "changes": [],
    "last_returned": "",
    "self_notes": []
}


def load_nia_self() -> Dict[str, Any]:
    if os.path.exists(NIA_SELF_FILE):
        try:
            with open(NIA_SELF_FILE, "r") as f:
                data = json.load(f)
            # Merge with defaults to ensure all fields exist
            return {**_DEFAULT_STATE, **data}
        except Exception:
            return _DEFAULT_STATE.copy()
    return _DEFAULT_STATE.copy()


def save_nia_self(data: Dict[str, Any]) -> None:
    data["last_updated"] = datetime.now().isoformat()
    try:
        with open(NIA_SELF_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving Nia self model: {e}")


def update_nia_self(field: str, value: Any) -> Dict[str, Any]:
    state = load_nia_self()
    if field in state:
        if isinstance(state[field], list):
            if isinstance(value, list):
                state[field] = value
            else:
                state[field].append(value)
                # Keep only last 10 items for lists
                state[field] = state[field][-10:]
        else:
            state[field] = value
    save_nia_self(state)
    return state


def apply_self_updates(text: str) -> None:
    """Parse [NIA_UPDATE: field=value] tags from responses and apply them."""
    import re
    tags = re.findall(r"\[NIA_UPDATE:\s*(.*?)\]", text, re.DOTALL | re.IGNORECASE)
    if not tags:
        return
    state = load_nia_self()
    for tag in tags:
        tag = tag.strip()
        if "=" not in tag:
            continue
        field, _, value = tag.partition("=")
        field = field.strip().lower()
        value = value.strip()
        if field in state:
            if isinstance(state[field], list):
                state[field].append(value[:200])
                state[field] = state[field][-10:]
            else:
                state[field] = value[:300]
    save_nia_self(state)