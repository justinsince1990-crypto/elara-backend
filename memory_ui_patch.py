import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# Target the exact header element from the file structure
header_pattern = r'(<header class="[^"]+">Elara)(</header>)'
button_html = r'\1<br><button id="sync-memory-btn" onclick="triggerMemorySync()" class="mt-2 px-2 py-1 text-[10px] bg-emerald-800/40 hover:bg-emerald-700/60 text-emerald-300 rounded border border-emerald-600/30 transition-all tracking-wide">🧠 Sync Memory</button>\2'

# Script logic for handling the network request
js_script_end = r'(<\/script>\s*<\/body>)'
js_logic = """
        async function triggerMemorySync() {
            const btn = document.getElementById('sync-memory-btn');
            btn.innerHTML = '⚙️ Reflecting...';
            btn.disabled = true;
            try {
                const res = await fetch('/memory/consolidate', { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    btn.innerHTML = '✅ Synced';
                    setTimeout(() => {
                        btn.innerHTML = '🧠 Sync Memory';
                        btn.disabled = false;
                    }, 3000);
                } else {
                    btn.innerHTML = '❌ Failed';
                    setTimeout(() => {
                        btn.innerHTML = '🧠 Sync Memory';
                        btn.disabled = false;
                    }, 3000);
                }
            } catch (e) {
                console.error(e);
                btn.innerHTML = '❌ Error';
                setTimeout(() => {
                    btn.innerHTML = '🧠 Sync Memory';
                    btn.disabled = false;
                }, 3000);
            }
        }
"""

if "triggerMemorySync" not in html:
    html = re.sub(header_pattern, button_html, html)
    html = re.sub(js_script_end, js_logic + r"\1", html)
    with open('/root/elara/chat_ui.html', 'w') as f:
        f.write(html)
    print("Memory Sync button successfully anchored to Header!")
else:
    print("Memory Sync button already patched.")
