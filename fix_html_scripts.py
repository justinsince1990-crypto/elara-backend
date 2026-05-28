import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# 1. Evacuate the Javascript from the Tailwind tag
html = re.sub(r'<script src="https://cdn.tailwindcss.com">.*?</script>', '<script src="https://cdn.tailwindcss.com"></script>', html, flags=re.DOTALL)

# 2. Remove any standalone Master JS blocks so we do not duplicate
html = re.sub(r'<script>\s*async function triggerMemorySync.*?</script>', '', html, flags=re.DOTALL)

# 3. Create a clean Master Script Block with alerts for total visibility
master_js = """
<script>
async function triggerMemorySync() {
    const btn = document.getElementById('sync-memory-btn');
    if (!btn) return;
    btn.innerHTML = '⚙️ Reflecting...';
    btn.disabled = true;
    try {
        const res = await fetch('/memory/consolidate', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            btn.innerHTML = '✅ Synced';
            setTimeout(() => { btn.innerHTML = '🧠 Sync Memory'; btn.disabled = false; }, 3000);
        } else {
            btn.innerHTML = '❌ Failed';
            setTimeout(() => { btn.innerHTML = '🧠 Sync Memory'; btn.disabled = false; }, 3000);
        }
    } catch (e) {
        console.error(e);
        btn.innerHTML = '❌ Error';
        setTimeout(() => { btn.innerHTML = '🧠 Sync Memory'; btn.disabled = false; }, 3000);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function initWebPush() {
    const btn = document.getElementById('enable-push-btn');
    if ('serviceWorker' in navigator && 'PushManager' in window) {
        try {
            const reg = await navigator.serviceWorker.register('/service-worker.js');
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                const pubKeyRes = await fetch('/push/public_key');
                const publicVapidKey = await pubKeyRes.text();
                const sub = await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
                });
                await fetch('/push_token', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: JSON.stringify(sub) })
                });
                if (btn) btn.innerHTML = '🔔 Bound!';
                alert('Handshake Successful! Her backend has your device token.');
            } else {
                alert('Permission denied by browser.');
                if (btn) btn.innerHTML = '❌ Denied';
            }
        } catch (err) {
            alert('Push Error: ' + err.message);
            if (btn) btn.innerHTML = '❌ Error';
        }
    } else {
        alert('Web Push is not supported here. (Are you on an unencrypted HTTP IP?)');
        if (btn) btn.innerHTML = '❌ Unsupported';
    }
}
</script>
"""

# 4. Inject cleanly at the bottom
html = html.replace('</body>', master_js + '\n</body>')

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("JavaScript architecture physically repaired!")
