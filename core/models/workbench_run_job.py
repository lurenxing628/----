"""Run identity and strict durable artifact serialization, separate from plan identity."""

import math
from datetime import date, datetime
from enum import Enum
from typing import Any, NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_system import is_maintenance_job_ref
from core.shared.refs import is_ref, new_ref
from core.shared.strict_json import load_strict_json

PROCESS_EXECUTOR_REF = new_ref()


def validate_run_ref(value):
    if not is_ref(value):
        raise WorkbenchCommandRejected("invalid_input", "这次排产的编号无效，请回到排产记录重新选择。", 400)
    return value


def _not_data_context() -> NoReturn:
    raise ValueError("Data context reference is not strict JSON")


def valid_data_context_ref(value):
    """The recorded restore-source content that RunDataContext.ref produces."""
    if type(value) is not str:
        return False
    try:
        data = load_strict_json(value, on_malformed=_not_data_context)
    except ValueError:
        return False
    return (type(data) is dict and set(data) == {"database_scope", "successful_restores"}
            and type(data["database_scope"]) is str and bool(data["database_scope"])
            and type(data["successful_restores"]) is list
            and all(is_maintenance_job_ref(ref) for ref in data["successful_restores"])
            and data["successful_restores"] == sorted(set(data["successful_restores"])))


def _durable_mapping(value):
    if any(not isinstance(key, (str, int)) for key in value):
        raise TypeError("Candidate artifact keys must be text or integer")
    if len({str(key) for key in value}) != len(value):
        raise ValueError("Candidate artifact keys collide after JSON conversion")
    return {str(key): durable_value(item) for key, item in value.items()}


def _durable_container(value):
    if isinstance(value, dict):
        return _durable_mapping(value)
    if isinstance(value, (list, tuple)):
        return [durable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [durable_value(item) for item in sorted(value)]
    raise TypeError("Unsupported candidate artifact type: " + type(value).__name__)


def durable_value(value: Any) -> Any:
    """Retain every supported artifact value; unsupported objects fail, never stringify.

    A dataclass is unsupported: its owner serializes it first (a key table such as facts/candidate_artifact,
    or its ``to_dict``).
    """
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
    return _durable_container(value)
