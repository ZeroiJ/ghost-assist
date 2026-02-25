"""Ghost Assistant — Ollama Local Fallback Client"""

import json
import logging
from typing import AsyncGenerator
import httpx
from config import OLLAMA_HOST, OLLAMA_MODEL, SYSTEM_PROMPT, USER_CONTEXT

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
    Stream an answer from Ollama, yielding text chunks as they arrive.

    Args:
        transcript: Rolling 2-minute conversation transcript
        screen_text: OCR-extracted screen content

    Yields:
        Text chunks as they stream from Ollama
    """
    prompt = SYSTEM_PROMPT.format(
        transcript=transcript or "(no transcript available)",
        screen_text=screen_text or "(no screen content captured)",
        user_context=f"ABOUT THE CANDIDATE:\n{USER_CONTEXT}\n\n"
        if USER_CONTEXT
        else "",
    )

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1024,
                    },
                },
            ) as resp:
                if resp.status_code != 200:
                    logger.error("Ollama HTTP %d", resp.status_code)
                    return

                chunk_count = 0
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            chunk_count += 1
                            yield token
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

                if chunk_count == 0:
                    logger.warning("Ollama stream returned no chunks")
                else:
                    logger.info("Ollama stream complete (%d chunks)", chunk_count)

    except httpx.TimeoutException:
        logger.error("Ollama request timed out (90s)")
    except Exception as e:
        logger.error("Ollama error: %s", e)
