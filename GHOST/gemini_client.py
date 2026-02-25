"""Ghost Assistant — Gemini Flash API Client (text + vision)"""

import logging
from pathlib import Path
from typing import AsyncGenerator
from config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_PROMPT, USER_CONTEXT

logger = logging.getLogger("ghost.gemini")

# --- Vision prompt for on-demand screen analysis ---
VISION_PROMPT = """You are a hidden teleprompter for a candidate in a live technical interview.
You are looking at exactly what the candidate sees on their screen RIGHT NOW.

{user_context}RULES:
- Identify what is being asked (coding problem, system design, terminal output, etc.)
- Give the COMPLETE ANSWER — exact code, exact words to say, or exact steps
- If it's a coding problem: give the full solution with time/space complexity
- If it's a system design diagram: describe the architecture answer
- If it's a terminal/error: give the fix
- No preamble — just the answer itself
- Be thorough — the candidate needs everything to respond confidently"""

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
    Non-streaming version (kept for backward compat).
    """
    result = []
    async for chunk in get_answer_stream(transcript, screen_text):
        result.append(chunk)
    return "".join(result)


async def get_answer_stream(
    transcript: str, screen_text: str
) -> AsyncGenerator[str, None]:
    """
    Stream an answer from Gemini Flash 2.0, yielding text chunks as they arrive.

    Args:
        transcript: Rolling 2-minute conversation transcript
        screen_text: OCR-extracted screen content

    Yields:
        Text chunks as they stream from the API
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("Gemini API key not set — skipping Gemini call")
        return

    prompt = SYSTEM_PROMPT.format(
        transcript=transcript or "(no transcript available)",
        screen_text=screen_text or "(no screen content captured)",
        user_context=f"ABOUT THE CANDIDATE:\n{USER_CONTEXT}\n\n"
        if USER_CONTEXT
        else "",
    )

    try:
        import asyncio

        client = _get_client()

        # generate_content_stream is synchronous, run in thread and iterate
        response = await asyncio.to_thread(
            client.models.generate_content_stream,
            model=GEMINI_MODEL,
            contents=prompt,
        )

        chunk_count = 0
        for chunk in response:
            if chunk.text:
                chunk_count += 1
                yield chunk.text

        if chunk_count == 0:
            logger.warning("Gemini stream returned no chunks")
        else:
            logger.info("Gemini stream complete (%d chunks)", chunk_count)

    except Exception as e:
        logger.error("Gemini API error: %s", e)


async def get_vision_answer_stream(
    image_path: str | Path,
) -> AsyncGenerator[str, None]:
    """
    Send a screenshot image to Gemini Vision and stream the answer.

    Args:
        image_path: Path to a PNG screenshot file

    Yields:
        Text chunks as they stream from the API
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("Gemini API key not set — skipping vision call")
        return

    image_path = Path(image_path)
    if not image_path.exists():
        logger.error("Screenshot not found: %s", image_path)
        return

    prompt = VISION_PROMPT.format(
        user_context=f"ABOUT THE CANDIDATE:\n{USER_CONTEXT}\n\n"
        if USER_CONTEXT
        else "",
    )

    try:
        import asyncio
        from PIL import Image

        client = _get_client()

        # Open the screenshot as a PIL Image (SDK accepts PIL.Image directly)
        img = await asyncio.to_thread(Image.open, image_path)

        # Send image + prompt to Gemini Vision (streaming)
        response = await asyncio.to_thread(
            client.models.generate_content_stream,
            model=GEMINI_MODEL,
            contents=[img, prompt],
        )

        chunk_count = 0
        for chunk in response:
            if chunk.text:
                chunk_count += 1
                yield chunk.text

        if chunk_count == 0:
            logger.warning("Gemini vision stream returned no chunks")
        else:
            logger.info("Gemini vision stream complete (%d chunks)", chunk_count)

    except Exception as e:
        logger.error("Gemini Vision API error: %s", e)
