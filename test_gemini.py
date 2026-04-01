from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

key = os.getenv("GEMINI_API_KEYS", "").split(",")[0].strip() or os.getenv("GEMINI_API_KEY", "").strip()
print("Usando key:", key[:6], "...")

client = genai.Client(api_key=key)

resp = client.models.generate_content(
    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    contents="Responda apenas com a palavra OK.",
    config=types.GenerateContentConfig(max_output_tokens=5),
)
print("Resposta:", resp.text)