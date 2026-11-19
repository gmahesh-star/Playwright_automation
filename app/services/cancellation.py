"""Cooperative cancellation flags for test runs.

Redis is the cross-process channel (API -> ARQ worker). The in-memory set
covers the no-Redis fallback where the run executes in the API process.
"""

from __future__ import annotations

import uuid
from typing import Any

_cancelled: set[str] = set()


def _key(run_id: uuid.UUID | str) -> str:
    return f"run:{run_id}:cancel"


async def request_cancel(
    run_id: uuid.UUID | str, redis: Any | None = None
) -> None:
    """Mark a run for cancellation."""
    rid = str(run_id)
    _cancelled.add(rid)
    if redis is not None:
        try:
            await redis.set(_key(rid), "1", ex=3600)
        except Exception:
            pass


async def is_cancelled(run_id: uuid.UUID | str, redis: Any | None = None) -> bool:
    """Return True if cancellation was requested for the run."""
    rid = str(run_id)
    if rid in _cancelled:
        return True
    if redis is not None:
        try:
            return bool(await redis.exists(_key(rid)))
        except Exception:
            pass
    return False


async def clear_cancel(run_id: uuid.UUID | str, redis: Any | None = None) -> None:
    """Clear a cancellation flag once the run has stopped."""
    rid = str(run_id)
    _cancelled.discard(rid)
    if redis is not None:
        try:
            await redis.delete(_key(rid))
        except Exception:
            pass
