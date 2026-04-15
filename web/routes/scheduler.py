"""Scheduler route entrypoint with stable public ``bp`` export."""

from __future__ import annotations

# Import the domain aggregator for route registration side effects.
from .domains.scheduler import scheduler_pages as _pages  # noqa: F401
from .domains.scheduler.scheduler_bp import bp

__all__ = ["bp"]
