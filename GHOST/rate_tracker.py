"""Ghost Assistant — Rate Limit Tracker + Model Rotation"""

import json
import logging
import time
from pathlib import Path
from config import BASE_DIR

logger = logging.getLogger("ghost.ratelimit")

LIMITS_FILE = BASE_DIR / "limits.json"

# Gemini free tier limits (approximate)
GEMINI_RPM_LIMIT = 15  # requests per minute
GEMINI_RPD_LIMIT = 1500  # requests per day

# Model priority list (tried in order)
MODEL_PRIORITY = [
    "gemini",  # Primary: Gemini Flash (cloud)
    "ollama",  # Fallback: Ollama local
]


class RateTracker:
    """Track API call counts and determine which model to use."""

    def __init__(self):
        self._calls: dict[str, list[float]] = {}  # model -> list of timestamps
        self._errors: dict[str, list[float]] = {}  # model -> list of error timestamps
        self._load()

    def _load(self):
        """Load saved rate data from limits.json."""
        try:
            if LIMITS_FILE.exists():
                data = json.loads(LIMITS_FILE.read_text())
                self._calls = {k: v for k, v in data.get("calls", {}).items()}
                self._errors = {k: v for k, v in data.get("errors", {}).items()}
                self._prune_old()
                logger.info("Rate data loaded: %s", self.summary())
        except Exception as e:
            logger.error("Failed to load rate data: %s", e)

    def _save(self):
        """Persist rate data to limits.json."""
        try:
            self._prune_old()
            LIMITS_FILE.write_text(
                json.dumps(
                    {
                        "calls": self._calls,
                        "errors": self._errors,
                        "updated": time.time(),
                    },
                    indent=2,
                )
            )
        except Exception as e:
            logger.error("Failed to save rate data: %s", e)

    def _prune_old(self):
        """Remove timestamps older than 24 hours."""
        cutoff = time.time() - 86400
        for model in list(self._calls.keys()):
            self._calls[model] = [t for t in self._calls[model] if t > cutoff]
        for model in list(self._errors.keys()):
            self._errors[model] = [t for t in self._errors[model] if t > cutoff]

    def record_call(self, model: str):
        """Record a successful API call."""
        if model not in self._calls:
            self._calls[model] = []
        self._calls[model].append(time.time())
        self._save()

    def record_error(self, model: str):
        """Record a failed API call (likely rate limited)."""
        if model not in self._errors:
            self._errors[model] = []
        self._errors[model].append(time.time())
        self._save()

    def calls_last_minute(self, model: str) -> int:
        """Count calls in the last 60 seconds."""
        cutoff = time.time() - 60
        return sum(1 for t in self._calls.get(model, []) if t > cutoff)

    def calls_today(self, model: str) -> int:
        """Count calls in the last 24 hours."""
        cutoff = time.time() - 86400
        return sum(1 for t in self._calls.get(model, []) if t > cutoff)

    def errors_last_5min(self, model: str) -> int:
        """Count errors in the last 5 minutes."""
        cutoff = time.time() - 300
        return sum(1 for t in self._errors.get(model, []) if t > cutoff)

    def is_rate_limited(self, model: str) -> bool:
        """Check if a model appears to be rate limited."""
        if model == "gemini":
            # Check RPM and RPD limits
            if self.calls_last_minute(model) >= GEMINI_RPM_LIMIT:
                return True
            if self.calls_today(model) >= GEMINI_RPD_LIMIT:
                return True
            # If we had 3+ errors in last 5 min, back off
            if self.errors_last_5min(model) >= 3:
                return True
        elif model == "ollama":
            # If 5+ errors in last 5 min, Ollama is probably down
            if self.errors_last_5min(model) >= 5:
                return True
        return False

    def get_best_model(self) -> str | None:
        """Return the best available model based on rate limits."""
        for model in MODEL_PRIORITY:
            if not self.is_rate_limited(model):
                return model
        # All models rate limited — try Gemini anyway (least bad option)
        logger.warning("All models appear rate limited, trying gemini anyway")
        return "gemini"

    def summary(self) -> dict:
        """Return a summary of current rate status."""
        return {
            model: {
                "calls_1m": self.calls_last_minute(model),
                "calls_24h": self.calls_today(model),
                "errors_5m": self.errors_last_5min(model),
                "rate_limited": self.is_rate_limited(model),
            }
            for model in MODEL_PRIORITY
        }


# Global singleton
tracker = RateTracker()
