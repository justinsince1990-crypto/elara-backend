with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

bad_patch = """
    # Evolution: Intimacy Engine
    self_data = load_elara_self()
    self_data['intimacy'] = min(self_data.get('intimacy', 1.0) + 0.05, 10.0)
    save_elara_self(self_data)
"""

# Undo the botched replacement
code = code.replace("touch_last_seen()\n" + bad_patch, "touch_last_seen()")

# Inject it safely inside the function instead
safe_patch = """def touch_last_seen():
    try:
        sd = load_elara_self()
        sd['intimacy'] = min(sd.get('intimacy', 1.0) + 0.05, 10.0)
        save_elara_self(sd)
    except: pass"""

if "except: pass" not in code:
    code = code.replace("def touch_last_seen():", safe_patch)

with open('/root/elara/brain.py', 'w') as f:
    f.write(code)
