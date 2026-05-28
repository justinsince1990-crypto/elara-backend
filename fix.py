import re
with open('/root/elara/chat_ui.html', 'r') as f:
 h = f.read()

# Protect Tailwind CSS
t1 = '<script src="https://cdn.tailwindcss.com"></script>'
t2 = '<!--TW-->'
h = h.replace(t1, t2)

# Nuke all broken/corrupted scripts
h = re.sub(r'<script.*?</script>', '', h, flags=re.DOTALL)

# Restore Tailwind
h = h.replace(t2, t1)

# Build Javascript block safely to avoid wrapping
js = "<script>\n"
js += "function urlBase64ToUint8Array(s) {\n"
js += " const pad = '='.repeat((4 - s.length % 4) % 4);\n"
js += " const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/');\n"
js += " const raw = window.atob(b64);\n"
js += " const arr = new Uint8Array(raw.length);\n"
js += " for(let i=0; i<raw.length; ++i) arr[i] = raw.charCodeAt(i);\n"
js += " return arr;\n"
js += "}\n"
js += "async function initWebPush() {\n"
js += " const b = document.getElementById('enable-push-btn');\n"
js += " try {\n"
js += "  const reg = await navigator.serviceWorker.register("
js += "'/service-worker.js');\n"
js += "  const p = await Notification.requestPermission();\n"
js += "  if(p === 'granted') {\n"
js += "   const res = await fetch('/push/public_key');\n"
js += "   const key = await res.text();\n"
js += "   const sub = await reg.pushManager.subscribe({\n"
js += "    userVisibleOnly: true,\n"
js += "    applicationServerKey: urlBase64ToUint8Array(key)\n"
js += "   });\n"
js += "   await fetch('/push_token', {\n"
js += "    method: 'POST',\n"
js += "    headers: {'Content-Type': 'application/json'},\n"
js += "    body: JSON.stringify({token: JSON.stringify(sub)})\n"
js += "   });\n"
js += "   if(b) b.innerHTML = '🔔 Bound!';\n"
js += "   alert('Handshake Successful!');\n"
js += "  } else { alert('Denied'); }\n"
js += " } catch(e) { alert('Error: '+e.message); }\n"
js += "}\n"
js += "async function triggerMemorySync() {\n"
js += " const b = document.getElementById('sync-memory-btn');\n"
js += " b.innerHTML = '⚙️...';\n"
js += " try {\n"
js += "  const r = await fetch('/memory/consolidate', {method: 'POST'});\n"
js += "  const d = await r.json();\n"
js += "  b.innerHTML = d.ok ? '✅ Synced' : '❌ Failed';\n"
js += " } catch(e) { b.innerHTML = '❌ Err'; }\n"
js += " setTimeout(() => { b.innerHTML = '🧠 Sync Memory'; }, 3000);\n"
js += "}\n"
js += "</script>"

h = h.replace('</body>', js + '\n</body>')
with open('/root/elara/chat_ui.html', 'w') as f:
 f.write(h)
print("UI Repaired Successfully!")
