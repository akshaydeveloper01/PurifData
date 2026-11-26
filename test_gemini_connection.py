
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not API_KEY:
    print("Gemini API key not found.")
    raise SystemExit

client = genai.Client(api_key=API_KEY)

try:
    print("\nPurifData - Interactions API Test")
    print("-----------------------------------")
    print("Model:", MODEL)

    print("\nSending test request...")

    interaction = client.interactions.create(
        model=MODEL,
        input="Explain data cleaning in three simple sentences."
    )

    result = interaction.output_text

    if result:
        print("\nGemini Response")
        print("-----------------------------------")
        print(result)
        print("\nInteractions API test successful.")
    else:
        print("Gemini returned an empty response.")

except Exception as error:
    print("\nInteractions API test failed:")
    print(error)

finally:
    client.close()
