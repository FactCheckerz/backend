import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    "whisper-large-v3-turbo"
)
GROQ_LLM = os.getenv(
    "GROQ_LLM",
    "llama-3.3-70b-versatile"
)
