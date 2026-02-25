"""Ghost Assistant — Silence + Keyword Question Detector"""

import time
import logging
from config import (
    SILENCE_THRESHOLD_SECONDS,
    COOLDOWN_DURATION,
    QUESTION_KEYWORDS,
)

logger = logging.getLogger("ghost.detector")


class QuestionDetector:
    """Detects when a question has likely been asked based on silence + keywords."""

    def __init__(self):
        self.last_trigger_time: float = 0
        self.cooldown_active: bool = False

    @property
    def in_cooldown(self) -> bool:
        """Check if we're still in cooldown from last trigger."""
        if time.time() - self.last_trigger_time < COOLDOWN_DURATION:
            return True
        self.cooldown_active = False
        return False

    @property
    def cooldown_remaining(self) -> float:
        """Seconds remaining in cooldown."""
        remaining = COOLDOWN_DURATION - (time.time() - self.last_trigger_time)
        return max(0, remaining)

    def _has_question_keyword(self, text: str) -> bool:
        """Check if the last sentence contains a question keyword."""
        if not text.strip():
            return False

        # Get the last sentence (split on common sentence endings)
        sentences = text.strip().replace("?", ".").replace("!", ".").split(".")
        # Filter out empty strings
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return False

        last_sentence = sentences[-1].lower()
        return any(kw in last_sentence for kw in QUESTION_KEYWORDS)

    def should_trigger(self, transcript: str, silence_duration: float) -> bool:
        """
        Check if we should auto-trigger an AI response.

        Both conditions must be true:
        1. Silence >= threshold (interviewer finished speaking)
        2. Last sentence contains a question keyword

        Returns False during cooldown period.
        """
        # Check cooldown
        if self.in_cooldown:
            return False

        # Condition 1: sufficient silence
        if silence_duration < SILENCE_THRESHOLD_SECONDS:
            return False

        # Condition 2: question keyword detected
        if not self._has_question_keyword(transcript):
            return False

        # Both conditions met — trigger!
        self.last_trigger_time = time.time()
        self.cooldown_active = True
        logger.info(
            "Auto-trigger fired (silence=%.1fs, keyword detected in transcript)",
            silence_duration,
        )
        return True

    def force_trigger(self) -> None:
        """Mark a manual trigger (does NOT check cooldown — always works)."""
        self.last_trigger_time = time.time()
        self.cooldown_active = True
        logger.info("Manual trigger fired (Super+Shift+H)")

    def reset(self) -> None:
        """Reset detector state."""
        self.last_trigger_time = 0
        self.cooldown_active = False
