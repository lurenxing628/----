"""HTML host and first read-only endpoint for the migrated workbench."""

from __future__ import annotations

import uuid
from datetime import datetime

from flask import Blueprint, current_app, g, get_flashed_messages, jsonify, render_template, request, url_for

from .assets import WorkbenchAssetsUnavailable, read_asset_manifest
from .navigation_boot import WorkbenchNavigationInvalid, read_navigation
from .navigation_metadata import VIEW_ALIASES, VIEW_TITLES, navigation_groups

bp = Blueprint("workbench", __name__)


def normalize_read_failure(response):
    if not request.path.startswith("/api/workbench/v1/"):
        return response
    response.headers["Cache-Control"] = "no-store"
    if response.status_code < 400:
        return response
    payload = response.get_json(silent=True) if response.is_json else None
    if isinstance(payload, dict) and payload.get("ok") is False:
        return response
    request_ref = uuid.uuid4().hex
    unavailable = response.status_code == 503
    current_app.logger.warning("工作台请求被中止 status=%s request_ref=%s", response.status_code, request_ref)
    response.set_data(current_app.json.dumps({"ok": False, "committed": False, "error": {
        "code": "service_unavailable" if unavailable else "request_failed",
        "message": "系统暂不可用，可能正在维护，请稍后重试。" if unavailable else "本机请求被中止，请检查入口、请求格式或运行日志后重试。",
        "fields": [], "retryable": response.status_code >= 500, "request_ref": request_ref,
    }}))
    response.content_type = "application/json"
    return response


@bp.record_once
def _register_api_response_boundary(state):
    # App-level registration also covers routing 404/405 before a blueprint matches.
    state.app.after_request(normalize_read_failure)


def _unavailable(message: str, status: int):
    response = current_app.make_response((render_template("workbench/unavailable.html", message=message), status))
    response.headers["Cache-Control"] = "no-store"
    return response


def _host(view: str):
    if view not in VIEW_TITLES:
        return _unavailable("工作区不存在，请检查入口地址。", 404)
    try:
        navigation = read_navigation(view, request.args)
    except WorkbenchNavigationInvalid as exc:
        return _unavailable(str(exc), 400)
    try:
        manifest = read_asset_manifest(current_app.static_folder)
    except WorkbenchAssetsUnavailable as exc:
        current_app.logger.error("工作台入口资源不可用：%s", exc, exc_info=True)
        return _unavailable(str(exc), 503)
    config = {
        "schema_version": 1,
        "view": view,
        "navigation": navigation,
        "messages": [{"category": str(category), "message": str(message)}
                     for category, message in get_flashed_messages(with_categories=True)],
        "titles": VIEW_TITLES,
        "enabled_views": ["system", "process", "batches", "analysis", "gantt", "review", "reports", "basedata",
                          "field", "fieldgantt", "run", "calib", "trial", "dashboard", "delay"],
        "entry_url": url_for("workbench.index"),
        "trial_url": url_for("workbench.trial"),
        "nav_groups": navigation_groups(),
        "view_aliases": dict(VIEW_ALIASES),
        "help_url": url_for("scheduler.config_manual_page"),
        "overview_url": url_for("workbench.system_overview"),
        "instance_label": current_app.config.get("WORKBENCH_INSTANCE_LABEL", "本机数据"),
    }
    response = current_app.make_response(render_template("workbench/index.html", assets=manifest, boot=config))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/workbench")
def index():
    return _host(request.args.get("view", "dashboard"))


@bp.get("/workbench/trial")
def trial():
    return _host("trial")


@bp.get("/api/workbench/v1/system/overview")
def system_overview():
    request_ref = uuid.uuid4().hex
    try:
        from core.services.system.workbench_overview import build_system_overview

        data = build_system_overview(
            g.db,
            db_path=current_app.config["DATABASE_PATH"],
            backup_dir=current_app.config["BACKUP_DIR"],
            log_dir=current_app.config["LOG_DIR"],
            backup_keep_days_default=int(current_app.config["BACKUP_KEEP_DAYS"]),
        )
    except Exception:
        current_app.logger.exception("工作台系统概况读取失败 request_ref=%s", request_ref)
        response = jsonify({"ok": False, "committed": False, "error": {
            "code": "system_read_failed", "message": "本机状态读取失败，请查看运行日志后重试。",
            "fields": [], "retryable": True, "request_ref": request_ref,
        }})
        response.status_code = 500
    else:
        response = jsonify({"ok": True, "schema_version": 1, "data": data, "meta": {
            "request_ref": request_ref, "source": "production",
            "as_of": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "time_basis": "factory_local", "snapshot_ref": uuid.uuid4().hex,
        }, "warnings": []})
    response.headers["Cache-Control"] = "no-store"
    return response
