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

from config import (
    HOST,
    PORT,
    STATIC_DIR,
    GhostState,
    OFFLINE_MODE,
    SCREENSHOTS_DIR,
    HISTORY_DIR,
    MAX_HISTORY_ENTRIES,
    AUTO_TRIGGER_ENABLED,
    SILENCE_THRESHOLD_SECONDS,
    COOLDOWN_DURATION,
)
from detector import QuestionDetector
from whisper_worker import WhisperWorker
from ocr_worker import OCRWorker
import gemini_client
import ollama_client
from rate_tracker import tracker as rate_tracker

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


# --- History Persistence ---
def _save_answer_to_history(entry: dict):
    """Save an answer entry to a JSON file in history/."""
    try:
        filename = f"{entry['id']}.json"
        filepath = HISTORY_DIR / filename
        filepath.write_text(json.dumps(entry, indent=2))

        # Prune old entries if over limit
        history_files = sorted(
            HISTORY_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_file in history_files[MAX_HISTORY_ENTRIES:]:
            old_file.unlink(missing_ok=True)

    except Exception as e:
        logger.error("Failed to save answer to history: %s", e)


def _load_history() -> list[dict]:
    """Load recent answers from history/ on startup."""
    entries = []
    try:
        history_files = sorted(
            HISTORY_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        for filepath in history_files[-MAX_HISTORY_ENTRIES:]:
            try:
                data = json.loads(filepath.read_text())
                entries.append(data)
            except Exception:
                pass
    except Exception as e:
        logger.error("Failed to load history: %s", e)
    return entries


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


# --- AI Answer Generation (Streaming with Rate-Aware Model Selection) ---
async def generate_answer(transcript: str, screen_text: str, source: str = "auto"):
    """Generate an AI answer with streaming — uses rate tracker for model selection."""
    global state
    await broadcast_state(GhostState.GENERATING)

    answer_id = f"{int(time.time() * 1000)}"
    full_answer = []
    got_answer = False
    ai_provider = None

    # Notify UI: a new answer is starting
    await broadcast_event(
        "answer-start",
        {
            "id": answer_id,
            "source": source,
            "timestamp": time.time(),
        },
    )

    # Determine model order based on rate limits
    best_model = rate_tracker.get_best_model() if not OFFLINE_MODE else "ollama"
    models_to_try = [best_model] if best_model == "ollama" else ["gemini", "ollama"]

    for model in models_to_try:
        if got_answer:
            break

        if model == "gemini" and OFFLINE_MODE:
            continue

        try:
            stream = (
                gemini_client.get_answer_stream(transcript, screen_text)
                if model == "gemini"
                else ollama_client.get_answer_stream(transcript, screen_text)
            )

            async for chunk in stream:
                full_answer.append(chunk)
                await broadcast_event(
                    "answer-chunk",
                    {
                        "id": answer_id,
                        "chunk": chunk,
                    },
                )
                got_answer = True

            if got_answer:
                ai_provider = model
                rate_tracker.record_call(model)
            else:
                rate_tracker.record_error(model)

        except Exception as e:
            logger.error("%s streaming failed: %s", model.capitalize(), e)
            rate_tracker.record_error(model)
            if model == "gemini":
                logger.info("Falling back to Ollama...")

    if got_answer:
        complete_text = "".join(full_answer)
        entry = {
            "id": answer_id,
            "answer": complete_text,
            "timestamp": time.time(),
            "source": source,
            "ai": ai_provider,
        }
        answers.append(entry)
        _save_answer_to_history(entry)

        # Notify UI: answer is complete
        await broadcast_event(
            "answer-done",
            {
                "id": answer_id,
                "answer": complete_text,
                "ai": ai_provider,
            },
        )
        await broadcast_state(GhostState.ANSWERING)
        logger.info(
            "Answer streamed via %s (%s, %d chars)",
            ai_provider,
            source,
            len(complete_text),
        )
    else:
        await broadcast_event(
            "answer-done",
            {
                "id": answer_id,
                "error": "No AI response available",
            },
        )
        await broadcast_event("error", {"message": "No AI response available"})
        await broadcast_state(GhostState.ERROR)
        logger.warning("No answer generated from any source")

    # Return to passive after a brief display period
    await asyncio.sleep(2)
    await broadcast_state(GhostState.PASSIVE)


# --- Auto-Trigger Loop ---
async def auto_trigger_loop():
    """Continuously check if a question was detected and auto-trigger."""
    if not detector.enabled:
        logger.info("Auto-trigger DISABLED (set AUTO_TRIGGER=true in .env to enable)")
        return

    logger.info(
        "Auto-trigger loop started (silence=%.1fs, cooldown=%ds).",
        SILENCE_THRESHOLD_SECONDS,
        COOLDOWN_DURATION,
    )
    while True:
        try:
            # Re-check in case toggled at runtime
            if not detector.enabled:
                await asyncio.sleep(2)
                continue

            transcript = whisper.get_transcript()
            silence = whisper.get_silence_duration()

            if detector.should_trigger(transcript, silence):
                screen_text = ocr.get_screen_text()
                logger.info("Auto-trigger! Generating answer...")
                await generate_answer(transcript, screen_text, source="auto")

        except Exception as e:
            logger.error("Auto-trigger loop error: %s", e)

        await asyncio.sleep(1.0)  # Check every 1s instead of 0.5s


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background workers."""
    logger.info("Ghost daemon starting up...")

    # Load answer history from previous sessions
    loaded = _load_history()
    if loaded:
        answers.extend(loaded)
        logger.info("Loaded %d answers from history", len(loaded))

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
    from config import USER_CONTEXT

    return JSONResponse(
        {
            "state": state,
            "auto_trigger": detector.enabled,
            "transcript_length": len(whisper.get_transcript()),
            "silence_duration": round(whisper.get_silence_duration(), 1),
            "cooldown_active": detector.in_cooldown,
            "cooldown_remaining": round(detector.cooldown_remaining, 1),
            "screen_snapshots": len(ocr._screen_buffer),
            "answers_count": len(answers),
            "user_context_length": len(USER_CONTEXT),
            "rate_limits": rate_tracker.summary(),
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


@app.post("/toggle-auto-trigger")
async def toggle_auto_trigger():
    """Toggle auto-trigger on/off at runtime."""
    detector.enabled = not detector.enabled
    status = "enabled" if detector.enabled else "disabled"
    logger.info("Auto-trigger %s via API", status)
    return JSONResponse({"auto_trigger": status})


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


# --- Screen Analysis ---
async def take_screenshot() -> str | None:
    """Take a fresh screenshot with grim, return the path."""
    timestamp = int(time.time())
    screenshot_path = SCREENSHOTS_DIR / f"analyze_{timestamp}.png"
    try:
        proc = await asyncio.create_subprocess_exec(
            "grim",
            str(screenshot_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0 or not screenshot_path.exists():
            logger.error("grim failed to capture screenshot for analysis")
            return None
        return str(screenshot_path)
    except FileNotFoundError:
        logger.error("grim not found — is it installed?")
        return None
    except Exception as e:
        logger.error("Screenshot capture error: %s", e)
        return None


async def generate_vision_answer(screenshot_path: str, source: str = "screen"):
    """Generate a vision-based AI answer — streams chunks via SSE."""
    global state
    await broadcast_state(GhostState.GENERATING)

    answer_id = f"{int(time.time() * 1000)}"
    full_answer = []
    got_answer = False

    await broadcast_event(
        "answer-start",
        {
            "id": answer_id,
            "source": source,
            "timestamp": time.time(),
        },
    )

    try:
        async for chunk in gemini_client.get_vision_answer_stream(screenshot_path):
            full_answer.append(chunk)
            await broadcast_event(
                "answer-chunk",
                {
                    "id": answer_id,
                    "chunk": chunk,
                },
            )
            got_answer = True
    except Exception as e:
        logger.error("Vision analysis failed: %s", e)

    if got_answer:
        complete_text = "".join(full_answer)
        entry = {
            "id": answer_id,
            "answer": complete_text,
            "timestamp": time.time(),
            "source": source,
            "ai": "gemini-vision",
        }
        answers.append(entry)
        _save_answer_to_history(entry)

        await broadcast_event(
            "answer-done",
            {
                "id": answer_id,
                "answer": complete_text,
                "ai": "gemini-vision",
            },
        )
        await broadcast_state(GhostState.ANSWERING)
        logger.info("Vision answer streamed (%d chars)", len(complete_text))
    else:
        await broadcast_event(
            "answer-done",
            {
                "id": answer_id,
                "error": "Vision analysis failed — no response from Gemini",
            },
        )
        await broadcast_event("error", {"message": "Vision analysis failed"})
        await broadcast_state(GhostState.ERROR)

    # Clean up the analysis screenshot
    try:
        from pathlib import Path

        Path(screenshot_path).unlink(missing_ok=True)
    except Exception:
        pass

    await asyncio.sleep(2)
    await broadcast_state(GhostState.PASSIVE)


@app.post("/analyze-screen")
async def analyze_screen():
    """Take a screenshot NOW and analyze it with Gemini Vision.
    Called by Super+Shift+A keybind or Ctrl+Enter in overlay.
    """
    if OFFLINE_MODE:
        return JSONResponse(
            {"error": "Screen analysis requires Gemini (online mode)"},
            status_code=503,
        )

    screenshot_path = await take_screenshot()
    if not screenshot_path:
        return JSONResponse(
            {"error": "Failed to capture screenshot"},
            status_code=500,
        )

    # Run in background so we respond immediately
    asyncio.create_task(generate_vision_answer(screenshot_path, source="screen"))

    return JSONResponse({"status": "analyzing"})


@app.post("/reload-context")
async def reload_context():
    """Hot-reload context.txt without restarting the daemon."""
    from config import reload_user_context, CONTEXT_FILE

    new_context = reload_user_context()

    # Also update the imported reference in gemini_client and ollama_client
    import gemini_client as gc
    import ollama_client as oc

    gc.USER_CONTEXT = new_context
    oc.USER_CONTEXT = new_context

    logger.info("User context reloaded (%d chars)", len(new_context))

    return JSONResponse(
        {
            "status": "reloaded",
            "context_length": len(new_context),
            "context_file": str(CONTEXT_FILE),
            "preview": new_context[:200] + "..."
            if len(new_context) > 200
            else new_context,
        }
    )


@app.get("/history")
async def get_history(limit: int = 20):
    """Return recent answer history (persisted across restarts)."""
    recent = answers[-limit:]
    return JSONResponse(
        {
            "total": len(answers),
            "returned": len(recent),
            "answers": recent,
        }
    )


@app.get("/stream")
async def sse_stream():
    """SSE endpoint for the overlay UI to receive real-time updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_clients.append(queue)

    async def event_generator():
        try:
            # Send current state on connect
            yield f"data: {json.dumps({'type': 'state', 'state': state})}\n\n"

            # Send recent complete answers (for reconnection)
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
