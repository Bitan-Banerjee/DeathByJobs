#!/usr/bin/env python3
import os, sys, time, signal, threading, traceback

PROJECT_ROOT = "/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation"
LOG_FILE     = os.path.join(PROJECT_ROOT, "logs", "app_launch.log")
PORT         = 8000
URL          = f"http://127.0.0.1:{PORT}"

os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
sys.path.insert(0, PROJECT_ROOT)

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
    print(msg)

# Clear log on fresh launch
open(LOG_FILE, "w").close()
log("=== app.py started ===")
log(f"PROJECT_ROOT: {PROJECT_ROOT}")
log(f"cwd: {os.getcwd()}")

# Kill anything on the port
import subprocess
result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
for pid in result.stdout.strip().splitlines():
    try:
        os.kill(int(pid), signal.SIGKILL)
        log(f"Killed stale PID {pid} on port {PORT}")
    except: pass
time.sleep(0.5)

# Start server
log("Starting uvicorn...")
try:
    import uvicorn
    def run_server():
        try:
            uvicorn.run("bridge.main:app", host="127.0.0.1", port=PORT, log_level="warning")
        except Exception as e:
            log(f"uvicorn error: {e}\n{traceback.format_exc()}")
    threading.Thread(target=run_server, daemon=True).start()
except Exception as e:
    log(f"Failed to start server: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# Wait for server
import urllib.request
server_up = False
for i in range(40):
    time.sleep(0.5)
    try:
        urllib.request.urlopen(URL + "/status")
        log(f"Server ready after {(i+1)*0.5:.1f}s")
        server_up = True
        break
    except Exception as e:
        log(f"  [{(i+1)*0.5:.1f}s] waiting... ({e})")

if not server_up:
    log("ERROR: Server never came up")
    sys.exit(1)

# Open webview
log("Opening webview...")
try:
    import webview
    window = webview.create_window("AiAutomation", URL, width=1100, height=780, min_size=(800, 600))
    window.events.closed += lambda: os.kill(os.getpid(), signal.SIGTERM)
    log("webview.start() called")
    webview.start()
except Exception as e:
    log(f"webview error: {e}\n{traceback.format_exc()}")
