import re

with open('/root/elara/chat_ui.html', 'r') as f:
    html = f.read()

smart_logic = """const cameraBtn = document.getElementById('camera-btn');
        // INJECT: Smart Audio State
        window.autoPlayAudio = false;
        
        const sendBtnRef = document.getElementById('send-btn');
        if (sendBtnRef && sendBtnRef.parentNode && !document.getElementById('audio-toggle')) {
            const toggleBtn = document.createElement('button');
            toggleBtn.id = 'audio-toggle';
            toggleBtn.innerHTML = '🔇';
            toggleBtn.className = 'px-3 py-2 text-xl text-gray-400 hover:text-white transition-all duration-200';
            toggleBtn.title = 'Toggle Auto-Play';
            toggleBtn.onclick = (e) => { 
                e.preventDefault();
                window.autoPlayAudio = !window.autoPlayAudio; 
                toggleBtn.innerHTML = window.autoPlayAudio ? '🔊' : '🔇'; 
            };
            sendBtnRef.parentNode.insertBefore(toggleBtn, sendBtnRef);
        }

        window.handleAudio = function(snd) {
            const historyDiv = document.getElementById('chat-history');
            const lastBubble = historyDiv.lastElementChild;
            if (lastBubble) {
                lastBubble.style.cursor = 'pointer';
                lastBubble.title = 'Tap bubble to play audio';
                lastBubble.onclick = () => { snd.currentTime = 0; snd.play(); };
                const ts = lastBubble.querySelector('.text-\\\\[10px\\\\]');
                if (ts && !ts.innerHTML.includes('🎵')) {
                    ts.innerHTML += ' <span class="text-emerald-400 ml-1">🎵</span>';
                }
            }
            if (window.autoPlayAudio) {
                snd.play().catch(e => console.log("Autoplay blocked:", e));
            }
            return Promise.resolve();
        };
"""

if "window.autoPlayAudio = false;" not in html:
    html = html.replace("const cameraBtn = document.getElementById('camera-btn');", smart_logic)

# Replace the messy playback calls with the clean smart logic
html = re.sub(r'snd\.play\(\);', r'window.handleAudio(snd);', html)
html = re.sub(r'await\s+audio\.play\(\);', r'await window.handleAudio(audio);', html)
html = re.sub(r'audio\.play\(\)\.catch\([^)]+\);', r'window.handleAudio(audio);', html)

with open('/root/elara/chat_ui.html', 'w') as f:
    f.write(html)

print("Toggle Switch and Tap-to-Play Patched!")
