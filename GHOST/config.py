"""Ghost Assistant — Central Configuration"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

SCREENSHOTS_DIR = BASE_DIR / "screenshots"
HISTORY_DIR = BASE_DIR / "history"
STATIC_DIR = BASE_DIR / "static"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

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

# --- Auto-Trigger Master Switch ---
AUTO_TRIGGER_ENABLED = os.getenv("AUTO_TRIGGER", "false").lower() == "true"

# --- Silence Detection ---
SILENCE_THRESHOLD_SECONDS = (
    4.0  # seconds of silence before considering a question ended
)
# RMS energy below this = silence (0-1 range for 16-bit audio normalized)
# Typical quiet room ~0.005-0.01, normal speech ~0.05-0.15
SILENCE_ENERGY_THRESHOLD = 0.03

# --- Question Detection ---
COOLDOWN_DURATION = 30  # seconds after auto-trigger before next auto-trigger
MIN_TRANSCRIPT_WORDS = 8  # minimum words in last sentence to consider as a question
REQUIRED_KEYWORD_MATCHES = 2  # must match at least this many keyword indicators
QUESTION_KEYWORDS = [
    # Multi-word phrases (higher signal, less ambiguous)
    "tell me",
    "can you",
    "walk me",
    "difference between",
    "when would",
    "have you",
    "do you",
    "could you",
    "would you",
    "what is",
    "what are",
    "how would",
    "how do",
    "how does",
    "why would",
    "why do",
    "why does",
    # Single-word (only counted as secondary signal)
    "explain",
    "implement",
    "design",
    "describe",
    "complexity",
    "optimize",
    "trade-off",
    "trade off",
]

# --- OCR / Screenshots ---
SCREENSHOT_INTERVAL = 10  # seconds between screenshots
MAX_SCREEN_SNAPSHOTS = 5  # rolling buffer size
MAX_HISTORY_ENTRIES = 50  # max saved answers in history/

# --- AI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "false").lower() == "true"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava:7b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- User Context ---
CONTEXT_FILE = BASE_DIR / "context.txt"


def _load_user_context() -> str:
    """Load user context from context.txt if it exists."""
    if CONTEXT_FILE.exists():
        text = CONTEXT_FILE.read_text().strip()
        if text:
            return text
    return ""


USER_CONTEXT = _load_user_context()


def reload_user_context() -> str:
    """Reload user context from context.txt (called by hot-reload endpoint)."""
    global USER_CONTEXT
    USER_CONTEXT = _load_user_context()
    return USER_CONTEXT


# --- Gemini Prompt ---
SYSTEM_PROMPT = """You are a hidden teleprompter for a candidate in a live technical interview.
The candidate is reading your output in real-time on a small overlay — they need EXACT WORDS TO SAY.

RULES:
- Give the actual words to speak, not suggestions or options
- 1-3 sentences for verbal answers — concise, confident, natural-sounding
- If it's a coding question, give the code solution with a brief verbal explanation
- No preamble ("You could say...", "A good answer would be...") — just the answer itself
- Sound like a senior engineer who knows their stuff
- If you detect a follow-up, build on the previous context

{user_context}CONVERSATION (last 2 minutes):
{transcript}

SCREEN CONTENT (OCR):
{screen_text}

Detect what's being asked and give the answer to say NOW:"""


# --- Ghost State ---
class GhostState:
    PASSIVE = "passive"
    GENERATING = "generating"
    ANSWERING = "answering"
    COOLDOWN = "cooldown"
    ERROR = "error"
