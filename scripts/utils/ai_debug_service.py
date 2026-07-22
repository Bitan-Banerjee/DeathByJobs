import os
import json
import base64
from google import genai
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

api_key = os.getenv("GEMINI_API_KEY")

def analyze_job_failure(job_details, screenshot_path, dom_path):
    """
    Sends application failure evidence to Gemini for structural/behavioral analysis.
    Follows the 'Debugging Philosophy' from GEMINI.md.
    """
    if not api_key:
        return "❌ Gemini API Key missing."

    if not os.path.exists(screenshot_path) or not os.path.exists(dom_path):
        return "❌ Evidence files not found."

    with open(dom_path, 'r', encoding='utf-8') as f:
        dom_content = f.read()[:30000] # Limit DOM size

    with open(screenshot_path, "rb") as f:
        screenshot_data = base64.b64encode(f.read()).decode("utf-8")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert Automation Debugger. 
    TASK: Analyze why a job application failed and provide a fix.
    
    JOB DETAILS:
    {json.dumps(job_details, indent=2)}
    
    EVIDENCE:
    1. Screenshot (attached)
    2. DOM Snapshot (last 30k chars)
    
    DOM CONTENT:
    ```html
    {dom_content}
    ```
    
    OUTPUT REQUIREMENTS (JSON ONLY):
    {{
      "analysis": "Brief explanation of failure",
      "debug_script": "Full standalone python playwright script to reproduce and fix",
      "patch": "A surgical code replacement or patch for the main apply script",
      "verification_logic": "How to verify success in the debug script"
    }}

    DEBUGGING PHILOSOPHY:
    - Target specific selectors found in DOM.
    - Handle unexpected popups/drawers.
    - Ensure native events (click/change) are used.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Use flash for speed
            contents=[
                prompt,
                {'mime_type': 'image/png', 'data': screenshot_data}
            ]
        )
        return response.text
    except Exception as e:
        return f"❌ AI Analysis failed: {str(e)}"

if __name__ == "__main__":
    # Test stub
    pass
