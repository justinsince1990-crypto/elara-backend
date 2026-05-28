with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

time_logic = """
    # INJECT: Time Awareness
    import datetime
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Chicago")
    except:
        tz = datetime.timezone(datetime.timedelta(hours=-5))
    current_time = datetime.datetime.now(tz).strftime("%A, %B %d, %Y at %I:%M %p")
    
    for msg in kwargs.get('messages', []):
        if msg.get('role') == 'system':
            msg['content'] += f"\\n\\n[SYSTEM LOG: The current local time for Justin is {current_time}. You must be aware of this time when responding.]"
"""

if "INJECT: Time Awareness" not in code:
    code = code.replace(
        "def _create_completion(stream: bool = False, **kwargs) -> Any:\n",
        "def _create_completion(stream: bool = False, **kwargs) -> Any:\n" + time_logic
    )
    with open('/root/elara/brain.py', 'w') as f:
        f.write(code)
    print("Time Awareness Patch applied successfully.")
else:
    print("Patch already exists.")
