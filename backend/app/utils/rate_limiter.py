"""
Module: rate_limiter.py
Purpose: Pacing delay and exponential backoff retry for Gemini API 429 quota protection.
Standards: Rule 3 (Low Code & High Accuracy), Rule 5 (Production Reliability).
"""
import re
import time
import logging
from typing import Any, Callable

logger = logging.getLogger("rate_limiter")

class RateLimiter:
    """Controls request frequency and manages exponential backoff for AI calls."""

    def __init__(self, min_interval_seconds: float = 2.5, max_retries: int = 3):
        self.min_interval = min_interval_seconds
        self.max_retries = max_retries
        self.last_call_time = 0.0

    def pace(self) -> None:
        """Enforces spacing between calls to stay below the 15 RPM free tier limit."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_call_time = time.time()

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Executes a function with rate-limit pacing and automatic exponential backoff.
        Backoff is capped at MAX_BACKOFF_CAP seconds to prevent indefinite stalls.
        """
        self.pace()
        retries = 0
        backoff = 10.0
        MAX_BACKOFF_CAP = 60.0  # Never sleep more than 60s — prevents indefinite stalls

        while True:
            try:
                result = func(*args, **kwargs)
                self.last_call_time = time.time()
                return result
            except Exception as exc:
                err_str = str(exc).lower()
                is_rate_limited = (
                    "429" in err_str
                    or "resourceexhausted" in err_str
                    or "quota" in err_str
                    or "503" in err_str
                    or "unavailable" in err_str
                    or "high demand" in err_str
                )
                
                if is_rate_limited and retries < self.max_retries:
                    retries += 1
                    
                    # Intelligently extract recommended retry delay if provided by Google API
                    retry_match = re.search(r"retry in ([\d\.]+)s", err_str)
                    delay_match = re.search(r"seconds:\s*(\d+)", err_str)
                    
                    if retry_match:
                        sleep_duration = min(float(retry_match.group(1)) + 2.0, MAX_BACKOFF_CAP)
                    elif delay_match:
                        sleep_duration = min(float(delay_match.group(1)) + 2.0, MAX_BACKOFF_CAP)
                    else:
                        sleep_duration = min(backoff, MAX_BACKOFF_CAP)
                        backoff *= 2.0

                    logger.warning(
                        f"[RATE LIMIT] Gemini quota reached. Sleeping {sleep_duration:.1f}s "
                        f"(Attempt {retries}/{self.max_retries})..."
                    )
                    time.sleep(sleep_duration)
                else:
                    raise exc

# Global rate limiter instance for AI calls
ai_limiter = RateLimiter(min_interval_seconds=2.5, max_retries=3)

def execute_with_rate_limit(func: Callable, *args, **kwargs) -> Any:
    """Convenience helper to run an AI function through the global rate limiter."""
    return ai_limiter.execute(func, *args, **kwargs)
