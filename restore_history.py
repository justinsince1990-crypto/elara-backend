import os, json, re

# 1. Fix the brain.py folder path (removing the weird nested /data/elara path)
brain_path = '/root/elara/brain.py'
with open(brain_path, 'r') as f:
    brain_code = f.read()
if '"/root/elara/data/elara/conversations"' in brain_code:
    brain_code = brain_code.replace('"/root/elara/data/elara/conversations"', '"/root/elara/conversations"')
    with open(brain_path, 'w') as f:
        f.write(brain_code)

# 2. Find the true history file
best_id = "default"
max_msgs = -1

for d in ['/root/elara/conversations', '/root/elara/data/elara/conversations']:
    if os.path.exists(d):
        for filename in os.listdir(d):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(d, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        msgs = len(data.get('messages', []))
                        if msgs > max_msgs:
                            max_msgs = msgs
                            best_id = filename.replace('.json', '')
                except:
                    pass

print(f"Found your history! ID: {best_id} with {max_msgs} messages.")

# 3. Patch chat_ui.html to use this exact ID for loading and sending
ui_path = '/root/elara/chat_ui.html'
with open(ui_path, 'r') as f:
    ui_code = f.read()

# Update the load fetch URL
ui_code = re.sub(r"fetch\('/history\?conversation_id=[^']+'\)", f"fetch('/history?conversation_id={best_id}')", ui_code)

# Update the send payload so new messages save to the right place
if "conversation_id:" not in ui_code:
    ui_code = ui_code.replace("const payload = { message: text };", f"const payload = {{ message: text, conversation_id: '{best_id}' }};")
else:
    ui_code = re.sub(r"conversation_id:\s*'[^']+'", f"conversation_id: '{best_id}'", ui_code)

with open(ui_path, 'w') as f:
    f.write(ui_code)

