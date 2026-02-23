import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Available Models:")
for m in client.models.list():
    if "gemini" in m.name:
        print(m.name)
