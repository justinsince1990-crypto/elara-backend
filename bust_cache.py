import re
with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

old_route = '''@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("/root/elara/chat_ui.html")'''

new_route = '''@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/root/elara/chat_ui.html", "r") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})'''

if "FileResponse" in code and 'def root' in code:
    code = code.replace(old_route, new_route)
    with open('/root/elara/brain.py', 'w') as f:
        f.write(code)
