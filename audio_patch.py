import re

with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

# We look for the exact spot where the chat endpoint builds the return dictionary
pattern = r'(maybe_auto_title[^\n]+)\n+(\s+)return\s*\{\n*\s*"ok":\s*True,\n*\s*"response":\s*reply,'

def repl(m):
    indent = m.group(2)
    inner_indent = "\n" + indent + "    "
    inj = (
        m.group(1) + "\n\n" +
        indent + "# INJECT: Auto-TTS for Chat\n" +
        indent + "audio_url = None\n" +
        indent + "try:\n" +
        indent + "    tts_req = TTSRequest(text=reply)\n" +
        indent + "    tts_resp = await generate_tts(tts_req)\n" +
        indent + "    import json\n" +
        indent + "    audio_url = json.loads(tts_resp.body.decode('utf-8')).get('url')\n" +
        indent + "except Exception as e:\n" +
        indent + "    print(f'Auto-TTS failed: {e}')\n\n" +
        indent + "return {" +
        inner_indent + "\"audio\": audio_url," +
        inner_indent + "\"ok\": True," +
        inner_indent + "\"response\": reply,"
    )
    return inj

if "Auto-TTS for Chat" not in code:
    code, count = re.subn(pattern, repl, code, count=1)
    if count > 0:
        with open('/root/elara/brain.py', 'w') as f:
            f.write(code)
        print("Audio Payload Patched!")
    else:
        print("Failed to find replacement target.")
else:
    print("Already patched.")
