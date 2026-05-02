"""Scheduler route entrypoint with stable public ``bp`` export."""

from __future__ import annotations

from .domains.scheduler.scheduler_bp import bp
from .domains.scheduler.scheduler_route_registrar import register_scheduler_routes

__all__ = ["bp", "register_scheduler_routes"]
