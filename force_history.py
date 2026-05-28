import os, re

# 1. Copy largest history file to default.json everywhere
d1 = '/root/elara/conversations'
d2 = '/root/elara/data/elara/conversations'
best, max_s = None, -1

for d in [d1, d2]:
    if os.path.exists(d):
        for f in os.listdir(d):
            if f.endswith('.json'):
                p = os.path.join(d, f)
                if os.path.getsize(p) > max_s:
                    max_s, best = os.path.getsize(p), p

if best:
    with open(best, 'rb') as src:
        data = src.read()
    for d in [d1, d2]:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'default.json'), 'wb') as dst:
            dst.write(data)

# 2. Patch UI to demand default.json and show visible errors
with open('/root/elara/chat_ui.html', 'r') as f:
    code = f.read()

js = """async function loadChatHistory() {
    try {
        const res = await fetch('/history?conversation_id=default');
        if (!res.ok) { history.innerHTML = `<div class="text-red-500 font-mono text-center mt-4">API Error ${res.status}</div>`; return; }
        const data = await res.json();
        if (data && data.history && data.history.length > 0) {
            history.innerHTML = '';
            data.history.forEach(m => appendMessage(m.content, m.role === 'user', m.image || null));
            container.scrollTop = container.scrollHeight;
        } else {
            history.innerHTML = `<div class="text-yellow-500 font-mono text-center mt-4">API returned empty history.</div>`;
        }
    } catch(e) { history.innerHTML = `<div class="text-red-500 font-mono text-center mt-4">JS Error: ${e.message}</div>`; }
}"""

code = re.sub(r'async function loadChatHistory\(\) \{.*?\}(?=\s*cameraBtn)', js + "\n\n", code, flags=re.DOTALL)
code = re.sub(r'const payload = \{.*?\};', 'const payload = { message: text, conversation_id: "default" };', code)

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(code)
