from __future__ import annotations

import ast
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from tools import check_full_test_debt, collect_full_test_debt
from tools.long_gate_collect import COLLECT_NODEIDS_REL, load_collect_nodeids
from tools.long_gate_fingerprint import diff_fingerprints
from tools.long_gate_schema import FULL_TEST_DEBT_NODE_CACHE_SCHEMA_VERSION, stable_json_hash
from tools.quality_gate_ledger import sort_ledger, validate_ledger
from tools.quality_gate_shared import (
    FORMAL_FULL_TEST_PYTEST_ARGS,
    LEDGER_BEGIN,
    LEDGER_END,
    LEDGER_PATH,
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL,
    QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL,
    QualityGateError,
    extract_json_code_block,
    iter_quality_gate_required_tests,
)
from tools.test_debt_registry import validate_current_candidate_payload
from tools.test_registry import iter_test_only_helper_impacts

NODE_CACHE_REL = QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL.replace("\\", "/")
LEDGER_REL = os.path.relpath(LEDGER_PATH, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))).replace(
    "\\",
    "/",
)
COLLECT_REL = COLLECT_NODEIDS_REL.replace("\\", "/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _repo_root(repo_root: str) -> str:
    return os.path.abspath(str(repo_root))


def _abs_path(repo_root: str, rel_path: str) -> str:
    return os.path.join(_repo_root(repo_root), str(rel_path).replace("\\", "/").replace("/", os.sep))


def _sha256_file(abs_path: str) -> str:
    hasher = hashlib.sha256()
    with open(abs_path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    normalized = dict(payload)
    normalized.pop("payload_hash", None)
    return f"sha256:{stable_json_hash(normalized)}"


def _read_json_object(repo_root: str, rel_path: str) -> Tuple[Optional[Dict[str, Any]], str]:
    abs_path = _abs_path(repo_root, rel_path)
    if not os.path.isfile(abs_path):
        return None, f"{rel_path} missing"
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{rel_path} unreadable/corrupt: {exc}"
    if not isinstance(payload, dict):
        return None, f"{rel_path} top-level value is not an object"
    return payload, ""


def _write_json_atomically(repo_root: str, rel_path: str, payload: Mapping[str, Any]) -> None:
    abs_path = _abs_path(repo_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=os.path.dirname(abs_path),
            prefix=f".{os.path.basename(abs_path)}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = handle.name
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, abs_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _git_head(repo_root: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return str(proc.stdout or "").strip() if int(proc.returncode) == 0 else ""


def _git_status(repo_root: str) -> List[str]:
    proc = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=_repo_root(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if int(proc.returncode) != 0:
        return ["git_status_unavailable"]
    return [line for line in str(proc.stdout or "").splitlines() if line.strip()]


def _nodeid_file(nodeid: str) -> str:
    return str(nodeid or "").split("::", 1)[0]


def _group_nodeids_by_file(nodeids: Sequence[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for nodeid in list(nodeids or []):
        file_path = _nodeid_file(str(nodeid))
        grouped.setdefault(file_path, []).append(str(nodeid))
    return {path: grouped[path] for path in sorted(grouped)}


def _validate_collect_payload(payload: Mapping[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    raw_nodeids = payload.get("nodeids")
    if payload.get("schema_version") != 1:
        return None, "collect_nodeids schema_version is invalid"
    if str(payload.get("status") or "") != "passed":
        return None, "collect_nodeids status is not passed"
    if not isinstance(raw_nodeids, list) or any(not isinstance(item, str) for item in raw_nodeids):
        return None, "collect_nodeids nodeids must be a list of strings"
    nodeids = [str(item) for item in raw_nodeids]
    if payload.get("nodeid_count") != len(nodeids):
        return None, "collect_nodeids nodeid_count does not match nodeids"
    if str(payload.get("nodeid_hash") or "") != stable_json_hash(nodeids):
        return None, "collect_nodeids nodeid_hash does not match nodeids"
    expected_by_file = _group_nodeids_by_file(nodeids)
    if payload.get("nodeids_by_file") != expected_by_file:
        return None, "collect_nodeids nodeids_by_file does not match nodeids"
    return {
        "schema_version": payload.get("schema_version"),
        "status": str(payload.get("status") or ""),
        "nodeids": nodeids,
        "nodeid_count": len(nodeids),
        "nodeid_hash": str(payload.get("nodeid_hash") or ""),
        "nodeids_by_file": expected_by_file,
        "pytest_version": str(payload.get("pytest_version") or ""),
        "generated_from_stdout_sha256": str(payload.get("generated_from_stdout_sha256") or ""),
        "collect_stdout_log_path": str(payload.get("collect_stdout_log_path") or "").replace("\\", "/"),
    }, ""


def _load_collect_snapshot(repo_root: str) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        payload = load_collect_nodeids(repo_root=repo_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"collect_nodeids payload is invalid: {exc}"
    return _validate_collect_payload(payload)


def _load_ledger_for_repo(repo_root: str) -> Dict[str, Any]:
    abs_path = _abs_path(repo_root, LEDGER_REL)
    if not os.path.isfile(abs_path):
        raise QualityGateError("治理台账不存在：开发文档/技术债务治理台账.md")
    with open(abs_path, encoding="utf-8") as handle:
        text = handle.read()
    ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")
    validate_ledger(ledger)
    return sort_ledger(ledger)


def _ledger_test_debt_nodeids(ledger: Mapping[str, Any]) -> Set[str]:
    test_debt = ledger.get("test_debt") if isinstance(ledger.get("test_debt"), dict) else {}
    entries = test_debt.get("entries") if isinstance(test_debt, dict) else []
    return {str(row.get("nodeid") or "") for row in list(entries or []) if isinstance(row, dict)}


def _fingerprint_files_by_path(fingerprint: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    components = fingerprint.get("components") if isinstance(fingerprint.get("components"), dict) else {}
    files_component = components.get("files") if isinstance(components, dict) else {}
    rows = files_component.get("files") if isinstance(files_component, dict) else []
    return {str(row.get("path") or ""): row for row in list(rows or []) if isinstance(row, dict)}


def _changed_paths_from_fingerprints(previous: Mapping[str, Any], current: Mapping[str, Any]) -> List[str]:
    previous_files = _fingerprint_files_by_path(previous)
    current_files = _fingerprint_files_by_path(current)
    paths: Set[str] = set(previous_files) | set(current_files)
    changed = []
    for path in sorted(paths):
        before = previous_files.get(path)
        after = current_files.get(path)
        if before is None or after is None:
            changed.append(path)
            continue
        if (
            before.get("exists") != after.get("exists")
            or before.get("kind") != after.get("kind")
            or before.get("sha256") != after.get("sha256")
        ):
            changed.append(path)
    if not changed and previous.get("hash") != current.get("hash"):
        changed.extend([str(item) for item in list(diff_fingerprints(previous, current).get("reasons") or [])])
    return changed


def _non_file_fingerprint_change_reason(previous: Mapping[str, Any], current: Mapping[str, Any]) -> str:
    if previous.get("schema_version") != current.get("schema_version"):
        return "fingerprint schema changed"
    previous_components = previous.get("components") if isinstance(previous.get("components"), dict) else {}
    current_components = current.get("components") if isinstance(current.get("components"), dict) else {}
    previous_checked = {key: value for key, value in previous_components.items() if key not in {"files", "collect_nodeids"}}
    current_checked = {key: value for key, value in current_components.items() if key not in {"files", "collect_nodeids"}}
    if stable_json_hash(previous_checked) == stable_json_hash(current_checked):
        return ""
    changed_keys = [
        key
        for key in sorted(set(previous_checked) | set(current_checked))
        if stable_json_hash(previous_checked.get(key)) != stable_json_hash(current_checked.get(key))
    ]
    return "non-file fingerprint changed: " + ", ".join(changed_keys or ["unknown"])


def _is_regular_test_file(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/")
    name = os.path.basename(normalized)
    if normalized == "conftest.py" or normalized.endswith("/conftest.py"):
        return False
    if not normalized.startswith("tests/") or normalized.count("/") != 1 or not normalized.endswith(".py"):
        return False
    if name.endswith("_helpers.py"):
        return False
    return name.startswith("test_") or name.startswith("regression_")


def _is_top_level_test_helper_file(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/")
    name = os.path.basename(normalized)
    return (
        normalized.startswith("tests/")
        and normalized.count("/") == 1
        and normalized.endswith(".py")
        and name.endswith("_helpers.py")
        and name != "conftest.py"
    )


def _module_names_for_test_path(path: str) -> Set[str]:
    normalized = str(path or "").replace("\\", "/")
    if not normalized.startswith("tests/") or not normalized.endswith(".py"):
        return set()
    module = normalized[:-3].replace("/", ".")
    stem = os.path.splitext(os.path.basename(normalized))[0]
    names = {module, stem}
    if module.startswith("tests."):
        names.add(module[len("tests.") :])
    return {name for name in names if name}


def _module_names_for_test_helper_path(path: str) -> Set[str]:
    normalized = str(path or "").replace("\\", "/")
    if not _is_top_level_test_helper_file(normalized):
        return set()
    stem = os.path.splitext(os.path.basename(normalized))[0]
    return {stem, f"tests.{stem}"}


def _dynamic_import_aliases(tree: ast.AST) -> Tuple[Set[str], Set[str]]:
    importlib_module_names = {"importlib"}
    import_module_function_names = {"import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if str(alias.name or "") == "importlib":
                    importlib_module_names.add(str(alias.asname or alias.name))
        elif isinstance(node, ast.ImportFrom) and str(node.module or "") == "importlib":
            for alias in node.names:
                if str(alias.name or "") == "import_module":
                    import_module_function_names.add(str(alias.asname or alias.name))
    return importlib_module_names, import_module_function_names


def _constant_texts(node: ast.AST) -> Tuple[Set[str], bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {str(node.value)}, True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: Set[str] = set()
        for item in node.elts:
            item_values, safe = _constant_texts(item)
            if not safe:
                return set(), False
            values.update(item_values)
        return values, True
    return set(), False


def _dunder_import_matches_changed_test_module(node: ast.Call, changed_modules: Set[str]) -> bool:
    if not node.args:
        return True
    first_arg = node.args[0]
    module_values, module_is_constant = _constant_texts(first_arg)
    if not module_is_constant:
        return True
    if any(value in changed_modules for value in module_values):
        return True
    fromlist_node: Optional[ast.AST] = None
    if len(node.args) >= 4:
        fromlist_node = node.args[3]
    for keyword in node.keywords:
        if keyword.arg == "fromlist":
            fromlist_node = keyword.value
            break
    if fromlist_node is None:
        return False
    fromlist_values, fromlist_is_constant = _constant_texts(fromlist_node)
    if not fromlist_is_constant:
        return any(
            value == "tests" or any(changed.startswith(value + ".") for changed in changed_modules)
            for value in module_values
        )
    for module_value in module_values:
        for fromlist_value in fromlist_values:
            candidate = f"{module_value}.{fromlist_value}".strip(".")
            if candidate in changed_modules or fromlist_value in changed_modules:
                return True
    return False


def _import_matches_changed_test_module(
    node: ast.AST,
    changed_modules: Set[str],
    *,
    importlib_module_names: Set[str],
    import_module_function_names: Set[str],
) -> bool:
    if isinstance(node, ast.Import):
        for alias in node.names:
            imported = str(alias.name or "")
            if imported in changed_modules:
                return True
        return False
    if isinstance(node, ast.ImportFrom):
        module = str(node.module or "")
        if module in changed_modules:
            return True
        if node.level > 0 and module:
            return module in {name.rsplit(".", 1)[-1] for name in changed_modules}
        return any(str(alias.name or "") in changed_modules for alias in node.names)
    if isinstance(node, ast.Call):
        func = node.func
        is_import_module = (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id in importlib_module_names
        )
        is_named_import_module = isinstance(func, ast.Name) and func.id in import_module_function_names
        is_dunder_import = isinstance(func, ast.Name) and func.id == "__import__"
        if not (is_import_module or is_named_import_module or is_dunder_import):
            return False
        if is_dunder_import:
            return _dunder_import_matches_changed_test_module(node, changed_modules)
        if not node.args:
            return True
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return str(first_arg.value) in changed_modules
        return True
    return False


def _call_is_dynamic_import(
    node: ast.Call,
    *,
    importlib_module_names: Set[str],
    import_module_function_names: Set[str],
) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "__import__":
        return True
    if isinstance(func, ast.Name) and func.id in import_module_function_names:
        return True
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id in importlib_module_names
    )


def _source_may_reference_helper_module(source: str, helper_modules: Set[str]) -> bool:
    helper_tokens = set(helper_modules)
    helper_tokens.update(name.rsplit(".", 1)[-1] for name in helper_modules)
    if any(token and token in source for token in helper_tokens):
        return True
    for stem in {name.rsplit(".", 1)[-1] for name in helper_modules}:
        parts = [part for part in stem.split("_") if part and part != "helpers"]
        if len(parts) >= 2 and all(part in source for part in parts):
            return True
    return False


def _dynamic_import_may_reference_helper(node: ast.Call, helper_modules: Set[str], source: str) -> bool:
    if not node.args:
        return _source_may_reference_helper_module(source, helper_modules)
    module_values, module_is_constant = _constant_texts(node.args[0])
    if not module_is_constant:
        return _source_may_reference_helper_module(source, helper_modules)
    if any(value in helper_modules for value in module_values):
        return True
    fromlist_node: Optional[ast.AST] = None
    if len(node.args) >= 4:
        fromlist_node = node.args[3]
    for keyword in node.keywords:
        if keyword.arg == "fromlist":
            fromlist_node = keyword.value
            break
    if fromlist_node is None:
        return False
    fromlist_values, fromlist_is_constant = _constant_texts(fromlist_node)
    if not fromlist_is_constant:
        return any(value == "tests" for value in module_values) and _source_may_reference_helper_module(
            source,
            helper_modules,
        )
    for module_value in module_values:
        for fromlist_value in fromlist_values:
            candidate = f"{module_value}.{fromlist_value}".strip(".")
            if candidate in helper_modules or fromlist_value in helper_modules:
                return True
    return False


def _static_import_references_helper(node: ast.AST, helper_modules: Set[str]) -> bool:
    helper_stems = {name.rsplit(".", 1)[-1] for name in helper_modules}
    if isinstance(node, ast.Import):
        return any(str(alias.name or "") in helper_modules for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = str(node.module or "")
        if module in helper_modules:
            return True
        if module == "tests":
            return any(str(alias.name or "") in helper_stems for alias in node.names)
        if node.level > 0:
            if module in helper_stems:
                return True
            if not module:
                return any(str(alias.name or "") in helper_stems for alias in node.names)
    return False


def _test_files_importing_helper(repo_root: str, helper_path: str) -> Tuple[List[str], str]:
    normalized_helper = str(helper_path or "").replace("\\", "/")
    helper_modules = _module_names_for_test_helper_path(normalized_helper)
    if not helper_modules:
        return [], f"test helper is not a top-level tests/*_helpers.py file: {normalized_helper}"
    importers: List[str] = []
    pattern = os.path.join(_repo_root(repo_root), "tests", "**", "*.py")
    for abs_path in sorted(glob.glob(pattern, recursive=True)):
        rel_path = os.path.relpath(abs_path, _repo_root(repo_root)).replace("\\", "/")
        if rel_path == normalized_helper:
            continue
        try:
            with open(abs_path, encoding="utf-8") as handle:
                source = handle.read()
            tree = ast.parse(source, filename=rel_path)
        except (OSError, UnicodeDecodeError, SyntaxError):
            return [], f"cannot safely inspect test helper imports: {rel_path}"
        importlib_module_names, import_module_function_names = _dynamic_import_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_is_dynamic_import(
                node,
                importlib_module_names=importlib_module_names,
                import_module_function_names=import_module_function_names,
            ):
                if _dynamic_import_may_reference_helper(node, helper_modules, source):
                    return [], f"dynamic test helper import cannot be proven safe: {rel_path}"
            if _static_import_references_helper(node, helper_modules):
                if _is_top_level_test_helper_file(rel_path):
                    return [], f"test helper is imported by another helper: {rel_path}"
                importers.append(rel_path)
                break
    return list(dict.fromkeys(importers)), ""


def _source_may_import_changed_test_module(source: str, changed_modules: Set[str]) -> bool:
    if "import_module" in source or "__import__" in source:
        return True
    tokens: Set[str] = set()
    for module in changed_modules:
        if module:
            tokens.add(module)
            tokens.add(module.rsplit(".", 1)[-1])
    return any(token in source for token in tokens)


def _changed_test_imported_elsewhere(repo_root: str, changed_test_files: Sequence[str]) -> str:
    changed = {str(path).replace("\\", "/") for path in changed_test_files}
    changed_modules: Set[str] = set()
    for path in changed:
        changed_modules.update(_module_names_for_test_path(path))
    if not changed_modules:
        return ""
    pattern = os.path.join(_repo_root(repo_root), "tests", "**", "*.py")
    for abs_path in sorted(glob.glob(pattern, recursive=True)):
        rel_path = os.path.relpath(abs_path, _repo_root(repo_root)).replace("\\", "/")
        if rel_path in changed:
            continue
        try:
            with open(abs_path, encoding="utf-8") as handle:
                source = handle.read()
            if not _source_may_import_changed_test_module(source, changed_modules):
                continue
            tree = ast.parse(source, filename=rel_path)
        except (OSError, UnicodeDecodeError, SyntaxError):
            return f"cannot safely inspect test imports: {rel_path}"
        importlib_module_names, import_module_function_names = _dynamic_import_aliases(tree)
        for node in ast.walk(tree):
            if _import_matches_changed_test_module(
                node,
                changed_modules,
                importlib_module_names=importlib_module_names,
                import_module_function_names=import_module_function_names,
            ):
                return f"changed test file is imported by another test file: {rel_path}"
    return ""


def _classify_incremental_plan(
    *,
    repo_root: str,
    previous_fingerprint: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    collect_snapshot: Mapping[str, Any],
    node_cache: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str]:
    non_file_reason = _non_file_fingerprint_change_reason(previous_fingerprint, current_fingerprint)
    if non_file_reason:
        return None, non_file_reason
    changed_paths = _changed_paths_from_fingerprints(previous_fingerprint, current_fingerprint)
    if not changed_paths:
        return None, "fingerprint changed but changed path list is empty"

    meaningful_paths = [path for path in changed_paths if path != COLLECT_REL]
    ledger_only = changed_paths == [LEDGER_REL]
    if not meaningful_paths and not ledger_only:
        return None, "only collect_nodeids changed"
    try:
        helper_impacts = iter_test_only_helper_impacts()
    except ValueError as exc:
        return None, str(exc)
    changed_regular_test_files: List[str] = []
    changed_helpers: List[str] = []
    if not ledger_only:
        for path in meaningful_paths:
            if _is_regular_test_file(path):
                changed_regular_test_files.append(path)
                continue
            if _is_top_level_test_helper_file(path):
                if path not in helper_impacts:
                    return None, f"test helper is not declared: {path}"
                changed_helpers.append(path)
                continue
            return None, "changed paths are outside safe test-file-only scope: " + ", ".join(changed_paths)

    nodeids_by_file = collect_snapshot.get("nodeids_by_file")
    if not isinstance(nodeids_by_file, dict):
        return None, "collect_nodeids.nodeids_by_file is invalid"
    test_hashes = node_cache.get("test_file_hashes")
    if not isinstance(test_hashes, dict):
        return None, "node cache test_file_hashes is invalid"
    cached_collect = node_cache.get("collect_nodeids")
    cached_by_file = cached_collect.get("nodeids_by_file") if isinstance(cached_collect, dict) else None
    if not isinstance(cached_by_file, dict):
        return None, "node cache collect_nodeids.nodeids_by_file is invalid"

    if ledger_only:
        hash_error = _validate_node_cache_test_file_hashes(repo_root, test_hashes, allowed_changed_files=())
        if hash_error:
            return None, hash_error
        return {
            "mode": "ledger_only",
            "changed_paths": changed_paths,
            "selected_nodeids": [],
            "changed_test_files": [],
            "safety_checks": {
                "collect_nodeids_valid": True,
                "node_cache_valid": True,
                "unchanged_test_hashes_valid": True,
                "unchanged_nodeid_mapping_valid": True,
                "changed_test_imported_elsewhere": False,
                "registered_debt_nodeid_in_changed_files": False,
            },
        }, ""

    declared_helper_impacts: Dict[str, List[str]] = {}
    actual_importing_test_files: List[str] = []
    for helper_path in changed_helpers:
        declared = list(helper_impacts.get(helper_path) or [])
        actual, import_error = _test_files_importing_helper(repo_root, helper_path)
        if import_error:
            return None, import_error
        actual_set = set(actual)
        declared_set = set(declared)
        extra = sorted(actual_set - declared_set)
        if extra:
            return None, f"test helper has undeclared importer: {helper_path} -> {extra[0]}"
        declared_helper_impacts[helper_path] = declared
        actual_importing_test_files.extend(actual)

    affected_test_files = list(changed_regular_test_files)
    for helper_path in changed_helpers:
        affected_test_files.extend(declared_helper_impacts.get(helper_path) or [])
    affected_test_files.extend(actual_importing_test_files)
    affected_test_files = list(dict.fromkeys(affected_test_files))

    selected: List[str] = []
    ledger_nodeids = _ledger_test_debt_nodeids(ledger)
    helper_affected_files = set(affected_test_files) - set(changed_regular_test_files)
    for path in affected_test_files:
        mapped = nodeids_by_file.get(path)
        if not isinstance(mapped, list) or not mapped or any(not isinstance(item, str) for item in mapped):
            if path in helper_affected_files:
                return None, f"helper impact target has no trusted nodeid mapping: {path}"
            return None, f"changed test file has no trusted nodeid mapping: {path}"
        if any(str(item) in ledger_nodeids for item in mapped):
            if path in helper_affected_files:
                return None, f"helper impact target contains registered full-test-debt nodeid: {path}"
            return None, f"changed test file contains registered full-test-debt nodeid: {path}"
        selected.extend(str(item) for item in mapped)

    import_error = _changed_test_imported_elsewhere(repo_root, affected_test_files)
    if import_error:
        return None, import_error

    changed_file_set = set(affected_test_files)
    for path in sorted(set(str(item) for item in nodeids_by_file) | set(str(item) for item in cached_by_file)):
        if path in changed_file_set:
            continue
        if nodeids_by_file.get(path) != cached_by_file.get(path):
            return None, f"nodeid mapping changed outside changed test files: {path}"

    hash_error = _validate_node_cache_test_file_hashes(
        repo_root,
        test_hashes,
        allowed_changed_files=affected_test_files,
    )
    if hash_error:
        return None, hash_error

    return {
        "mode": "nodeid_incremental",
        "changed_paths": changed_paths,
        "changed_test_files": affected_test_files,
        "changed_helpers": changed_helpers,
        "declared_helper_impacts": declared_helper_impacts,
        "actual_importing_test_files": list(dict.fromkeys(actual_importing_test_files)),
        "affected_test_files": affected_test_files,
        "selected_nodeids": list(dict.fromkeys(selected)),
        "safety_checks": {
            "collect_nodeids_valid": True,
            "node_cache_valid": True,
            "unchanged_test_hashes_valid": True,
            "unchanged_nodeid_mapping_valid": True,
            "changed_test_imported_elsewhere": False,
            "registered_debt_nodeid_in_changed_files": False,
            "declared_helper_impacts_valid": True,
            "actual_helper_imports_within_declared_impacts": True,
        },
    }, ""


def _validate_node_cache_test_file_hashes(
    repo_root: str,
    test_hashes: Mapping[str, Any],
    *,
    allowed_changed_files: Sequence[str],
) -> str:
    allowed = {str(path).replace("\\", "/") for path in allowed_changed_files}
    for path, cached in test_hashes.items():
        normalized = str(path).replace("\\", "/")
        if normalized in allowed:
            continue
        abs_path = _abs_path(repo_root, normalized)
        current_hash = _sha256_file(abs_path) if os.path.isfile(abs_path) else ""
        if current_hash != str(cached):
            return f"node cache test file hash mismatch outside changed files: {normalized}"
    return ""


def _validated_previous_success(
    *,
    repo_root: str,
    decision: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str]:
    previous = evaluation.get("validated_success") if isinstance(evaluation.get("validated_success"), dict) else None
    result_path = str(decision.get("previous_result_path") or "").replace("\\", "/")
    if previous is None and result_path:
        previous, error = _read_json_object(repo_root, result_path)
        if error:
            return None, error
    if not isinstance(previous, dict):
        return None, "previous success cache is missing"
    if str(previous.get("status") or "") != "passed":
        return None, "previous success cache is not passed"
    returncode = previous.get("returncode")
    if not isinstance(returncode, int) or isinstance(returncode, bool):
        return None, "previous success cache returncode is invalid"
    if returncode != 0:
        return None, "previous success cache returncode is not zero"
    if any(bool(previous.get(field)) for field in ("timed_out", "interrupted", "partial_write")):
        return None, "previous success cache is incomplete"
    for hash_field, log_field in (("stdout_sha256", "stdout_log_path"), ("stderr_sha256", "stderr_log_path")):
        log_rel = str(previous.get(log_field) or "").replace("\\", "/")
        if not log_rel:
            return None, f"previous {log_field} is missing"
        log_abs = _abs_path(repo_root, log_rel)
        if not os.path.isfile(log_abs):
            return None, f"previous log is missing: {log_rel}"
        if _sha256_file(log_abs) != str(previous.get(hash_field) or ""):
            return None, f"previous log hash mismatch: {log_rel}"
    return dict(previous), ""


def _load_node_cache(repo_root: str, previous_success: Mapping[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    payload, error = _read_json_object(repo_root, NODE_CACHE_REL)
    if error:
        return None, error
    assert payload is not None
    if payload.get("schema_version") != FULL_TEST_DEBT_NODE_CACHE_SCHEMA_VERSION:
        return None, "node cache schema_version mismatch"
    if payload.get("payload_hash") != _payload_hash(payload):
        return None, "node cache payload_hash mismatch"
    output_rows = {
        str(row.get("path") or "").replace("\\", "/"): str(row.get("sha256") or "")
        for row in list(previous_success.get("output_files") or [])
        if isinstance(row, dict)
    }
    expected_node_cache_hash = output_rows.get(NODE_CACHE_REL)
    if not expected_node_cache_hash:
        return None, "previous success did not declare node cache output"
    if _sha256_file(_abs_path(repo_root, NODE_CACHE_REL)) != expected_node_cache_hash:
        return None, "node cache output hash mismatch"
    for field in (
        "fingerprint",
        "ledger_sha256",
        "files_content_hash",
        "current_payload",
        "summary",
        "collect_nodeids",
        "test_file_hashes",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_log_path",
        "stderr_log_path",
    ):
        if field not in payload:
            return None, f"node cache missing required field: {field}"
    if not isinstance(payload.get("fingerprint"), dict):
        return None, "node cache fingerprint is invalid"
    if str(payload.get("fingerprint_hash") or "") != str(previous_success.get("fingerprint_hash") or ""):
        return None, "node cache fingerprint_hash mismatch"
    if str(payload["fingerprint"].get("hash") or "") != str(payload.get("fingerprint_hash") or ""):
        return None, "node cache fingerprint hash mismatch"
    for hash_field, log_field in (("stdout_sha256", "stdout_log_path"), ("stderr_sha256", "stderr_log_path")):
        log_rel = str(payload.get(log_field) or "").replace("\\", "/")
        if not log_rel:
            return None, f"node cache {log_field} is missing"
        log_abs = _abs_path(repo_root, log_rel)
        if not os.path.isfile(log_abs):
            return None, f"node cache log is missing: {log_rel}"
        if _sha256_file(log_abs) != str(payload.get(hash_field) or ""):
            return None, f"node cache log hash mismatch: {log_rel}"
    current_payload = payload.get("current_payload")
    summary = payload.get("summary")
    if not isinstance(current_payload, dict) or not isinstance(summary, dict):
        return None, "node cache current payload or summary is invalid"
    collect_snapshot, collect_error = _validate_collect_payload(payload.get("collect_nodeids", {}))
    if collect_error:
        return None, f"node cache collect_nodeids is invalid: {collect_error}"
    test_hashes = payload.get("test_file_hashes")
    if not isinstance(test_hashes, dict) or any(not isinstance(key, str) for key in test_hashes):
        return None, "node cache test_file_hashes is invalid"
    collect_files = set(str(path) for path in dict(collect_snapshot.get("nodeids_by_file") or {}))
    cached_hash_files = set(str(path) for path in test_hashes)
    if cached_hash_files != collect_files:
        return None, "node cache test_file_hashes does not cover collect_nodeids files"
    payload_nodeids = current_payload.get("collected_nodeids")
    collect_nodeids = collect_snapshot.get("nodeids")
    if (
        not isinstance(payload_nodeids, list)
        or any(not isinstance(item, str) for item in payload_nodeids)
        or payload_nodeids != collect_nodeids
    ):
        return None, "node cache current payload collected_nodeids does not match collect_nodeids"
    if f"sha256:{stable_json_hash(current_payload)}" != str(payload.get("current_payload_hash") or ""):
        return None, "node cache current payload hash mismatch"
    if f"sha256:{stable_json_hash(summary)}" != str(payload.get("summary_hash") or ""):
        return None, "node cache summary hash mismatch"
    try:
        validate_current_candidate_payload(current_payload, expected_nodeids=[])
    except QualityGateError as exc:
        return None, f"node cache current payload is invalid: {exc}"
    payload["collect_nodeids"] = collect_snapshot
    return payload, ""


def _read_previous_success_for_diagnostics(
    *,
    repo_root: str,
    decision: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str]:
    previous = evaluation.get("validated_success") if isinstance(evaluation.get("validated_success"), dict) else None
    result_path = str(decision.get("previous_result_path") or "").replace("\\", "/")
    if previous is None and result_path:
        previous, _error = _read_json_object(repo_root, result_path)
    return dict(previous) if isinstance(previous, dict) else None, result_path


def _node_cache_diagnostics(repo_root: str, node_cache: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    payload: Optional[Mapping[str, Any]] = node_cache
    error = ""
    if payload is None:
        loaded, error = _read_json_object(repo_root, NODE_CACHE_REL)
        payload = loaded
    diagnostics: Dict[str, Any] = {
        "node_cache_path": NODE_CACHE_REL,
        "node_cache_schema_version": None,
        "node_cache_collect_nodeid_count": "missing legacy diagnostic field",
        "node_cache_collect_nodeids_by_file_count": "missing legacy diagnostic field",
    }
    if error:
        diagnostics["node_cache_error"] = error
        return diagnostics
    if not isinstance(payload, Mapping):
        diagnostics["node_cache_error"] = "node cache is missing"
        return diagnostics
    diagnostics["node_cache_schema_version"] = payload.get("schema_version")
    count = payload.get("collected_nodeid_count")
    by_file_count = payload.get("collect_nodeids_by_file_count")
    collect_snapshot = payload.get("collect_nodeids") if isinstance(payload.get("collect_nodeids"), dict) else {}
    if isinstance(count, int) and not isinstance(count, bool):
        diagnostics["node_cache_collect_nodeid_count"] = int(count)
    elif isinstance(collect_snapshot.get("nodeid_count"), int) and not isinstance(collect_snapshot.get("nodeid_count"), bool):
        diagnostics["node_cache_collect_nodeid_count"] = int(collect_snapshot.get("nodeid_count"))
    if isinstance(by_file_count, int) and not isinstance(by_file_count, bool):
        diagnostics["node_cache_collect_nodeids_by_file_count"] = int(by_file_count)
    elif isinstance(collect_snapshot.get("nodeids_by_file"), dict):
        diagnostics["node_cache_collect_nodeids_by_file_count"] = len(dict(collect_snapshot.get("nodeids_by_file") or {}))
    return diagnostics


def _special_explain_diagnostics(
    *,
    repo_root: str,
    decision: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    fallback_reason: str,
    previous_success: Optional[Mapping[str, Any]] = None,
    node_cache: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    raw_previous, previous_path = _read_previous_success_for_diagnostics(
        repo_root=repo_root,
        decision=decision,
        evaluation=evaluation,
    )
    previous_for_display = previous_success if isinstance(previous_success, Mapping) else raw_previous
    diagnostics = {
        "previous_success_path": previous_path,
        "previous_success_returncode": previous_for_display.get("returncode")
        if isinstance(previous_for_display, Mapping)
        else None,
        "fallback_reason": str(fallback_reason or ""),
    }
    diagnostics.update(_node_cache_diagnostics(repo_root, node_cache=node_cache))
    return diagnostics


def _test_file_hashes(repo_root: str, nodeids_by_file: Mapping[str, Any]) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for path in sorted(str(item) for item in nodeids_by_file):
        abs_path = _abs_path(repo_root, path)
        rows[path] = _sha256_file(abs_path) if os.path.isfile(abs_path) else ""
    return rows


def write_full_test_debt_node_cache_after_success(
    *,
    repo_root: str,
    entry: Mapping[str, Any],
    fingerprint: Mapping[str, Any],
    result: Mapping[str, Any],
    cache_dir: str,
) -> str:
    collect_snapshot, collect_error = _load_collect_snapshot(repo_root)
    if collect_error:
        raise QualityGateError("无法写入 node cache：" + collect_error)
    current_payload, current_error = _read_json_object(repo_root, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL)
    summary, summary_error = _read_json_object(repo_root, QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL)
    if current_error or summary_error:
        raise QualityGateError("无法写入 node cache：" + (current_error or summary_error))
    assert collect_snapshot is not None and current_payload is not None and summary is not None
    cache_root = str(cache_dir or "evidence/QualityGate/long_gate").replace("\\", "/")
    success_stdout_log_path = f"{cache_root}/logs/full_test_debt.stdout.log"
    success_stderr_log_path = f"{cache_root}/logs/full_test_debt.stderr.log"
    payload: Dict[str, Any] = {
        "schema_version": FULL_TEST_DEBT_NODE_CACHE_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "entry_id": str(entry.get("entry_id") or "full_test_debt"),
        "cache_dir": cache_root,
        "previous_result_path": os.path.join(
            cache_root,
            "results",
            "full_test_debt.success.json",
        ).replace("\\", "/"),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "fingerprint": dict(fingerprint),
        "files_content_hash": str(
            dict(dict(fingerprint.get("components") or {}).get("files") or {}).get("content_hash") or ""
        ),
        "ledger_sha256": _sha256_file(_abs_path(repo_root, LEDGER_REL))
        if os.path.isfile(_abs_path(repo_root, LEDGER_REL))
        else "",
        "head_sha": _git_head(repo_root),
        "execution_mode": str(result.get("execution_mode") or "executed"),
        "result_returncode": int(result.get("returncode"))
        if isinstance(result.get("returncode"), int) and not isinstance(result.get("returncode"), bool)
        else None,
        "collect_nodeids": collect_snapshot,
        "collected_nodeid_count": int(collect_snapshot.get("nodeid_count") or 0),
        "collect_nodeids_by_file_count": len(dict(collect_snapshot.get("nodeids_by_file") or {})),
        "collect_nodeid_hash": str(collect_snapshot.get("nodeid_hash") or ""),
        "test_file_hashes": _test_file_hashes(repo_root, collect_snapshot.get("nodeids_by_file", {})),
        "current_payload": current_payload,
        "current_payload_hash": f"sha256:{stable_json_hash(current_payload)}",
        "summary": summary,
        "summary_hash": f"sha256:{stable_json_hash(summary)}",
        "stdout_sha256": str(result.get("stdout_sha256") or _sha256_text(str(result.get("stdout") or ""))),
        "stderr_sha256": str(result.get("stderr_sha256") or _sha256_text(str(result.get("stderr") or ""))),
        "stdout_log_path": success_stdout_log_path,
        "stderr_log_path": success_stderr_log_path,
    }
    payload["payload_hash"] = _payload_hash(payload)
    _write_json_atomically(repo_root, NODE_CACHE_REL, payload)
    return NODE_CACHE_REL


def _run_incremental_collector(repo_root: str, nodeids: Sequence[str]) -> Dict[str, Any]:
    pytest_args = [*list(nodeids), "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
    args = [
        sys.executable,
        "tools/collect_full_test_debt.py",
        "--baseline-kind",
        "after_main_style_isolation",
        "--no-current-payload",
        "--repo-root",
        _repo_root(repo_root),
        "--",
        *pytest_args,
    ]
    proc = subprocess.run(
        args,
        cwd=_repo_root(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = check_full_test_debt.parse_collector_payload(str(proc.stdout or ""), str(proc.stderr or ""))
        payload_exitstatus = int(payload.get("exitstatus") or 0)
    except QualityGateError as exc:
        return {
            "stdout": str(proc.stdout or ""),
            "stderr": str(proc.stderr or "") + f"\nERROR: {exc}\n",
            "returncode": 2,
            "payload": None,
            "pytest_args": pytest_args,
            "collector_contract_error": True,
        }
    if int(proc.returncode) != payload_exitstatus:
        return {
            "stdout": str(proc.stdout or ""),
            "stderr": str(proc.stderr or "")
            + f"\nERROR: collector returncode 与 payload.exitstatus 不一致：{proc.returncode} != {payload_exitstatus}\n",
            "returncode": 2,
            "payload": payload,
            "pytest_args": pytest_args,
            "collector_contract_error": True,
        }
    if int(proc.returncode) != 0:
        return {
            "stdout": str(proc.stdout or ""),
            "stderr": str(proc.stderr or ""),
            "returncode": int(proc.returncode),
            "payload": payload,
            "pytest_args": pytest_args,
            "collector_contract_error": False,
        }
    return {
        "stdout": str(proc.stdout or ""),
        "stderr": str(proc.stderr or ""),
        "returncode": 0,
        "payload": payload,
        "pytest_args": pytest_args,
        "collector_contract_error": False,
    }


def _merge_payload(
    *,
    repo_root: str,
    old_payload: Mapping[str, Any],
    incremental_payload: Mapping[str, Any],
    collect_snapshot: Mapping[str, Any],
    node_cache: Mapping[str, Any],
    changed_test_files: Sequence[str],
    selected_nodeids: Sequence[str],
    pytest_args: Sequence[str],
    incremental_plan: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    changed_files = {str(path) for path in changed_test_files}
    plan = incremental_plan if isinstance(incremental_plan, Mapping) else {}

    def keep_report(report: Mapping[str, Any]) -> bool:
        return _nodeid_file(str(report.get("nodeid") or "")) not in changed_files

    def keep_error(error: Mapping[str, Any]) -> bool:
        return _nodeid_file(str(error.get("nodeid") or "")) not in changed_files

    reports = [
        dict(report)
        for report in list(old_payload.get("reports") or [])
        if isinstance(report, dict) and keep_report(report)
    ]
    reports.extend(
        dict(report) for report in list(incremental_payload.get("reports") or []) if isinstance(report, dict)
    )
    collection_errors = [
        dict(error)
        for error in list(old_payload.get("collection_errors") or [])
        if isinstance(error, dict) and keep_error(error)
    ]
    collection_errors.extend(
        dict(error)
        for error in list(incremental_payload.get("collection_errors") or [])
        if isinstance(error, dict)
    )
    nodeids = [str(item) for item in list(collect_snapshot.get("nodeids") or [])]
    reports = collect_full_test_debt._sort_reports(reports, nodeids)  # noqa: SLF001
    collection_errors = sorted(collection_errors, key=lambda item: str(item.get("nodeid") or ""))
    baseline_kind = str(old_payload.get("baseline_kind") or "after_main_style_isolation")
    classifications = collect_full_test_debt._classify_failures(  # noqa: SLF001
        reports,
        collection_errors,
        iter_quality_gate_required_tests(),
        baseline_kind,
    )
    summary = collect_full_test_debt._summarize(nodeids, reports, collection_errors, classifications)  # noqa: SLF001
    payload = dict(old_payload)
    git_status_short_before = _git_status(repo_root)
    payload.update(
        {
            "generated_at": _now_iso(),
            "head_sha": _git_head(repo_root),
            "collector_argv": [
                "tools/collect_full_test_debt.py",
                "--baseline-kind",
                "after_main_style_isolation",
                "--no-current-payload",
                "--",
                *list(pytest_args),
            ],
            "git_status_short_before": git_status_short_before,
            "worktree_clean_before": git_status_short_before == [],
            "pytest_args": list(FORMAL_FULL_TEST_PYTEST_ARGS),
            "exitstatus": int(incremental_payload.get("exitstatus") or 0),
            "collected_nodeids": nodeids,
            "collection_errors": collection_errors,
            "reports": reports,
            "summary": summary,
            "classifications": classifications,
            "incremental_proof": {
                "mode": "nodeid_incremental",
                "selected_nodeids": list(selected_nodeids),
                "changed_test_files": list(changed_test_files),
                "changed_helpers": list(plan.get("changed_helpers") or []),
                "declared_helper_impacts": dict(plan.get("declared_helper_impacts") or {}),
                "actual_importing_test_files": list(plan.get("actual_importing_test_files") or []),
                "affected_test_files": list(plan.get("affected_test_files") or changed_test_files),
                "previous_payload_hash": f"sha256:{stable_json_hash(dict(old_payload))}",
                "node_cache_hash": str(node_cache.get("payload_hash") or ""),
                "collect_nodeids_hash": str(collect_snapshot.get("nodeid_hash") or ""),
                "merge_policy": "replace_reports_for_changed_test_files",
            },
            "incremental_source": {
                "mode": "nodeid_incremental",
                "changed_test_files": list(changed_test_files),
                "changed_helpers": list(plan.get("changed_helpers") or []),
                "affected_test_files": list(plan.get("affected_test_files") or changed_test_files),
                "selected_nodeids": list(selected_nodeids),
            },
        }
    )
    return payload


def _build_ledger_only_payload(
    *,
    repo_root: str,
    old_payload: Mapping[str, Any],
    node_cache: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    ledger: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> Dict[str, Any]:
    del ledger
    payload = dict(old_payload)
    git_status_short_before = _git_status(repo_root)
    previous_fingerprint = node_cache.get("fingerprint") if isinstance(node_cache.get("fingerprint"), dict) else {}
    ledger_abs = _abs_path(repo_root, LEDGER_REL)
    ledger_sha256 = _sha256_file(ledger_abs) if os.path.isfile(ledger_abs) else ""
    payload.update(
        {
            "generated_at": _now_iso(),
            "head_sha": _git_head(repo_root),
            "git_status_short_before": git_status_short_before,
            "worktree_clean_before": git_status_short_before == [],
            "pytest_args": list(FORMAL_FULL_TEST_PYTEST_ARGS),
            "incremental_proof": {
                "mode": "ledger_only",
                "changed_paths": [str(path) for path in list(plan.get("changed_paths") or [])],
                "previous_payload_hash": f"sha256:{stable_json_hash(dict(old_payload))}",
                "previous_head_sha": str(old_payload.get("head_sha") or ""),
                "previous_generated_at": str(old_payload.get("generated_at") or ""),
                "node_cache_hash": str(node_cache.get("payload_hash") or ""),
                "previous_fingerprint_hash": str(
                    node_cache.get("fingerprint_hash") or dict(previous_fingerprint).get("hash") or ""
                ),
                "current_fingerprint_hash": str(current_fingerprint.get("hash") or ""),
                "ledger_sha256": ledger_sha256,
                "merge_policy": "reuse_previous_test_observations_with_current_ledger",
            },
            "incremental_source": {
                "mode": "ledger_only",
                "changed_paths": [str(path) for path in list(plan.get("changed_paths") or [])],
            },
        }
    )
    return payload


def _summary_stdout(summary: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    payload = dict(summary)
    payload["long_gate_full_test_debt"] = dict(metadata)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_outputs_and_node_cache(
    *,
    repo_root: str,
    entry: Mapping[str, Any],
    fingerprint: Mapping[str, Any],
    result: Mapping[str, Any],
    cache_dir: str,
    current_payload: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> None:
    _write_json_atomically(repo_root, QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL, current_payload)
    _write_json_atomically(repo_root, QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL, summary)
    write_full_test_debt_node_cache_after_success(
        repo_root=repo_root,
        entry=entry,
        fingerprint=fingerprint,
        result=result,
        cache_dir=cache_dir,
    )


def try_run_special_full_test_debt_mode(
    *,
    repo_root: str,
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    decision: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    cache_dir: str,
) -> Optional[Dict[str, Any]]:
    if str(entry.get("entry_id") or "") != "full_test_debt":
        return None
    if str(decision.get("decision") or "") != "run":
        return None
    if str(decision.get("reason") or "") != "input fingerprint changed":
        return None

    previous_success, previous_error = _validated_previous_success(
        repo_root=repo_root,
        decision=decision,
        evaluation=evaluation,
    )
    if previous_error or previous_success is None:
        return None
    previous_fingerprint = (
        previous_success.get("fingerprint") if isinstance(previous_success.get("fingerprint"), dict) else {}
    )
    node_cache, node_cache_error = _load_node_cache(repo_root, previous_success)
    if node_cache_error or node_cache is None:
        return None
    collect_snapshot, collect_error = _load_collect_snapshot(repo_root)
    if collect_error or collect_snapshot is None:
        return None
    try:
        ledger = _load_ledger_for_repo(repo_root)
    except QualityGateError:
        return None
    plan, plan_error = _classify_incremental_plan(
        repo_root=repo_root,
        previous_fingerprint=previous_fingerprint,
        current_fingerprint=current_fingerprint,
        collect_snapshot=collect_snapshot,
        node_cache=node_cache,
        ledger=ledger,
    )
    if plan_error or plan is None:
        return None

    previous_result_path = str(decision.get("previous_result_path") or "")
    reused_from = {
        "node_cache_path": NODE_CACHE_REL,
        "previous_result_path": previous_result_path,
        "fingerprint_hash": str(previous_success.get("fingerprint_hash") or ""),
        "current_fingerprint_hash": str(current_fingerprint.get("hash") or ""),
        "changed_paths": list(plan.get("changed_paths") or []),
    }

    if plan["mode"] == "ledger_only":
        old_payload = dict(node_cache["current_payload"])
        ledger_payload = _build_ledger_only_payload(
            repo_root=repo_root,
            old_payload=old_payload,
            node_cache=node_cache,
            current_fingerprint=current_fingerprint,
            ledger=ledger,
            plan=plan,
        )
        try:
            summary = check_full_test_debt.run_check_from_existing_payload(
                ledger_payload,
                ledger=ledger,
                require_clean_worktree_proof=True,
            )
        except QualityGateError:
            return None
        metadata = {"execution_mode": "ledger_only", "changed_paths": list(plan["changed_paths"])}
        result: Dict[str, Any] = {
            "stdout": _summary_stdout(summary, metadata),
            "stderr": "[long-gate-full-test-debt] ledger-only 校验通过\n",
            "returncode": 0,
            "execution_mode": "ledger_only",
            "reused_from": reused_from,
        }
        _write_outputs_and_node_cache(
            repo_root=repo_root,
            entry=entry,
            fingerprint=current_fingerprint,
            result=result,
            cache_dir=cache_dir,
            current_payload=ledger_payload,
            summary=summary,
        )
        return result

    selected_nodeids = [str(item) for item in list(plan.get("selected_nodeids") or [])]
    if not selected_nodeids:
        return None
    collector_result = _run_incremental_collector(repo_root, selected_nodeids)
    if bool(collector_result.get("collector_contract_error")):
        return {
            "stdout": str(collector_result.get("stdout") or ""),
            "stderr": str(collector_result.get("stderr") or ""),
            "returncode": int(collector_result["returncode"]),
            "execution_mode": "nodeid_incremental",
            "reused_from": reused_from,
        }
    incremental_payload = collector_result.get("payload")
    if not isinstance(incremental_payload, dict):
        return None
    merged_payload = _merge_payload(
        repo_root=repo_root,
        old_payload=dict(node_cache["current_payload"]),
        incremental_payload=incremental_payload,
        collect_snapshot=collect_snapshot,
        node_cache=node_cache,
        changed_test_files=[str(item) for item in list(plan.get("changed_test_files") or [])],
        selected_nodeids=selected_nodeids,
        pytest_args=list(collector_result.get("pytest_args") or []),
        incremental_plan=plan,
    )
    try:
        summary = check_full_test_debt.run_check_from_existing_payload(
            merged_payload,
            ledger=ledger,
            require_clean_worktree_proof=True,
        )
    except QualityGateError as exc:
        return {
            "stdout": str(collector_result.get("stdout") or ""),
            "stderr": str(collector_result.get("stderr") or "") + f"\nERROR: {exc}\n",
            "returncode": 2,
            "execution_mode": "nodeid_incremental",
            "reused_from": reused_from,
        }
    metadata = {
        "execution_mode": "nodeid_incremental",
        "changed_test_files": list(plan.get("changed_test_files") or []),
        "changed_helpers": list(plan.get("changed_helpers") or []),
        "declared_helper_impacts": dict(plan.get("declared_helper_impacts") or {}),
        "actual_importing_test_files": list(plan.get("actual_importing_test_files") or []),
        "affected_test_files": list(plan.get("affected_test_files") or []),
        "selected_nodeids": selected_nodeids,
    }
    result = {
        "stdout": _summary_stdout(summary, metadata),
        "stderr": str(collector_result.get("stderr") or "") + "[long-gate-full-test-debt] nodeid 增量校验通过\n",
        "returncode": 0,
        "execution_mode": "nodeid_incremental",
        "reused_from": {
            **reused_from,
            "changed_test_files": list(plan.get("changed_test_files") or []),
            "changed_helpers": list(plan.get("changed_helpers") or []),
            "declared_helper_impacts": dict(plan.get("declared_helper_impacts") or {}),
            "actual_importing_test_files": list(plan.get("actual_importing_test_files") or []),
            "affected_test_files": list(plan.get("affected_test_files") or []),
            "selected_nodeids": selected_nodeids,
        },
    }
    _write_outputs_and_node_cache(
        repo_root=repo_root,
        entry=entry,
        fingerprint=current_fingerprint,
        result=result,
        cache_dir=cache_dir,
        current_payload=merged_payload,
        summary=summary,
    )
    return result


def explain_special_full_test_debt_plan(
    *,
    repo_root: str,
    current_fingerprint: Mapping[str, Any],
    decision: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> Dict[str, Any]:
    if str(decision.get("decision") or "") != "run":
        return {"available": False, "mode": "", "reason": "decision is not run"}
    if str(decision.get("reason") or "") != "input fingerprint changed":
        return {"available": False, "mode": "", "reason": str(decision.get("reason") or "")}
    previous_success, previous_error = _validated_previous_success(
        repo_root=repo_root,
        decision=decision,
        evaluation=evaluation,
    )
    if previous_error or previous_success is None:
        reason = previous_error or "previous success cache is missing"
        return {
            "available": False,
            "mode": "",
            "reason": reason,
            **_special_explain_diagnostics(
                repo_root=repo_root,
                decision=decision,
                evaluation=evaluation,
                fallback_reason=reason,
            ),
        }
    previous_fingerprint = (
        previous_success.get("fingerprint") if isinstance(previous_success.get("fingerprint"), dict) else {}
    )
    node_cache, node_cache_error = _load_node_cache(repo_root, previous_success)
    if node_cache_error or node_cache is None:
        reason = node_cache_error or "node cache is invalid"
        return {
            "available": False,
            "mode": "",
            "reason": reason,
            **_special_explain_diagnostics(
                repo_root=repo_root,
                decision=decision,
                evaluation=evaluation,
                fallback_reason=reason,
                previous_success=previous_success,
            ),
        }
    collect_snapshot, collect_error = _load_collect_snapshot(repo_root)
    if collect_error or collect_snapshot is None:
        reason = collect_error or "collect_nodeids is invalid"
        return {
            "available": False,
            "mode": "",
            "reason": reason,
            **_special_explain_diagnostics(
                repo_root=repo_root,
                decision=decision,
                evaluation=evaluation,
                fallback_reason=reason,
                previous_success=previous_success,
                node_cache=node_cache,
            ),
        }
    try:
        ledger = _load_ledger_for_repo(repo_root)
    except QualityGateError as exc:
        reason = str(exc)
        return {
            "available": False,
            "mode": "",
            "reason": reason,
            **_special_explain_diagnostics(
                repo_root=repo_root,
                decision=decision,
                evaluation=evaluation,
                fallback_reason=reason,
                previous_success=previous_success,
                node_cache=node_cache,
            ),
        }
    plan, plan_error = _classify_incremental_plan(
        repo_root=repo_root,
        previous_fingerprint=previous_fingerprint,
        current_fingerprint=current_fingerprint,
        collect_snapshot=collect_snapshot,
        node_cache=node_cache,
        ledger=ledger,
    )
    if plan_error or plan is None:
        reason = plan_error or "no incremental plan"
        return {
            "available": False,
            "mode": "",
            "reason": reason,
            **_special_explain_diagnostics(
                repo_root=repo_root,
                decision=decision,
                evaluation=evaluation,
                fallback_reason=reason,
                previous_success=previous_success,
                node_cache=node_cache,
            ),
        }
    return {
        "available": True,
        "mode": str(plan.get("mode") or ""),
        "changed_paths": list(plan.get("changed_paths") or []),
        "changed_test_files": list(plan.get("changed_test_files") or []),
        "changed_helpers": list(plan.get("changed_helpers") or []),
        "declared_helper_impacts": dict(plan.get("declared_helper_impacts") or {}),
        "actual_importing_test_files": list(plan.get("actual_importing_test_files") or []),
        "affected_test_files": list(plan.get("affected_test_files") or []),
        "selected_nodeids": list(plan.get("selected_nodeids") or []),
        "safety_checks": dict(plan.get("safety_checks") or {}),
        **_special_explain_diagnostics(
            repo_root=repo_root,
            decision=decision,
            evaluation=evaluation,
            fallback_reason="",
            previous_success=previous_success,
            node_cache=node_cache,
        ),
    }
