"""Ghost Assistant — FastAPI Daemon

The central server that ties together all workers:
- Whisper audio transcription
- OCR screen capture
- Silence + keyword question detection
- Gemini / Ollama AI answer generation
- SSE streaming to overlay UI
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import HOST, PORT, STATIC_DIR, GhostState, OFFLINE_MODE
from detector import QuestionDetector
from whisper_worker import WhisperWorker
from ocr_worker import OCRWorker
import gemini_client
import ollama_client

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ghost.daemon")

# --- Global State ---
whisper = WhisperWorker()
ocr = OCRWorker()
detector = QuestionDetector()

state = GhostState.PASSIVE
answers: list[dict] = []  # Answer history for this session
sse_clients: list[asyncio.Queue] = []  # Connected SSE clients


# --- SSE Broadcasting ---
async def broadcast_event(event_type: str, data: dict):
    """Send an event to all connected SSE clients."""
    payload = json.dumps({"type": event_type, **data})
    dead = []
    for q in sse_clients:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        sse_clients.remove(q)


async def broadcast_state(new_state: str):
    """Update and broadcast the current ghost state."""
    global state
    state = new_state
    await broadcast_event("state", {"state": new_state})


# --- AI Answer Generation ---
async def generate_answer(transcript: str, screen_text: str, source: str = "auto"):
    """Generate an AI answer using Gemini (primary) or Ollama (fallback)."""
    global state
    await broadcast_state(GhostState.GENERATING)

    answer = ""

    # Try Gemini first (unless offline mode)
    if not OFFLINE_MODE:
        try:
            answer = await gemini_client.get_answer(transcript, screen_text)
        except Exception as e:
            logger.error("Gemini failed: %s", e)

    # Fallback to Ollama
    if not answer:
        logger.info("Falling back to Ollama...")
        try:
            answer = await ollama_client.get_answer(transcript, screen_text)
        except Exception as e:
            logger.error("Ollama also failed: %s", e)

    if answer:
        entry = {
            "answer": answer,
            "timestamp": time.time(),
            "source": source,
            "ai": "ollama" if (OFFLINE_MODE or not answer) else "gemini",
        }
        answers.append(entry)
        await broadcast_event("answer", entry)
        await broadcast_state(GhostState.ANSWERING)
        logger.info("Answer generated via %s (%s)", entry["ai"], source)
    else:
        await broadcast_event("error", {"message": "No AI response available"})
        await broadcast_state(GhostState.ERROR)
        logger.warning("No answer generated from any source")

    # Return to passive after a brief display period
    await asyncio.sleep(2)
    await broadcast_state(GhostState.PASSIVE)


# --- Auto-Trigger Loop ---
async def auto_trigger_loop():
    """Continuously check if a question was detected and auto-trigger."""
    logger.info("Auto-trigger loop started.")
    while True:
        try:
            transcript = whisper.get_transcript()
            silence = whisper.get_silence_duration()

            if detector.should_trigger(transcript, silence):
                screen_text = ocr.get_screen_text()
                logger.info("Auto-trigger! Generating answer...")
                await generate_answer(transcript, screen_text, source="auto")

        except Exception as e:
            logger.error("Auto-trigger loop error: %s", e)

        await asyncio.sleep(0.5)


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background workers."""
    logger.info("Ghost daemon starting up...")

    # Start workers
    await whisper.start()
    await ocr.start()

    # Start auto-trigger loop
    trigger_task = asyncio.create_task(auto_trigger_loop())

    await broadcast_state(GhostState.PASSIVE)
    logger.info("Ghost daemon ready on http://%s:%d", HOST, PORT)

    yield

    # Shutdown
    logger.info("Ghost daemon shutting down...")
    trigger_task.cancel()
    await whisper.stop()
    await ocr.stop()


# --- FastAPI App ---
app = FastAPI(title="Ghost Assistant", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def serve_overlay():
    """Serve the overlay UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>Ghost overlay not found</h1>", status_code=404)


@app.get("/status")
async def get_status():
    """Return current ghost status (used by Waybar module)."""
    return JSONResponse(
        {
            "state": state,
            "transcript_length": len(whisper.get_transcript()),
            "silence_duration": round(whisper.get_silence_duration(), 1),
            "cooldown_active": detector.in_cooldown,
            "cooldown_remaining": round(detector.cooldown_remaining, 1),
            "screen_snapshots": len(ocr._screen_buffer),
            "answers_count": len(answers),
        }
    )


@app.post("/trigger")
async def force_trigger():
    """Force-trigger an AI answer (called by Super+Shift+H keybind)."""
    detector.force_trigger()
    transcript = whisper.get_transcript()
    screen_text = ocr.get_screen_text()

    # Run in background so we respond immediately
    asyncio.create_task(generate_answer(transcript, screen_text, source="manual"))

    return JSONResponse({"status": "triggered"})


@app.post("/ask")
async def manual_ask(request: Request):
    """Handle a manual question typed in the overlay."""
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "No question provided"}, status_code=400)

    # Prepend the manual question to the transcript context
    transcript = whisper.get_transcript()
    full_context = f"{transcript}\n\n[User manually asks: {question}]"
    screen_text = ocr.get_screen_text()

    asyncio.create_task(generate_answer(full_context, screen_text, source="manual"))

    return JSONResponse({"status": "processing"})


@app.get("/stream")
async def sse_stream():
    """SSE endpoint for the overlay UI to receive real-time updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    sse_clients.append(queue)

    async def event_generator():
        try:
            # Send current state on connect
            yield f"data: {json.dumps({'type': 'state', 'state': state})}\n\n"

            # Send recent answers
            for entry in answers[-5:]:
                yield f"data: {json.dumps({'type': 'answer', **entry})}\n\n"

            # Stream new events
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            if queue in sse_clients:
                sse_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Mount static files (CSS, JS) — after routes so /static/* doesn't shadow them
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "daemon:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False,
    )
