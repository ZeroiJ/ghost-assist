"""Ghost Assistant — Audio Capture + Whisper Transcription Worker"""

from __future__ import annotations

import asyncio
import logging
import struct
import tempfile
import time
from collections import deque
from pathlib import Path
from typing import Any

from config import (
    AUDIO_CHUNK_DURATION,
    AUDIO_SAMPLE_RATE,
    AUDIO_CHANNELS,
    SILENCE_ENERGY_THRESHOLD,
    TRANSCRIPT_BUFFER_DURATION,
    WHISPER_MODEL,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
)

logger = logging.getLogger("ghost.whisper")


class WhisperWorker:
    """Captures audio via PipeWire and transcribes with faster-whisper."""

    def __init__(self):
        self._transcript_buffer: deque[tuple[float, str]] = deque()
        self._silence_start: float = time.time()
        self._last_voice_time: float = time.time()
        self._model: Any = None
        self._running = False
        self._process: Any = None
        self._lock = asyncio.Lock()

    def _load_model(self):
        """Lazy-load the whisper model."""
        if self._model is None:
            logger.info("Loading faster-whisper model '%s'...", WHISPER_MODEL)
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
            logger.info("Whisper model loaded.")

    def get_transcript(self) -> str:
        """Get the full rolling transcript buffer as a single string."""
        now = time.time()
        # Prune old entries beyond buffer duration
        while (
            self._transcript_buffer
            and now - self._transcript_buffer[0][0] > TRANSCRIPT_BUFFER_DURATION
        ):
            self._transcript_buffer.popleft()
        return " ".join(text for _, text in self._transcript_buffer)

    def get_silence_duration(self) -> float:
        """Get how long silence has been ongoing (seconds)."""
        return time.time() - self._last_voice_time

    def _compute_rms(self, audio_bytes: bytes) -> float:
        """Compute RMS energy of raw 16-bit PCM audio."""
        if len(audio_bytes) < 2:
            return 0.0
        n_samples = len(audio_bytes) // 2
        try:
            samples = struct.unpack(f"<{n_samples}h", audio_bytes[: n_samples * 2])
        except struct.error:
            return 0.0
        if not samples:
            return 0.0
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        # Normalize to 0-1 range (16-bit audio max = 32768)
        return rms / 32768.0

    def _transcribe_chunk(self, audio_path: str) -> str:
        """Transcribe an audio file with faster-whisper."""
        self._load_model()
        try:
            segments, _info = self._model.transcribe(
                audio_path,
                beam_size=1,
                language="en",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )
            text = " ".join(seg.text.strip() for seg in segments)
            return text.strip()
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return ""

    async def start(self):
        """Start the audio capture and transcription loop."""
        self._running = True
        logger.info("WhisperWorker starting...")

        # Ensure PipeWire ghost sink exists
        await self._setup_pipewire_sink()

        # Run the capture loop in background
        asyncio.create_task(self._capture_loop())

    async def _setup_pipewire_sink(self):
        """Set up the PipeWire virtual sink for combined audio capture."""
        try:
            # Check if ghost_sink already exists
            result = await asyncio.create_subprocess_exec(
                "pactl",
                "list",
                "short",
                "sinks",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            if b"ghost_sink" in stdout:
                logger.info("PipeWire ghost_sink already exists.")
                return

            # Create null sink
            await asyncio.create_subprocess_exec(
                "pactl",
                "load-module",
                "module-null-sink",
                "sink_name=ghost_sink",
                "sink_properties=device.description=GhostSink",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Loopback system audio into it
            await asyncio.create_subprocess_exec(
                "pactl",
                "load-module",
                "module-loopback",
                "source=ghost_sink.monitor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            logger.info("PipeWire ghost_sink created with loopback.")
        except Exception as e:
            logger.warning("Could not set up PipeWire sink: %s", e)
            logger.warning("Audio capture will use default source instead.")

    async def _capture_loop(self):
        """Main loop: capture audio chunks via pw-record, transcribe each."""
        logger.info("Audio capture loop started.")

        while self._running:
            try:
                # Record a chunk to a temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                # Use pw-record to capture audio
                # Try ghost_sink.monitor first, fall back to default
                record_cmd = [
                    "pw-record",
                    f"--rate={AUDIO_SAMPLE_RATE}",
                    f"--channels={AUDIO_CHANNELS}",
                    "--format=s16",
                    tmp_path,
                ]

                # Check if ghost_sink exists for target
                try:
                    check = await asyncio.create_subprocess_exec(
                        "pactl",
                        "list",
                        "short",
                        "sinks",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await check.communicate()
                    if b"ghost_sink" in stdout:
                        record_cmd.insert(1, "--target=ghost_sink.monitor")
                except Exception:
                    pass

                self._process = await asyncio.create_subprocess_exec(
                    *record_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Record for AUDIO_CHUNK_DURATION seconds
                await asyncio.sleep(AUDIO_CHUNK_DURATION)

                # Stop recording
                if self._process and self._process.returncode is None:
                    self._process.terminate()
                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        self._process.kill()

                # Check if file has audio data
                tmp_file = Path(tmp_path)
                if not tmp_file.exists() or tmp_file.stat().st_size < 100:
                    tmp_file.unlink(missing_ok=True)
                    continue

                # Read raw audio for RMS check
                try:
                    raw_bytes = tmp_file.read_bytes()
                    # Skip WAV header (44 bytes)
                    audio_data = raw_bytes[44:] if len(raw_bytes) > 44 else raw_bytes
                    rms = self._compute_rms(audio_data)
                except Exception:
                    rms = 0.0

                # Update silence tracking
                if rms > SILENCE_ENERGY_THRESHOLD:
                    self._last_voice_time = time.time()

                # Transcribe in a thread to not block
                text = await asyncio.to_thread(self._transcribe_chunk, tmp_path)

                # Clean up temp file
                tmp_file.unlink(missing_ok=True)

                # Add to buffer if we got text
                if text:
                    async with self._lock:
                        self._transcript_buffer.append((time.time(), text))
                    logger.debug("Transcribed: %s", text[:80])

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Capture loop error: %s", e)
                await asyncio.sleep(1)

    async def stop(self):
        """Stop the audio capture."""
        self._running = False
        if self._process and self._process.returncode is None:
            self._process.terminate()
        logger.info("WhisperWorker stopped.")
