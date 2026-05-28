with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

# Define the fix for the history endpoint if it's missing or misconfigured
history_fix = """
@app.get("/history")
async def get_history(conversation_id: str = "default"):
    conv = await _io_get_conversation(conversation_id)
    hist = conv.get("messages") or []
    # Ensure every message has an audio_url field for the frontend
    formatted_hist = []
    for m in hist:
        msg_data = {"role": m.get("role"), "content": m.get("content")}
        # If this is an assistant message and you want to re-enable audio, 
        # add logic here to compute the audio_url if it exists
        formatted_hist.append(msg_data)
    return {"history": formatted_hist}
"""

if '@app.get("/history")' in code:
    print("History route already exists.")
else:
    # Append the route to brain.py
    with open('/root/elara/brain.py', 'a') as f:
        f.write(history_fix)
    print("History route patched.")
