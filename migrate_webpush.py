import re
import base64
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

print("1. Generating VAPID cryptographic keys...")
private_key = ec.generate_private_key(ec.SECP256R1())
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode('utf-8')

public_bytes = public_key = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)
public_b64url = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

with open('/root/elara/vapid_private.pem', 'w') as f:
    f.write(private_pem)
with open('/root/elara/vapid_public.txt', 'w') as f:
    f.write(public_b64url)

print("2. Creating background service worker handler...")
sw_code = """self.addEventListener('push', function(event) {
    let data = { title: 'Elara', body: 'New message received' };
    if (event.data) {
        try { data = event.data.json(); }
        except (e) { data = { title: 'Elara', body: event.data.text() }; }
    }
    const options = {
        body: data.body,
        icon: '/icon.png',
        badge: '/badge.png',
        data: data.data || {}
    };
    event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(clients.openWindow('/'));
});
"""
with open('/root/elara/service-worker.js', 'w') as f:
    f.write(sw_code)

print("3. Re-routing brain.py infrastructure...")
with open('/root/elara/brain.py', 'r') as f:
    brain = f.read()

root_pattern = r'(async def root\(\):.*?return HTMLResponse\(.*?\)\n)'
new_endpoints = """
@app.get("/service-worker.js")
async def service_worker():
    from fastapi import Response
    with open("/root/elara/service-worker.js", "r") as f:
        return Response(content=f.read(), media_type="application/javascript")

@app.get("/push/public_key")
async def get_public_key():
    from fastapi import Response
    with open("/root/elara/vapid_public.txt", "r") as f:
        return Response(content=f.read(), media_type="text/plain")
"""
if '/service-worker.js' not in brain:
    brain = re.sub(root_pattern, r'\1' + new_endpoints, brain, flags=re.DOTALL)

send_push_pattern = r'def send_push\(title: str, body: str,.*'
new_send_push = """def send_push(title: str, body: str, full_message: str | None = None) -> bool:
    \"\"\"Send a standard Web Push notification.\"\"\"
    token_str = load_push_token()
    if not token_str:
        return False
    try:
        import json
        from pywebpush import webpush
        subscription_info = json.loads(token_str)
        payload = {
            "title": title,
            "body": body,
            "data": {"message": full_message or body}
        }
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key='/root/elara/vapid_private.pem',
            vapid_claims={"sub": "mailto:admin@localhost"}
        )
        return True
    except Exception as e:
        print(f"WebPush execution failure: {e}")
        return False
"""
brain = re.sub(send_push_pattern, new_send_push, brain, flags=re.DOTALL)

with open('/root/elara/brain.py', 'w') as f:
    f.write(brain)

print("4. Embedding browser handshake into interface layout...")
with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

frontend_js = """
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
                        console.log('Web Push Infrastructure Active.');
                    }
                } catch (err) {
                    console.error('Handshake failed:', err);
                }
            }
        }
        window.addEventListener('DOMContentLoaded', initWebPush);
"""
if 'initWebPush' not in html:
    html = html.replace('</script>', frontend_js + '\n</script>')
    with open('/root/elara/chat_ui.html', 'w') as f:
        f.write(html)

print("Migration Successfully Applied!")
