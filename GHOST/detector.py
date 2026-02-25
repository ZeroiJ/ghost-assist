"""Ghost Assistant — Silence + Keyword Question Detector"""

import time
import logging
from config import (
    AUTO_TRIGGER_ENABLED,
    SILENCE_THRESHOLD_SECONDS,
    COOLDOWN_DURATION,
    QUESTION_KEYWORDS,
    MIN_TRANSCRIPT_WORDS,
    REQUIRED_KEYWORD_MATCHES,
)

logger = logging.getLogger("ghost.detector")


class QuestionDetector:
    """Detects when a question has likely been asked based on silence + keywords."""

    def __init__(self):
        self.last_trigger_time: float = 0
        self.cooldown_active: bool = False
        self.enabled: bool = AUTO_TRIGGER_ENABLED

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

    def _count_keyword_matches(self, text: str) -> int:
        """Count how many distinct keywords match in the text."""
        if not text.strip():
            return 0
        text_lower = text.lower()
        return sum(1 for kw in QUESTION_KEYWORDS if kw in text_lower)

    def _has_question_keyword(self, text: str) -> bool:
        """Check if the last sentence has enough keyword matches to be a real question."""
        if not text.strip():
            return False

        # Get the last sentence (split on common sentence endings)
        sentences = text.strip().replace("?", ".").replace("!", ".").split(".")
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return False

        last_sentence = sentences[-1]

        # Require minimum word count — short fragments are likely noise
        word_count = len(last_sentence.split())
        if word_count < MIN_TRANSCRIPT_WORDS:
            return False

        # Require multiple keyword matches to reduce false positives
        matches = self._count_keyword_matches(last_sentence)
        if matches < REQUIRED_KEYWORD_MATCHES:
            return False

        return True

    def should_trigger(self, transcript: str, silence_duration: float) -> bool:
        """
        Check if we should auto-trigger an AI response.

        All conditions must be true:
        1. Auto-trigger is enabled
        2. Not in cooldown
        3. Silence >= threshold (interviewer finished speaking)
        4. Last sentence is long enough and contains enough question keywords

        Returns False during cooldown period.
        """
        # Master switch
        if not self.enabled:
            return False

        # Check cooldown
        if self.in_cooldown:
            return False

        # Condition 1: sufficient silence
        if silence_duration < SILENCE_THRESHOLD_SECONDS:
            return False

        # Condition 2: question keyword detected (with stricter matching)
        if not self._has_question_keyword(transcript):
            return False

        # All conditions met — trigger!
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
