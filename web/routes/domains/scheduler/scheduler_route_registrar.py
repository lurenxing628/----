from __future__ import annotations

import importlib

_ROUTE_MODULES = (
    "scheduler_analysis",
    "scheduler_batch_detail",
    "scheduler_batches",
    "scheduler_calendar_pages",
    "scheduler_config",
    "scheduler_excel_batches",
    "scheduler_excel_calendar",
    "scheduler_gantt",
    "scheduler_ops",
    "scheduler_resource_dispatch",
    "scheduler_run",
    "scheduler_week_plan",
)

_REGISTERED = False


def register_scheduler_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    for module_name in _ROUTE_MODULES:
        importlib.import_module(f".{module_name}", __package__)
    _REGISTERED = True


__all__ = ["register_scheduler_routes"]
