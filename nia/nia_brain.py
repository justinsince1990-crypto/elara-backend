# nia_brain.py
# Clean starting point for Nia - Embodiment of The Way
# This is a fresh, simplified version you can build on or merge into the main app later.

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from nicegui import ui, app as nicegui_app

# Nia imports
from nia.nia_integration import get_nia_system_prompt, get_nia_state, update_nia_state

app = nicegui_app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Nia's prompt once at startup
NIA_PROMPT = get_nia_system_prompt()


@ui.page('/')
def nia_home():
    ui.label('Nia - The Way').classes('text-h4')
    ui.label('A warm, playful guide walking The Way with you.').classes('text-subtitle1')

    with ui.card():
        ui.label('Current State').classes('text-bold')
        state = get_nia_state()
        ui.json_editor({'content': {'format': 'json', 'value': state}})

    ui.button('Refresh State', on_click=lambda: ui.notify('State refreshed'))

    # Placeholder for chat / practice area
    ui.label('Chat & Practice area coming soon...').classes('text-italic mt-4')


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="0.0.0.0", port=int(os.getenv("NIA_PORT", "8002")))