with open('/root/elara/brain.py', 'r') as f:
    content = f.read()

# Strip the previous uvicorn block execution path
if 'if __name__ == "__main__":' in content:
    content = content.split('if __name__ == "__main__":')[0]

# Append the native NiceGUI worker multiprocessing block
nicegui_block = """
if __name__ in {"__main__", "__mp_main__"}:
    from nicegui import ui
    ui.run(host="0.0.0.0", port=8001, show=False, reload=False)
"""

with open('/root/elara/brain.py', 'w') as f:
    f.write(content.strip() + "\n\n" + nicegui_block.strip() + "\n")

print("NiceGUI startup block successfully restored!")
