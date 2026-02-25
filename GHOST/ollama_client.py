"""Ghost Assistant — Ollama Local Fallback Client"""

import logging
import httpx
from config import OLLAMA_HOST, OLLAMA_MODEL, SYSTEM_PROMPT

logger = logging.getLogger("ghost.ollama")


async def is_available() -> bool:
    """Check if Ollama server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def get_answer(transcript: str, screen_text: str) -> str:
    """
    Send context to local Ollama model and get an interview answer.

    Args:
        transcript: Rolling 2-minute conversation transcript
        screen_text: OCR-extracted screen content

    Returns:
        Formatted answer string, or empty string on failure
    """
    prompt = SYSTEM_PROMPT.format(
        transcript=transcript or "(no transcript available)",
        screen_text=screen_text or "(no screen content captured)",
    )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1024,
                    },
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("response", "").strip()
                if answer:
                    logger.info("Ollama response received (%d chars)", len(answer))
                    return answer
                logger.warning("Ollama returned empty response")
                return ""
            else:
                logger.error("Ollama HTTP %d: %s", resp.status_code, resp.text[:200])
                return ""

    except httpx.TimeoutException:
        logger.error("Ollama request timed out (60s)")
        return ""
    except Exception as e:
        logger.error("Ollama error: %s", e)
        return ""
