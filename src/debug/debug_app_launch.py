#!/usr/bin/env python3
"""
Debug script for AiAutomation app blank screen issue.
Follows GEMINI.md: diagnose first, evidence via screenshots, fix->run->evidence cycle.
"""
import os, sys, time, subprocess, traceback

PROJECT_ROOT = "/Users/bitanbanerjee/Coding/GitHub_Repos/AiAutomation"
DEBUG_LOG    = os.path.join(PROJECT_ROOT, "logs", "debug_app_launch.log")
PORT         = 8000

sys.path.insert(0, PROJECT_ROOT)

lines = []
def log(msg):
    print(msg)
    lines.append(msg)

log("=" * 60)
log("DEBUG: AiAutomation App Launch")
log("=" * 60)

# ── 1. Kill anything on port 8000 ────────────────────────────────────────────
log("\n[1] Clearing port 8000...")
result = subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True, text=True)
pids = result.stdout.strip().splitlines()
if pids:
    for pid in pids:
        os.system(f"kill -9 {pid} 2>/dev/null")
    log(f"    Killed PIDs: {pids}")
else:
    log("    Port was already free.")
time.sleep(0.5)

# ── 2. Try importing bridge ───────────────────────────────────────────────────
log("\n[2] Testing bridge import...")
try:
    from bridge.main import app
    log("    ✅ bridge.main imported OK")
except Exception as e:
    log(f"    ❌ FAILED: {e}")
    traceback.print_exc()

# ── 3. Start uvicorn in background thread ────────────────────────────────────
log("\n[3] Starting uvicorn server...")
import threading, uvicorn

def run_server():
    try:
        uvicorn.run("bridge.main:app", host="127.0.0.1", port=PORT, log_level="info")
    except Exception as e:
        log(f"    ❌ uvicorn crashed: {e}")

t = threading.Thread(target=run_server, daemon=True)
t.start()

# ── 4. Wait and probe server ──────────────────────────────────────────────────
log("\n[4] Waiting for server to respond...")
import urllib.request
server_ok = False
for i in range(20):
    time.sleep(0.5)
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status")
        body = resp.read().decode()
        log(f"    ✅ Server responded after {(i+1)*0.5:.1f}s: {body}")
        server_ok = True
        break
    except Exception as ex:
        log(f"    [{(i+1)*0.5:.1f}s] not ready: {ex}")

if not server_ok:
    log("    ❌ Server never responded. Aborting webview test.")
    with open(DEBUG_LOG, "w") as f: f.write("\n".join(lines))
    sys.exit(1)

# ── 5. Fetch the UI HTML and check it ────────────────────────────────────────
log("\n[5] Fetching UI from server...")
try:
    resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/")
    html = resp.read().decode()
    log(f"    ✅ Got {len(html)} bytes")
    log(f"    Has <div id=root>: {'<div id=\"root\">' in html}")
    log(f"    Has React script:  {'react' in html.lower()}")
    log(f"    Has Babel script:  {'babel' in html.lower()}")
except Exception as e:
    log(f"    ❌ FAILED to fetch UI: {e}")

# ── 6. Open webview and take screenshot ──────────────────────────────────────
log("\n[6] Opening webview window...")
SCREENSHOT = os.path.join(PROJECT_ROOT, "logs", "debug_screenshots", "debug_app_window.png")
os.makedirs(os.path.dirname(SCREENSHOT), exist_ok=True)

try:
    import webview

    def take_screenshot(window):
        time.sleep(3)
        log("    Taking screenshot...")
        try:
            window.take_snapshot(SCREENSHOT)
            log(f"    ✅ Screenshot saved: {SCREENSHOT}")
        except Exception as e:
            log(f"    ⚠️  snapshot API failed ({e}), trying JS eval...")
            try:
                title = window.evaluate_js("document.title")
                body  = window.evaluate_js("document.body ? document.body.innerHTML.substring(0, 300) : 'EMPTY'")
                log(f"    Page title: {title}")
                log(f"    Body preview: {body}")
            except Exception as e2:
                log(f"    ❌ JS eval also failed: {e2}")
        with open(DEBUG_LOG, "w") as f: f.write("\n".join(lines))
        window.destroy()

    window = webview.create_window("DEBUG - AiAutomation", f"http://127.0.0.1:{PORT}", width=1100, height=780)
    webview.start(take_screenshot, window)

except Exception as e:
    log(f"    ❌ webview crashed: {e}")
    traceback.print_exc()

# ── 7. Write log ──────────────────────────────────────────────────────────────
with open(DEBUG_LOG, "w") as f:
    f.write("\n".join(lines))

log(f"\n✅ Debug log written to: {DEBUG_LOG}")
