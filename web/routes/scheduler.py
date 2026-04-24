"""Scheduler route entrypoint with stable public ``bp`` export."""

from __future__ import annotations

from .domains.scheduler import scheduler_pages as _pages  # noqa: F401
from .domains.scheduler.scheduler_bp import bp

register_scheduler_routes = _pages.register_scheduler_routes
register_scheduler_routes()

__all__ = ["bp", "register_scheduler_routes"]
