"""Recovery presentation only: templates and external journal, never Flask or SQLite."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.wrappers import Request, Response

from core.models.workbench_command import WorkbenchCommandRejected

from .paths import runtime_base_dir

BASE = "/api/workbench/v1/system"
LABELS = {"accepted": "已接收", "checking": "检查中", "protecting": "生成保护副本", "restoring": "恢复中",
          "verifying": "完整性检查中", "rolling_back": "还原中", "succeeded": "已完成", "failed": "操作失败",
          "rolled_back": "恢复失败，已还原", "rollback_failed": "还原失败，需人工核对",
          "recovery_required": "结果不确定，需人工核对"}
ORIGINS = {"selected_backup": "来自所选备份", "protection_backup": "已还原到恢复前的保护副本",
           "unchanged": "原数据库未被替换", "unconfirmed": "未知，不能确认当前数据库内容"}


def _query(request, status):
    args = request.args
    if (request.method != "GET" or set(args) - {"reference", "kind", "download", "view"}
            or any(len(args.getlist(key)) != 1 for key in args)
            or args.get("download", "") not in ("", "diagnostic")
            or args.get("kind", "request") not in ("request", "job")):
        raise WorkbenchCommandRejected("invalid_input", "这一页只能查看，查询条件不对，没有执行任何操作。", 400)
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
        error = "维护记录损坏或读不出来，不能确认这次恢复的结果。系统已停下，请不要再操作，联系维护人员。"
    # A bad record must not turn into an empty/successful maintenance history.
    rows, history_error = [], ""
    try:
        rows = _recent_records(journal)
    except Exception:
        history_error = "维护记录列表没能完整读出来，这里不是完整清单。可以用操作编号单独查一条记录。"
    operation = result.get("operation") if result else None
    uncertain = (status["state"] == "recovery_required" or not operation or not operation["terminal"]
                 or status.get("request_key") != operation["request_key"])
    data = {"host": status, "result": result, "query_error": error or None, "history_error": history_error or None,
            "query": {"kind": kind, "reference": reference},
            "recent_records": rows, "scope": "read_only_maintenance", "result_source": "external_maintenance_journal",
            "database_checked_by_page": False, "history_limit": 20,
            "note": "这一页只显示本次读到的维护状态，不含数据库内容和完整日志；打开这一页不会改动任何数据。"}
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
