import subprocess
import signal
import sys
import time
import os
import socket

brain_proc = None

def _port_in_use(port: int) -> bool:
    """Return True if something is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("0.0.0.0", port)) == 0

def shutdown(sig, frame):
    if brain_proc is not None:
        try:
            brain_proc.terminate()
            brain_proc.wait(timeout=60)
        except Exception:
            try:
                brain_proc.kill()
            except Exception:
                pass
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

BRAIN_PORT = int(os.getenv("BRAIN_PORT", "8001"))

# If another instance of the brain is already running on this port, don't
# start a second one — just exit cleanly.  This prevents the duplicate
# "artifacts/nexus-companion: brain" workflow from racing with
# "Start application" and taking each other down.
if _port_in_use(BRAIN_PORT):
    print(f"🧠 Brain already running on port {BRAIN_PORT} — skipping duplicate start.")
    sys.exit(0)

print("🧠 Awakening the Brain...")
script_dir = os.path.dirname(os.path.abspath(__file__))
brain_path = os.path.join(script_dir, "brain.py")
brain_proc = subprocess.Popen([sys.executable, brain_path], cwd=script_dir)

brain_proc.wait()
