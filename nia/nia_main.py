import subprocess
import signal
import sys
import os
import socket

nia_proc = None

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("0.0.0.0", port)) == 0

def shutdown(sig, frame):
    if nia_proc is not None:
        try:
            nia_proc.terminate()
            nia_proc.wait(timeout=60)
        except Exception:
            try:
                nia_proc.kill()
            except Exception:
                pass
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

NIA_PORT = int(os.getenv("NIA_PORT", "8002"))

if _port_in_use(NIA_PORT):
    print(f"🧞 Nia already running on port {NIA_PORT} — skipping duplicate start.")
    sys.exit(0)

print("🧞 Awakening Nia...")
script_dir = os.path.dirname(os.path.abspath(__file__))
nia_path = os.path.join(script_dir, "nia/nia_brain.py")
nia_proc = subprocess.Popen([sys.executable, nia_path], cwd=script_dir)

nia_proc.wait()
