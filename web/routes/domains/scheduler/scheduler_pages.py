from __future__ import annotations

from . import scheduler_route_registrar as _scheduler_route_registrar  # noqa: F401
from .scheduler_bp import bp

register_scheduler_routes = _scheduler_route_registrar.register_scheduler_routes

__all__ = ["bp", "register_scheduler_routes"]
