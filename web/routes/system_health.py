from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from flask import current_app, request

from .system_bp import bp

_APP_ID = "aps"
_CONTRACT_VERSION = 1


@bp.get("/health")
def health():
    payload = {
        "app": _APP_ID,
        "status": "ok",
        "contract_version": _CONTRACT_VERSION,
        "ui_mode": str(current_app.config.get("APP_UI_MODE") or "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return current_app.response_class(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        mimetype="application/json",
    )


@bp.post("/runtime/shutdown")
def runtime_shutdown():
    remote_addr = str(request.remote_addr or "").strip()
    if remote_addr not in {"127.0.0.1", "::1"}:
        payload = {"app": _APP_ID, "status": "forbidden"}
        return current_app.response_class(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            status=403,
            mimetype="application/json",
        )

    expected_token = str(current_app.config.get("APS_RUNTIME_SHUTDOWN_TOKEN") or "").strip()
    provided_token = str(request.headers.get("X-APS-Shutdown-Token") or "").strip()
    if not expected_token or not provided_token or not secrets.compare_digest(expected_token, provided_token):
        payload = {"app": _APP_ID, "status": "forbidden"}
        return current_app.response_class(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            status=403,
            mimetype="application/json",
        )

    from web.bootstrap.factory import request_runtime_server_shutdown

    if not request_runtime_server_shutdown(logger=current_app.logger):
        payload = {"app": _APP_ID, "status": "shutdown_unavailable"}
        return current_app.response_class(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            status=503,
            mimetype="application/json",
        )

    payload = {"app": _APP_ID, "status": "shutting_down"}
    return current_app.response_class(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=202,
        mimetype="application/json",
    )
