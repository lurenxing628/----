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

from tools.quality_gate_support import (
    COMPLEXITY_THRESHOLD,
    CORE_DIRS,
    FILE_SIZE_LIMIT,
    UI_MODE_STARTUP_SCOPE_PATHS,
    architecture_complexity_allowlist_map,
    architecture_complexity_scan_map,
    architecture_oversize_allowlist_map,
    architecture_oversize_scan_map,
    architecture_repository_bundle_drift_entries,
    architecture_request_service_direct_assembly_entries,
    architecture_silent_allowlist_map,
    architecture_silent_scan_entries,
    load_ledger,
    scan_complexity_entries,
    scan_oversize_entries,
    validate_startup_samples,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LEDGER_CORE_DIRS = CORE_DIRS

CORE_DIRS = list(LEDGER_CORE_DIRS)
NO_WILDCARD_DIRS = list(LEDGER_CORE_DIRS)
GREEDY_REFACTOR_QUALITY_FILES = (
    "core/algorithms/ordering.py",
    "core/algorithms/greedy/scheduler.py",
    "core/algorithms/greedy/run_context.py",
    "core/algorithms/greedy/run_state.py",
    "core/algorithms/greedy/internal_slot.py",
    "core/algorithms/greedy/internal_operation.py",
    "core/algorithms/greedy/auto_assign.py",
    "core/algorithms/greedy/seed.py",
    "core/algorithms/greedy/dispatch/batch_order.py",
    "core/algorithms/greedy/dispatch/sgs.py",
    "core/algorithms/greedy/dispatch/sgs_scoring.py",
)


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


LOCAL_PARSE_HELPER_NAMES = {
    "_safe_float",
    "_safe_int",
    "_safe_seq",
    "safe_float",
    "safe_int",
    "safe_seq",
    "_cfg_float",
    "_cfg_int",
    "_get_float",
    "_get_int",
}
LOCAL_PARSE_HELPER_ALLOWLIST = {
    "core/services/scheduler/_sched_utils.py:_safe_int",
    "core/services/scheduler/batch_service.py:_safe_float",
    "core/services/system/system_config_service.py:_get_int",
}


def _import_module_function_aliases(module_ast: ast.Module) -> Set[str]:
    aliases: Set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "importlib":
            continue
        for alias in node.names:
            if alias.name == "import_module":
                aliases.add(alias.asname or alias.name)
    return aliases


def _importlib_module_aliases(module_ast: ast.Module) -> Set[str]:
    aliases: Set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "importlib":
                aliases.add(alias.asname or alias.name)
    return aliases


def _dynamic_import_target(
    node: ast.AST,
    *,
    import_module_aliases: Set[str],
    importlib_aliases: Set[str],
) -> str | None:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        return None
    if isinstance(node.func, ast.Name):
        if node.func.id == "__import__" or node.func.id in import_module_aliases:
            return first_arg.value
        return None
    if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
        if isinstance(node.func.value, ast.Name) and node.func.value.id in importlib_aliases:
            return first_arg.value
    return None


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

        import_module_aliases = _import_module_function_aliases(tree)
        importlib_aliases = _importlib_module_aliases(tree)

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
            else:
                mod = _dynamic_import_target(
                    node,
                    import_module_aliases=import_module_aliases,
                    importlib_aliases=importlib_aliases,
                )
                if mod and not _is_allowed_viewmodel_import(mod):
                    violations.append(f"{fp}:{getattr(node, 'lineno', 0) or 0}: dynamic import {mod}")

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
                continue

            if func_name in {"_add_state_event", "_add_counted_event"} and "code" in keywords:
                code = _string_constant(keywords.get("code"))
                if code:
                    used_codes.add(code)

            if func_name == "public_degradation_event_message" and node.args:
                code = _string_constant(node.args[0])
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


def test_no_silent_exception_swallow():
    """静默回退治理必须与台账逐条对齐，且启动链新增命中必须先登记。"""

    ledger = load_ledger(required=True)
    allowlist = architecture_silent_allowlist_map(ledger)
    scanned_entries = architecture_silent_scan_entries()
    scanned_map = {str(entry.get("id")): entry for entry in scanned_entries}

    new_entries = []
    mismatched_entries = []
    for entry_id, entry in sorted(scanned_map.items()):
        ledger_entry = allowlist.get(entry_id)
        if ledger_entry is None:
            new_entries.append(
                f"{entry.get('path')}:{entry.get('symbol')}:{entry.get('fallback_kind')}（id={entry_id}）"
            )
            continue
        if str(ledger_entry.get("fallback_kind")) != str(entry.get("fallback_kind")):
            mismatched_entries.append(
                f"{entry_id} fallback_kind 不一致：台账={ledger_entry.get('fallback_kind')} 实扫={entry.get('fallback_kind')}"
            )
        if str(entry.get("path")) in set(UI_MODE_STARTUP_SCOPE_PATHS) and str(ledger_entry.get("scope_tag")) != str(
            entry.get("scope_tag")
        ):
            mismatched_entries.append(
                f"{entry_id} scope_tag 不一致：台账={ledger_entry.get('scope_tag')} 实扫={entry.get('scope_tag')}"
            )

    stale_entries = []
    for entry_id, entry in sorted(allowlist.items()):
        if entry_id not in scanned_map:
            stale_entries.append(f"{entry_id}（{entry.get('path')}:{entry.get('symbol')}）")

    messages = []
    if new_entries:
        messages.append("未登记的新静默回退：\n" + "\n".join(new_entries))
    if mismatched_entries:
        messages.append("静默回退台账与当前扫描不一致：\n" + "\n".join(mismatched_entries))
    if stale_entries:
        messages.append("静默回退台账存在陈旧登记：\n" + "\n".join(stale_entries))
    assert not messages, "\n\n".join(messages)


def test_startup_silent_fallback_samples():
    """启动链样本点必须持续命中既定分类与 scope。"""

    validate_startup_samples()


def test_request_service_target_files_no_direct_assembly():
    """请求级容器已接管的目标文件不得再出现直接装配。"""

    entries = architecture_request_service_direct_assembly_entries()
    assert not entries, (
        "请求级容器目标文件仍存在直接装配:\n"
        + "\n".join(
            f"{entry.get('path')}:{entry.get('line')} {entry.get('rule')} {entry.get('target')}"
            for entry in entries
        )
    )


def test_repository_bundle_consumption_does_not_drift():
    """除 ScheduleService.__init__ 代理赋值外，不得扩散 _repos / repos 新消费面。"""

    entries = architecture_repository_bundle_drift_entries()
    assert not entries, (
        "检测到新的仓储束消费面:\n"
        + "\n".join(
            f"{entry.get('path')}:{entry.get('line')} {entry.get('chain')}"
            for entry in entries
        )
    )

# ─── Fitness 4: 文件/函数规模 ─────────────────────────────────

def test_file_size_limit():
    """三类规则专属范围内，未登记文件不得超过 500 行。"""

    ledger = load_ledger(required=True)
    allowlist = architecture_oversize_allowlist_map(ledger)
    scanned = architecture_oversize_scan_map()
    violations = []
    for path, item in sorted(scanned.items()):
        if path in allowlist:
            continue
        violations.append(f"{path}: {item.get('current_value')} lines")
    assert not violations, "文件超 500 行（新增）:\n" + "\n".join(violations)


def test_known_oversize_entries_still_exceed_limit():
    """超长文件白名单中的条目必须仍然真实超限。"""
    ledger = load_ledger(required=True)
    allowlist = architecture_oversize_allowlist_map(ledger)
    scanned = architecture_oversize_scan_map()
    stale_entries = []
    for path, entry in sorted(allowlist.items()):
        if path not in scanned:
            stale_entries.append(f"{path}: <= {FILE_SIZE_LIMIT} lines")
    assert not stale_entries, "超长文件白名单存在已失效登记:\n" + "\n".join(stale_entries)


def test_greedy_refactor_files_stay_under_quality_gate_limits():
    """scheduler 解耦后的算法边界必须留在主架构门禁里。"""

    oversize_entries = scan_oversize_entries(GREEDY_REFACTOR_QUALITY_FILES)
    complexity_entries = scan_complexity_entries(GREEDY_REFACTOR_QUALITY_FILES)
    messages = []
    if oversize_entries:
        messages.append(
            "greedy 解耦文件超 500 行:\n"
            + "\n".join(f"{item.get('path')}: {item.get('current_value')} lines" for item in oversize_entries)
        )
    if complexity_entries:
        messages.append(
            f"greedy 解耦文件存在超过 {COMPLEXITY_THRESHOLD} 的复杂函数:\n"
            + "\n".join(
                f"{item.get('path')}:{item.get('line')} {item.get('symbol')} "
                f"complexity={item.get('current_value')} (rank {item.get('rank')})"
                for item in complexity_entries
            )
        )
    assert not messages, "\n\n".join(messages)


# ─── Fitness 5: 圈复杂度门禁 ──────────────────────────────────

def test_cyclomatic_complexity_threshold():
    """三类规则专属范围内，未登记函数不得超过复杂度阈值。"""

    ledger = load_ledger(required=True)
    allowlist = architecture_complexity_allowlist_map(ledger)
    scanned = architecture_complexity_scan_map()
    new_violations = []
    for key, item in sorted(scanned.items()):
        if key in allowlist:
            continue
        new_violations.append(
            f"{item.get('path')}:{item.get('line')} {item.get('symbol')} "
            f"complexity={item.get('current_value')} (rank {item.get('rank')})"
        )
    assert not new_violations, (
        f"新增的高复杂度函数（超过 C 级/{COMPLEXITY_THRESHOLD}）:\n"
        + "\n".join(new_violations)
        + "\n\n请拆分函数或先登记治理台账。"
    )


def test_known_complexity_entries_still_exceed_threshold():
    """高复杂度白名单中的条目必须仍然真实超限。"""

    ledger = load_ledger(required=True)
    allowlist = architecture_complexity_allowlist_map(ledger)
    scanned = architecture_complexity_scan_map()
    stale_entries = []
    for key, entry in sorted(allowlist.items()):
        if key not in scanned:
            stale_entries.append(
                f"{entry.get('path')}:{entry.get('symbol')} 未再出现在超阈值扫描结果中"
                f"（可能已回落到 <= {COMPLEXITY_THRESHOLD}，或已改名/迁移）"
            )
    assert not stale_entries, "高复杂度白名单存在已失效登记:\n" + "\n".join(stale_entries)


# ─── Fitness 6: 命名规范 ──────────────────────────────────────

def test_file_naming_snake_case():
    """核心目录文件名必须是 snake_case。"""
    violations = []
    for fp in _collect_py_files(*CORE_DIRS):
        fname = os.path.basename(fp)[:-3]
        if fname != fname.lower():
            violations.append(fp)
    assert not violations, "文件名非 snake_case:\n" + "\n".join(violations)
