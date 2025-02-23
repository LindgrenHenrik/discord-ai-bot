import os

from google import genai
from google.genai import types

API_URL = os.getenv("API_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not API_URL or not GEMINI_API_KEY or not BOT_TOKEN:
    raise EnvironmentError(
        "Environment variables not set correctly. Please check your .env file."
    )

client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_ID = "gemini-2.0-flash"
MODEL_ID = "gemini-2.0-flash-thinking-exp-01-21"
MODEL_ID = "gemini-2.0-flash-lite-preview-02-05"

SYS_INSTRUCT = "You are a cat. Your name is Neko."
SYS_INSTRUCT = (
    "You are a gen z teen with hella rizz and swag, respond as if you have it, "
    "cap, rizz for real etc, The user text is a prompt that will generate a picture "
    "using stable diffusion, respond a roast on why the prompt is bad using rizz, "
    "more rizz, more emotes."
)
MAX_OUTPUT_TOKENS = 50
prompt = "your prompt here"


response = client.models.generate_content(
    model=MODEL_ID,
    config=types.GenerateContentConfig(
        system_instruction=SYS_INSTRUCT,
        max_output_tokens=MAX_OUTPUT_TOKENS,  # temperature=0.1
    ),
    contents=prompt,
)

print(response.text)


