from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from flask import g, request

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from data.repositories import ScheduleHistoryRepository

from .system_bp import bp
from .system_utils import _safe_int


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    limit = _safe_int(request.args.get("limit"), field="limit", default=20, min_v=1, max_v=200)

    repo = ScheduleHistoryRepository(g.db)
    versions = repo.list_versions(limit=30)

    selected = None
    selected_summary = None
    if version_raw:
        try:
            ver = int(version_raw)
        except Exception:
            raise ValidationError("version 不合法（期望整数）", field="version")
        item = repo.get_by_version(ver)
        if item:
            selected = item.to_dict()
            if selected.get("result_summary"):
                try:
                    selected_summary = json.loads(selected.get("result_summary") or "{}")
                except Exception:
                    selected_summary = None

    items = [x.to_dict() for x in repo.list_recent(limit=limit)]
    for it in items:
        if it.get("result_summary"):
            try:
                it["result_summary_obj"] = json.loads(it.get("result_summary") or "{}")
            except Exception:
                it["result_summary_obj"] = None

    return render_template(
        "system/history.html",
        title="系统管理 - 排产历史",
        versions=versions,
        selected=selected,
        selected_summary=selected_summary,
        items=items,
        filters={"version": version_raw, "limit": str(limit)},
    )

