import os
import re
import sys
import csv
import json
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- PATH SETUP ---
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BRIDGE_DIR)
sys.path.append(os.path.join(BASE_DIR, "scripts"))

app = FastAPI(title="AI Job Pipeline API")

# Serve UI
UI_DIR = os.path.join(BRIDGE_DIR, "ui")
if os.path.exists(UI_DIR):
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

active_process = None

# ── Models ────────────────────────────────────────────────────────────────────

class PipelineParams(BaseModel):
    jobs: int = 25
    target: int = 50
    max_loops: int = 4
    mode: str = "quota"  # "quota" | "single_test" | "resume"

class CronUpdate(BaseModel):
    job_id: int          # index in the managed cron list
    enabled: bool | None = None
    hour: int | None = None
    minute: int | None = None

# ── Helpers ───────────────────────────────────────────────────────────────────

MANAGED_MARKER = "# AI_PIPELINE_MANAGED"

def _read_crontab() -> list[str]:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()

def _write_crontab(lines: list[str]):
    content = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)

def _get_managed_jobs() -> list[dict]:
    lines = _read_crontab()
    jobs = []
    for i, line in enumerate(lines):
        if MANAGED_MARKER in line:
            stripped = line.lstrip("#").strip()
            enabled = not line.strip().startswith("#")
            # parse cron expression
            parts = stripped.split()
            minute, hour = parts[0], parts[1]
            label = "Main Pipeline" if "main.py" in line and "naukri_update" not in line else "Naukri Resume Upload"
            jobs.append({
                "id": len(jobs),
                "line_index": i,
                "enabled": enabled,
                "minute": minute,
                "hour": hour,
                "label": label,
                "raw": line,
            })
    return jobs

def get_process_status():
    if active_process is None:
        return "idle"
    if active_process.poll() is None:
        return "running"
    return "finished"

# ── Pipeline endpoints ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "AI Pipeline API running. UI not found."}

@app.get("/status")
async def status():
    return {"status": get_process_status(), "pid": active_process.pid if active_process else None}

@app.post("/start")
async def start_pipeline(params: PipelineParams):
    global active_process
    if get_process_status() == "running":
        raise HTTPException(status_code=400, detail="Pipeline already running.")

    cmd = [sys.executable, "-u", "scripts/main.py"]
    if params.mode == "quota":
        cmd.extend(["--target", str(params.target), "--max-loops", str(params.max_loops), "--jobs", str(params.jobs)])
    elif params.mode == "single_test":
        cmd.extend(["--jobs", str(params.jobs), "--max-loops", "1"])
    elif params.mode == "resume":
        cmd.append("--resume")

    log_path = os.path.join(BASE_DIR, "logs", "api_run.log")
    active_process = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=open(log_path, "w"), stderr=subprocess.STDOUT)
    return {"status": "started", "pid": active_process.pid}

@app.post("/stop")
async def stop_pipeline():
    global active_process
    if active_process and active_process.poll() is None:
        active_process.terminate()
        active_process.wait()
        active_process = None
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active pipeline to stop.")

@app.get("/logs")
async def get_logs(lines: int = 100):
    log_path = os.path.join(BASE_DIR, "logs", "api_run.log")
    if not os.path.exists(log_path):
        return {"lines": []}
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}

# ── Report endpoint ───────────────────────────────────────────────────────────

@app.get("/report")
async def get_report():
    data = {
        "linkedin": {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
        "naukri":   {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
    }

    # Scraped counts from intermediate JSON (only present mid-run)
    for platform in ["linkedin", "naukri"]:
        p = os.path.join(BASE_DIR, "data", f"{platform}_jobs.json")
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                data[platform]["scraped"] = len(d) if isinstance(d, list) else len(d.get("jobs", []))
            except: pass

        m = os.path.join(BASE_DIR, "data", f"{platform}_matched_jobs.json")
        if os.path.exists(m):
            try:
                d = json.load(open(m))
                jobs = d.get("approved_jobs", [])
                data[platform]["matched"] = len(jobs)
            except: pass

    # Applied + failed from tracker CSV (source of truth)
    tracker = os.path.join(BASE_DIR, "Job_Applications_Tracker.csv")
    if os.path.exists(tracker):
        try:
            with open(tracker, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url    = row.get("Job URL", "")
                    status = row.get("Status", "")
                    platform = "linkedin" if "linkedin.com" in url else "naukri" if "naukri.com" in url else None
                    if not platform:
                        continue
                    if "Applied" in status:
                        data[platform]["applied"] += 1
                    elif "Failed" in status or "failed" in status:
                        data[platform]["failed"] += 1
        except: pass

    # Failed from quarantine file
    failed_path = os.path.join(BASE_DIR, "data", "failed_applications.json")
    if os.path.exists(failed_path):
        try:
            fj = json.load(open(failed_path)).get("failed_jobs", [])
            for job in fj:
                url = job.get("url", "")
                platform = "linkedin" if "linkedin.com" in url else "naukri" if "naukri.com" in url else None
                if platform:
                    data[platform]["failed"] += 1
        except: pass

    # Consolidated
    combined = {k: data["linkedin"][k] + data["naukri"][k] for k in ["scraped", "matched", "applied", "failed"]}
    return {"linkedin": data["linkedin"], "naukri": data["naukri"], "combined": combined}

# ── Cron endpoints ────────────────────────────────────────────────────────────

@app.get("/cron")
async def list_cron_jobs():
    return {"jobs": _get_managed_jobs()}

@app.patch("/cron")
async def update_cron_job(update: CronUpdate):
    lines = _read_crontab()
    jobs = _get_managed_jobs()

    if update.job_id >= len(jobs):
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[update.job_id]
    idx = job["line_index"]
    raw = lines[idx]

    # Strip leading comment chars to get the base cron line
    base = raw.lstrip("#").strip()
    parts = base.split(None, 5)  # min hour dom mon dow cmd...

    # Update time if provided
    if update.minute is not None:
        parts[0] = str(update.minute)
    if update.hour is not None:
        parts[1] = str(update.hour)

    new_base = " ".join(parts)

    # Apply enabled/disabled
    enabled = update.enabled if update.enabled is not None else job["enabled"]
    lines[idx] = new_base if enabled else f"# {new_base}"

    _write_crontab(lines)
    return {"status": "updated", "job": _get_managed_jobs()[update.job_id]}
