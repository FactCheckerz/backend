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
# limits for input media:
MAX_VIDEO_DURATION_MINUTES = int(os.getenv("MAX_VIDEO_DURATION_MINUTES","5"))
MAX_AUDIO_DURATION_MINUTES = int(os.getenv("MAX_AUDIO_DURATION_MINUTES","5"))
MAX_VIDEO_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB","100"))
MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB","50"))
TEMP_MEDIA_DIR = os.getenv("TEMP_MEDIA_DIR","temp_media")
