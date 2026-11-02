"""Request transport for workbench routes: strict JSON and bounded file uploads.

Bodies and JSON-valued arguments both decode through ``core.shared.strict_json``: duplicate keys and
non-finite numbers are rejected. Uploaded import files share one byte limit. Codes and statuses are
shared here, wording stays with the route.
"""

from typing import AbstractSet, Optional, Tuple

from flask import current_app, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_json import Reject, load_strict_json


def rejecter(message: str, code: str = "invalid_input", status: int = 400) -> Reject:
    def reject():
        raise WorkbenchCommandRejected(code, message, status)
    return reject


def read_upload_file(too_large: str) -> bytes:
    """The single multipart ``file`` within ``EXCEL_MAX_UPLOAD_BYTES``.

    Reads at most one byte past the limit; a larger file is rejected whole (413), never imported in part.
    """
    limit = current_app.config["EXCEL_MAX_UPLOAD_BYTES"]
    content = request.files["file"].read(limit + 1)
    if len(content) > limit:
        rejecter(too_large, "invalid_input", 413)()
    return content


def read_upload_form(required: AbstractSet[str], *, optional: AbstractSet[str] = frozenset(), transport: str, shape: str):
    """The multipart form around exactly one ``file``: every ``required`` key, any ``optional`` one, each once.

    URL arguments or a non-multipart body are rejected with ``transport`` before ``request.files`` is read,
    so they stay a 400 even when the body is too large; a wrong file or form shape is rejected with ``shape``.
    """
    if request.args or request.mimetype != "multipart/form-data":
        rejecter(transport)()
    keys = set(request.form)
    if (set(request.files) != {"file"} or len(request.files.getlist("file")) != 1 or not required <= keys
            or keys - required - optional or any(len(request.form.getlist(key)) != 1 for key in keys)):
        rejecter(shape)()
    return request.form


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
