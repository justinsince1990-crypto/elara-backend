import json, os, re

# 1. Update/Initialize Intimacy in self profile
self_path = '/root/elara/elara_self.json'
if os.path.exists(self_path):
    with open(self_path, 'r') as f:
        data = json.load(f)
    if 'intimacy' not in data:
        data['intimacy'] = 1.0
        with open(self_path, 'w') as f:
            json.dump(data, f, indent=2)

# 2. Patch brain.py to track intimacy
brain_path = '/root/elara/brain.py'
with open(brain_path, 'r') as f:
    code = f.read()

# Inject the logic to increment intimacy per message
new_patch = """
    # Evolution: Intimacy Engine
    self_data = load_elara_self()
    self_data['intimacy'] = min(self_data.get('intimacy', 1.0) + 0.05, 10.0)
    save_elara_self(self_data)
"""
# Find where the user message is handled in chat_endpoint and inject the intimacy bump
if "Evolution: Intimacy Engine" not in code:
    code = code.replace("touch_last_seen()", "touch_last_seen()\n" + new_patch)
    with open(brain_path, 'w') as f:
        f.write(code)

print("Evolution Patch Applied Successfully.")
