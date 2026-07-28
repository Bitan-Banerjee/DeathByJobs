import os
from dotenv import load_dotenv
from google import genai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Available Gemini Models & Token Limits:")
print(f"{'MODEL NAME':<40} | {'MAX INPUT TOKENS':<18} | {'MAX OUTPUT TOKENS'}")
print("-" * 85)
for model in client.models.list():
    name = model.name.replace('models/', '')
    in_limit = getattr(model, 'input_token_limit', 'Unknown')
    out_limit = getattr(model, 'output_token_limit', 'Unknown')
    print(f"{name:<40} | {str(in_limit):<18} | {str(out_limit)}")