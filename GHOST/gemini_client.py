"""Ghost Assistant — Gemini Flash 2.0 API Client"""

import logging
from config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT

logger = logging.getLogger("ghost.gemini")

# Global client — lazy initialized
_client = None


def _get_client():
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def get_answer(transcript: str, screen_text: str) -> str:
    """
    Send context to Gemini Flash 2.0 and get an interview answer.

    Args:
        transcript: Rolling 2-minute conversation transcript
        screen_text: OCR-extracted screen content

    Returns:
        Formatted answer string, or empty string on failure
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("Gemini API key not set — skipping Gemini call")
        return ""

    prompt = SYSTEM_PROMPT.format(
        transcript=transcript or "(no transcript available)",
        screen_text=screen_text or "(no screen content captured)",
    )

    try:
        import asyncio

        client = _get_client()

        # Run synchronous API call in a thread
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if response and response.text:
            logger.info("Gemini response received (%d chars)", len(response.text))
            return response.text.strip()
        else:
            logger.warning("Gemini returned empty response")
            return ""

    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return ""
