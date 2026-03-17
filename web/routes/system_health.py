from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import current_app

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
