"""Ghost Assistant — Screenshot + OCR Worker"""

import asyncio
import logging
import time
from collections import deque
from pathlib import Path

from config import SCREENSHOTS_DIR, SCREENSHOT_INTERVAL, MAX_SCREEN_SNAPSHOTS

logger = logging.getLogger("ghost.ocr")


class OCRWorker:
    """Captures screenshots via grim and extracts text via Tesseract."""

    def __init__(self):
        self._screen_buffer: deque[tuple[float, str]] = deque(
            maxlen=MAX_SCREEN_SNAPSHOTS
        )
        self._running = False
        self._lock = asyncio.Lock()

    def get_screen_text(self) -> str:
        """Get combined screen text from the rolling buffer."""
        if not self._screen_buffer:
            return ""
        # Return the most recent snapshot (most relevant)
        # Plus a separator for context from older ones
        texts = []
        for i, (ts, text) in enumerate(reversed(list(self._screen_buffer))):
            if i == 0:
                texts.append(f"[Current screen]\n{text}")
            else:
                texts.append(f"[{int(time.time() - ts)}s ago]\n{text}")
        return "\n\n".join(texts)

    def get_latest_screen_text(self) -> str:
        """Get only the most recent screen text."""
        if not self._screen_buffer:
            return ""
        return self._screen_buffer[-1][1]

    async def start(self):
        """Start the screenshot + OCR loop."""
        self._running = True
        logger.info("OCRWorker starting...")
        asyncio.create_task(self._ocr_loop())

    async def _ocr_loop(self):
        """Main loop: screenshot every N seconds, OCR each."""
        # Small delay to let the system settle
        await asyncio.sleep(2)

        while self._running:
            try:
                text = await self._capture_and_ocr()
                if text:
                    async with self._lock:
                        self._screen_buffer.append((time.time(), text))
                    logger.debug("OCR captured %d chars", len(text))

                # Clean up old screenshots beyond buffer size
                await self._cleanup_screenshots()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("OCR loop error: %s", e)

            await asyncio.sleep(SCREENSHOT_INTERVAL)

    async def _capture_and_ocr(self) -> str:
        """Take a screenshot with grim and run Tesseract OCR."""
        timestamp = int(time.time())
        screenshot_path = SCREENSHOTS_DIR / f"ghost_{timestamp}.png"

        try:
            # Capture screenshot with grim
            proc = await asyncio.create_subprocess_exec(
                "grim",
                str(screenshot_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode != 0 or not screenshot_path.exists():
                logger.warning("grim failed to capture screenshot")
                return ""

            # Run Tesseract OCR in a thread
            text = await asyncio.to_thread(self._run_tesseract, screenshot_path)
            return text

        except FileNotFoundError:
            logger.error("grim not found — is it installed?")
            return ""
        except Exception as e:
            logger.error("Screenshot/OCR error: %s", e)
            return ""

    def _run_tesseract(self, image_path: Path) -> str:
        """Run Tesseract OCR on an image file."""
        try:
            from PIL import Image
            import pytesseract

            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except ImportError:
            logger.error("pytesseract or Pillow not installed")
            return ""
        except Exception as e:
            logger.error("Tesseract error: %s", e)
            return ""

    async def _cleanup_screenshots(self):
        """Remove old screenshots, keeping only the latest MAX_SCREEN_SNAPSHOTS."""
        try:
            screenshots = sorted(
                SCREENSHOTS_DIR.glob("ghost_*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_file in screenshots[MAX_SCREEN_SNAPSHOTS:]:
                old_file.unlink(missing_ok=True)
        except Exception as e:
            logger.debug("Screenshot cleanup error: %s", e)

    async def stop(self):
        """Stop the OCR loop."""
        self._running = False
        logger.info("OCRWorker stopped.")
