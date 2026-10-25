"""Strict JSON transport for workbench routes; each route keeps its own user-facing texts.

Bodies and JSON-valued arguments both decode through ``core.shared.strict_json``: duplicate keys and
non-finite numbers are rejected. Codes and statuses are shared here, wording stays with the route.
"""

from typing import Optional, Tuple

from flask import request

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_json import Reject, load_strict_json


def rejecter(message: str, code: str = "invalid_input", status: int = 400) -> Reject:
    def reject():
        raise WorkbenchCommandRejected(code, message, status)
    return reject


def read_json_body(*, transport: str, malformed: str, incomplete: str, duplicate: Optional[str] = None,
                   limit: Optional[Tuple[int, str]] = None):
    """One JSON object from a POST body without URL arguments.

    ``limit`` is ``(max_bytes, too_large_message)``; without it only the application-wide
    ``MAX_CONTENT_LENGTH`` bounds the body. ``duplicate`` defaults to the ``malformed`` text.
    """
    if request.args or not request.is_json:
        rejecter(transport)()
    if limit is None:
        raw = request.get_data()
    else:
        maximum, too_large = limit
        if request.content_length is not None and request.content_length > maximum:
            rejecter(too_large, "capacity_exceeded", 413)()
        raw = request.stream.read(maximum + 1)
        if len(raw) > maximum:
            rejecter(too_large, "capacity_exceeded", 413)()
    return load_strict_json(raw, on_malformed=rejecter(malformed),
                            on_duplicate=rejecter(duplicate) if duplicate is not None else None,
                            expected=dict, on_unexpected=rejecter(incomplete))
