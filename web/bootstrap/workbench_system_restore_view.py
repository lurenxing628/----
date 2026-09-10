"""Recovery presentation only: templates and external journal, never Flask or SQLite."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.wrappers import Request, Response

from core.models.workbench_command import WorkbenchCommandRejected

from .paths import runtime_base_dir

BASE = "/api/workbench/v1/system"
LABELS = {"accepted": "已受理", "checking": "检查中", "protecting": "创建保护副本", "restoring": "恢复中",
          "verifying": "校验中", "rolling_back": "回滚中", "succeeded": "已完成", "failed": "操作失败",
          "rolled_back": "恢复失败，已回滚", "rollback_failed": "回滚失败，需人工核查", "recovery_required": "结果未知，需人工核查"}
ORIGINS = {"selected_backup": "来自所选备份", "protection_backup": "已回滚到恢复前保护副本",
           "unchanged": "原数据库未被替换", "unconfirmed": "未知，不能确认当前数据库内容"}


def _query(request, status):
    args = request.args
    if (request.method != "GET" or set(args) - {"reference", "kind", "download", "view"}
            or any(len(args.getlist(key)) != 1 for key in args)
            or args.get("download", "") not in ("", "diagnostic")
            or args.get("kind", "request") not in ("request", "job")):
        raise WorkbenchCommandRejected("invalid_input", "维护页只接受只读查询；查询条件无效，未执行任何操作。", 400)
    kind = args.get("kind", "request")
    reference = args.get("reference", status.get("request_key") or "").strip()
    return kind, reference


def _recent_records(journal):
    records = sorted(journal.records(), key=lambda row: row["updated_at"], reverse=True)
    return [journal.public(row, True) for row in records[:20]]


def recovery_response(environ, journal, status, lookup):
    request = Request(environ)
    kind, reference, result, error, code = "request", "", None, "", 503
    try:
        kind, reference = _query(request, status)
        if reference:
            result = lookup(BASE + ("/jobs/" if kind == "job" else "/results/") + reference, status)
    except WorkbenchCommandRejected as exc:
        error, code = str(exc), exc.status
    except Exception:
        error = "维护记录损坏或无法读取，不能确认执行结果。系统保持停止，请保留原记录，不要重复恢复。"
    # A bad record must not turn into an empty/successful maintenance history.
    rows, history_error = [], ""
    try:
        rows = _recent_records(journal)
    except Exception:
        history_error = "维护记录清单无法完整读取；没有按空记录处理。仍可用原请求标识核查单条记录。"
    operation = result.get("operation") if result else None
    uncertain = (status["state"] == "recovery_required" or not operation or not operation["terminal"]
                 or status.get("request_key") != operation["request_key"])
    data = {"host": status, "result": result, "query_error": error or None, "history_error": history_error or None,
            "query": {"kind": kind, "reference": reference},
            "recent_records": rows, "scope": "read_only_maintenance", "result_source": "external_maintenance_journal",
            "database_checked_by_page": False, "history_limit": 20,
            "note": "仅含本次读取的外置维护状态，不含数据库或完整日志；没有修改数据库或维护标记。"}
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
    if request.method == "GET" and request.args.get("download") == "diagnostic" and code != 400:
        headers["Content-Disposition"] = 'attachment; filename="aps-restore-maintenance-diagnostic.json"'
        return Response(json.dumps(data, ensure_ascii=True, indent=2), content_type="application/json", headers=headers)
    root = Path(runtime_base_dir(anchor_file=str(Path(__file__).resolve().parents[2] / "app.py")))
    templates = Environment(loader=FileSystemLoader(str(root / "templates")), autoescape=select_autoescape(("html",)))
    html = templates.get_template("workbench/recovery.html").render(
        host=status, result=result, operation=operation, error=error, history_error=history_error, rows=rows,
        kind=kind, reference=reference, uncertain=uncertain, labels=LABELS, origins=ORIGINS)
    headers["Content-Security-Policy"] = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                                         "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    return Response(html, status=code, content_type="text/html; charset=utf-8", headers=headers)
