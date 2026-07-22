import os
import subprocess
import json
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')

def run_debug_script(script_content, company_name):
    """Save and run the AI-generated debug script."""
    safe_name = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
    debug_path = os.path.join(SCRIPTS_DIR, 'debug', f"debug_{safe_name}.py")
    os.makedirs(os.path.dirname(debug_path), exist_ok=True)
    
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"    🧪 Running debug script: {debug_path}...")
    try:
        result = subprocess.run([sys.executable, debug_path], capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print("    ✅ Debug script SUCCEEDED.")
            return True, result.stdout
        else:
            print(f"    ❌ Debug script FAILED: {result.stderr[:200]}")
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def apply_patch(target_file, patch_content):
    """
    Very basic patch applier. In real world, Gemini should provide 
    instructions for the 'replace' tool or a standard diff.
    """
    # For now, we log it. Full automated file editing via scripts is risky 
    # without a robust diff engine. We'll use Gemini CLI's 'replace' style 
    # but triggered via the orchestrator.
    print(f"    🛠️ Patch generated for {target_file}. Integration pending verification loop.")
    # Implementation of automated apply_patch involves logic to find/replace 
    # code blocks in the apply scripts.
    return True

if __name__ == "__main__":
    pass
