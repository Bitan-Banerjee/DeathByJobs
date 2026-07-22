import os
import signal
import sys
import subprocess

# --- PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_FILE = os.path.join(BASE_DIR, "app.lock")
PIPELINE_SCRIPT_NAME = "scripts/main.py"

def find_pids_by_script_name(script_name):
    """Finds PIDs of processes running a specific script using pgrep."""
    pids = []
    try:
        # Use pgrep -f to match against the full command line.
        # This is more reliable than ps aux | grep.
        result = subprocess.run(['pgrep', '-f', script_name], capture_output=True, text=True, check=False)
        if result.stdout:
            pids = [int(p) for p in result.stdout.strip().split('\n')]
    except FileNotFoundError:
        print("   - `pgrep` not found. This is unusual for a Unix-like system. Cannot scan processes.", file=sys.stderr)
        return []
        
    # Exclude the current process to prevent the script from killing itself
    my_pid = os.getpid()
    return [pid for pid in pids if pid != my_pid]

def kill_active_pipeline():
    """
    Finds and terminates the active pipeline process, first via lock file, then by scanning system processes.
    """
    lock_file_found = os.path.exists(LOCK_FILE)

    if lock_file_found:
        print("INFO: Lock file found. Attempting to terminate process via PID.")
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            
            os.kill(pid, signal.SIGTERM)
            print(f"✅ Successfully sent termination signal to pipeline process (PID: {pid}).")
            # The lock file is the most reliable source, so we can exit successfully.
            return
        except (ValueError, IOError) as e:
            print(f"⚠️ Could not read PID from lock file: {e}. It may be corrupt.")
        except ProcessLookupError:
            print(f"🤔 Process with PID from lock file not found. The lock file is stale.")
            os.remove(LOCK_FILE)
            print("   - Removed stale lock file.")
        except Exception as e:
            print(f"❌ An error occurred while trying to kill process from lock file: {e}")

    # --- Fallback: Scan system processes if lock file method fails or is absent ---
    print("\nINFO: Searching system for active pipeline processes...")
    if not lock_file_found:
        print("      (Lock file method skipped as app.lock was not found)")
    else:
        print("      (Lock file method failed, now using system scan as fallback)")

    pids_to_kill = find_pids_by_script_name(PIPELINE_SCRIPT_NAME)
    
    if not pids_to_kill:
        print("✅ No running pipeline process found on the system.")
        return

    killed_count = 0
    for pid in pids_to_kill:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✅ Successfully sent termination signal to pipeline process (PID: {pid}).")
            killed_count += 1
        except ProcessLookupError:
            # This can happen in a race condition if the process ended between find and kill
            pass
        except Exception as e:
            print(f"❌ An error occurred while trying to kill process {pid}: {e}")
            
    if killed_count == 0:
        print("✅ No running pipeline process found on the system.")
    else:
        print(f"\n🎉 Terminated {killed_count} pipeline process(es).")

if __name__ == "__main__":
    kill_active_pipeline()
