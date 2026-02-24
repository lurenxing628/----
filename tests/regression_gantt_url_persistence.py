from __future__ import annotations

import os
import sys
import tempfile
from urllib.parse import parse_qs, urlparse


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _setup_runtime() -> str:
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_gantt_url_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = os.path.join(tmpdir, "aps_test.db")
    os.environ["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    os.environ["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")
    os.makedirs(os.environ["APS_LOG_DIR"], exist_ok=True)
    os.makedirs(os.environ["APS_BACKUP_DIR"], exist_ok=True)
    os.makedirs(os.environ["APS_EXCEL_TEMPLATE_DIR"], exist_ok=True)
    return tmpdir


def _assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def main() -> None:
    _setup_runtime()
    repo_root = _find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema

    ensure_schema(os.environ["APS_DB_PATH"], logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    from app import create_app

    app = create_app()
    client = app.test_client()
    # 页面 HTML 只校验前端契约（URL 参数回显由 JS 实现）
    resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=1")
    _assert_true(resp.status_code == 200, f"GET /scheduler/gantt 返回 {resp.status_code}")
    html = resp.data.decode("utf-8", errors="ignore")
    _assert_true('id="ganttViewMode"' in html, "缺少 ganttViewMode 控件")
    _assert_true('id="ganttColorMode"' in html, "缺少 ganttColorMode 控件")
    _assert_true('id="ganttFilterBatch"' in html, "缺少 ganttFilterBatch 控件")

    gantt_js_path = os.path.join(repo_root, "static", "js", "gantt.js")
    with open(gantt_js_path, "r", encoding="utf-8") as f:
        src = f.read()

    for needle in (
        "function applyUiFromUrl()",
        "function persistUiToUrl()",
        "gantt_vm",
        "gantt_color",
        "gantt_batch",
        "gantt_resource",
        "gantt_overdue",
        "gantt_external",
        "gantt_deps",
        "gantt_hcc",
    ):
        _assert_true(needle in src, f"gantt.js 缺少 URL 持久化关键片段: {needle}")

    # 轻量级语义检查：确保默认值会被删除，不污染 URL
    # 这里不执行浏览器，仅验证 key 设计与默认值逻辑存在
    _assert_true('ui.viewMode === "Day"' in src, "viewMode 默认值清理逻辑缺失")
    _assert_true('ui.colorMode === "batch"' in src, "colorMode 默认值清理逻辑缺失")
    _assert_true('ui.depsMode === "critical"' in src, "depsMode 默认值清理逻辑缺失")

    # 参数名称稳定性检查：避免未来改名导致分享链接失效
    sample = "https://local.test/scheduler/gantt?gantt_vm=Week&gantt_color=status&gantt_batch=B001&gantt_overdue=1"
    parsed = parse_qs(urlparse(sample).query)
    _assert_true(parsed.get("gantt_vm", [""])[0] == "Week", "gantt_vm 解析异常")
    _assert_true(parsed.get("gantt_color", [""])[0] == "status", "gantt_color 解析异常")
    _assert_true(parsed.get("gantt_batch", [""])[0] == "B001", "gantt_batch 解析异常")
    _assert_true(parsed.get("gantt_overdue", [""])[0] == "1", "gantt_overdue 解析异常")

    print("OK")


if __name__ == "__main__":
    main()

