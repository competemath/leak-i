"""Load the embedding model without ever depending on the Hub being up at start.

2026-10-13 21:17 UTC: huggingface.co answered 429 (rate limit), then 500 (internal error) to every request for minutes; server.py asked the Hub for
`all-MiniLM-L6-v2` at start, ran out of its five retries and exited, and the Space ended in RUNTIME_ERROR until someone restarted it by hand.

The model is baked into the image (Dockerfile), so the first attempt is the local cache only. Only when that is empty do we go to the network, and
then with a patient back-off (the Hub's outages last minutes, not seconds) before giving up.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def load(constructor, name: str, attempts: int = 8, first_delay: float = 5.0, max_delay: float = 120.0, sleep=time.sleep):
    """constructor(name, local_files_only=True) from the local cache; failing that constructor(name) up to `attempts` times, waiting
    first_delay, 2x, 4x … (capped at max_delay) between tries. The last error is raised when every try failed."""
    try:
        return constructor(name, local_files_only=True)
    except Exception as e:  # noqa: BLE001 (any failure to read the cache means: go to the network)
        logger.warning("%s is not in the local cache (%s: %s): fetching it, patiently", name, type(e).__name__, str(e)[:120])
    delay = first_delay
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return constructor(name)
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("fetching %s failed (attempt %d/%d): %s: %s", name, attempt, attempts, type(e).__name__, str(e)[:120])
            if attempt < attempts:
                sleep(delay)
                delay = min(delay * 2, max_delay)
    raise RuntimeError(f"could not load {name} from the cache or the Hub after {attempts} attempts") from last
