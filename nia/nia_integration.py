# Nia Integration Starter
# This file shows how to load Nia's system prompt and self-model
# You can import from this in brain.py or create a dedicated nia_brain.py

import os

# Load Nia's system prompt
with open("nia/nia_system_prompt.md", "r") as f:
    NIA_SYSTEM_PROMPT = f.read()

# Import memory functions
from nia.nia_memory import load_nia_self, save_nia_self, update_nia_self, apply_self_updates


def get_nia_system_prompt() -> str:
    """Returns the current system prompt for Nia."""
    return NIA_SYSTEM_PROMPT


def get_nia_state() -> dict:
    """Returns Nia's current self-model state."""
    return load_nia_self()


def update_nia_state(field: str, value):
    """Update a field in Nia's self-model."""
    return update_nia_self(field, value)


def nia_apply_updates(text: str):
    """Parse and apply [NIA_UPDATE: ...] tags from Nia's responses."""
    apply_self_updates(text)


# Example usage in your main app:
# from nia.nia_integration import get_nia_system_prompt, get_nia_state
#
# system_prompt = get_nia_system_prompt()
# nia_state = get_nia_state()
# Then pass system_prompt to your LLM call and use nia_state for context