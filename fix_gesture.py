import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# 1. Remove the broken background auto-load trigger
html = html.replace("window.addEventListener('DOMContentLoaded', initWebPush);", "")

# 2. Inject a manual trigger button right beside the Sync Memory button
if 'id="enable-push-btn"' not in html:
    button_html = r'<button id="enable-push-btn" onclick="initWebPush(); this.innerHTML=\'🔔 Enabled\';" class="mt-2 mr-2 px-2 py-1 text-[10px] bg-blue-800/40 hover:bg-blue-700/60 text-blue-300 rounded border border-blue-600/30 transition-all tracking-wide">🔔 Enable Alerts</button>\n\g<0>'
    html = re.sub(r'<button id="sync-memory-btn".*?</button>', button_html, html, flags=re.DOTALL)

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("Gesture patch successfully applied!")
