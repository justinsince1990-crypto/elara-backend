import re
with open('/root/elara/chat_ui.html', 'r') as f: h = f.read()
h = re.sub(r'<script src="https://cdn.tailwindcss.com">.*?</script>', '<script src="https://cdn.tailwindcss.com"></script>', h, flags=re.DOTALL)
h = re.sub(r'<script>\s*async function.*?</script>', '', h, flags=re.DOTALL)
with open('/root/elara/chat_ui.html', 'w') as f: f.write(h)
print("1. Old scripts cleared.")
