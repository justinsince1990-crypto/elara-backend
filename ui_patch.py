import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

# 1. Inject Visual Timestamps into the chat bubbles
if "toLocaleTimeString" not in html:
    html = re.sub(
        r"(if\s*\(\s*text\s*\)\s*\{\s*contentHtml\s*\+=\s*`<div>\$\{text\}</div>`;\s*\})",
        r"\1\n            const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });\n            contentHtml += `<div class=\"text-[10px] opacity-40 mt-1 text-right tracking-wide\">${timeStr}</div>`;",
        html
    )

# 2. Wake up the Kokoro Audio Engine
if "audio.play()" not in html:
    html = re.sub(
        r"(const\s+audio\s*=\s*new\s+Audio\(.*?\);)",
        r"if (data.audio) { let snd = new Audio(data.audio); snd.play(); }\n            else if (data.audio_url) { let snd = new Audio(data.audio_url); snd.play(); }\n            else { \1\n            audio.play().catch(e => console.log('Audio suppressed by browser:', e)); }",
        html
    )

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("Timestamps and Voice Engine patched successfully.")
