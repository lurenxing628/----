import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    兼容不同目录结构：优先 tests/ 上一级，其次扫描 D:\\Github 下子目录。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    base = r"D:\Github"
    try:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
                    return p
    except Exception:
        pass

    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _exists(repo_root: str, rel: str) -> bool:
    return os.path.exists(os.path.join(repo_root, rel))


def _list_files(repo_root: str, rel_dir: str) -> List[str]:
    p = os.path.join(repo_root, rel_dir)
    if not os.path.isdir(p):
        return []
    return sorted([x for x in os.listdir(p) if os.path.isfile(os.path.join(p, x))])


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str  # BLOCKER / MAJOR / MINOR / INFO
    evidence: List[str]
    details: Optional[str] = None


def _check_requirements(repo_root: str) -> CheckResult:
    path = os.path.join(repo_root, "requirements.txt")
    txt = _read_text(path)
    evidence = [f"`requirements.txt` 存在：是", "内容摘要：", "```", *(txt.strip().splitlines()[:30]), "```"]

    banned = ["pandas", "numpy", "schedule"]
    banned_hit = []
    for b in banned:
        if re.search(rf"(?im)^{re.escape(b)}\\b", txt):
            banned_hit.append(b)

    has_openpyxl = bool(re.search(r"(?im)^openpyxl==", txt))
    ok = has_openpyxl and not banned_hit
    details = None
    if not has_openpyxl:
        details = "requirements.txt 未锁定 openpyxl==...（V1 约束要求 openpyxl-only）。"
    elif banned_hit:
        details = f"requirements.txt 出现禁止依赖：{banned_hit}（V1 禁止 pandas/numpy/schedule）。"
    return CheckResult(
        name="依赖约束（openpyxl-only；不引入 pandas/numpy/schedule）",
        ok=ok,
        severity="BLOCKER" if not ok else "INFO",
        evidence=evidence,
        details=details,
    )


def _check_no_locking(repo_root: str) -> CheckResult:
    locking_py = os.path.join(repo_root, "core", "infrastructure", "locking.py")
    schema_sql = _read_text(os.path.join(repo_root, "schema.sql"))
    # 仅以“建表语句”为准，避免注释文本误报
    has_resource_locks = bool(re.search(r"(?im)^\\s*CREATE\\s+TABLE\\s+(IF\\s+NOT\\s+EXISTS\\s+)?ResourceLocks\\b", schema_sql))
    ok = (not os.path.exists(locking_py)) and (not has_resource_locks)
    evidence = [
        f"`core/infrastructure/locking.py` 存在：{'是' if os.path.exists(locking_py) else '否'}",
        f"`schema.sql` 包含 ResourceLocks 建表语句：{'是' if has_resource_locks else '否'}",
    ]
    details = None
    if not ok:
        details = "并发/资源锁为 V1 明确不实现项，发现相关实现将与开发文档冲突。"
    return CheckResult(
        name="V1 边界：不实现并发锁/资源锁（无 locking.py / 无 ResourceLocks 表）",
        ok=ok,
        severity="BLOCKER" if not ok else "INFO",
        evidence=evidence,
        details=details,
    )


def _check_gantt_assets(repo_root: str) -> CheckResult:
    js_ok = _exists(repo_root, "static/js/frappe-gantt.min.js")
    css_ok = _exists(repo_root, "static/css/frappe-gantt.css")
    ok = js_ok and css_ok
    evidence = [
        f"`static/js/frappe-gantt.min.js` 存在：{'是' if js_ok else '否'}",
        f"`static/css/frappe-gantt.css` 存在：{'是' if css_ok else '否'}",
    ]
    return CheckResult(
        name="甘特图资源本地化（Frappe Gantt 0.6.1 静态资源在仓库内）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "静态资源缺失将导致离线/打包运行时甘特图不可用。",
    )


def _check_excel_templates(repo_root: str) -> CheckResult:
    required = [
        "人员基本信息.xlsx",
        "人员设备关联.xlsx",
        "设备信息.xlsx",
        "设备人员关联.xlsx",
        "工种配置.xlsx",
        "供应商配置.xlsx",
        "零件工艺路线.xlsx",
        "批次信息.xlsx",
        "工作日历.xlsx",
    ]
    existing = _list_files(repo_root, "templates_excel")
    missing = [x for x in required if x not in existing]
    ok = len(missing) == 0
    evidence = [
        f"`templates_excel/` 文件数：{len(existing)}",
        f"缺失模板：{missing if missing else '无'}",
    ]
    return CheckResult(
        name="交付模板（templates_excel/ 固定模板文件齐全）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "模板缺失会导致“从Excel导入开始跑测试/交付”不完整（虽有动态兜底，但不满足交付清单）。",
    )


def _check_backup_on_exit(repo_root: str) -> CheckResult:
    app_py = _read_text(os.path.join(repo_root, "app.py"))
    ok = ("atexit.register" in app_py) and ("backup_manager.backup(suffix=\"auto\")" in app_py or "backup(suffix=\"auto\")" in app_py)
    evidence = []
    evidence.append("`app.py` 关键片段（退出自动备份）：")
    lines = app_py.splitlines()
    # 抽取 atexit.register 附近上下文
    idx = None
    for i, line in enumerate(lines):
        if "atexit.register" in line:
            idx = i
            break
    if idx is not None:
        start = max(0, idx - 6)
        end = min(len(lines), idx + 8)
        evidence.extend(["```", *lines[start:end], "```"])
    else:
        evidence.append("未找到 atexit.register")
    return CheckResult(
        name="退出自动备份（atexit.register + suffix=auto；不启后台定时线程）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "未发现退出自动备份实现（或未按 suffix=auto 执行）。",
    )


def _check_scheduler_config_defaults(repo_root: str) -> CheckResult:
    path = os.path.join(repo_root, "core", "services", "scheduler", "config_service.py")
    txt = _read_text(path)
    ok = (
        "DEFAULT_SORT_STRATEGY = \"priority_first\"" in txt
        and "DEFAULT_PRIORITY_WEIGHT = 0.4" in txt
        and "DEFAULT_DUE_WEIGHT = 0.5" in txt
        and "DEFAULT_READY_WEIGHT = 0.1" in txt
    )
    evidence = ["`core/services/scheduler/config_service.py` 默认值片段："]
    # 抽取 DEFAULT_* 区域
    lines = txt.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "DEFAULT_SORT_STRATEGY" in line:
            start = i
            break
    if start is not None:
        evidence.extend(["```", *lines[start : min(len(lines), start + 12)], "```"])
    else:
        evidence.append("未找到 DEFAULT_* 常量定义")
    return CheckResult(
        name="排产策略默认值（priority_first；权重 0.4/0.5/0.1）对齐开发文档",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "默认策略/权重未与开发文档对齐，可能影响验收口径与用户预期。",
    )


def _check_operation_logs_keys(repo_root: str) -> CheckResult:
    txt = _read_text(os.path.join(repo_root, "core", "services", "common", "excel_audit.py"))
    required_keys = ["filename", "mode", "time_cost_ms", "total_rows", "new_count", "update_count", "skip_count", "error_count", "errors_sample"]
    ok = all((f"\"{k}\"" in txt) for k in required_keys)
    evidence = ["`core/services/common/excel_audit.py`（导入留痕键名）检查：", f"期望键：{required_keys}"]
    return CheckResult(
        name="Excel 导入留痕 detail 键名（英文固定键）对齐开发文档",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "excel_audit.py 未体现固定键名（或键名被改动），后续审计/报表会不一致。",
    )


def _check_scheduler_schedule_logging(repo_root: str) -> CheckResult:
    txt = _read_text(os.path.join(repo_root, "core", "services", "scheduler", "schedule_service.py"))
    ok = 'action="simulate" if simulate else "schedule"' in txt and "ScheduleHistory" in txt and "with self.tx_manager.transaction()" in txt
    evidence = ["`core/services/scheduler/schedule_service.py` 排产留痕片段："]
    lines = txt.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if 'action="simulate" if simulate else "schedule"' in line:
            idx = i
            break
    if idx is not None:
        start = max(0, idx - 12)
        end = min(len(lines), idx + 12)
        evidence.extend(["```", *lines[start:end], "```"])
    else:
        evidence.append("未找到 action=schedule/simulate 留痕写入逻辑")
    return CheckResult(
        name="排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "排产留痕/事务原子性实现与开发文档要求不一致。",
    )


def _check_routes_presence(repo_root: str) -> CheckResult:
    """
    用 create_app() 的 url_map 做存在性验证（只验证关键路由，不追求全文档逐条比对）。
    为避免污染真实目录，这里用临时目录覆盖 APS_DB_PATH/APS_*_DIR。
    """
    tmpdir = tempfile.mkdtemp(prefix="aps_conformance_routes_")
    test_db = os.path.join(tmpdir, "aps_routes.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    import importlib

    # 确保可 import app.py（仓库根目录）
    if repo_root not in os.sys.path:
        os.sys.path.insert(0, repo_root)

    # 这里会触发 ensure_schema 与 ensure_excel_templates（写入临时目录）
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    rules = sorted({str(r.rule) for r in app.url_map.iter_rules()})

    required_rules = [
        "/personnel/excel/operators/preview",
        "/personnel/excel/operators/confirm",
        "/equipment/excel/machines/preview",
        "/equipment/excel/machines/confirm",
        "/process/excel/routes/preview",
        "/process/excel/routes/confirm",
        "/scheduler/excel/batches/preview",
        "/scheduler/excel/batches/confirm",
        "/scheduler/run",
        "/scheduler/gantt/data",
        "/scheduler/week-plan/export",
        "/system/logs",
        "/system/history",
        "/system/backup",
    ]
    missing = [r for r in required_rules if r not in rules]
    ok = len(missing) == 0
    evidence = [
        f"url_map 路由总数：{len(rules)}",
        f"关键路由缺失：{missing if missing else '无'}",
    ]
    return CheckResult(
        name="关键路由存在性（对齐系统速查表核心链路）",
        ok=ok,
        severity="BLOCKER" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "关键路由缺失将直接阻断端到端验收。",
    )


def generate_report(repo_root: str) -> Tuple[str, List[CheckResult]]:
    checks: List[CheckResult] = []
    checks.append(_check_requirements(repo_root))
    checks.append(_check_no_locking(repo_root))
    checks.append(_check_gantt_assets(repo_root))
    checks.append(_check_excel_templates(repo_root))
    checks.append(_check_backup_on_exit(repo_root))
    checks.append(_check_scheduler_config_defaults(repo_root))
    checks.append(_check_operation_logs_keys(repo_root))
    checks.append(_check_scheduler_schedule_logging(repo_root))
    checks.append(_check_routes_presence(repo_root))

    blockers = [c for c in checks if (not c.ok) and c.severity == "BLOCKER"]
    majors = [c for c in checks if (not c.ok) and c.severity == "MAJOR"]

    lines: List[str] = []
    lines.append("# 实现一致性对标报告（实现 vs 开发文档规划）")
    lines.append("")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 仓库根目录：`{repo_root}`")
    lines.append("")
    lines.append("## 总结")
    lines.append(f"- 检查项总数：{len(checks)}")
    lines.append(f"- BLOCKER：{len(blockers)}")
    lines.append(f"- MAJOR：{len(majors)}")
    lines.append(f"- 结论：{'通过' if (len(blockers) == 0 and len(majors) == 0) else '不通过（存在差异项）'}")
    lines.append("")

    lines.append("## 逐项对标结果")
    for c in checks:
        status = "通过" if c.ok else "不通过"
        lines.append(f"### {c.name}")
        lines.append(f"- **结果**：{status}")
        lines.append(f"- **严重性**：{c.severity}")
        if c.details:
            lines.append(f"- **说明**：{c.details}")
        if c.evidence:
            lines.append("- **证据**：")
            for ev in c.evidence:
                lines.append(f"  - {ev}" if not ev.startswith("```") else ev)
        lines.append("")

    lines.append("## 差异项清单（便于验收沟通/修复排期）")
    diffs = [c for c in checks if not c.ok]
    if not diffs:
        lines.append("- 无")
    else:
        for c in diffs:
            lines.append(f"- **[{c.severity}] {c.name}**：{c.details or '请见上方证据'}")
    lines.append("")

    return "\n".join(lines) + "\n", checks


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    content, _ = generate_report(repo_root)
    out_path = os.path.join(repo_root, "evidence", "Conformance", "conformance_report.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK")
    print(out_path)


if __name__ == "__main__":
    main()

