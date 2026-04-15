import ast
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


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
    evidence = ["`requirements.txt` 存在：是", "内容摘要：", "```", *(txt.strip().splitlines()[:30]), "```"]

    banned = ["pandas", "numpy", "schedule"]
    banned_hit = []
    for b in banned:
        if re.search(rf"(?im)^{re.escape(b)}\b", txt):
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
    has_resource_locks = bool(
        re.search(
            r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?ResourceLocks\b",
            schema_sql,
        )
    )
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
        "零件工序工时.xlsx",
        "批次信息.xlsx",
        "工作日历.xlsx",
        "人员专属工作日历.xlsx",
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
    # 退出自动备份实现可能在：
    # - 旧布局：app.py
    # - 新布局：web/bootstrap/factory.py（create_app_core 内注册 atexit）
    candidates = [
        ("app.py", os.path.join(repo_root, "app.py")),
        ("web/bootstrap/factory.py", os.path.join(repo_root, "web", "bootstrap", "factory.py")),
    ]

    def _has_exit_backup(txt: str) -> bool:
        has_atexit = bool(re.search(r"\batexit\.register\s*\(", txt))
        has_backup_exit = bool(re.search(r"\.backup\s*\(\s*suffix\s*=\s*['\"]exit['\"]\s*\)", txt))
        has_cfg_guard = "get_snapshot_readonly" in txt and "auto_backup_enabled" in txt
        return has_atexit and has_backup_exit and has_cfg_guard

    ok = False
    evidence = []
    evidence.append("关键片段（退出自动备份）：")
    for label, path in candidates:
        if not os.path.exists(path):
            evidence.append(f"- `{label}`：文件不存在")
            continue
        txt = _read_text(path)
        if _has_exit_backup(txt):
            ok = True

        evidence.append(f"- `{label}`：")
        lines = txt.splitlines()
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
            evidence.append("  - 未找到 atexit.register")
    return CheckResult(
        name="退出自动备份（atexit.register + suffix=exit + 配置守卫；不启后台定时线程）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "未发现受 auto_backup_enabled 控制的退出自动备份实现（或未按 suffix=exit 执行）。",
    )


def _check_scheduler_config_defaults(repo_root: str) -> CheckResult:
    path = os.path.join(repo_root, "core", "services", "scheduler", "config", "config_service.py")
    txt = _read_text(path)
    ok = (
        "DEFAULT_SORT_STRATEGY = \"priority_first\"" in txt
        and "DEFAULT_PRIORITY_WEIGHT = 0.4" in txt
        and "DEFAULT_DUE_WEIGHT = 0.5" in txt
        and "DEFAULT_READY_WEIGHT = 0.1" in txt
    )
    evidence = ["`core/services/scheduler/config/config_service.py` 默认值片段："]
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
    # 排产落库+留痕逻辑在 scheduler 内部已按职责拆分：
    # - 原子落库（Schedule + 状态更新 + ScheduleHistory）
    # - 操作日志（OperationLogs[action=schedule/simulate]）
    path = os.path.join(repo_root, "core", "services", "scheduler", "run", "schedule_persistence.py")
    txt = _read_text(path)
    evidence = ["`core/services/scheduler/run/schedule_persistence.py`（AST）排产留痕检查："]

    try:
        tree = ast.parse(txt, filename=path)
    except SyntaxError as e:
        return CheckResult(
            name="排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）",
            ok=False,
            severity="MAJOR",
            evidence=[*evidence, f"AST 解析失败：{e}"],
            details="无法解析 schedule_persistence.py，conformance 检查无法进行。",
        )

    persist = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "persist_schedule"), None)
    if persist is None:
        return CheckResult(
            name="排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）",
            ok=False,
            severity="MAJOR",
            evidence=[*evidence, "未找到函数：persist_schedule()"],
            details="排产留痕实现位置与对标脚本不一致。",
        )

    def _is_transaction_with_item(expr: ast.AST) -> bool:
        return (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Attribute)
            and isinstance(expr.func.attr, str)
            and expr.func.attr == "transaction"
        )

    def _is_history_repo_create(call: ast.Call) -> bool:
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "create"
            and isinstance(call.func.value, ast.Attribute)
            and call.func.value.attr == "history_repo"
        )

    def _is_op_logger_info(call: ast.Call) -> bool:
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "info"
            and isinstance(call.func.value, ast.Attribute)
            and call.func.value.attr == "op_logger"
        )

    def _is_call_to_name(call: ast.Call, func_name: str) -> bool:
        return isinstance(call.func, ast.Name) and call.func.id == func_name

    def _kw(call: ast.Call, name: str) -> Optional[ast.AST]:
        for k in call.keywords or []:
            if k is not None and k.arg == name:
                return k.value
        return None

    def _is_action_ifexp(v: ast.AST) -> bool:
        if not isinstance(v, ast.IfExp):
            return False
        if not (isinstance(v.test, ast.Name) and v.test.id == "simulate"):
            return False
        if not (isinstance(v.body, ast.Constant) and v.body.value == "simulate"):
            return False
        if not (isinstance(v.orelse, ast.Constant) and v.orelse.value == "schedule"):
            return False
        return True

    # 允许将“DB 留痕/OperationLogs”拆分到 helper（避免 persist_schedule 复杂度膨胀），
    # 但仍要求：
    # - history helper 在 transaction 内被调用
    # - op_logger helper 被调用且 action kw 形如：("simulate" if simulate else "schedule")
    history_helper = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_persist_schedule_history"), None
    )
    op_log_helper = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_log_schedule_operation"), None
    )

    history_helper_create_lineno = None
    if history_helper is not None:
        for sub in ast.walk(history_helper):
            if isinstance(sub, ast.Call) and _is_history_repo_create(sub):
                history_helper_create_lineno = int(getattr(sub, "lineno", 0) or 0) or None
                break

    op_helper_info_lineno = None
    op_helper_action_ok = False
    if op_log_helper is not None:
        for sub in ast.walk(op_log_helper):
            if not (isinstance(sub, ast.Call) and _is_op_logger_info(sub)):
                continue
            op_helper_info_lineno = int(getattr(sub, "lineno", 0) or 0) or None
            action_expr = _kw(sub, "action")
            op_helper_action_ok = _is_action_ifexp(action_expr) if action_expr is not None else False
            if op_helper_action_ok:
                break

    tx_with_lineno = None
    history_create_lineno = None
    history_inside_tx = False

    for node in ast.walk(persist):
        if not isinstance(node, ast.With):
            continue
        items = list(getattr(node, "items", []) or [])
        if not items:
            continue
        if not any(_is_transaction_with_item(getattr(it, "context_expr", None)) for it in items):
            continue
        tx_with_lineno = int(getattr(node, "lineno", 0) or 0) or None
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and _is_history_repo_create(sub):
                history_create_lineno = int(getattr(sub, "lineno", 0) or 0) or None
                history_inside_tx = True
                break
            if (
                isinstance(sub, ast.Call)
                and _is_call_to_name(sub, "_persist_schedule_history")
                and history_helper_create_lineno is not None
            ):
                history_create_lineno = history_helper_create_lineno
                history_inside_tx = True
                break
        if history_inside_tx:
            break

    op_info_lineno = None
    action_ok = False
    for sub in ast.walk(persist):
        if not isinstance(sub, ast.Call):
            continue
        if not _is_op_logger_info(sub):
            continue
        op_info_lineno = int(getattr(sub, "lineno", 0) or 0) or None
        action_expr = _kw(sub, "action")
        action_ok = _is_action_ifexp(action_expr) if action_expr is not None else False
        if action_ok:
            break

    if not (op_info_lineno and action_ok):
        called_helper = any(
            isinstance(sub, ast.Call) and _is_call_to_name(sub, "_log_schedule_operation") for sub in ast.walk(persist)
        )
        if called_helper and op_helper_info_lineno and op_helper_action_ok:
            op_info_lineno = op_helper_info_lineno
            action_ok = op_helper_action_ok

    ok = bool(history_inside_tx and op_info_lineno and action_ok)
    evidence.append(f"- persist_schedule(): line={getattr(persist, 'lineno', None)}")
    evidence.append(f"- with *.transaction(): line={tx_with_lineno}")
    evidence.append(f"- history_repo.create(...): line={history_create_lineno} inside_tx={history_inside_tx}")
    evidence.append(f"- op_logger.info(...): line={op_info_lineno} action_ifexp_ok={action_ok}")
    return CheckResult(
        name="排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "排产留痕/事务原子性实现与开发文档要求不一致。",
    )


def _check_architecture_layers(repo_root: str) -> CheckResult:
    """检查分层架构是否被违反：route 不能直接操作 DB，service 不能导入 Flask request。"""
    violations = []

    route_dir = os.path.join(repo_root, "web", "routes")
    if os.path.isdir(route_dir):
        for dirpath, _, filenames in os.walk(route_dir):
            for fname in filenames:
                if not fname.endswith(".py") or fname.startswith("__"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    txt = _read_text(fpath)
                except Exception:
                    continue
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.search(r"\bcursor\.execute\b", stripped):
                        violations.append(f"{rel}:{i} - route 层直接执行 cursor.execute")
                    if re.search(r"\bfetchone\b", stripped) and "BaseRepository" not in txt:
                        violations.append(f"{rel}:{i} - route 层直接调用 fetchone")
                    if re.search(r"\bconn\.execute\b", stripped):
                        violations.append(f"{rel}:{i} - route 层直接执行 conn.execute")
    svc_base = os.path.join(repo_root, "core", "services")
    if os.path.isdir(svc_base):
        for dirpath, _, filenames in os.walk(svc_base):
            for fname in filenames:
                if not fname.endswith(".py") or fname.startswith("__"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    txt = _read_text(fpath)
                except Exception:
                    continue
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.search(r"from\s+flask\s+import\s+.*\brequest\b", stripped):
                        violations.append(f"{rel}:{i} - service 层导入了 flask.request")

    ok = len(violations) == 0
    evidence = [f"违反项数：{len(violations)}"]
    if violations:
        evidence.extend(violations[:20])
        if len(violations) > 20:
            evidence.append(f"...（共 {len(violations)} 项，仅展示前 20）")
    return CheckResult(
        name="分层架构合规（route 不直接操作 DB，service 不导入 Flask request）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "发现分层架构违反，请按 architecture-invariants 规则修正。",
    )


def _check_schema_tables_documented(repo_root: str) -> CheckResult:
    """检查 schema.sql 中的所有表是否在开发文档中有记录。"""
    schema_path = os.path.join(repo_root, "schema.sql")
    schema_txt = _read_text(schema_path)
    tables = re.findall(r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", schema_txt)
    tables = [t for t in tables if t != "SchemaVersion"]

    doc_path = os.path.join(repo_root, "开发文档", "开发文档.md")
    doc_txt = ""
    if os.path.exists(doc_path):
        doc_txt = _read_text(doc_path)

    quickref_path = os.path.join(repo_root, "开发文档", "系统速查表.md")
    quickref_txt = ""
    if os.path.exists(quickref_path):
        quickref_txt = _read_text(quickref_path)

    combined = doc_txt + "\n" + quickref_txt
    undocumented = [t for t in tables if t not in combined]

    ok = len(undocumented) == 0
    evidence = [
        f"schema.sql 表数量：{len(tables)}",
        f"未在文档中出现的表：{undocumented if undocumented else '无'}",
    ]
    return CheckResult(
        name="Schema 表文档化（schema.sql 所有表在开发文档/速查表中有记录）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else f"以下表未在开发文档中记录：{undocumented}。请同步更新文档。",
    )


def _check_file_sizes(repo_root: str) -> CheckResult:
    """检查 Python 文件是否超过 500 行限制。"""
    oversized = []
    for check_dir in ["web/routes", "core/services", "data/repositories", "core/infrastructure", "core/models"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py") or fname.startswith("__"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    line_count = len(_read_text(fpath).splitlines())
                except Exception:
                    continue
                if line_count > 500:
                    rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                    oversized.append(f"{rel}（{line_count} 行）")

    ok = len(oversized) == 0
    evidence = [f"超过 500 行的文件数：{len(oversized)}"]
    if oversized:
        evidence.extend(oversized[:15])
    return CheckResult(
        name="文件行数约束（核心目录 Python 文件不超过 500 行）",
        ok=ok,
        severity="MINOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "建议按职责拆分超大文件（参考 scheduler.py 拆分先例）。",
    )


def _check_template_files_exist(repo_root: str) -> CheckResult:
    """检查 templates/ 目录结构是否与主要模块对齐。"""
    expected_dirs = ["scheduler", "equipment", "personnel", "process", "material", "reports"]
    tmpl_root = os.path.join(repo_root, "templates")
    missing_dirs = []
    if os.path.isdir(tmpl_root):
        for d in expected_dirs:
            if not os.path.isdir(os.path.join(tmpl_root, d)):
                missing_dirs.append(d)
    else:
        missing_dirs = expected_dirs

    expected_files = ["templates/base.html", "templates/scheduler/gantt.html", "templates/scheduler/batches.html"]
    missing_files = [f for f in expected_files if not _exists(repo_root, f)]

    ok = len(missing_dirs) == 0 and len(missing_files) == 0
    evidence = [
        f"模板子目录缺失：{missing_dirs if missing_dirs else '无'}",
        f"关键模板文件缺失：{missing_files if missing_files else '无'}",
    ]
    return CheckResult(
        name="模板目录完整性（templates/ 子目录与模块对齐）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "模板目录/文件缺失可能导致页面 404。",
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

    env_keys = ["APS_ENV", "APS_DB_PATH", "APS_LOG_DIR", "APS_BACKUP_DIR", "APS_EXCEL_TEMPLATE_DIR"]
    old_env = {k: os.environ.get(k) for k in env_keys}
    inserted_sys_path = False

    try:
        os.environ["APS_ENV"] = "development"
        os.environ["APS_DB_PATH"] = test_db
        os.environ["APS_LOG_DIR"] = test_logs
        os.environ["APS_BACKUP_DIR"] = test_backups
        os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

        import importlib

        # 确保可 import app.py（仓库根目录）
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
            inserted_sys_path = True

        # 这里会触发 ensure_schema 与 ensure_excel_templates（写入临时目录）
        app_mod = importlib.import_module("app")
        app = app_mod.create_app()
        rules = sorted({str(r.rule) for r in app.url_map.iter_rules()})
    finally:
        if inserted_sys_path:
            try:
                sys.path.remove(repo_root)
            except ValueError:
                pass
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

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
    checks.append(_check_architecture_layers(repo_root))
    checks.append(_check_schema_tables_documented(repo_root))
    checks.append(_check_file_sizes(repo_root))
    checks.append(_check_template_files_exist(repo_root))
    checks.append(_check_routes_presence(repo_root))

    blockers = [c for c in checks if (not c.ok) and c.severity == "BLOCKER"]
    majors = [c for c in checks if (not c.ok) and c.severity == "MAJOR"]

    lines: List[str] = []
    lines.append("# 实现一致性对标报告（实现 vs 开发文档规划 + 架构合规）")
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
    content, checks = generate_report(repo_root)
    out_path = os.path.join(repo_root, "evidence", "Conformance", "conformance_report.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    blockers = [c for c in checks if (not c.ok) and c.severity == "BLOCKER"]
    majors = [c for c in checks if (not c.ok) and c.severity == "MAJOR"]
    ok = (len(blockers) == 0) and (len(majors) == 0)

    print("OK" if ok else "FAILED")
    print(out_path)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
