"""Request transport for workbench routes: strict JSON, command envelopes, URL arguments, opaque refs and bounded uploads.

Bodies and JSON-valued arguments both decode through ``core.shared.strict_json``: duplicate keys and
non-finite numbers are rejected. Uploaded import files share one byte limit. Key sets are judged by
``core.shared.key_sets.keys_conform``. Codes and statuses are shared here, wording stays with the route.
"""

import re
from dataclasses import dataclass
from typing import AbstractSet, Any, Dict, Iterable, Optional, Tuple

from flask import current_app, g, request
from werkzeug.wsgi import get_input_stream

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.shared.key_sets import keys_conform
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
    if (set(request.files) != {"file"} or len(request.files.getlist("file")) != 1
            or not keys_conform(request.form.to_dict(), required, optional)
            or any(len(values) != 1 for values in request.form.listvalues())):
        rejecter(shape)()
    return request.form


def single_value_arguments(allowed: Iterable[str], *, required: Iterable[str] = (), message: str,
                           status: int = 400) -> Dict[str, str]:
    """The URL arguments, one value each: every ``required`` key and otherwise only ``allowed`` ones.

    Anything else, or any key given twice, is rejected with the route's ``message`` and ``status``.
    """
    arguments = request.args.to_dict()
    if (not keys_conform(arguments, required, allowed)
            or any(len(values) != 1 for values in request.args.listvalues())):
        rejecter(message, status=status)()
    return arguments


@dataclass(frozen=True)
class BodyTexts:
    """One route family's wording for a JSON body it does not take.

    ``transport``: URL arguments, or a body that is not JSON. ``malformed``: unreadable JSON, and duplicate
    keys unless ``duplicate`` is given. ``incomplete``: a JSON value that is not an object, or an envelope
    without exactly its declared keys.
    """

    transport: str
    malformed: str
    incomplete: str
    duplicate: Optional[str] = None


def read_json_body(texts: BodyTexts, *, limit: Optional[Tuple[int, str]] = None) -> Dict[str, Any]:
    """One JSON object from a POST body without URL arguments.

    ``limit`` is ``(max_bytes, too_large_message)``; without it only the application-wide
    ``MAX_CONTENT_LENGTH`` bounds the body.
    """
    if request.args or not request.is_json:
        rejecter(texts.transport)()
    if limit is None:
        raw = request.get_data()
    else:
        maximum, too_large = limit
        if request.content_length is not None and request.content_length > maximum:
            rejecter(too_large, "capacity_exceeded", 413)()
        raw = get_input_stream(request.environ, max_content_length=maximum + 1).read(maximum + 1)
        if len(raw) > maximum:
            rejecter(too_large, "capacity_exceeded", 413)()
    return load_strict_json(raw, on_malformed=rejecter(texts.malformed),
                            on_duplicate=rejecter(texts.duplicate) if texts.duplicate is not None else None,
                            expected=dict, on_unexpected=rejecter(texts.incomplete))


def command_body(texts: BodyTexts, *, stale: str, payload: str = "input",
                 limit: Optional[Tuple[int, str]] = None) -> Dict[str, Any]:
    """The command envelope: exactly ``request_key``, ``write_token`` and the entry's ``payload`` key.

    Only the envelope's structure is judged here. The request key is bound for the receipt lookup as soon as
    its form is valid; the write token must be a non-empty string (``stale`` otherwise). The token's validity
    and the payload belong to the entry: a committed request replays before its guard resolves the token, so
    nothing here looks a token up.
    """
    body = read_json_body(texts, limit=limit)
    if not keys_conform(body, ("request_key", "write_token", payload)):
        rejecter(texts.incomplete)()
    g.workbench_request_key = validate_request_key(body["request_key"])
    if type(body["write_token"]) is not str or not body["write_token"]:
        rejecter(stale)()
    return body


def preview_confirm_body(texts: BodyTexts, *, stale_ref: str, mismatch: str) -> Dict[str, Any]:
    """Confirm a retained preview: the command envelope with ``input == {preview_ref}``.

    The write token and the preview ref are both server-issued opaque tokens, checked for shape with
    ``stale_ref``; the entry's guard resolves them. Any other input is rejected with ``mismatch``.
    """
    body = command_body(texts, stale=stale_ref)
    opaque_ref(body["write_token"], stale_ref)
    if not keys_conform(body["input"], ("preview_ref",)):
        rejecter(mismatch)()
    opaque_ref(body["input"]["preview_ref"], stale_ref)
    return body


def opaque_ref(value: object, message: str) -> str:
    """A server-issued 32-character public token, checked for shape before it is looked up."""
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{32}", value) is None:
        rejecter(message)()
    return value
