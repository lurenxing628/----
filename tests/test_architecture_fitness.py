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
from typing import Dict, List, Set, Tuple

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
            pair = tuple(sorted([pkg_a, dep]))
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


def test_no_silent_exception_swallow():
    """禁止 except Exception: pass / ...（静默吞异常）。新增违反必须修复。"""

    known_violations = {
        # core/infrastructure/*
        "core/infrastructure/backup.py:42",
        "core/infrastructure/backup.py:69",
        "core/infrastructure/backup.py:91",
        "core/infrastructure/backup.py:111",
        "core/infrastructure/backup.py:136",
        "core/infrastructure/backup.py:156",
        "core/infrastructure/backup.py:161",
        "core/infrastructure/backup.py:165",
        "core/infrastructure/database.py:20",
        "core/infrastructure/database.py:36",
        "core/infrastructure/database.py:59",
        "core/infrastructure/database.py:70",
        "core/infrastructure/database.py:74",
        "core/infrastructure/database.py:80",
        "core/infrastructure/database.py:124",
        "core/infrastructure/database.py:170",
        "core/infrastructure/database.py:180",
        "core/infrastructure/database.py:219",
        "core/infrastructure/database.py:295",
        "core/infrastructure/database.py:305",
        "core/infrastructure/database.py:320",
        "core/infrastructure/database.py:344",
        "core/infrastructure/database.py:353",
        "core/infrastructure/database.py:359",
        "core/infrastructure/database.py:363",
        "core/infrastructure/database.py:373",
        "core/infrastructure/database.py:379",
        "core/infrastructure/errors.py:75",
        "core/infrastructure/errors.py:81",
        "core/infrastructure/logging.py:149",
        "core/infrastructure/migrations/v1.py:65",
        "core/infrastructure/migrations/v1.py:80",
        "core/infrastructure/migrations/v1.py:112",
        "core/infrastructure/migrations/v1.py:187",
        "core/infrastructure/migrations/v1.py:196",
        "core/infrastructure/migrations/v2.py:17",
        "core/infrastructure/migrations/v3.py:19",
        "core/infrastructure/migrations/v3.py:28",
        "core/infrastructure/migrations/v4.py:62",
        "core/infrastructure/migrations/v4.py:80",
        "core/infrastructure/migrations/v4.py:102",
        "core/infrastructure/migrations/v4.py:124",
        "core/infrastructure/migrations/v4.py:147",
        "core/infrastructure/migrations/v4.py:160",
        "core/infrastructure/transaction.py:103",
        "core/infrastructure/transaction.py:125",
        "core/infrastructure/transaction.py:136",
        # core/models/*
        "core/models/_helpers.py:60",
        # core/services/common/*
        "core/services/common/excel_templates.py:22",
        "core/services/common/openpyxl_backend.py:57",
        "core/services/common/openpyxl_backend.py:92",
        "core/services/common/pandas_backend.py:72",
        # core/services/process/*
        "core/services/process/part_service.py:121",
        "core/services/process/route_parser.py:248",
        "core/services/process/unit_excel/exporter.py:36",
        "core/services/process/unit_excel/parser.py:107",
        # core/services/report/*
        "core/services/report/exporters/xlsx.py:36",
        "core/services/report/exporters/xlsx.py:79",
        "core/services/report/exporters/xlsx.py:107",
        # core/services/scheduler/*
        "core/services/scheduler/gantt_service.py:86",
        "core/services/scheduler/gantt_service.py:97",
        "core/services/scheduler/gantt_service.py:119",
        "core/services/scheduler/schedule_summary.py:23",
        "core/services/scheduler/schedule_summary.py:106",
        "core/services/scheduler/schedule_summary.py:112",
        "core/services/scheduler/schedule_summary.py:162",
        "core/services/scheduler/resource_pool_builder.py:60",
        "core/services/scheduler/resource_pool_builder.py:68",
        "core/services/scheduler/resource_pool_builder.py:184",
        "core/services/scheduler/resource_pool_builder.py:240",
        "core/services/scheduler/resource_pool_builder.py:248",
        "core/services/scheduler/gantt_tasks.py:216",
        "core/services/scheduler/gantt_critical_chain.py:158",
        # core/services/system/*
        "core/services/system/maintenance/backup_task.py:90",
        "core/services/system/maintenance/cleanup_task.py:164",
        "core/services/system/maintenance/cleanup_task.py:248",
        # data/repositories/*
        "data/repositories/base_repo.py:166",
        "data/repositories/external_group_repo.py:78",
        "data/repositories/schedule_history_repo.py:91",
        # web/routes/*
        "web/routes/excel_utils.py:109",
        "web/routes/scheduler_config.py:30",
        "web/routes/scheduler_config.py:94",
        "web/routes/scheduler_config.py:268",
        "web/routes/system_backup.py:212",
        "web/routes/system_backup.py:252",
        "web/routes/system_ui_mode.py:35",
        "web/routes/system_ui_mode.py:48",
        "web/routes/system_utils.py:100",
    }

    # 白名单采用“按文件计数上限”策略：
    # - 允许减少（修复/重构后吞异常点变少）
    # - 禁止增加（新增 except Exception: pass/...）
    # 目的：避免因机械插入 import/拆分函数导致行号漂移而误判“新增”。
    known_counts: Dict[str, int] = {}
    for v in known_violations:
        try:
            fp, _ = v.rsplit(":", 1)
        except ValueError:
            continue
        known_counts[fp] = int(known_counts.get(fp, 0)) + 1

    def _scan_file(fp: str) -> List[str]:
        try:
            tree = ast.parse(_read(fp), filename=fp)
        except SyntaxError:
            return []
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
                elif (
                    len(body) == 1
                    and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and body[0].value.value is Ellipsis
                ):
                    hit = True
                if hit:
                    out.append(f"{fp}:{h.lineno}")
        return out

    violations_by_file: Dict[str, List[str]] = {}
    for fp in _collect_py_files(*CORE_DIRS):
        hits = _scan_file(fp)
        if hits:
            violations_by_file[fp] = hits

    new_files = []
    for fp, hits in sorted(violations_by_file.items(), key=lambda x: x[0]):
        expected_max = int(known_counts.get(fp, 0))
        if len(hits) > expected_max:
            new_files.append(
                f"{fp}: expected<={expected_max} got={len(hits)}\n  "
                + "\n  ".join(sorted(hits))
            )

    assert not new_files, (
        "新增静默吞异常（except Exception: pass / ...）违反（按文件计数上限判定）：\n"
        + "\n".join(new_files)
        + "\n\n如有合理理由，请添加到 known_violations 白名单并说明原因。"
    )


# ─── Fitness 4: 文件/函数规模 ─────────────────────────────────

def test_file_size_limit():
    """核心目录单文件不超过 500 行。"""
    known_oversize = {
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_service.py",
    }
    violations = []
    for fp in _collect_py_files(*CORE_DIRS):
        if fp in known_oversize:
            continue
        line_count = len(_read(fp).splitlines())
        if line_count > 500:
            violations.append(f"{fp}: {line_count} lines")
    assert not violations, "文件超 500 行（新增）:\n" + "\n".join(violations)


# ─── Fitness 5: 圈复杂度门禁 ──────────────────────────────────

def test_cyclomatic_complexity_threshold():
    """核心目录单函数圈复杂度不超过 C 级（≤15）。

    注意：当前存在历史遗留的高复杂度函数，此测试用 known_violations
    白名单豁免它们。新增代码不可超标。
    """
    try:
        from radon.complexity import cc_visit
    except ImportError:
        import pytest
        pytest.skip("radon not installed")

    THRESHOLD = 15

    known_violations = {
        # --- Route 层（Excel confirm 路由普遍复杂） ---
        "web/routes/equipment_excel_machines.py:excel_machine_confirm",
        "web/routes/excel_demo.py:preview",
        "web/routes/excel_demo.py:confirm",
        "web/routes/personnel_excel_operators.py:excel_operator_confirm",
        "web/routes/personnel_excel_operator_calendar.py:excel_operator_calendar_confirm",
        "web/routes/process_excel_op_types.py:excel_op_type_confirm",
        "web/routes/process_excel_part_operation_hours.py:excel_part_op_hours_confirm",
        "web/routes/process_excel_routes.py:excel_routes_confirm",
        "web/routes/process_excel_suppliers.py:excel_supplier_confirm",
        "web/routes/process_parts.py:part_detail",
        "web/routes/scheduler_analysis.py:analysis_page",
        "web/routes/scheduler_batches.py:bulk_update_batches",
        "web/routes/scheduler_batch_detail.py:batch_detail",
        "web/routes/scheduler_excel_batches.py:excel_batches_confirm",
        "web/routes/scheduler_excel_calendar.py:excel_calendar_confirm",
        "web/routes/scheduler_run.py:run_schedule",
        "web/routes/scheduler_week_plan.py:week_plan_export",
        "web/routes/system_logs.py:logs_page",
        # --- ViewModel 层 ---
        "web/viewmodels/scheduler_analysis_vm.py:build_selected_details",
        # --- Service 层 ---
        "core/services/common/openpyxl_backend.py:read",
        "core/services/common/pandas_backend.py:read",
        "core/services/equipment/machine_downtime_service.py:create_by_scope",
        "core/services/personnel/operator_machine_service.py:preview_import_links",
        "core/services/personnel/operator_machine_service.py:apply_import_links",
        "core/services/process/deletion_validator.py:can_delete",
        "core/services/process/external_group_service.py:set_merge_mode",
        "core/services/process/part_service.py:delete_external_group",
        "core/services/process/part_service.py:calc_deletable_external_group_ids",
        "core/services/process/route_parser.py:parse",
        "core/services/process/unit_excel/parser.py:parse",
        "core/services/process/unit_excel/template_builder.py:build",
        "core/services/report/calculations.py:compute_downtime_impact",
        "core/services/report/calculations.py:compute_utilization",
        "core/services/scheduler/batch_service.py:update",
        "core/services/scheduler/batch_service.py:create_batch_from_template_no_tx",
        "core/services/scheduler/calendar_engine.py:_policy_for_date",
        "core/services/scheduler/config_service.py:ensure_defaults",
        "core/services/scheduler/config_service.py:_snapshot_close",
        "core/services/scheduler/config_validator.py:normalize_preset_snapshot",
        "core/services/scheduler/freeze_window.py:build_freeze_window_seed",
        "core/services/scheduler/gantt_critical_chain.py:compute_critical_chain",
        "core/services/scheduler/gantt_range.py:resolve_week_range",
        "core/services/scheduler/gantt_tasks.py:build_tasks",
        "core/services/scheduler/operation_edit_service.py:update_internal_operation",
        "core/services/scheduler/operation_edit_service.py:update_external_operation",
        "core/services/scheduler/resource_pool_builder.py:build_resource_pool",
        "core/services/scheduler/resource_pool_builder.py:load_machine_downtimes",
        "core/services/scheduler/resource_pool_builder.py:extend_downtime_map_for_resource_pool",
        "core/services/scheduler/schedule_optimizer.py:optimize_schedule",
        "core/services/scheduler/schedule_optimizer.py:_run_local_search",
        "core/services/scheduler/schedule_persistence.py:persist_schedule",
        "core/services/scheduler/schedule_service.py:_get_template_and_group_for_op",
        "core/services/scheduler/schedule_service.py:_run_schedule_impl",
        "core/services/scheduler/schedule_summary.py:build_result_summary",
        # --- Model 层（from_row 解析） ---
        "core/models/batch_operation.py:from_row",
        "core/models/calendar.py:from_row",
        "core/models/part_operation.py:from_row",
        # --- Infrastructure 层 ---
        "core/infrastructure/backup.py:restore",
        "core/infrastructure/database.py:_restore_db_file_from_backup",
        "core/infrastructure/database.py:ensure_schema",
        "core/infrastructure/database.py:_migrate_with_backup",
        "core/infrastructure/transaction.py:transaction",
        "core/infrastructure/migrations/v1.py:_ensure_columns",
        "core/infrastructure/migrations/v1.py:_sanitize_batch_dates",
        "core/infrastructure/migrations/v4.py:_sanitize_field",
    }

    new_violations = []
    for fp in _collect_py_files(*CORE_DIRS):
        try:
            source = _read(fp)
            blocks = cc_visit(source)
            for block in blocks:
                if block.complexity > THRESHOLD:
                    key = f"{fp}:{block.name}"
                    if key not in known_violations:
                        new_violations.append(
                            f"{fp}:{block.lineno} {block.name} "
                            f"complexity={block.complexity} (rank {block.letter})"
                        )
        except (SyntaxError, Exception):
            pass

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
