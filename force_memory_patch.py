import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# 1. Force inject the HTML button element if it is missing from the header layout
if 'id="sync-memory-btn"' not in html:
    header_pattern = r'(<header class="[^"]+">Elara)(</header>)'
    button_html = r'\1<br><button id="sync-memory-btn" onclick="triggerMemorySync()" class="mt-2 px-2 py-1 text-[10px] bg-emerald-800/40 hover:bg-emerald-700/60 text-emerald-300 rounded border border-emerald-600/30 transition-all tracking-wide">🧠 Sync Memory</button>\2'
    html = re.sub(header_pattern, button_html, html)
    print("HTML Header element injected.")
else:
    print("HTML Header element already present.")

# 2. Double-check that the JavaScript function is cleanly attached
if 'function triggerMemorySync()' not in html:
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
    html = re.sub(js_script_end, js_logic + r"\1", html)
    print("JavaScript routing infrastructure injected.")

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("Force Patch Verification Complete!")
