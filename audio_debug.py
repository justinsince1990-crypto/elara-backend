with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# 1. Surface backend missing data errors
if "Server did not generate audio payload" not in html:
    html = html.replace(
        "appendMessage(reply, false);",
        "appendMessage(reply, false);\n            if (!data.audio) { appendMessage('⚠️ System: Server did not generate audio payload.', false); }"
    )

# 2. Surface mobile browser autoplay blocks
if "Browser autoplay blocked" not in html:
    html = html.replace(
        "console.error(\"Local audio synthesis engine dropped context:\", audioErr);",
        "console.error(audioErr);\n                appendMessage(`⚠️ System: Browser autoplay blocked playback.`, false);"
    )

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("Diagnostic Patch Applied!")
