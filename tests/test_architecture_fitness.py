"""
架构适应度函数（Architecture Fitness Functions）。

把架构规则写成 pytest 用例，跑 pytest 即可同时验证功能测试和架构合规。
参考：Neal Ford《Building Evolutionary Architectures》的 Fitness Function 模式。

运行：pytest tests/test_architecture_fitness.py -v
"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Set, Tuple, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CORE_DIRS = ["web/routes", "core/services", "data/repositories", "core/models", "core/infrastructure", "web/viewmodels"]
NO_WILDCARD_DIRS = CORE_DIRS


def _collect_py_files(*rel_dirs: str) -> List[str]:
    """收集指定目录下所有 .py 文件的相对路径。"""
    files = []
    for rd in rel_dirs:
        base = os.path.join(REPO_ROOT, rd)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fn in filenames:
                if fn.endswith(".py") and (fn == "__init__.py" or not fn.startswith("__")):
                    files.append(os.path.relpath(os.path.join(dirpath, fn), REPO_ROOT).replace("\\", "/"))
    return files


def _read(rel_path: str) -> str:
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _known_oversize_files() -> Set[str]:
    return {
        # Phase 5 采用“显式登记技术债”路径：这些历史大文件本轮不继续做高风险拆分，
        # 仅在 strict_mode / silent fallback 收口完成后单独拆批处理。
        "web/routes/scheduler_excel_calendar.py",
        "core/services/process/part_service.py",
        "core/services/process/unit_excel/template_builder.py",
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/personnel/operator_machine_service.py",
        "core/infrastructure/database.py",
    }


LOCAL_PARSE_HELPER_NAMES = {"_safe_float", "_safe_int", "_cfg_float", "_cfg_int", "_get_float", "_get_int"}
LOCAL_PARSE_HELPER_ALLOWLIST = {
    "core/algorithms/greedy/scheduler.py:_safe_int",
    "core/services/scheduler/_sched_utils.py:_safe_int",
    "core/services/scheduler/batch_service.py:_safe_float",
    "core/services/scheduler/config_snapshot.py:_get_float",
    "core/services/scheduler/config_snapshot.py:_get_int",
    "core/services/scheduler/config_validator.py:_get_float",
    "core/services/scheduler/config_validator.py:_get_int",
    "core/services/scheduler/schedule_optimizer_steps.py:_cfg_float",
    "core/services/scheduler/schedule_optimizer_steps.py:_cfg_int",
    "core/services/system/system_config_service.py:_get_int",
}


# ─── Fitness 1: 分层依赖方向 ───────────────────────────────────

def test_routes_do_not_execute_sql_directly():
    """Route 层禁止直接执行 SQL（必须通过 Service → Repository）。"""
    violations = []
    for fp in _collect_py_files("web/routes"):
        for i, line in enumerate(_read(fp).splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if re.search(r"\b(cursor|conn)\.(execute|fetchone|fetchall)\b", s):
                violations.append(f"{fp}:{i}")
    assert not violations, "Route 直接执行 SQL:\n" + "\n".join(violations)


def test_services_do_not_import_flask_request():
    """Service 层禁止导入 flask.request（Web 层对象）。"""
    violations = []
    for fp in _collect_py_files("core/services"):
        for i, line in enumerate(_read(fp).splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if re.search(r"from\s+flask\s+import\s+.*\brequest\b", s):
                violations.append(f"{fp}:{i}")
    assert not violations, "Service 导入 flask.request:\n" + "\n".join(violations)


def test_routes_do_not_import_repository():
    """Route 层禁止直接导入 Repository（应通过 Service 中转）。

    历史代码中有大量 Route 直接使用 Repository 的情况（尤其是 Excel 导入路由），
    通过 known_imports 白名单豁免。新增 Route 不应直接导入 Repository。
    """
    # 目标：Route 层不再允许任何 Repository 直连。
    # 历史白名单已逐步清理；若确有合理例外，请添加到此处并说明原因。
    known_imports = set()
    violations = []
    repo_re = re.compile(r"\b(\w+Repository)\b")
    for fp in _collect_py_files("web/routes"):
        for line in _read(fp).splitlines():
            s = line.strip()
            if not (s.startswith("from ") or s.startswith("import ")):
                continue
            if "repositories" not in s:
                continue
            for name in repo_re.findall(s):
                entry = f"{fp}: {name}"
                if entry not in known_imports:
                    violations.append(entry)
    assert not violations, (
        "Route 新增了越层 Repository 导入:\n" + "\n".join(violations)
        + "\n\n如有合理理由，请添加到 known_imports 白名单。"
    )


def test_web_helpers_do_not_import_repository():
    """web/*.py 顶层辅助模块禁止直接导入 Repository。"""
    known_imports = set()
    violations = []
    repo_re = re.compile(r"\b(\w+Repository)\b")
    web_base = os.path.join(REPO_ROOT, "web")
    if not os.path.isdir(web_base):
        return
    for fn in sorted(os.listdir(web_base)):
        if not fn.endswith(".py"):
            continue
        fp = f"web/{fn}"
        for line in _read(fp).splitlines():
            s = line.strip()
            if not (s.startswith("from ") or s.startswith("import ")):
                continue
            if "repositories" not in s:
                continue
            for name in repo_re.findall(s):
                entry = f"{fp}: {name}"
                if entry not in known_imports:
                    violations.append(entry)
    assert not violations, (
        "web 顶层辅助模块新增了越层 Repository 导入:\n" + "\n".join(violations)
        + "\n\n如有合理理由，请添加到 known_imports 白名单。"
    )


def test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes():
    """
    ViewModel 层（web/viewmodels）必须是纯数据变换。

    允许清单（allowlist）语义：
    - 允许：标准库、core.models*、相对导入
    - 禁止：flask*、core.*（除 core.models*）、data.*、web.*
    """

    def _is_stdlib_root_module(root: str) -> bool:
        if not root:
            return False
        if root in sys.builtin_module_names:
            return True
        try:
            spec = importlib.util.find_spec(root)
        except Exception:
            return False
        if spec is None:
            return False
        origin = getattr(spec, "origin", None)
        if origin in ("built-in", "frozen"):
            return True
        if not origin:
            return False
        origin_path = os.path.normcase(os.path.abspath(str(origin)))
        lower = origin_path.lower()
        if ("site-packages" in lower) or ("dist-packages" in lower):
            return False
        for bp in (getattr(sys, "base_prefix", None), getattr(sys, "prefix", None)):
            if not bp:
                continue
            bp_path = os.path.normcase(os.path.abspath(str(bp)))
            if origin_path.startswith(bp_path + os.sep):
                return True
        return False

    def _is_allowed_viewmodel_import(mod: str) -> bool:
        m = str(mod or "").strip()
        if not m:
            return False
        if m == "core.models" or m.startswith("core.models."):
            return True
        root = m.split(".", 1)[0]
        if root in ("flask", "web", "data"):
            return False
        if root == "core":
            return False
        return _is_stdlib_root_module(root)

    violations: List[str] = []
    for fp in _collect_py_files("web/viewmodels"):
        src = _read(fp)
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError as e:
            violations.append(f"{fp}:{getattr(e, 'lineno', 0) or 0}: SyntaxError: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = str(alias.name or "")
                    if not _is_allowed_viewmodel_import(mod):
                        violations.append(f"{fp}:{node.lineno}: import {mod}")
            elif isinstance(node, ast.ImportFrom):
                # 禁止 viewmodels 内使用 import *
                if any(a.name == "*" for a in node.names or []):
                    violations.append(f"{fp}:{node.lineno}: from {node.module} import *")

                # 相对导入（from .foo import bar）允许
                if int(getattr(node, "level", 0) or 0) > 0:
                    continue

                mod = str(node.module or "")
                if mod and not _is_allowed_viewmodel_import(mod):
                    violations.append(f"{fp}:{node.lineno}: from {mod} import ...")

    assert not violations, "ViewModel 导入越界:\n" + "\n".join(violations)


# ─── Fitness 2: 循环依赖 ──────────────────────────────────────

def test_no_circular_service_dependencies():
    """Service 包之间禁止循环导入（A→B 且 B→A）。"""
    svc_base = os.path.join(REPO_ROOT, "core", "services")
    if not os.path.isdir(svc_base):
        return

    pkg_deps: Dict[str, Set[str]] = {}
    for dirpath, _, filenames in os.walk(svc_base):
        for fn in filenames:
            if not fn.endswith(".py") or fn.startswith("__"):
                continue
            fpath = os.path.join(dirpath, fn)
            pkg = os.path.relpath(dirpath, svc_base).replace("\\", "/").split("/")[0]
            if pkg == ".":
                pkg = fn[:-3]
            deps = pkg_deps.setdefault(pkg, set())
            for line in _read(os.path.relpath(fpath, REPO_ROOT).replace("\\", "/")).splitlines():
                m = re.search(r"core\.services\.(\w+)", line.strip())
                if m:
                    target_pkg = m.group(1)
                    if target_pkg != pkg:
                        deps.add(target_pkg)

    cycles = []
    checked: Set[Tuple[str, str]] = set()
    for pkg_a, deps_a in pkg_deps.items():
        for dep in deps_a:
            if pkg_a <= dep:
                pair: Tuple[str, str] = (pkg_a, dep)
            else:
                pair = (dep, pkg_a)
            if pair in checked:
                continue
            checked.add(pair)
            if dep in pkg_deps and pkg_a in pkg_deps.get(dep, set()):
                cycles.append(f"{pkg_a} <-> {dep}")

    known_cycles: Set[str] = set()
    new_cycles = [c for c in cycles if c not in known_cycles]
    assert not new_cycles, "Service 新增循环依赖:\n" + "\n".join(new_cycles)


# ─── Fitness 3: 禁止模式 ──────────────────────────────────────

def test_no_wildcard_imports():
    """核心目录禁止 import *。"""
    violations = []
    for fp in _collect_py_files(*NO_WILDCARD_DIRS):
        for i, line in enumerate(_read(fp).splitlines(), 1):
            if re.match(r"\s*from\s+\S+\s+import\s+\*", line):
                violations.append(f"{fp}:{i}")
    assert not violations, "import * 违反:\n" + "\n".join(violations)


def _string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def test_no_new_local_parse_helpers():
    """禁止在 core/ 下继续新增局部解析函数。"""
    violations: List[str] = []
    found_allowlist: Set[str] = set()

    for fp in _collect_py_files("core"):
        src = _read(fp)
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError as e:
            violations.append(f"{fp}:{getattr(e, 'lineno', 0) or 0}: SyntaxError: {e}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = str(getattr(node, "name", "") or "")
            if name not in LOCAL_PARSE_HELPER_NAMES:
                continue
            entry = f"{fp}:{name}"
            if entry in LOCAL_PARSE_HELPER_ALLOWLIST:
                found_allowlist.add(entry)
                continue
            violations.append(entry)

    stale_entries = sorted(LOCAL_PARSE_HELPER_ALLOWLIST - found_allowlist)
    assert not violations, "core/ 新增了局部解析函数:\n" + "\n".join(sorted(violations))
    assert not stale_entries, "局部解析函数白名单存在失效项:\n" + "\n".join(stale_entries)


def test_stable_degradation_codes_cover_actual_usages():
    """稳定退化原因码清单必须覆盖当前实际使用。"""
    from core.services.common.degradation import STABLE_DEGRADATION_CODES

    used_codes: Set[str] = set()
    for fp in _collect_py_files("core", "web/bootstrap"):
        src = _read(fp)
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError as e:
            raise AssertionError(f"无法解析 {fp}: {e}") from e

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if func_name == "FieldPolicy":
                for key in ("strict_reason_code", "compat_reason_code", "blank_reason_code"):
                    code = _string_constant(keywords.get(key))
                    if code:
                        used_codes.add(code)
                continue

            if func_name in {"add", "DegradationEvent"} and "code" in keywords and (
                func_name == "DegradationEvent" or "scope" in keywords or "message" in keywords
            ):
                code = _string_constant(keywords.get("code"))
                if code:
                    used_codes.add(code)

    missing = sorted(code for code in used_codes if code not in set(STABLE_DEGRADATION_CODES))
    assert not missing, "存在未纳入 STABLE_DEGRADATION_CODES 的退化原因码:\n" + "\n".join(missing)


def test_services_do_not_use_assert_for_runtime_guards():
    """
    Service 层业务路径禁止使用 assert 作为运行期保障。

    原因：
    - `python -O` 会移除 assert，导致防线失效
    - assert 更适合开发期不变量，而不是业务输入/契约保障
    """
    violations: List[str] = []
    for fp in _collect_py_files("core/services"):
        src = _read(fp)
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError as e:
            violations.append(f"{fp}:{getattr(e, 'lineno', 0) or 0}: SyntaxError: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                violations.append(f"{fp}:{node.lineno}: assert ...")
    assert not violations, "Service 使用 assert（禁止）:\n" + "\n".join(violations)


def _find_enclosing_name(node: ast.AST) -> str:
    """上溯 AST，返回最近的函数/类名；若不存在则返回 <module>。"""
    cur = node
    while hasattr(cur, "_ast_parent"):
        cur = cur._ast_parent  # type: ignore[attr-defined]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        if isinstance(cur, ast.ClassDef):
            return cur.name
    return "<module>"


def test_no_silent_exception_swallow():
    """禁止 except Exception: pass / ...（静默吞异常）。新增违反必须修复。"""

    # 白名单采用 file:enclosing_func 指纹，并保留同一函数内的命中次数。
    known_violations = Counter(
        {
            # core/infrastructure/*
            "core/infrastructure/backup.py:maintenance_window": 3,
            "core/infrastructure/backup.py:backup": 2,
            "core/infrastructure/backup.py:_copy_db_file": 1,
            "core/infrastructure/database.py:_is_windows_lock_error": 1,
            "core/infrastructure/database.py:_restore_db_file_from_backup": 3,
            "core/infrastructure/database.py:_bootstrap_missing_tables_from_schema": 1,
            "core/infrastructure/database.py:_cleanup_probe_db": 1,
            "core/infrastructure/database.py:_preflight_migration_contract": 3,
            "core/infrastructure/database.py:ensure_schema": 2,
            "core/infrastructure/database.py:_migrate_with_backup": 2,
            "core/infrastructure/errors.py:__post_init__": 2,
            "core/infrastructure/migrations/common.py:fallback_log": 2,
            "core/infrastructure/transaction.py:transaction": 2,
            # core/models/*
            "core/models/_helpers.py:parse_int": 1,
            # core/services/common/*
            "core/services/common/openpyxl_backend.py:read": 1,
            "core/services/common/openpyxl_backend.py:write": 1,
            # core/services/process/*
            "core/services/process/unit_excel/parser.py:parse": 1,
            # core/services/report/*
            "core/services/report/exporters/xlsx.py:export_overdue_xlsx": 1,
            "core/services/report/exporters/xlsx.py:export_utilization_xlsx": 1,
            "core/services/report/exporters/xlsx.py:export_downtime_impact_xlsx": 1,
            # core/services/scheduler/*
            "core/services/scheduler/gantt_service.py:_critical_chain_cache_key": 1,
            "core/services/scheduler/gantt_service.py:_get_critical_chain": 2,
            "core/services/scheduler/schedule_summary.py:serialize_end_date": 1,
            # core/services/system/*
            "core/services/system/maintenance/backup_task.py:_safe_logger_emit": 1,
            "core/services/system/maintenance/cleanup_task.py:_safe_logger_emit": 1,
            # data/repositories/*
            "data/repositories/base_repo.py:_log_db_error": 1,
            "data/repositories/external_group_repo.py:update": 1,
            "data/repositories/schedule_history_repo.py:allocate_next_version": 1,
            # web/routes/*
            "web/routes/excel_utils.py:read_uploaded_xlsx": 1,
            "web/routes/scheduler_config.py:_load_manual_text_and_mtime": 1,
            "web/routes/system_backup.py:backup_restore": 2,
        }
    )

    def _scan_file(fp: str) -> List[str]:
        try:
            source = _read(fp)
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._ast_parent = node  # type: ignore[attr-defined]
        out: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for h in node.handlers:
                if not (isinstance(h.type, ast.Name) and h.type.id == "Exception"):
                    continue
                body = list(h.body or [])
                hit = False
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    hit = True
                elif len(body) == 1:
                    expr_stmt = body[0]
                    if isinstance(expr_stmt, ast.Expr) and isinstance(expr_stmt.value, ast.Constant):
                        if expr_stmt.value.value is Ellipsis:
                            hit = True
                if not hit:
                    continue
                out.append(f"{fp}:{_find_enclosing_name(h)}")
        return out

    current_violations: Counter = Counter()
    for fp in _collect_py_files(*CORE_DIRS):
        current_violations.update(_scan_file(fp))

    new_violations: List[str] = []
    for hit, count in sorted(current_violations.items()):
        allowed = int(known_violations.get(hit, 0))
        if count > allowed:
            new_violations.append(f"{hit}（当前 {count}，白名单 {allowed}）")

    assert not new_violations, (
        "新增静默吞异常（except Exception: pass / ...）违反：\n"
        + "\n".join(new_violations)
        + "\n\n如有合理理由，请添加到 known_violations 白名单并说明原因。"
    )

# ─── Fitness 4: 文件/函数规模 ─────────────────────────────────

def test_file_size_limit():
    """核心目录单文件不超过 500 行。"""
    violations = []
    for fp in _collect_py_files(*CORE_DIRS):
        if fp in _known_oversize_files():
            continue
        line_count = len(_read(fp).splitlines())
        if line_count > 500:
            violations.append(f"{fp}: {line_count} lines")
    assert not violations, "文件超 500 行（新增）:\n" + "\n".join(violations)


def test_known_oversize_entries_still_exceed_limit():
    """超长文件白名单中的条目必须仍然真实超限。"""
    stale_entries = []
    for fp in sorted(_known_oversize_files()):
        line_count = len(_read(fp).splitlines())
        if line_count <= 500:
            stale_entries.append(f"{fp}: {line_count} lines")
    assert not stale_entries, "超长文件白名单存在已失效登记:\n" + "\n".join(stale_entries)


# ─── Fitness 5: 圈复杂度门禁 ──────────────────────────────────

def test_cyclomatic_complexity_threshold():
    """核心目录单函数圈复杂度不超过 C 级（≤15）。

    注意：当前存在历史遗留的高复杂度函数，此测试用 known_violations
    白名单豁免它们。新增代码不可超标。
    """
    import pytest

    if importlib.util.find_spec("radon") is None:
        pytest.skip("radon not installed")

    try:
        radon_complexity = importlib.import_module("radon.complexity")
        cc_visit = getattr(radon_complexity, "cc_visit", None)
    except ImportError:
        pytest.skip("radon not installed")
    if not callable(cc_visit):
        pytest.skip("radon cc_visit unavailable")

    THRESHOLD = 15

    known_violations = {
        # --- Route 层（Excel confirm 路由普遍复杂） ---
        "web/routes/excel_demo.py:preview",
        "web/routes/excel_demo.py:confirm",
        "web/routes/personnel_excel_operators.py:excel_operator_confirm",
        "web/routes/personnel_excel_operator_calendar.py:excel_operator_calendar_confirm",
        "web/routes/process_excel_op_types.py:excel_op_type_confirm",
        "web/routes/process_excel_part_operation_hours.py:excel_part_op_hours_confirm",
        "web/routes/process_excel_routes.py:excel_routes_confirm",
        "web/routes/process_excel_suppliers.py:excel_supplier_confirm",
        "web/routes/scheduler_excel_calendar.py:excel_calendar_confirm",
        # --- ViewModel 层 ---
        "web/viewmodels/scheduler_analysis_vm.py:build_selected_details",
        # --- Service 层 ---
        "core/services/equipment/machine_downtime_service.py:create_by_scope",
        "core/services/personnel/operator_machine_service.py:apply_import_links",
        "core/services/process/part_service.py:delete_external_group",
        "core/services/process/part_service.py:calc_deletable_external_group_ids",
        "core/services/process/route_parser.py:parse",
        "core/services/report/calculations.py:compute_downtime_impact",
        "core/services/report/calculations.py:compute_utilization",
        "core/services/scheduler/config_service.py:ensure_defaults",
        "core/services/scheduler/config_validator.py:normalize_preset_snapshot",
        "core/services/scheduler/freeze_window.py:build_freeze_window_seed",
        "core/services/scheduler/gantt_range.py:resolve_week_range",
        "core/services/scheduler/operation_edit_service.py:update_external_operation",
        "core/services/scheduler/resource_pool_builder.py:load_machine_downtimes",
        "core/services/scheduler/resource_pool_builder.py:extend_downtime_map_for_resource_pool",
        "core/services/scheduler/schedule_optimizer.py:optimize_schedule",
        "core/services/scheduler/schedule_optimizer.py:_run_local_search",
        # --- Model 层（from_row 解析） ---
        "core/models/batch_operation.py:from_row",
        "core/models/calendar.py:from_row",
        "core/models/part_operation.py:from_row",
        # --- Infrastructure 层 ---
        "core/infrastructure/database.py:ensure_schema",
        "core/infrastructure/database.py:_migrate_with_backup",
        # --- Infrastructure / Route 历史热点（本轮显式登记技术债，不在 strict_mode 收口批次内继续大拆） ---
        "web/routes/equipment_excel_links.py:excel_link_confirm",
        "web/routes/personnel_excel_links.py:excel_link_confirm",
        "web/routes/system_backup.py:backup_restore",
        "core/infrastructure/backup.py:read_maintenance_lock_state",
        "core/infrastructure/backup.py:maintenance_window",
        # --- Existing known violations ---
        "core/infrastructure/transaction.py:transaction",
        "core/infrastructure/migrations/v1.py:_sanitize_batch_dates",
        "core/infrastructure/migrations/v4.py:_sanitize_field",
        # --- 阶段 04 最终验收：显式登记既有结构债，避免误判为本轮新增 ---
        "web/routes/personnel_pages.py:detail_page",
        "web/routes/scheduler_batches.py:batches_page",
        "web/viewmodels/scheduler_analysis_vm.py:build_freeze_display",
        "core/services/personnel/operator_machine_query_service.py:_normalize_row",
        "core/services/process/unit_excel/template_builder.py:_build_suppliers_rows",
        "core/services/scheduler/gantt_week_plan.py:build_week_plan_rows",
        "core/services/scheduler/resource_dispatch_excel.py:_summary_pairs",
        "core/services/scheduler/resource_dispatch_support.py:extract_overdue_batch_ids_with_meta",
        "core/services/scheduler/schedule_input_builder.py:_build_algo_operations_outcome",
        "core/services/scheduler/schedule_template_lookup.py:lookup_template_group_context_for_op",
    }

    new_violations = []
    scan_errors = []
    for fp in _collect_py_files(*CORE_DIRS):
        try:
            source = _read(fp)
            blocks = cast(Iterable[Any], cc_visit(source))
            for block in blocks:
                complexity = int(getattr(block, "complexity", 0) or 0)
                if complexity > THRESHOLD:
                    name = str(getattr(block, "name", ""))
                    lineno = int(getattr(block, "lineno", 0) or 0)
                    letter = str(getattr(block, "letter", "?"))
                    key = f"{fp}:{name}"
                    if key not in known_violations:
                        new_violations.append(
                            f"{fp}:{lineno} {name} "
                            f"complexity={complexity} (rank {letter})"
                        )
        except SyntaxError as exc:
            scan_errors.append(f"{fp}: SyntaxError: {exc}")
        except Exception as exc:
            scan_errors.append(f"{fp}: {type(exc).__name__}: {exc}")

    assert not scan_errors, "复杂度扫描失败:\n" + "\n".join(scan_errors)

    assert not new_violations, (
        f"新增的高复杂度函数（超过 C 级/{THRESHOLD}）:\n"
        + "\n".join(new_violations)
        + "\n\n请拆分函数或添加到 known_violations 白名单（需说明原因）。"
    )


# ─── Fitness 6: 命名规范 ──────────────────────────────────────

def test_file_naming_snake_case():
    """核心目录文件名必须是 snake_case。"""
    violations = []
    for fp in _collect_py_files(*CORE_DIRS):
        fname = os.path.basename(fp)[:-3]
        if fname != fname.lower():
            violations.append(fp)
    assert not violations, "文件名非 snake_case:\n" + "\n".join(violations)
