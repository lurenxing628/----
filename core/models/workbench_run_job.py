"""Run identity and strict durable artifact serialization, separate from plan identity."""

import base64
import math
import re
import secrets
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from core.models.workbench_command import WorkbenchCommandRejected

TERMINAL_STATES = frozenset(("complete", "partial", "failed", "interrupted"))
PROCESS_EXECUTOR_REF = secrets.token_hex(24)


def new_run_ref():
    return secrets.token_hex(24)


def validate_run_ref(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "运行引用无效。", 400)
    return value


def _durable_mapping(value):
    if any(not isinstance(key, (str, int)) for key in value):
        raise TypeError("Candidate artifact keys must be text or integer")
    if len({str(key) for key in value}) != len(value):
        raise ValueError("Candidate artifact keys collide after JSON conversion")
    return {str(key): durable_value(item) for key, item in value.items()}


def _durable_container(value):
    if is_dataclass(value):
        return {item.name: durable_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return _durable_mapping(value)
    if isinstance(value, (list, tuple)):
        return [durable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [durable_value(item) for item in sorted(value)]
    raise TypeError("Unsupported candidate artifact type: " + type(value).__name__)


def durable_value(value: Any) -> Any:
    """Retain every supported artifact field; unsupported objects fail, never stringify."""
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, Enum):
        return durable_value(value.value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Nonfinite candidate artifact")
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"sqlite_blob_base64": base64.b64encode(value).decode("ascii")}
    return _durable_container(value)
