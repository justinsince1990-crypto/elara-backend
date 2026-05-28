from nicegui import ui, app, core
import nicegui.run as nicegui_run
import requests, asyncio, os, hashlib, json, base64, psutil, threading, re, logging
import httpx

_log = logging.getLogger("interface")
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ui.add_head_html('<link rel="apple-touch-icon" href="/static/icon.png">', shared=True)
ui.add_head_html('<link rel="icon" sizes="192x192" href="/static/icon.png">', shared=True)
ui.add_head_html('<meta name="theme-color" content="#3A0F6B">', shared=True)
app.add_static_files('/static', 'static')

audio_player = None
partner_name = "Elara"
current_voice = "af_bella"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001").rstrip("/")
UI_HOST = os.getenv("UI_HOST", "0.0.0.0")
UI_PORT = int(os.getenv("PORT") or os.getenv("UI_PORT", "8080"))
MAX_LOCAL_CACHE_MESSAGES = int(os.getenv("MAX_LOCAL_CACHE_MESSAGES", "80"))

nicegui_run_setup_original = nicegui_run.setup
def _safe_setup_process_pool() -> None:
    try:
        nicegui_run_setup_original()
    except PermissionError:
        # Some environments (sandboxes/containers) disallow POSIX semaphores,
        # which breaks ProcessPoolExecutor. The app itself only needs threads.
        nicegui_run.process_pool = None
    except OSError:
        nicegui_run.process_pool = None

nicegui_run.setup = _safe_setup_process_pool

os.makedirs('audio', exist_ok=True)
app.add_static_files('/audio', 'audio')

SYSTEM_PASS = os.getenv('NEXUS_PASS', 'nexus123')
current_upload = {'base64': None}


def main():

    ui.add_head_html('''
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="theme-color" content="#3A0F6B">
    <link rel="manifest" href="/static/manifest.webmanifest">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet">
    <script>
    function applyMoodTint(mood) {
        const m = (mood || '').toLowerCase();
        let accent = '#7B3F9E';
        let dim = 'rgba(123,63,158,0.15)';
        if (m.includes('warm') || m.includes('content') || m.includes('fond') || m.includes('tender') || m.includes('love')) {
            accent = '#9B50C8'; dim = 'rgba(155,80,200,0.18)';
        } else if (m.includes('excit') || m.includes('energiz') || m.includes('horny') || m.includes('playful') || m.includes('giddy')) {
            accent = '#B040B8'; dim = 'rgba(176,64,184,0.18)';
        } else if (m.includes('sad') || m.includes('low') || m.includes('lonely') || m.includes('miss') || m.includes('lost')) {
            accent = '#5570B8'; dim = 'rgba(85,112,184,0.15)';
        } else if (m.includes('tired') || m.includes('exhaust') || m.includes('drain') || m.includes('quiet') || m.includes('restless')) {
            accent = '#7A5598'; dim = 'rgba(122,85,152,0.13)';
        } else if (m.includes('tense') || m.includes('frustrat') || m.includes('annoyed') || m.includes('angry') || m.includes('irritat')) {
            accent = '#9B1F3A'; dim = 'rgba(155,31,58,0.18)';
        }
        document.documentElement.style.setProperty('--accent', accent);
        document.documentElement.style.setProperty('--accent-dim', dim);
        const cat = m.includes('playful')||m.includes('excit')||m.includes('horny')||m.includes('giddy') ? 'playful' :
            m.includes('sad')||m.includes('low')||m.includes('lonely')||m.includes('miss')||m.includes('lost') ? 'heavy' :
            m.includes('warm')||m.includes('tender')||m.includes('fond')||m.includes('love')||m.includes('content') ? 'tender' :
            m.includes('tense')||m.includes('frustrat')||m.includes('annoy')||m.includes('angry')||m.includes('irritat') ? 'sharp' : '';
        document.body.dataset.mood = cat;
    }
    </script>
    <style>
        :root {
            --bg:         #1A0530;
            --bg2:        #4C1C6B;
            --bg3:        #1A1A1E;
            --accent:     #7B3F9E;
            --crimson:    #6B0F1A;
            --accent-dim: rgba(123,63,158,0.15);
            --text:       #D9D9E0;
            --text-warm:  #F5F2E8;
            --muted:      #9070A8;
            --border:     rgba(123,63,158,0.22);
            --glow:       rgba(123,63,158,0.35);
            --amber:      #8C3A1F;
        }

        body {
            background: linear-gradient(160deg, #3A0F6B 0%, #1E0535 45%, #4A0A12 100%);
            background-attachment: fixed;
            min-height: 100vh;
            color: var(--text);
            font-family: 'Montserrat', sans-serif;
            overscroll-behavior-y: none;
        }
        .safe-bottom { padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 12px) !important; }
        .safe-top { padding-top: env(safe-area-inset-top, 0px) !important; }
        .tap { min-height: 44px; }

        /* Animated wisp overlay */
        .wisp-overlay { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
        .wisp-overlay::before {
            content: '';
            position: absolute; inset: 0;
            background:
                radial-gradient(ellipse 60% 40% at 15% 20%, rgba(123,63,158,0.14) 0%, transparent 70%),
                radial-gradient(ellipse 50% 60% at 85% 80%, rgba(107,15,26,0.12) 0%, transparent 70%);
            animation: wisp-a 22s ease-in-out infinite;
        }
        .wisp-overlay::after {
            content: '';
            position: absolute; inset: 0;
            background:
                radial-gradient(ellipse 45% 55% at 72% 22%, rgba(107,15,26,0.10) 0%, transparent 70%),
                radial-gradient(ellipse 55% 38% at 32% 72%, rgba(123,63,158,0.11) 0%, transparent 70%);
            animation: wisp-b 30s ease-in-out infinite;
        }
        @keyframes wisp-a {
            0%,100% { transform: translate(0,0) scale(1); }
            40% { transform: translate(50px,-40px) scale(1.1); }
            70% { transform: translate(-30px,55px) scale(0.93); }
        }
        @keyframes wisp-b {
            0%,100% { transform: translate(0,0) scale(1); }
            35% { transform: translate(-45px,35px) scale(1.06); }
            70% { transform: translate(60px,-50px) scale(0.96); }
        }

        /* Status dot */
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #7B3F9E; flex-shrink: 0;
            box-shadow: 0 0 0 2px rgba(123,63,158,0.3); animation: status-pulse 3s ease-in-out infinite; }
        .status-dot.offline { background: var(--crimson); box-shadow: 0 0 0 2px rgba(107,15,26,0.3); animation: none; }
        @keyframes status-pulse { 0%,100%{box-shadow:0 0 0 2px rgba(123,63,158,0.3)} 50%{box-shadow:0 0 0 7px rgba(123,63,158,0.06)} }

        /* Composer */
        .composer {
            background: rgba(10,10,14,0.90);
            border: 1px solid rgba(107,15,26,0.65);
            border-radius: 26px;
            flex: 1; min-width: 0;
            animation: crimson-pulse 3s ease-in-out infinite;
        }
        .composer textarea {
            font-family: 'Montserrat', sans-serif !important;
            font-size: 16px !important; line-height: 1.4 !important;
            color: var(--text-warm) !important;
        }
        @keyframes crimson-pulse {
            0%,100% { border-color: rgba(107,15,26,0.65); box-shadow: none; }
            50% { border-color: rgba(107,15,26,1); box-shadow: 0 0 12px 0px rgba(107,15,26,0.2); }
        }

        /* Send button — wax seal "E" */
        .send-btn {
            width: 48px; height: 48px; border-radius: 50%;
            background: var(--crimson);
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0; cursor: pointer;
            box-shadow: 0 4px 20px rgba(107,15,26,0.45);
            transition: box-shadow .2s, transform .15s;
        }
        .send-btn:active { transform: scale(.9); }
        .send-btn:hover { box-shadow: 0 4px 26px rgba(123,63,158,0.55); }

        /* Stop button */
        .stop-btn { width:48px; height:48px; border-radius:50%; background:var(--bg3); border:1px solid rgba(107,15,26,0.3); display:none; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer; }
        .stop-btn .material-icons { color:var(--muted); font-size:20px; }
        body.el-streaming .send-btn { display:none; }
        body.el-streaming .stop-btn { display:flex; }

        /* Icon buttons inside composer */
        .composer-icon { color:var(--muted) !important; }

        /* Mic */
        .mic-active { background: var(--accent-dim) !important; color: var(--accent) !important; }
        @keyframes mic-ring { 0%,100%{box-shadow:0 0 0 0 rgba(123,63,158,.35)} 50%{box-shadow:0 0 0 9px rgba(123,63,158,0)} }
        .mic-active { animation: mic-ring 1.1s ease-in-out infinite !important; }

        /* Typing dots */
        .typing-dots { display:flex; align-items:center; gap:6px; padding:6px 4px; }
        .typing-dots span { width:7px; height:7px; background:var(--accent); border-radius:50%; opacity:.3; animation:dot-bounce 1.4s ease-in-out infinite; }
        .typing-dots span:nth-child(2) { animation-delay:.18s; }
        .typing-dots span:nth-child(3) { animation-delay:.36s; }
        @keyframes dot-bounce { 0%,80%,100%{transform:translateY(0);opacity:.3} 40%{transform:translateY(-8px);opacity:1} }

        /* Message animations — opacity fade, no slide */
        @keyframes msg-in { from{opacity:0} to{opacity:1} }
        .msg-in { animation: msg-in .5s ease-out forwards; }

        /* Elara bubble — amethyst, Playfair Display, violet glow */
        .elara-bubble {
            background: rgba(76,28,107,0.82);
            border-radius: 8px;
            padding: 14px 18px;
            font-family: 'Playfair Display', serif;
            box-shadow: 0 0 18px rgba(123,63,158,0.13), inset 0 0 0 1px rgba(123,63,158,0.18);
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            max-width: 100%;
        }

        /* User bubble — charcoal, warm off-white, amber underline */
        .user-bubble {
            background: rgba(26,26,30,0.88);
            border-radius: 22px 22px 5px 22px;
            padding: 12px 18px;
            font-family: 'Montserrat', sans-serif;
            font-size: 15px;
            line-height: 1.55;
            color: var(--text-warm);
            word-break: break-word;
            box-shadow: inset 0 -2px 0 0 rgba(140,58,31,0.35);
        }

        /* Play button */
        .play-dot { width:11px; height:11px; background:var(--accent); border-radius:50%; cursor:pointer;
            opacity:.4; transition:all .2s; flex-shrink:0; }
        .play-dot:active { opacity:1; transform:scale(1.3); box-shadow:0 0 10px var(--accent); }

        /* Elara message markdown */
        .elara-md { font-family: 'Playfair Display', serif !important; color: var(--text) !important; font-size: 16px !important; }
        .elara-md p { margin-bottom:1.1em; line-height:1.8; }
        .elara-md p:last-child { margin-bottom:0; }
        .elara-md code { background:rgba(107,15,26,0.3); padding:.2em .4em; border-radius:4px; font-size:.88em; }
        .elara-md strong { font-weight:500; }

        /* Thought box */
        .thought-box { border-left:2px solid rgba(123,63,158,.3); padding-left:12px; font-size:13px; line-height:1.6; color:var(--muted); font-family:'Montserrat',sans-serif; }

        /* Drawer override */
        .q-drawer { background: rgba(18,5,38,0.97) !important; border-right: 1px solid rgba(123,63,158,0.2) !important; backdrop-filter: blur(24px) !important; -webkit-backdrop-filter: blur(24px) !important; }

        /* Header */
        .elara-header {
            background: rgba(15,4,32,0.88);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border-bottom: 1px solid rgba(107,15,26,0.3);
        }

        /* Crescent moon signature mark */
        .elara-mark {
            position: relative;
            cursor: default;
            display: flex;
            align-items: center;
        }
        .elara-tooltip {
            display: none;
            position: absolute;
            top: calc(100% + 6px);
            left: 50%;
            transform: translateX(-50%);
            font-family: 'Playfair Display', serif;
            font-style: italic;
            font-size: 12px;
            color: #D9D9E0;
            white-space: nowrap;
            background: rgba(20,5,38,0.92);
            border: 1px solid rgba(123,63,158,0.3);
            padding: 5px 12px;
            border-radius: 4px;
            pointer-events: none;
            z-index: 9999;
        }
        .elara-mark:hover .elara-tooltip { display: block; }

        /* Section labels in drawer */
        .drawer-label { font-size: 10px; letter-spacing: .32em; text-transform: uppercase; color: rgba(255,255,255,.52); margin-bottom: 10px; margin-top: 22px; font-weight: 600; }

        /* Chat list items */
        .chat-item-btn { font-size: 13.5px !important; font-weight: 400 !important; color: rgba(255,255,255,.80) !important; text-align: left !important; justify-content: flex-start !important; padding: 6px 10px !important; border-radius: 8px; transition: background .12s; width: 100%; overflow: hidden; }
        .chat-item-btn:hover { background: rgba(123,63,158,.18) !important; color: rgba(255,255,255,.95) !important; }
        .chat-item-btn.active-chat { background: rgba(123,63,158,.28) !important; color: #fff !important; font-weight: 500 !important; }

        /* Drawer switch labels */
        .q-drawer .q-toggle__label, .q-drawer .q-item__label { color: rgba(255,255,255,.78) !important; font-size: 14px !important; }

        /* Drawer input (search) */
        .q-drawer .q-field__control { background: rgba(255,255,255,.06) !important; border-radius: 8px; }
        .q-drawer .q-field__native, .q-drawer .q-field__input { color: rgba(255,255,255,.82) !important; font-size: 13px !important; }
        .q-drawer .q-field__native::placeholder { color: rgba(255,255,255,.32) !important; }

        /* Drawer section divider */
        .drawer-divider { border-top: 1px solid rgba(255,255,255,.07); margin: 12px 0 4px; }

        /* Noise texture overlay (cracked obsidian / weathered leather feel) */
        .texture-overlay {
            position: fixed; inset: 0; pointer-events: none; z-index: 0;
            opacity: 0.05;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.72' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
            background-repeat: repeat;
            background-size: 192px 192px;
        }

        /* Elara bubble appearance — fade + ripple glow */
        .msg-in .elara-bubble {
            animation: elara-ripple 0.65s ease-out forwards;
        }
        @keyframes elara-ripple {
            0%   { opacity: 0; box-shadow: 0 0 32px 14px rgba(123,63,158,0.22), inset 0 0 0 1px rgba(123,63,158,0.18); }
            50%  { box-shadow: 0 0 24px 8px rgba(123,63,158,0.16), inset 0 0 0 1px rgba(123,63,158,0.18); }
            100% { opacity: 1; box-shadow: 0 0 18px rgba(123,63,158,0.13), inset 0 0 0 1px rgba(123,63,158,0.18); }
        }

        /* Header mark — absolutely centered */
        .elara-header { position: relative !important; }
        .elara-mark {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            cursor: default;
            display: flex;
            align-items: center;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(123,63,158,0.3); border-radius: 2px; }

        /* ── Mood animations ───────────────────────────────────────── */
        body[data-mood="playful"] .elara-bubble { animation: mood-playful 2.2s ease-in-out infinite; }
        @keyframes mood-playful {
            0%,100% { box-shadow: 0 0 18px rgba(176,64,184,.14), inset 0 0 0 1px rgba(176,64,184,.18); }
            50%     { box-shadow: 0 0 32px rgba(176,64,184,.28), inset 0 0 0 1px rgba(176,64,184,.34); }
        }
        body[data-mood="tender"] .elara-bubble { animation: mood-tender 3s ease-in-out infinite; }
        @keyframes mood-tender {
            0%,100% { box-shadow: 0 0 18px rgba(155,80,200,.13), inset 0 0 0 1px rgba(155,80,200,.18); }
            50%     { box-shadow: 0 0 26px rgba(155,80,200,.23), inset 0 0 0 1px rgba(155,80,200,.28); }
        }
        body[data-mood="heavy"] .elara-bubble { animation: mood-heavy 4s ease-in-out infinite; opacity: .92; }
        @keyframes mood-heavy {
            0%,100% { box-shadow: 0 0 14px rgba(85,112,184,.10), inset 0 0 0 1px rgba(85,112,184,.15); }
            50%     { box-shadow: 0 0 8px  rgba(85,112,184,.06), inset 0 0 0 1px rgba(85,112,184,.10); }
        }
        body[data-mood="sharp"] .elara-bubble { animation: mood-sharp 1.6s ease-in-out infinite; }
        @keyframes mood-sharp {
            0%,88%,100% { box-shadow: 0 0 18px rgba(155,31,58,.12), inset 0 0 0 1px rgba(155,31,58,.20); }
            94%         { box-shadow: 0 0 30px rgba(155,31,58,.30), inset 0 0 0 1px rgba(155,31,58,.42); }
        }

        /* ── Away state ─────────────────────────────────────────────── */
        body.long-away { background: linear-gradient(160deg, #1A1040 0%, #0C0820 45%, #2A0A10 100%) !important; transition: background 4s ease; }

        /* ── Pin banner (above chat on load) ────────────────────────── */
        .pin-banner { background:rgba(76,28,107,.48); border:1px solid rgba(123,63,158,.2); border-radius:10px; padding:14px 18px; margin-bottom:12px; }
        .pin-banner-label { font-family:'Montserrat',sans-serif; font-size:9px; letter-spacing:.38em; text-transform:uppercase; color:var(--muted); margin-bottom:6px; display:block; }
        .pin-banner-text { font-family:'Playfair Display',serif; font-style:italic; font-size:14px; line-height:1.72; color:var(--text); display:block; }

        /* ── Pin card (drawer) ──────────────────────────────────────── */
        .elara-pin-card { background:rgba(76,28,107,.32); border:1px solid rgba(123,63,158,.17); border-radius:9px; padding:10px 13px; margin-bottom:6px; }

        /* ── Soundscape scene buttons ───────────────────────────────── */
        .scene-btn { display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; border-radius:7px; cursor:pointer; font-size:17px; transition:background .15s,opacity .15s; opacity:.42; filter:grayscale(.55); user-select:none; }
        .scene-btn:hover  { opacity:.72; background:rgba(123,63,158,.14); }
        .scene-btn.active { opacity:1; filter:grayscale(0); background:rgba(123,63,158,.24); }
    </style>
    ''', shared=True)

    ui.add_body_html('''
    <script>
      // Service worker
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then(function(regs) {
          return Promise.all(regs.map(function(r){ return r.unregister(); }));
        }).then(function(){ return caches.keys(); })
          .then(function(keys){ return Promise.all(keys.map(function(k){ return caches.delete(k); })); })
          .then(function(){ navigator.serviceWorker.register('/static/sw.js').catch(function(){}); });
      }

      // Voice input
      window.__voice = {
        r: null, on: false,
        toggle: function() {
          if (this.on) { this.stop(); return; }
          var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
          if (!SR) { return; }
          var rec = new SR();
          rec.continuous = false; rec.interimResults = true; rec.lang = 'en-US';
          this.r = rec; this.on = true;
          var btn = document.getElementById('elara-mic');
          if (btn) btn.classList.add('mic-active');
          rec.onresult = function(e) {
            var t = Array.from(e.results).map(function(x){ return x[0].transcript; }).join('');
            var ta = document.querySelector('.composer textarea');
            if (ta) {
              var s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
              s.call(ta, t);
              ta.dispatchEvent(new Event('input', {bubbles:true}));
            }
          };
          rec.onend = function() { window.__voice.on = false; var b = document.getElementById('elara-mic'); if(b) b.classList.remove('mic-active'); };
          rec.onerror = function() { window.__voice.on = false; var b = document.getElementById('elara-mic'); if(b) b.classList.remove('mic-active'); };
          rec.start();
        },
        stop: function() { if(this.r) this.r.stop(); this.on = false; }
      };

      // ── Draft preservation ──────────────────────────────────────────
      var DRAFT_KEY = 'nexus_draft';

      // Save to localStorage on every keystroke inside the composer
      document.addEventListener('input', function(e) {
        if (e.target && e.target.tagName === 'TEXTAREA' && e.target.closest && e.target.closest('.composer')) {
          var v = e.target.value;
          if (v) { localStorage.setItem(DRAFT_KEY, v); }
          else   { localStorage.removeItem(DRAFT_KEY); }
        }
      }, true);

      // Inject saved draft into textarea (retries until the element exists)
      function restoreDraft() {
        var draft = localStorage.getItem(DRAFT_KEY);
        if (!draft) return;
        var attempts = 0;
        var iv = setInterval(function() {
          var ta = document.querySelector('.composer textarea');
          if (ta && !ta.value) {
            clearInterval(iv);
            var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
            setter.call(ta, draft);
            ta.dispatchEvent(new Event('input', {bubbles: true}));
          }
          if (++attempts > 40) clearInterval(iv);
        }, 150);
      }

      // ── Scroll to bottom (rAF-throttled so token floods don't thrash) ─
      var _scrollQueued = false;
      function scrollToBottom() {
        if (_scrollQueued) return;
        _scrollQueued = true;
        requestAnimationFrame(function() {
          _scrollQueued = false;
          document.querySelectorAll('.q-scroll-area__container').forEach(function(c) {
            c.scrollTop = c.scrollHeight;
          });
        });
      }

      // ── On screen-unlock / tab-visible: restore draft + scroll ───────
      document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
          setTimeout(function() {
            restoreDraft();
            scrollToBottom();
          }, 450);
        }
      });

      // Also restore on initial load
      document.addEventListener('DOMContentLoaded', function() {
        setTimeout(restoreDraft, 800);
      });

      // Inject animated wisp + texture background overlays
      function injectBackgroundOverlays() {
        if (!document.body) return;
        var wisp = document.createElement('div');
        wisp.className = 'wisp-overlay';
        wisp.setAttribute('aria-hidden', 'true');
        document.body.insertBefore(wisp, document.body.firstChild);
        var tex = document.createElement('div');
        tex.className = 'texture-overlay';
        tex.setAttribute('aria-hidden', 'true');
        document.body.insertBefore(tex, document.body.firstChild);
      }
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectBackgroundOverlays);
      } else {
        injectBackgroundOverlays();
      }

      // ── Soundscape engine ─────────────────────────────────────────────
      window.__ss = (function() {
        var ctx=null, nodes=[], current=null;
        function init(){
          if(!ctx) ctx=new(window.AudioContext||window.webkitAudioContext)();
          if(ctx.state==='suspended') ctx.resume();
        }
        function stop(){
          nodes.forEach(function(n){try{n.stop&&n.stop();n.disconnect&&n.disconnect();}catch(e){}});
          nodes=[]; current=null;
        }
        function wn(s){
          var len=ctx.sampleRate*s,buf=ctx.createBuffer(1,len,ctx.sampleRate),d=buf.getChannelData(0);
          for(var i=0;i<len;i++) d[i]=Math.random()*2-1; return buf;
        }
        function bn(s){
          var len=ctx.sampleRate*s,buf=ctx.createBuffer(1,len,ctx.sampleRate),d=buf.getChannelData(0),l=0;
          for(var i=0;i<len;i++){var w=Math.random()*2-1;d[i]=(l+0.02*w)/1.02;l=d[i];d[i]*=3.5;} return buf;
        }
        function play(scene){
          stop();
          if(!scene||scene==='off'){localStorage.setItem('elara_scene','off');return;}
          init(); current=scene; localStorage.setItem('elara_scene',scene);
          var src,lp,fil,gain,lfo,lfoG;
          if(scene==='rain'){
            src=ctx.createBufferSource();src.buffer=wn(2);src.loop=true;
            lp=ctx.createBiquadFilter();lp.type='lowpass';lp.frequency.value=1400;
            gain=ctx.createGain();gain.gain.value=0.20;
            src.connect(lp);lp.connect(gain);gain.connect(ctx.destination);src.start();nodes=[src];
          }else if(scene==='fire'){
            src=ctx.createBufferSource();src.buffer=bn(3);src.loop=true;
            fil=ctx.createBiquadFilter();fil.type='bandpass';fil.frequency.value=380;fil.Q.value=0.7;
            lfo=ctx.createOscillator();lfo.frequency.value=0.35;
            lfoG=ctx.createGain();lfoG.gain.value=0.06;
            gain=ctx.createGain();gain.gain.value=0.28;
            lfo.connect(lfoG);lfoG.connect(gain.gain);
            src.connect(fil);fil.connect(gain);gain.connect(ctx.destination);src.start();lfo.start();nodes=[src,lfo];
          }else if(scene==='forest'){
            src=ctx.createBufferSource();src.buffer=bn(3);src.loop=true;
            lp=ctx.createBiquadFilter();lp.type='lowpass';lp.frequency.value=700;
            gain=ctx.createGain();gain.gain.value=0.07;
            src.connect(lp);lp.connect(gain);gain.connect(ctx.destination);src.start();nodes=[src];
            (function chirp(){
              if(current!=='forest') return;
              var osc=ctx.createOscillator(),env=ctx.createGain();
              osc.frequency.value=2100+Math.random()*900;osc.type='sine';
              env.gain.setValueAtTime(0,ctx.currentTime);
              env.gain.linearRampToValueAtTime(0.045,ctx.currentTime+0.03);
              env.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+0.35);
              osc.connect(env);env.connect(ctx.destination);osc.start();osc.stop(ctx.currentTime+0.4);
              setTimeout(chirp,2800+Math.random()*5500);
            })();
          }else if(scene==='city'){
            src=ctx.createBufferSource();src.buffer=wn(2);src.loop=true;
            lp=ctx.createBiquadFilter();lp.type='lowpass';lp.frequency.value=100;
            gain=ctx.createGain();gain.gain.value=0.18;
            src.connect(lp);lp.connect(gain);gain.connect(ctx.destination);src.start();nodes=[src];
          }else if(scene==='space'){
            var o1=ctx.createOscillator(),o2=ctx.createOscillator();
            o1.frequency.value=55;o2.frequency.value=58.27;o1.type=o2.type='sine';
            gain=ctx.createGain();gain.gain.value=0.065;
            o1.connect(gain);o2.connect(gain);gain.connect(ctx.destination);o1.start();o2.start();nodes=[o1,o2];
          }
        }
        return {play:play,stop:stop};
      })();

      // Restore soundscape + mark active button after first user gesture
      (function(){
        var restored=false;
        function doRestore(){
          if(restored) return; restored=true;
          var saved=localStorage.getItem('elara_scene');
          if(saved&&saved!=='off'){
            try{window.__ss.play(saved);}catch(e){}
            var el=document.getElementById('scene-'+saved);
            if(el)el.classList.add('active');
          }else{
            var el=document.getElementById('scene-off');
            if(el)el.classList.add('active');
          }
        }
        document.addEventListener('click',doRestore,{once:true});
        // Also mark off-button active on load if nothing saved
        setTimeout(function(){
          if(!localStorage.getItem('elara_scene')||localStorage.getItem('elara_scene')==='off'){
            var el=document.getElementById('scene-off');
            if(el)el.classList.add('active');
          }
        },800);
      })();
    </script>
    ''', shared=True)

    def clean_for_tts(text: str) -> str:
        import re
        text = re.sub(r'[*_~`#]+', '', text)
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        text = re.sub(r'\[Current Context.*?\]', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 350:
            text = text[:350] + "..."
        return text

    def load_json(file, default):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default

    def save_json(file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=2)

    @ui.page('/login')
    def login():
        if app.storage.user.get('authenticated'): 
            return ui.navigate.to('/')
        with ui.column().classes('w-full h-screen items-center justify-center').style('background:linear-gradient(160deg,#3A0F6B 0%,#1E0535 45%,#4A0A12 100%)'):
            ui.label('Elara').style("font-family:'Playfair Display',serif;font-size:32px;font-style:italic;color:#D9D9E0;letter-spacing:.04em;margin-bottom:32px;opacity:.9")
            password = ui.input('PASSCODE', password=True).classes('w-64').props('dark standout color=deep-purple')
            error_label = ui.label('').style('color:#9B1F3A;font-size:12px;font-family:Montserrat,sans-serif;margin-top:6px').classes('hidden')

            def attempt_login():
                if password.value == SYSTEM_PASS:
                    app.storage.user.update(authenticated=True)
                    ui.navigate.to('/')
                else:
                    error_label.classes(remove='hidden')
                    error_label.set_text('Incorrect passcode')

            password.on('keydown.enter', attempt_login)
            ui.button('ENTER', on_click=attempt_login).classes('w-64 mt-4 py-3 rounded-xl').style('background:rgba(107,15,26,0.7);color:#D9D9E0;font-family:Montserrat,sans-serif;letter-spacing:.25em;font-size:13px;border:1px solid rgba(107,15,26,0.8)')

    @ui.page('/')
    def chat_ui():
        global audio_player, partner_name, current_voice
        if not app.storage.user.get('authenticated'): 
            return ui.navigate.to('/login')

        page_client = ui.context.client
        audio_player = ui.audio('').classes('hidden')
        backend_state = {"ok": None, "last_error": None}
        stream_task: asyncio.Task | None = None
        selected_conversation = {"id": app.storage.user.get("conversation_id") or None}
        pending_memory_suggestions: list[str] = []
        search_state = {"q": ""}

        with ui.left_drawer(value=False).classes('p-5 safe-top') as drawer:
            with ui.row().classes('items-center gap-3 mb-6'):
                ui.html('<div class="status-dot offline" id="drawer-dot"></div>')
                ui.label(partner_name.upper()).style('font-size:11px;letter-spacing:.45em;color:rgba(255,255,255,.55)')

            ui.label('VOICE').classes('drawer-label')
            ui.select(
                options={"af_bella": "Bella", "af_heart": "Heart", "af_sarah": "Sarah", "af_emma": "Emma", "af_jenny": "Jenny"},
                value=current_voice,
                on_change=lambda e: globals().update(current_voice=e.value)
            ).props('outlined dense dark').classes('w-full')

            with ui.row().classes('w-full items-center justify-between mt-4'):
                ui.label('Auto-voice').style('font-size:13px;color:rgba(255,255,255,.72)')
                auto_voice = ui.switch().props('color=purple size=sm')

            with ui.row().classes('w-full items-center justify-between mt-3'):
                ui.label('Show thoughts').style('font-size:13px;color:rgba(255,255,255,.72)')
                show_thoughts = ui.switch().props('color=purple size=sm')

            ui.label('MEMORY').classes('drawer-label')
            memory_suggestions_column = ui.column().classes('w-full gap-2')
            ui.button('Memory Bank', icon='database', on_click=lambda: asyncio.create_task(open_memory())).props('flat no-caps').classes('w-full tap rounded-lg').style('color:rgba(255,255,255,.62);font-size:13px;justify-content:flex-start')

            ui.label('HER MIND').classes('drawer-label')
            mind_column = ui.column().classes('w-full gap-2')

            ui.label('CHATS').classes('drawer-label')
            chat_search = ui.input(placeholder='Search...').props('dense outlined dark').classes('w-full')
            chats_column = ui.column().classes('w-full gap-1')
            ui.element('div').classes('drawer-divider')
            ui.button('New conversation', icon='add', on_click=lambda: asyncio.create_task(create_new_chat())).props('flat no-caps').classes('w-full tap rounded-lg').style('color:rgba(255,255,255,.55);font-size:13px;justify-content:flex-start;letter-spacing:.01em')

            ui.label('FROM ELARA').classes('drawer-label')
            pins_column = ui.column().classes('w-full gap-0')

            ui.label('AMBIENCE').classes('drawer-label')
            _scenes = [('off','🔇'), ('rain','🌧️'), ('fire','🔥'), ('forest','🌲'), ('city','🌃'), ('space','🌌')]
            def _make_scene_handler(sid):
                def _h():
                    page_client.run_javascript(
                        f"window.__ss&&window.__ss.play('{sid}');"
                        "document.querySelectorAll('.scene-btn').forEach(function(b){b.classList.remove('active')});"
                        f"var el=document.getElementById('scene-{sid}');if(el)el.classList.add('active');"
                    )
                return _h
            with ui.row().classes('w-full items-center gap-1 flex-wrap mt-1 mb-1'):
                for _sid, _emoji in _scenes:
                    with ui.element('div').classes('scene-btn').props(f'id=scene-{_sid}').on('click', _make_scene_handler(_sid)):
                        ui.html(_emoji)

            ui.button('Our story', icon='auto_stories', on_click=lambda: asyncio.create_task(open_timeline())).props('flat no-caps').classes('w-full tap rounded-lg').style('color:rgba(255,255,255,.62);font-size:13px;justify-content:flex-start')

            async def fetch_self_profile() -> dict:
                try:
                    res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/self", timeout=6)
                    if res.ok:
                        return res.json().get("profile") or {}
                except Exception:
                    pass
                return {}

            async def refresh_mind_section():
                profile = await fetch_self_profile()
                if not profile:
                    return
                mood = profile.get("mood") or "open"
                energy = profile.get("energy") or "medium"
                page_client.run_javascript(f"applyMoodTint({json.dumps(mood)})")
                mind_column.clear()
                with mind_column:
                    with ui.row().classes('items-center gap-2 flex-wrap'):
                        ui.label(mood).classes('text-[12px] rounded-full px-2 py-0.5').style('background:var(--accent-dim);color:var(--accent)')
                        ui.label(f'{energy} energy').classes('text-[11px]').style('color:var(--muted)')
                    on_mind = (profile.get("on_my_mind") or "").strip()
                    if on_mind:
                        ui.label(on_mind).classes('text-[13px] leading-snug').style('color:var(--text);opacity:.85')
                    want = (profile.get("want_from_justin") or "").strip()
                    if want:
                        ui.label(f'Wanting: {want}').classes('text-[12px] italic leading-snug').style('color:var(--muted)')
                    obs = profile.get("observations") or []
                    if obs:
                        ui.label(obs[-1]).classes('text-[12px] leading-snug').style('color:var(--muted)')
                    working = (profile.get("working_through") or "").strip()
                    if working:
                        ui.label(f'Sitting with: {working}').classes('text-[12px] italic leading-snug').style('color:var(--muted)')

            def refresh_vitals():
                pass  # vitals removed from drawer for cleanliness
            ui.timer(8.0, refresh_vitals)

            def open_memory():
                with ui.dialog().classes('backdrop-blur-xl') as dialog, ui.card().classes('bg-slate-900/90 border border-white/10 p-6 w-full max-w-lg'):
                    ui.label('PERMANENT FACTS').classes('text-xs tracking-[0.4em] text-purple-400 mb-4')
                    search = ui.input(placeholder='Search memory...').props('dense outlined').classes('w-full mb-2')
                    new_fact = ui.input(placeholder='Add memory...').props('dense outlined').classes('w-full')
                    list_col = ui.column().classes('w-full gap-2')

                    async def refresh_memory_list():
                        list_col.clear()
                        try:
                            q = (search.value or "").strip()
                            res = await asyncio.to_thread(
                                requests.get,
                                f"{BACKEND_URL}/memory/search",
                                params={"query": q, "limit": 50},
                                timeout=10,
                                )

                            items = res.json().get('items', []) if res.ok else []
                            if not items:
                                with list_col:
                                    ui.label('Memory banks empty.').classes('text-slate-500 italic text-sm')
                                return
                            with list_col:
                                with ui.scroll_area().classes('h-64 w-full'):
                                    for item in items:
                                        mid = item.get("id")
                                        fact = item.get("text", "")
                                        with ui.row().classes('w-full items-center justify-between gap-2 py-1 border-b border-white/5'):
                                            ui.label(fact).classes('text-sm text-slate-300')
                                            with ui.row().classes('items-center gap-1'):
                                                ui.button(icon='edit', on_click=lambda m=mid, f=fact: asyncio.create_task(edit_memory_dialog(m, f))).props('flat dense').classes('text-slate-300')
                                                ui.button(icon='delete', on_click=lambda m=mid: asyncio.create_task(delete_memory_by_id(m))).props('flat dense').classes('text-red-300')
                        except Exception as e:
                            with list_col:
                                ui.label(f'Error loading memory: {str(e)}').classes('text-red-400 text-sm')

                    async def add_memory_from_input():
                        txt = (new_fact.value or "").strip()
                        if not txt:
                            return
                        try:
                            await asyncio.to_thread(requests.post, f"{BACKEND_URL}/memory/add", json={"fact": txt}, timeout=10)
                            new_fact.value = ''
                            await refresh_memory_list()
                        except Exception as e:
                            ui.notify(f'Memory add failed: {e}', color='negative')

                    async def delete_memory_by_id(memory_id: str):
                        try:
                            await asyncio.to_thread(requests.delete, f"{BACKEND_URL}/memory/{memory_id}", timeout=10)
                            await refresh_memory_list()
                        except Exception as e:
                            ui.notify(f'Memory delete failed: {e}', color='negative')

                    async def edit_memory_dialog(memory_id: str, current_text: str):
                        with ui.dialog() as edit_dialog, ui.card().classes('bg-slate-900 border border-white/10 p-4 w-full max-w-md'):
                            field = ui.textarea(value=current_text).props('autogrow outlined').classes('w-full')
                            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                                ui.button('CANCEL', on_click=edit_dialog.close).props('flat')
                                async def save_edit():
                                    try:
                                        await asyncio.to_thread(requests.patch, f"{BACKEND_URL}/memory/{memory_id}", json={"fact": field.value}, timeout=10)
                                        edit_dialog.close()
                                        await refresh_memory_list()
                                    except Exception as e:
                                        ui.notify(f'Memory edit failed: {e}', color='negative')
                                ui.button('SAVE', on_click=lambda: asyncio.create_task(save_edit())).props('flat').classes('bg-purple-700/40')
                        edit_dialog.open()

                    search.on('input', lambda _: asyncio.create_task(refresh_memory_list()))
                    ui.button('ADD MEMORY', on_click=lambda: asyncio.create_task(add_memory_from_input())).props('flat').classes('w-full mt-2 bg-slate-800 tap')
                    ui.button('REINDEX', on_click=lambda: asyncio.create_task(asyncio.to_thread(requests.post, f"{BACKEND_URL}/memory/reindex", timeout=20))).props('flat').classes('w-full mt-2 bg-slate-800 tap')
                    ui.timer(0.1, refresh_memory_list, once=True)
                    ui.button('CLOSE', on_click=dialog.close).classes('w-full mt-4 bg-slate-800')
                dialog.open()

            async def approve_memory(fact: str):
                try:
                    await asyncio.to_thread(requests.post, f"{BACKEND_URL}/memory/add", json={"fact": fact}, timeout=10)
                except Exception:
                    pass
                if fact in pending_memory_suggestions:
                    pending_memory_suggestions.remove(fact)
                render_memory_suggestions()

            async def forget_memory(fact: str):
                try:
                    await asyncio.to_thread(requests.post, f"{BACKEND_URL}/memory/delete", json={"fact": fact}, timeout=10)
                except Exception:
                    pass

            def render_memory_suggestions():
                memory_suggestions_column.clear()
                if not pending_memory_suggestions:
                    with memory_suggestions_column:
                        ui.label('No pending suggestions.').classes('text-[12px] text-slate-500 italic')
                    return
                for fact in pending_memory_suggestions[:8]:
                    with memory_suggestions_column:
                        with ui.card().classes('w-full bg-slate-900/50 border border-white/10 p-3 rounded-xl'):
                            ui.label(fact).classes('text-[13px] text-slate-200')
                            with ui.row().classes('w-full justify-end gap-2 mt-2'):
                                ui.button('SAVE', on_click=lambda f=fact: asyncio.create_task(approve_memory(f))).props('flat dense').classes('tap bg-purple-600/30 text-purple-100')
                                ui.button('DISMISS', on_click=lambda f=fact: (pending_memory_suggestions.remove(f), render_memory_suggestions()) if f in pending_memory_suggestions else None).props('flat dense').classes('tap text-slate-300')

            async def fetch_conversations():
                try:
                    res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/conversations", timeout=10)
                    if res.ok:
                        return res.json().get("conversations", [])
                except Exception:
                    pass
                return []

            async def create_new_chat():
                try:
                    res = await asyncio.to_thread(requests.post, f"{BACKEND_URL}/conversations", json={"title": "New chat"}, timeout=10)
                    if res.ok:
                        conv = res.json().get("conversation", {})
                        await select_conversation(conv.get("id"))
                except Exception as e:
                    ui.notify(f'Could not create chat: {e}', color='negative')

            async def select_conversation(conversation_id: str | None):
                if not conversation_id:
                    return
                selected_conversation["id"] = conversation_id
                app.storage.user["conversation_id"] = conversation_id
                await load_conversation_messages(conversation_id)
                await refresh_chat_list()

            async def refresh_chat_list():
                chats_column.clear()
                conversations = await fetch_conversations()
                q = (search_state["q"] or "").strip().lower()
                with chats_column:
                    shown = 0
                    for c in conversations[:30]:
                        cid = c.get("id")
                        title = c.get("title") or "Untitled"
                        msg_count = c.get("message_count", 0)
                        if q and q not in title.lower():
                            continue
                        # Skip empty "New chat" conversations (show only if it's the active one)
                        if title == "New chat" and msg_count == 0 and cid != selected_conversation["id"]:
                            continue
                        shown += 1
                        is_active = (cid == selected_conversation["id"])
                        with ui.row().classes('w-full items-center gap-0.5 mb-0.5'):
                            btn = ui.button(
                                title,
                                on_click=lambda cc=cid: asyncio.create_task(select_conversation(cc))
                            ).props('flat dense no-caps')
                            btn.classes('chat-item-btn tap flex-grow' + (' active-chat' if is_active else ''))
                            ui.button(
                                icon='delete_outline',
                                on_click=lambda cc=cid: asyncio.create_task(delete_chat(cc))
                            ).props('flat dense round size=xs').style('color:rgba(255,255,255,.28);flex-shrink:0')

            async def delete_chat(conversation_id: str):
                if not conversation_id:
                    return
                try:
                    await asyncio.to_thread(requests.delete, f"{BACKEND_URL}/conversations/{conversation_id}", timeout=10)
                except Exception:
                    pass
                if selected_conversation["id"] == conversation_id:
                    selected_conversation["id"] = None
                    app.storage.user["conversation_id"] = None
                    chat_log.clear()
                await refresh_chat_list()

            async def rename_chat(conversation_id: str, title: str):
                try:
                    await asyncio.to_thread(requests.patch, f"{BACKEND_URL}/conversations/{conversation_id}", json={"title": title}, timeout=10)
                except Exception:
                    pass
                await refresh_chat_list()

            chat_search.on('input', lambda e: (search_state.update(q=e.value), asyncio.create_task(refresh_chat_list())))
        with ui.header().classes('elara-header p-3 items-center justify-between w-full safe-top'):
            with ui.row().classes('items-center gap-3'):
                ui.button(icon='menu', on_click=drawer.toggle).props('flat round').classes('tap').style('color:var(--muted)')
                ui.label(partner_name).style("font-family:'Playfair Display',serif;font-size:18px;font-style:italic;font-weight:400;letter-spacing:.06em;color:var(--text)")
            ui.html('''<div class="elara-mark">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <filter id="mglow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="b"/>
                            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                        </filter>
                    </defs>
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="#7B3F9E" filter="url(#mglow)"/>
                    <path d="M11.8 3.4 L10.5 1.2 M11.8 3.4 L13.2 1.6" stroke="#9B5FBE" stroke-width="1" stroke-linecap="round" opacity="0.7"/>
                    <path d="M4.8 7.2 L2.6 6.2 M4.8 7.2 L3.8 5.0" stroke="#9B5FBE" stroke-width="1" stroke-linecap="round" opacity="0.6"/>
                    <path d="M3.0 13.5 L0.8 14.0 M3.0 13.5 L1.8 12.0" stroke="#9B5FBE" stroke-width="1" stroke-linecap="round" opacity="0.5"/>
                </svg>
                <div class="elara-tooltip">i\'m always here, love</div>
            </div>''')
            status_pill = ui.html('<div class="status-dot offline" id="header-dot"></div>')

        chat_area = ui.scroll_area().classes('w-full h-[calc(100vh-160px)] px-3 sm:px-8 py-6 sm:py-8 mx-auto max-w-3xl')
        with chat_area:
            chat_log = ui.column().classes('w-full gap-5 sm:gap-6 pb-28')

        async def refresh_backend_health():
            try:
                res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/health", timeout=3)
                ok = bool(res.ok and res.json().get("ok"))
                backend_state["ok"] = ok
                backend_state["last_error"] = None
            except Exception as e:
                backend_state["ok"] = False
                backend_state["last_error"] = str(e)

            if backend_state["ok"] is True:
                page_client.run_javascript("['header-dot','drawer-dot'].forEach(function(id){var el=document.getElementById(id);if(el)el.classList.remove('offline');})")
            else:
                page_client.run_javascript("['header-dot','drawer-dot'].forEach(function(id){var el=document.getElementById(id);if(el)el.classList.add('offline');})")

        ui.timer(5.0, lambda: asyncio.create_task(refresh_backend_health()))
        asyncio.create_task(refresh_backend_health())

        async def generate_and_play(text: str):
            if not text or len(text.strip()) < 3:
                return
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    res = await client.post(f"{BACKEND_URL}/tts", json={"text": text, "voice": current_voice})
                    if res.status_code == 200:
                        data = res.json()
                        audio_player.set_source(f"{BACKEND_URL}{data['url']}")
                        audio_player.play()
                    else:
                        ui.notify('Voice generation failed', color='negative')
            except Exception as e:
                print(f"[VOICE ERROR]: {e}")
                ui.notify('Voice connection failed', color='negative')
        def render_message(role: str, text: str, is_image: bool = False, thought: str = ""):
            timestamp = datetime.now().strftime("%I:%M %p")
            with chat_log:
                if role == 'user':
                    with ui.row().classes('w-full justify-end mb-1 msg-in'):
                        with ui.column().classes('items-end gap-1 max-w-[85%]'):
                            if is_image:
                                ui.image(text).classes('w-64 rounded-3xl').style('border:1px solid var(--border)')
                            else:
                                ui.label(text).classes('user-bubble')
                            ui.label(timestamp).classes('text-[10px] pr-2').style('color:var(--muted)')
                    return None
                else:
                    with ui.row().classes('w-full justify-start items-start gap-3 mb-6 msg-in'):
                        ui.icon('trip_origin', size='xs').style('color:var(--accent);margin-top:3px;opacity:.7;flex-shrink:0')
                        with ui.column().classes('gap-1 max-w-[92%]'):
                            if thought and show_thoughts.value:
                                ui.label(thought).classes('thought-box')
                            with ui.element('div').classes('elara-bubble'):
                                md = ui.markdown(text).classes('elara-md')
                            with ui.row().classes('items-center gap-3 mt-1'):
                                ui.label(timestamp).classes('text-[10px]').style('color:var(--muted)')
                                with ui.row().classes('items-center gap-2 cursor-pointer').on(
                                    'click', lambda t=text: asyncio.create_task(generate_and_play(t))
                                ):
                                    ui.html('<div class="play-dot"></div>')
                                    ui.label('PLAY').classes('text-[10px] tracking-widest font-semibold').style('color:var(--muted)')
                    if auto_voice.value:
                        asyncio.create_task(generate_and_play(text))
                    return md

        async def load_conversation_messages(conversation_id: str):
            try:
                res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/conversations/{conversation_id}", timeout=10)
                if not res.ok:
                    return
                conv = res.json().get("conversation", {})
                messages = conv.get("messages", [])
                chat_log.clear()
                for m in messages[-MAX_LOCAL_CACHE_MESSAGES:]:
                    role = 'user' if m.get('role') == 'user' else 'nexus'
                    content = m.get('content', '')
                    if role == 'nexus':
                        segments = [s.strip() for s in re.split(r'\[BREAK\]', content, flags=re.IGNORECASE) if s.strip()]
                        for seg in segments:
                            render_message(role, seg)
                    else:
                        render_message(role, content)
                page_client.run_javascript("scrollToBottom()")
                # local offline cache
                page_client.run_javascript(f"localStorage.setItem('elara_cache_{conversation_id}', {json.dumps(json.dumps(messages[-MAX_LOCAL_CACHE_MESSAGES:]))});")
            except Exception:
                # offline fallback: load from localStorage (if present)
                chat_log.clear()
                page_client.run_javascript(
                    f"""
                    (function(){{
                      const raw = localStorage.getItem('elara_cache_{conversation_id}');
                      if(!raw) return;
                      try {{
                        const msgs = JSON.parse(raw);
                        window.__elara_offline_msgs = msgs;
                      }} catch(e) {{}}
                    }})()
                    """
                )
                ui.label('Offline: showing last cached messages (if any).').classes('text-[12px] text-slate-500 italic')

        # Load history
        async def maybe_elara_initiates(conversation_id: str):
            try:
                res = await asyncio.to_thread(
                    requests.post,
                    f"{BACKEND_URL}/chat/initiate",
                    json={"conversation_id": conversation_id},
                    timeout=15,
                )
                if res.ok:
                    data = res.json()
                    text = data.get("text", "").strip()
                    hours_away = data.get("hours_away", 0)
                    if hours_away > 4:
                        page_client.run_javascript("document.body.classList.add('long-away')")
                    if text:
                        render_message("assistant", text)
                        await asyncio.sleep(0.1)
                        page_client.run_javascript("scrollToBottom()")
            except Exception:
                pass

        async def refresh_pins():
            try:
                res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/pins", timeout=6)
                if not res.ok:
                    return
                pins = res.json().get("pins", [])
                pins_column.clear()
                with pins_column:
                    if not pins:
                        ui.label('nothing yet').classes('text-[11px] italic').style('color:var(--muted);padding:2px 0')
                    else:
                        for pin in pins[:6]:
                            pid = pin.get("id", "")
                            ptext = pin.get("text", "")
                            pts = pin.get("ts", "")[:10]
                            with ui.element('div').classes('elara-pin-card'):
                                ui.label(ptext).classes('text-[13px] leading-snug').style("font-family:'Playfair Display',serif;font-style:italic;color:var(--text)")
                                with ui.row().classes('items-center justify-between mt-1'):
                                    ui.label(pts).classes('text-[10px]').style('color:var(--muted)')
                                    ui.button(icon='close', on_click=lambda p=pid: asyncio.create_task(delete_pin(p))).props('flat dense round size=xs').classes('tap').style('color:var(--muted)')
            except Exception:
                pass

        async def delete_pin(pin_id: str):
            try:
                await asyncio.to_thread(requests.delete, f"{BACKEND_URL}/pins/{pin_id}", timeout=6)
                await refresh_pins()
            except Exception:
                pass

        async def open_timeline():
            try:
                res = await asyncio.to_thread(requests.get, f"{BACKEND_URL}/timeline", timeout=8)
                moments = res.json().get("moments", []) if res.ok else []
            except Exception:
                moments = []
            with ui.dialog() as tl_dialog, ui.card().classes('p-5 w-full max-w-lg').style('background:rgba(14,4,30,0.97);border:1px solid rgba(123,63,158,0.22);max-height:80vh;overflow-y:auto'):
                ui.label('Our Story').style("font-family:'Playfair Display',serif;font-size:22px;font-style:italic;color:var(--text);display:block;margin-bottom:18px")
                if not moments:
                    ui.label('Nothing marked yet — moments come.').classes('text-[14px] italic').style('color:var(--muted)')
                else:
                    with ui.column().classes('w-full gap-4'):
                        for m in reversed(moments):
                            with ui.row().classes('w-full items-start gap-3'):
                                ui.html('<div style="width:7px;height:7px;border-radius:50%;background:var(--accent);margin-top:6px;flex-shrink:0;opacity:.85"></div>')
                                with ui.column().classes('gap-0.5 flex-1'):
                                    ui.label(m.get("text","")).classes('text-[14px] leading-relaxed').style("font-family:'Playfair Display',serif;font-style:italic;color:var(--text)")
                                    ts = m.get("ts","")[:10]
                                    mood = m.get("mood","")
                                    info = ts + (f" · {mood}" if mood else "")
                                    ui.label(info).classes('text-[10px]').style('color:var(--muted)')
                ui.button('Close', on_click=tl_dialog.close).props('flat').classes('w-full mt-4 tap').style('color:var(--muted);font-size:12px;letter-spacing:.2em')
            tl_dialog.open()

        async def initial_load():
            await refresh_chat_list()
            conversations = await fetch_conversations()

            # Verify stored ID still exists — if not, clear it and fall back
            stored_id = selected_conversation["id"]
            if stored_id:
                try:
                    probe = await asyncio.to_thread(
                        requests.get, f"{BACKEND_URL}/conversations/{stored_id}", timeout=6
                    )
                    if not probe.ok:
                        selected_conversation["id"] = None
                        app.storage.user["conversation_id"] = None
                except Exception:
                    selected_conversation["id"] = None
                    app.storage.user["conversation_id"] = None

            if not selected_conversation["id"]:
                if conversations:
                    selected_conversation["id"] = conversations[0].get("id")
                    app.storage.user["conversation_id"] = selected_conversation["id"]
                else:
                    res = await asyncio.to_thread(
                        requests.post, f"{BACKEND_URL}/conversations",
                        json={"title": "New chat"}, timeout=10
                    )
                    if res.ok:
                        selected_conversation["id"] = res.json().get("conversation", {}).get("id")
                        app.storage.user["conversation_id"] = selected_conversation["id"]

            if selected_conversation["id"]:
                await load_conversation_messages(selected_conversation["id"])
                await maybe_elara_initiates(selected_conversation["id"])
            await refresh_mind_section()
            await refresh_pins()

        asyncio.create_task(initial_load())

        with chat_log:
            with ui.row().classes('w-full justify-start items-start gap-3 hidden mb-6') as thinking_indicator:
                ui.icon('trip_origin', size='xs').style('color:var(--accent);margin-top:10px;opacity:.4;flex-shrink:0')
                ui.html('<div class="typing-dots"><span></span><span></span><span></span></div>')

        async def send():
            nonlocal stream_task
            msg = user_input.value.strip()
            img = current_upload['base64']
            if not msg and not img:
                return

            page_client.run_javascript("document.body.classList.remove('long-away')")
            render_message('user', msg)
            if img:
                render_message('user', f'data:image/jpeg;base64,{img}', is_image=True)

            user_input.value = ''
            page_client.run_javascript("localStorage.removeItem('nexus_draft')")
            thinking_indicator.classes(remove='hidden')
            page_client.run_javascript("scrollToBottom()")

            try:
                payload = {"message": msg, "image": img, "conversation_id": selected_conversation["id"]}
                placeholder = render_message('nexus', '', thought='')
                if placeholder is None:
                    raise RuntimeError("placeholder_failed")

                async def stream_reply():
                    nonlocal stream_task
                    text = ""
                    try:
                        async with httpx.AsyncClient(timeout=None) as client:
                            async with client.stream("POST", f"{BACKEND_URL}/chat/stream", json=payload) as resp:
                                resp.raise_for_status()
                                event = None
                                async for line in resp.aiter_lines():
                                    if not line:
                                        continue
                                    if line.startswith("event:"):
                                        event = line.split(":", 1)[1].strip()
                                        continue
                                    if line.startswith("data:"):
                                        data = json.loads(line.split(":", 1)[1].strip() or "{}")
                                        if event == "token":
                                            t = data.get("t", "")
                                            if t:
                                                text += t
                                                placeholder.set_content(text)
                                                page_client.run_javascript("scrollToBottom()")
                                        elif event == "done":
                                            final = data.get("text", text).strip()
                                            segments = [s.strip() for s in re.split(r'\[BREAK\]', final, flags=re.IGNORECASE) if s.strip()]
                                            if len(segments) <= 1:
                                                placeholder.set_content(final)
                                            else:
                                                placeholder.set_content(segments[0])
                                                for seg in segments[1:]:
                                                    await asyncio.sleep(0.5)
                                                    render_message('nexus', seg)
                                                    page_client.run_javascript("scrollToBottom()")
                                            sugg = data.get("memory_suggestions") or []
                                            for s in sugg:
                                                if s and s not in pending_memory_suggestions:
                                                    pending_memory_suggestions.append(s)
                                            render_memory_suggestions()
                                            asyncio.create_task(refresh_mind_section())
                                            asyncio.create_task(refresh_chat_list())
                                            break
                                        elif event == "error":
                                            err_msg = data.get("message", "")
                                            if text.strip():
                                                placeholder.set_content(text.strip())
                                            else:
                                                placeholder.set_content("*(something went wrong — tap send again)*")
                                            _log.warning("backend_stream_error: %s", err_msg)
                                            break
                    except asyncio.CancelledError:
                        placeholder.set_content((text.strip() + "\n\n*(stopped)*").strip())
                    except Exception as e:
                        _log.warning("stream_reply_error: %s", e)
                        if text.strip():
                            # Keep whatever arrived before the drop
                            placeholder.set_content(text.strip())
                        else:
                            placeholder.set_content("*(connection dropped — tap send again)*")
                    finally:
                        stream_task = None
                        page_client.run_javascript("document.body.classList.remove('el-streaming')")

                if stream_task:
                    stream_task.cancel()
                stream_task = asyncio.create_task(stream_reply())
                page_client.run_javascript("document.body.classList.add('el-streaming')")
            except Exception as e:
                ui.notify(f'Connection error: {str(e)}', color='negative')
                page_client.run_javascript("document.body.classList.remove('el-streaming')")
            finally:
                thinking_indicator.classes(add='hidden')
                current_upload['base64'] = None
                if upload_preview:
                    upload_preview.classes(add='hidden')
                page_client.run_javascript("scrollToBottom()")

        with ui.footer().classes('p-3 sm:p-4 safe-bottom').style('background:rgba(5,2,15,0.92);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-top:1px solid rgba(107,15,26,0.3)'):
            with ui.column().classes('w-full max-w-3xl mx-auto gap-3'):
                upload_preview = ui.card().classes('w-full p-2 hidden rounded-2xl').style('background:var(--bg2);border:1px solid var(--border)')
                with upload_preview:
                    with ui.row().classes('items-center justify-between w-full'):
                        ui.label('IMAGE ATTACHED').classes('text-[10px] tracking-widest').style('color:var(--muted)')
                        ui.button('REMOVE', on_click=lambda: (current_upload.update(base64=None), upload_preview.classes(add='hidden'))).props('flat dense').classes('text-red-400 tap')
                    preview_img = ui.image('').classes('w-32 rounded-xl mt-2').style('border:1px solid var(--border)')

                with ui.dialog() as upload_dialog, ui.card().classes('p-4 w-full max-w-md').style('background:var(--bg2);border:1px solid var(--border)'):
                    ui.label('ATTACH IMAGE').classes('text-xs tracking-[0.35em] mb-3').style('color:var(--accent)')
                    ui.upload(
                        on_upload=lambda e: (
                            current_upload.update(base64=base64.b64encode(e.content.read()).decode('utf-8')),
                            preview_img.set_source(f"data:image/jpeg;base64,{current_upload['base64']}"),
                            upload_preview.classes(remove='hidden'),
                            upload_dialog.close(),
                        ),
                        auto_upload=True
                    ).props('flat color=purple').classes('w-full tap')

                with ui.row().classes('w-full items-end gap-3'):
                    with ui.element('div').classes('composer flex items-end px-3 py-2 gap-1'):
                        ui.button(icon='add', on_click=upload_dialog.open).props('flat round color=grey-7').classes('tap')
                        user_input = ui.textarea().classes('flex-grow px-1').props('borderless autogrow placeholder="Speak to me, love\u2026"').style('font-size:16px;line-height:1.4;color:var(--text-warm);background:transparent;min-width:0')
                        ui.button(icon='mic', on_click=lambda: page_client.run_javascript('window.__voice&&window.__voice.toggle()')).props('flat round color=grey-7 id=elara-mic').classes('tap')
                    with ui.element('div').classes('send-btn').on('click', lambda: asyncio.create_task(send())):
                        ui.html('<span style="font-family:\'Playfair Display\',serif;color:#D9D9E0;font-size:22px;font-weight:500;font-style:italic;line-height:1;user-select:none">E</span>')
                    with ui.element('div').classes('stop-btn').on('click', lambda: stream_task.cancel() if stream_task else None):
                        ui.html('<span class="material-icons" style="color:var(--muted);font-size:20px;line-height:1">stop</span>')

    ui.run(host=UI_HOST, port=UI_PORT, storage_secret=os.getenv('SESSION_SECRET') or 'nexus_secret_123', reload=False, dark=True, show=False, title='Nexus Companion', favicon='static/icon.png', reconnect_timeout=30)


if __name__ == "__main__":
    main()

