import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

from tests._support.paths import REPO_ROOT_STR


def find_repo_root():
    """仓库根目录。以前会按 app.py + schema.sql 现场找，现在统一由 tests._support.paths 给。"""
    return REPO_ROOT_STR


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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


def _check_backup_on_exit(repo_root: str) -> CheckResult:
    """退出自动备份：注册点和执行体已经分家，三个要件要跨两个文件一起看。

    原来三个要件都在一个文件里找，所以执行体搬到 launcher_shutdown.py 之后这条就一直红着，
    红的是检查而不是实现。现在按要件分别认位置：注册在 factory.py，配置守卫和 suffix=exit
    在 launcher_shutdown.py。
    """
    parts = [
        ("注册（atexit.register）", "web/bootstrap/factory.py", r"\batexit\.register\s*\("),
        ("配置守卫（auto_backup_enabled）", "web/bootstrap/launcher_shutdown.py",
         r"auto_backup_enabled"),
        ("执行（backup(suffix=\"exit\")）", "web/bootstrap/launcher_shutdown.py",
         r"\.backup\s*\(\s*suffix\s*=\s*['\"]exit['\"]\s*\)"),
    ]
    ok = True
    evidence = ["关键片段（退出自动备份）："]
    for label, rel, pattern in parts:
        path = os.path.join(repo_root, *rel.split("/"))
        txt = _read_text(path) if os.path.exists(path) else ""
        lines = txt.splitlines()
        hit = next((i for i, line in enumerate(lines) if re.search(pattern, line)), None)
        if hit is None:
            ok = False
            evidence.append(f"- {label}：`{rel}` 里没找到")
            continue
        evidence.append(f"- {label}：`{rel}:{hit + 1}`")
        evidence.extend(["```", *lines[max(0, hit - 3):min(len(lines), hit + 4)], "```"])
    return CheckResult(
        name="退出自动备份（atexit.register + suffix=exit + 配置守卫；不启后台定时线程）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=None if ok else "未发现受 auto_backup_enabled 控制的退出自动备份实现（或未按 suffix=exit 执行）。",
    )


def _check_scheduler_config_defaults(repo_root: str) -> CheckResult:
    # DEFAULT_* 这组常量后来从 config_service.py 挪进了 config_constants.py，字面写法没变。
    svc_path = os.path.join(repo_root, "core", "services", "scheduler", "config", "config_constants.py")
    spec_path = os.path.join(repo_root, "core", "services", "scheduler", "config", "config_field_spec.py")
    txt = _read_text(svc_path)
    spec_txt = _read_text(spec_path)
    ok = (
        'DEFAULT_SORT_STRATEGY = str(default_for("sort_strategy"))' in txt
        and 'DEFAULT_PRIORITY_WEIGHT = float(default_for("priority_weight"))' in txt
        and 'DEFAULT_DUE_WEIGHT = float(default_for("due_weight"))' in txt
        and 'DEFAULT_READY_WEIGHT = float(default_for("ready_weight"))' in txt
        and 'key="sort_strategy"' in spec_txt
        and 'default="priority_first"' in spec_txt
        and 'key="priority_weight"' in spec_txt
        and "default=0.4" in spec_txt
        and 'key="due_weight"' in spec_txt
        and "default=0.5" in spec_txt
        and 'key="ready_weight"' in spec_txt
        and "default=0.1" in spec_txt
    )
    evidence = [
        "`core/services/scheduler/config/config_constants.py` 默认值片段：",
    ]
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
    evidence.append("`core/services/scheduler/config/config_field_spec.py` 默认值片段：")
    spec_lines = spec_txt.splitlines()
    for key in ("sort_strategy", "priority_weight", "due_weight", "ready_weight"):
        idx = next((i for i, line in enumerate(spec_lines) if f'key="{key}"' in line), None)
        if idx is None:
            evidence.append(f"- 未找到 key={key}")
            continue
        evidence.extend(["```", *spec_lines[max(0, idx - 2) : min(len(spec_lines), idx + 5)], "```"])
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


# schema.sql 里已经没文档的表。这是真实文档缺口，不是检查陈旧：78 张表里 53 张在开发文档和
# 速查表里都搜不到。一次补齐要单独立项，所以先把欠账清单钉在这里当棘轮——新建表没写文档会红，
# 清单里的表补上文档后必须从清单里划掉（多余条目同样红），欠账只能减不能增。
_UNDOCUMENTED_TABLES_DEBT = (
    "WorkbenchRequestLifecycle", "WorkbenchRuntimeLock",
)


def _documented_tables_debt(repo_root: str) -> Tuple[str, ...]:
    """欠账清单落在单独文件里，人改它时能看见一次改了多少。"""
    path = os.path.join(repo_root, ".codestable", "checkup", "undocumented_tables_baseline.txt")
    if not os.path.exists(path):
        return _UNDOCUMENTED_TABLES_DEBT
    return tuple(line.strip() for line in _read_text(path).splitlines()
                 if line.strip() and not line.startswith("#"))


def _check_schema_tables_documented(repo_root: str) -> CheckResult:
    """检查 schema.sql 中的所有表是否在开发文档中有记录（已知欠账见基线文件）。"""
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

    debt = _documented_tables_debt(repo_root)
    new_gaps = [t for t in undocumented if t not in debt]
    stale = [t for t in debt if t not in undocumented]

    ok = not new_gaps and not stale
    evidence = [
        f"schema.sql 表数量：{len(tables)}",
        f"没有文档的表：{len(undocumented)} 张（已记入欠账清单 {len(debt)} 张）",
        f"新增没文档的表：{new_gaps if new_gaps else '无'}",
        f"已补文档但还留在欠账清单里的表：{stale if stale else '无'}",
    ]
    details = None
    if new_gaps:
        details = f"这些表是新建的、开发文档和速查表里都没有：{new_gaps}。请补文档，不要往欠账清单里加。"
    elif stale:
        details = f"这些表已经有文档了，请从 .codestable/checkup/undocumented_tables_baseline.txt 里删掉：{stale}。"
    return CheckResult(
        name="Schema 表文档化（新建表必须有文档；存量欠账按清单只减不增）",
        ok=ok,
        severity="MAJOR" if not ok else "INFO",
        evidence=evidence,
        details=details,
    )


def generate_report(repo_root: str) -> Tuple[str, List[CheckResult]]:
    checks: List[CheckResult] = []
    checks.append(_check_requirements(repo_root))
    checks.append(_check_no_locking(repo_root))
    checks.append(_check_backup_on_exit(repo_root))
    checks.append(_check_scheduler_config_defaults(repo_root))
    checks.append(_check_operation_logs_keys(repo_root))
    checks.append(_check_architecture_layers(repo_root))
    checks.append(_check_schema_tables_documented(repo_root))

    blockers = [c for c in checks if (not c.ok) and c.severity == "BLOCKER"]
    majors = [c for c in checks if (not c.ok) and c.severity == "MAJOR"]

    lines: List[str] = []
    lines.append("# 实现一致性对标报告（实现 vs 开发文档规划 + 架构合规）")
    lines.append("")
    lines.append("- 生成方式：稳定快照（不含运行时间与绝对路径）")
    lines.append("- 仓库根目录：`<repo-root>`")
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
