"""Ghost Assistant — Central Configuration"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

SCREENSHOTS_DIR = BASE_DIR / "screenshots"
STATIC_DIR = BASE_DIR / "static"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# --- Server ---
HOST = "127.0.0.1"
PORT = 7777

# --- Audio / Whisper ---
WHISPER_MODEL = "tiny.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
# Rolling transcript buffer duration in seconds
TRANSCRIPT_BUFFER_DURATION = 120  # 2 minutes
# Chunk duration for processing (seconds)
AUDIO_CHUNK_DURATION = 3

# --- Silence Detection ---
SILENCE_THRESHOLD_SECONDS = 2.5
# RMS energy below this = silence (0-1 range for 16-bit audio normalized)
SILENCE_ENERGY_THRESHOLD = 0.01

# --- Question Detection ---
COOLDOWN_DURATION = 15  # seconds after auto-trigger before next auto-trigger
QUESTION_KEYWORDS = [
    "how",
    "why",
    "what",
    "explain",
    "implement",
    "design",
    "tell me",
    "can you",
    "walk me",
    "describe",
    "difference between",
    "when would",
    "have you",
    "do you",
    "could you",
    "would you",
    "what is",
    "what are",
    "complexity",
    "optimize",
    "approach",
    "trade-off",
    "trade off",
]

# --- OCR / Screenshots ---
SCREENSHOT_INTERVAL = 10  # seconds between screenshots
MAX_SCREEN_SNAPSHOTS = 5  # rolling buffer size

# --- AI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "false").lower() == "true"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava:7b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- Gemini Prompt ---
SYSTEM_PROMPT = """You are a hidden AI assistant helping during a technical interview.
The user cannot type long messages — give concise, directly usable answers.

CONTEXT:
- Last 2 minutes of conversation transcript:
  {transcript}

- Current screen content (OCR extracted):
  {screen_text}

Based on the conversation and screen content, what is the most likely
technical question being asked of the user right now, and what is the
best answer they should give?

Format your response exactly like this:
**Question detected:** <what you think was asked>
**Answer:** <direct, confident, complete answer>
**Tip:** <one quick extra tip if relevant, otherwise omit this line>

Keep the answer concise but complete. If it's a coding question,
include a short code snippet."""


# --- Ghost State ---
class GhostState:
    PASSIVE = "passive"
    GENERATING = "generating"
    ANSWERING = "answering"
    COOLDOWN = "cooldown"
    ERROR = "error"
