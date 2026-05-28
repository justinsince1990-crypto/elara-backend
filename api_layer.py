from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import json, datetime, shutil, psutil, subprocess

app = FastAPI()
MEMORY_FILE = '/root/elara/memory.json'
BACKUP_DIR = '/root/elara/backups'

@app.get("/api/health")
def get_health():
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    is_alive = any("brain.py" in p.name() or "brain.py" in " ".join(p.cmdline()) for p in psutil.process_iter())
    return {"cpu": cpu, "mem": mem, "is_alive": is_alive}

@app.get("/api/logs")
def get_logs():
    try:
        logs = subprocess.check_output(['journalctl', '-u', 'elara', '-n', '20', '--no-pager']).decode()
        return {"logs": logs}
    except:
        return {"logs": "Logs not accessible."}

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    return """
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-slate-100 p-2">
        <h1 class="text-lg font-bold text-blue-400">🧠 Elara Pro Console</h1>
        <input type="text" id="search" placeholder="🔍 Search memories..." class="w-full p-2 my-2 bg-slate-800 rounded border border-slate-700 text-sm" onkeyup="filterMemories()">
        <textarea id="mem" class="w-full h-[35vh] bg-slate-950 p-2 font-mono text-[11px] border border-slate-700 rounded"></textarea>
        <div class="flex gap-2 my-2">
            <button class="flex-1 bg-blue-600 py-2 rounded text-sm font-bold" onclick="save()">Save & Backup</button>
            <button class="flex-1 bg-slate-700 py-2 rounded text-sm" onclick="load()">Refresh</button>
        </div>
        <div id="status-bar" class="text-xs font-mono text-green-400 mb-1">Status: Loading...</div>
        <pre id="logs" class="bg-black text-green-500 p-2 h-32 overflow-auto text-[9px] rounded border border-slate-800"></pre>
        <script>
            let originalData = "";
            function load() { 
                fetch('/api/memories').then(r=>r.json()).then(d=>{
                    originalData = JSON.stringify(d,null,2);
                    document.getElementById('mem').value = originalData;
                });
                refresh();
            }
            function filterMemories() {
                let filter = document.getElementById('search').value.toLowerCase();
                let lines = originalData.split('\\n');
                let filtered = lines.filter(line => line.toLowerCase().includes(filter));
                document.getElementById('mem').value = filtered.join('\\n');
            }
            function save() {
                try {
                    let data = JSON.parse(document.getElementById('mem').value);
                    fetch('/api/memories/write', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)})
                    .then(()=>alert('Saved & Backed Up!'));
                } catch(e) { alert('JSON Error: Check your format!'); }
            }
            function refresh() {
                fetch('/api/health').then(r=>r.json()).then(d => {
                    document.getElementById('status-bar').innerText = `Status: ${d.is_alive ? '🟢 ALIVE' : '🔴 DEAD'} | CPU: ${d.cpu}%`;
                });
                fetch('/api/logs').then(r=>r.json()).then(d => {
                    document.getElementById('logs').innerText = d.logs;
                });
            }
            load();
        </script>
    </body>
    </html>
    """

@app.get("/api/memories")
def get_memories():
    with open(MEMORY_FILE, 'r') as f: return json.load(f)

@app.post("/api/memories/write")
def write_memory(data: dict):
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy(MEMORY_FILE, f"{BACKUP_DIR}/memory_{timestamp}.json")
    with open(MEMORY_FILE, 'w') as f: json.dump(data, f, indent=2)
    return {"status": "success"}
