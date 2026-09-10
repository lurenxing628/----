"""Typed private snapshot facts; these representations are never public DTOs."""

import math
from datetime import date, datetime


def plain_plan_facts(value):
    """Retain SQLite value types without stringifying unsupported objects."""
    if isinstance(value, dict):
        return {key: plain_plan_facts(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain_plan_facts(item) for item in value]
    if isinstance(value, (date, datetime)):
        return {"storage_type": type(value).__name__, "iso": value.isoformat()}
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("Unsupported private plan fact type: " + type(value).__name__)
