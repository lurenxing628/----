from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, TypedDict, cast

from tools.long_gate_fingerprint import diff_fingerprints
from tools.long_gate_paths import (
    LONG_GATE_CACHE_DIR_REL,
    LONG_GATE_LOGS_DIR_NAME,
    LONG_GATE_LOGS_DIR_REL,
    LONG_GATE_RESULTS_DIR_NAME,
    LONG_GATE_RESULTS_DIR_REL,
    real_repo_root,
    repo_relative_path,
    resolve_repo_path,
)
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    content_equal,
    long_gate_cache_metadata,
    read_file_content,
)
from tools.quality_gate_shared import REPO_ROOT, normalize_quality_gate_command, sanitize_quality_gate_output


class ReuseEvaluation(TypedDict):
    decision: Dict[str, Any]
    validated_success: Optional[Dict[str, Any]]
    stdout: str
    stderr: str


class FailureReuseEvaluation(TypedDict):
    decision: Dict[str, Any]
    validated_failure: Optional[Dict[str, Any]]
    stdout: str
    stderr: str


def _safe_entry_id(entry_id: str) -> str:
    return str(entry_id or "").replace("\\", "_").replace("/", "_").strip() or "unknown"


def _repo_root(repo_root: Optional[str]) -> str:
    return real_repo_root(repo_root or REPO_ROOT)


def _abs_from_rel(repo_root: str, rel_path: str) -> str:
    return resolve_repo_path(repo_root, rel_path, description="cache path")


def _rel_from_path(repo_root: str, path: str) -> str:
    return repo_relative_path(repo_root, path, description="cache path")


def resolve_cache_dir(repo_root: Optional[str] = None, cache_dir: Optional[str] = None) -> str:
    root = _repo_root(repo_root)
    raw_path = str(cache_dir or LONG_GATE_CACHE_DIR_REL).replace("\\", "/").strip()
    if not raw_path:
        raise ValueError("long gate cache dir is empty")
    try:
        abs_path = _abs_from_rel(root, raw_path)
        default_abs = _abs_from_rel(root, LONG_GATE_CACHE_DIR_REL)
    except ValueError as exc:
        raise ValueError(f"long gate cache dir is invalid: {exc}") from exc
    if abs_path != default_abs and not abs_path.startswith(default_abs + os.sep):
        raise ValueError(f"long gate cache dir must be under {LONG_GATE_CACHE_DIR_REL}: {raw_path}")
    return os.path.relpath(abs_path, root).replace("\\", "/")


def _cache_child_rel(cache_dir: str, child: str) -> str:
    return os.path.join(str(cache_dir or LONG_GATE_CACHE_DIR_REL), child).replace("\\", "/")


def _write_text_if_needed(repo_root: str, rel_path: str, text: str) -> None:
    abs_path = _abs_from_rel(repo_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(str(text or ""))


def _success_rel_path(entry_id: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> str:
    return _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_RESULTS_DIR_NAME, f"{_safe_entry_id(entry_id)}.v2.success.json"),
    )


def _failure_rel_path(entry_id: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> str:
    return _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_RESULTS_DIR_NAME, f"{_safe_entry_id(entry_id)}.v2.failure.json"),
    )


def _load_json_object(path: str) -> Tuple[Optional[Dict[str, Any]], str]:
    if not os.path.exists(path):
        return None, "missing"
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"cache unreadable/corrupt: {exc}"
    except OSError as exc:
        return None, f"cache unreadable/corrupt: {exc}"
    if not isinstance(loaded, dict):
        return None, "cache unreadable/corrupt: top-level value is not an object"
    return loaded, ""


def _legacy_cache_decision(
    repo_root: str, entry_id: str, cache_kind: str, cache_dir: str, current_fingerprint: Mapping[str, Any]
) -> Optional[Dict[str, Any]]:
    rel_path = _cache_child_rel(cache_dir, os.path.join(LONG_GATE_RESULTS_DIR_NAME, f"{entry_id}.{cache_kind}.json"))
    previous, error = _load_json_object(_abs_from_rel(repo_root, rel_path))
    if error == "missing":
        return None
    return _decision(
        entry_id,
        "run",
        "legacy cache lacks original content; rerun required",
        previous_completed_at=str((previous or {}).get("completed_at") or ""),
        previous_result_path=rel_path,
        current_fingerprint=current_fingerprint,
    )


def _decision(
    entry_id: str,
    decision: str,
    reason: str,
    *,
    invalidated_by: Optional[Sequence[str]] = None,
    fingerprint_diff: Optional[Sequence[Mapping[str, Any]]] = None,
    previous_completed_at: Optional[str] = None,
    previous_result_path: Optional[str] = None,
    current_fingerprint: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "entry_id": entry_id,
        "decision": decision,
        "reuse_allowed": decision == "reuse",
        "reason": reason,
        "invalidated_by": list(invalidated_by or []),
        "previous_completed_at": previous_completed_at,
        "previous_result_path": previous_result_path,
        "current_fingerprint": dict(current_fingerprint or {}),
    }
    if fingerprint_diff is not None:
        payload["fingerprint_diff"] = [dict(item) for item in list(fingerprint_diff or [])]
    return payload


def _missing_field(payload: Mapping[str, Any], field: str) -> Optional[str]:
    if field not in payload:
        return f"cache unreadable/corrupt/missing required field: {field}"
    return None


def _validate_required_fields(payload: Mapping[str, Any]) -> Optional[str]:
    for field in (
        "schema_version",
        "cache_schema_version",
        "fingerprint_schema_version",
        "runner_version_content",
        "tooling_version_content",
        "runner_version_untrusted_paths",
        "tooling_version_untrusted_paths",
        "cache_dir",
        "repo_root_realpath",
        "git_common_dir_realpath",
        "entry_id",
        "status",
        "command",
        "fingerprint",
        "returncode",
        "duration_s",
        "stdout_content",
        "stderr_content",
        "stdout_log_path",
        "stderr_log_path",
        "output_files",
        "timed_out",
        "interrupted",
        "partial_write",
    ):
        error = _missing_field(payload, field)
        if error:
            return error
    if not isinstance(payload.get("output_files"), list):
        return "cache unreadable/corrupt/missing required field: output_files"
    for field in ("runner_version_untrusted_paths", "tooling_version_untrusted_paths"):
        if not isinstance(payload.get(field), list):
            return f"cache unreadable/corrupt/missing required field: {field}"
    for field in ("command", "fingerprint"):
        if not isinstance(payload.get(field), dict):
            return f"cache unreadable/corrupt: {field} must be an object"
    for field in ("stdout_content", "stderr_content"):
        if not isinstance(payload.get(field), str):
            return f"cache unreadable/corrupt: {field} must be text"
    for field in ("runner_version_content", "tooling_version_content"):
        if not isinstance(payload.get(field), list):
            return f"cache unreadable/corrupt: {field} must be a list"
    for field in ("timed_out", "interrupted", "partial_write"):
        if not isinstance(payload.get(field), bool):
            return f"cache unreadable/corrupt/missing required field: {field}"
    return None


def _coerce_plain_int_field(payload: Mapping[str, Any], field: str) -> Tuple[Optional[int], Optional[str]]:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        return None, "cache unreadable/corrupt: numeric field has invalid type"
    return int(value), None


def _coerce_plain_float_field(payload: Mapping[str, Any], field: str) -> Tuple[Optional[float], Optional[str]]:
    value = payload.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None, "cache unreadable/corrupt: numeric field has invalid type"
    return float(value), None


def _validate_fingerprint_shape(fingerprint: Mapping[str, Any]) -> Optional[str]:
    schema_version = fingerprint.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        return "cache unreadable/corrupt: fingerprint schema_version has invalid type"
    components = fingerprint.get("components")
    if not isinstance(components, dict):
        return "cache unreadable/corrupt: fingerprint components is not an object"
    if not isinstance(components.get("command"), dict):
        return "cache unreadable/corrupt: fingerprint command is not an object"
    files_component = components.get("files")
    if files_component is not None:
        if not isinstance(files_component, dict):
            return "cache unreadable/corrupt: fingerprint files is not an object"
        files = files_component.get("files")
        if files is not None:
            if not isinstance(files, list):
                return "cache unreadable/corrupt: fingerprint files must be a list"
            for row in files:
                if not isinstance(row, dict):
                    return "cache unreadable/corrupt: fingerprint file row is not an object"
                if row.get("kind") == "file" and not isinstance(row.get("content_base64"), str):
                    return "cache unreadable/corrupt: fingerprint file content is missing"
                if row.get("kind") == "symlink" and (
                    not isinstance(row.get("target"), str) or not isinstance(row.get("target_content_base64"), str)
                ):
                    return "cache unreadable/corrupt: fingerprint symlink content is missing"
    if schema_version != LONG_GATE_FINGERPRINT_SCHEMA_VERSION:
        return "cache unreadable/corrupt: fingerprint schema changed"
    return None


def _fingerprint_untrusted_path_reason(fingerprint: Mapping[str, Any]) -> str:
    components = fingerprint.get("components")
    if not isinstance(components, dict):
        return ""
    files_component = components.get("files")
    if not isinstance(files_component, dict):
        return ""
    files = files_component.get("files")
    if not isinstance(files, list):
        return ""
    for row in files:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        path = str(row.get("path") or "")
        if kind == "outside_repo":
            return f"input path is outside repo: {path}"
        if kind == "symlink_outside_repo":
            return f"input symlink points outside repo: {path}"
    return ""


def _non_reusable_environment_keys(fingerprint: Mapping[str, Any]) -> List[str]:
    components = fingerprint.get("components")
    environment = components.get("environment") if isinstance(components, dict) else None
    if not isinstance(environment, dict):
        return []
    keys = [str(key) for key in list(environment.get("non_reusable_env_keys") or [])]
    values = environment.get("values")
    # Presence is descriptive only; a cached caller cannot bind the secret value.
    if (
        isinstance(values, dict)
        and isinstance(values.get("SECRET_KEY"), dict)
        and bool(values["SECRET_KEY"].get("present"))
    ):
        keys.append("SECRET_KEY")
    return sorted(set(keys))


def _non_reusable_environment_decision(entry_id: str, fingerprint: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    keys = _non_reusable_environment_keys(fingerprint)
    if not keys:
        return None
    return {
        **_decision(
            entry_id,
            "run",
            "environment values remain in memory; cache unavailable",
            invalidated_by=keys,
            current_fingerprint=fingerprint,
        ),
        "cache_unavailable": True,
        "non_reusable_env_keys": keys,
    }


def _fingerprint_invalid_collect_nodeids_reason(fingerprint: Mapping[str, Any]) -> str:
    components = fingerprint.get("components")
    if not isinstance(components, dict):
        return ""
    collect_nodeids = components.get("collect_nodeids")
    if collect_nodeids is None:
        return ""
    if not isinstance(collect_nodeids, dict):
        return "collect_nodeids fingerprint component is invalid"
    path = str(collect_nodeids.get("path") or "evidence/QualityGate/collect_nodeids.v2.json")
    if not bool(collect_nodeids.get("exists")):
        return f"collect_nodeids payload is missing: {path}"
    error = str(collect_nodeids.get("error") or "")
    if error:
        return f"collect_nodeids payload is invalid: {error}"
    if not bool(collect_nodeids.get("validated")):
        return "collect_nodeids payload validation is missing"
    schema_version = collect_nodeids.get("schema_version")
    if schema_version != 2:
        return "collect_nodeids payload schema_version is invalid"
    if str(collect_nodeids.get("status") or "") != "passed":
        return "collect_nodeids payload status is not passed"
    nodeids = collect_nodeids.get("nodeids")
    if not isinstance(nodeids, list) or any(not isinstance(nodeid, str) for nodeid in nodeids):
        return "collect_nodeids payload nodeids are missing"
    nodeid_count = collect_nodeids.get("nodeid_count")
    if not isinstance(nodeid_count, int) or isinstance(nodeid_count, bool) or nodeid_count != len(nodeids):
        return "collect_nodeids payload nodeid_count is invalid"
    return ""


def _fingerprint_invalid_required_reason(fingerprint: Mapping[str, Any]) -> str:
    components = fingerprint.get("components")
    component = components.get("required_full_test_debt") if isinstance(components, dict) else None
    if component is None:
        return ""
    if (
        not isinstance(component, dict)
        or not bool(component.get("exists"))
        or not bool(component.get("validated"))
        or component.get("error")
    ):
        return "required full-test-debt evidence is invalid"
    if not isinstance(component.get("verification"), dict):
        return "required full-test-debt verification is missing"
    return ""


def _fingerprint_content_error(previous: Mapping[str, Any]) -> Optional[str]:
    fingerprint = previous.get("fingerprint")
    if not isinstance(fingerprint, dict):
        return "cache unreadable/corrupt: fingerprint is not an object"
    shape_error = _validate_fingerprint_shape(fingerprint)
    if shape_error:
        return shape_error
    if not content_equal(fingerprint["components"].get("command"), previous.get("command")):
        return "cache unreadable/corrupt: command content mismatch"
    return None


def _file_content_match_error(
    repo_root: str, rel_path: str, expected_content: Any, *, missing_message: str
) -> Optional[str]:
    try:
        abs_path = _abs_from_rel(repo_root, rel_path)
        if not os.path.isfile(abs_path) or not isinstance(expected_content, str):
            return missing_message
        if not content_equal(read_file_content(abs_path), expected_content):
            return missing_message
    except (OSError, ValueError) as exc:
        return str(exc)
    return None


def _read_text_file_after_content_check(
    repo_root: str, rel_path: str, expected_content: Any, *, missing_message: str
) -> Tuple[str, Optional[str]]:
    try:
        abs_path = _abs_from_rel(repo_root, rel_path)
        if not os.path.isfile(abs_path) or not isinstance(expected_content, str):
            return "", missing_message
        with open(abs_path, "rb") as handle:
            data = handle.read()
        if data != expected_content.encode("utf-8"):
            return "", missing_message
        return data.decode("utf-8"), None
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return "", f"previous logs unreadable: {rel_path}: {exc}"


def _cache_log_path_error(repo_root: str, rel_path: str, *, cache_dir: str, expected_rel_path: str) -> Optional[str]:
    try:
        abs_path = _abs_from_rel(repo_root, rel_path)
        logs_abs = _abs_from_rel(repo_root, _cache_child_rel(cache_dir, LONG_GATE_LOGS_DIR_NAME))
    except ValueError as exc:
        return str(exc)

    if abs_path != logs_abs and not abs_path.startswith(logs_abs + os.sep):
        return f"previous logs path is outside current cache logs dir: {rel_path}"
    if rel_path != expected_rel_path:
        return f"previous logs path changed: {rel_path}"
    return None


def _validated_log_texts(
    repo_root: str,
    previous: Mapping[str, Any],
    *,
    cache_dir: str,
    entry_id: str,
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    texts: Dict[str, str] = {}
    expected_stdout_log_path, expected_stderr_log_path = _log_paths_for_result(entry_id, {}, cache_dir=cache_dir)
    expected_paths = {
        "stdout_log_path": expected_stdout_log_path,
        "stderr_log_path": expected_stderr_log_path,
    }

    for path_key, content_key, output_key in (
        ("stdout_log_path", "stdout_content", "stdout"),
        ("stderr_log_path", "stderr_content", "stderr"),
    ):
        rel_path = str(previous.get(path_key) or "").replace("\\", "/")
        if not rel_path:
            return None, "previous logs missing or content mismatch"
        path_error = _cache_log_path_error(
            repo_root,
            rel_path,
            cache_dir=cache_dir,
            expected_rel_path=expected_paths[path_key],
        )
        if path_error:
            return None, path_error
        text, error = _read_text_file_after_content_check(
            repo_root,
            rel_path,
            previous.get(content_key),
            missing_message="previous logs missing or content mismatch",
        )
        if error:
            return None, error

        texts[output_key] = text

    return texts, None


def _output_files_exist_and_content_match(repo_root: str, previous: Mapping[str, Any]) -> Optional[str]:
    for row in list(previous.get("output_files") or []):
        if not isinstance(row, dict):
            return "previous output files missing or content mismatch"
        rel_path = str(row.get("path") or "").replace("\\", "/")
        if not rel_path:
            return "previous output files missing or content mismatch"
        error = _file_content_match_error(
            repo_root,
            rel_path,
            row.get("content_base64"),
            missing_message="previous output files missing or content mismatch",
        )
        if error:
            return error
    return None


def _declared_output_files(repo_root: str, entry: Mapping[str, Any]) -> Tuple[List[str], Optional[str]]:
    rows: List[str] = []
    for path in list(entry.get("output_result_files") or []):
        try:
            rows.append(_rel_from_path(repo_root, str(path)))
        except ValueError as exc:
            return [], str(exc)
    return list(dict.fromkeys(rows)), None


def _output_files_cover_declared_paths(
    repo_root: str, entry: Mapping[str, Any], previous: Mapping[str, Any]
) -> Optional[str]:
    declared, error = _declared_output_files(repo_root, entry)
    if error:
        return error
    if not declared:
        return None
    cached_paths = {
        str(row.get("path") or "").replace("\\", "/")
        for row in list(previous.get("output_files") or [])
        if isinstance(row, dict)
    }
    for rel_path in declared:
        if rel_path not in cached_paths:
            return f"previous output files missing required path: {rel_path}"
    return None


def _reuse_evaluation(
    decision: Dict[str, Any],
    *,
    validated_success: Optional[Mapping[str, Any]] = None,
    stdout: str = "",
    stderr: str = "",
) -> ReuseEvaluation:
    return {
        "decision": decision,
        "validated_success": dict(validated_success) if validated_success is not None else None,
        "stdout": stdout,
        "stderr": stderr,
    }


def _failure_reuse_evaluation(
    decision: Dict[str, Any],
    *,
    validated_failure: Optional[Mapping[str, Any]] = None,
    stdout: str = "",
    stderr: str = "",
) -> FailureReuseEvaluation:
    return {
        "decision": decision,
        "validated_failure": dict(validated_failure) if validated_failure is not None else None,
        "stdout": stdout,
        "stderr": stderr,
    }


def evaluate_reuse(
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> ReuseEvaluation:
    root = _repo_root(repo_root)
    resolved_cache_dir = resolve_cache_dir(root, cache_dir)
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    current_content = dict(current_fingerprint)
    environment_decision = _non_reusable_environment_decision(entry_id, current_fingerprint)
    if environment_decision:
        return _reuse_evaluation(environment_decision)
    if not bool(entry.get("reuse_allowed")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "reuse is disabled for this entry", current_fingerprint=current_content)
        )
    result_rel = _success_rel_path(entry_id, cache_dir=resolved_cache_dir)
    previous, load_error = _load_json_object(_abs_from_rel(root, result_rel))
    if load_error == "missing":
        legacy_decision = _legacy_cache_decision(root, entry_id, "success", resolved_cache_dir, current_content)
        return _reuse_evaluation(
            legacy_decision
            or _decision(entry_id, "run", "no previous success cache", current_fingerprint=current_content)
        )
    if load_error:
        return _reuse_evaluation(_decision(entry_id, "run", load_error, current_fingerprint=current_content))
    assert previous is not None

    required_error = _validate_required_fields(previous)
    if required_error:
        return _reuse_evaluation(_decision(entry_id, "run", required_error, current_fingerprint=current_content))
    numeric_values: Dict[str, int] = {}
    for field in ("schema_version", "cache_schema_version", "fingerprint_schema_version", "returncode"):
        value, error = _coerce_plain_int_field(previous, field)
        if error:
            return _reuse_evaluation(_decision(entry_id, "run", error, current_fingerprint=current_content))
        assert value is not None
        numeric_values[field] = value
    schema_version = numeric_values["schema_version"]
    cache_schema_version = numeric_values["cache_schema_version"]
    fingerprint_schema_version = numeric_values["fingerprint_schema_version"]
    returncode = numeric_values["returncode"]
    _duration_s, duration_error = _coerce_plain_float_field(previous, "duration_s")
    if duration_error:
        return _reuse_evaluation(_decision(entry_id, "run", duration_error, current_fingerprint=current_content))
    if schema_version != LONG_GATE_CACHE_SCHEMA_VERSION or cache_schema_version != LONG_GATE_CACHE_SCHEMA_VERSION:
        return _reuse_evaluation(
            _decision(entry_id, "run", "cache schema changed", current_fingerprint=current_content)
        )
    if fingerprint_schema_version != LONG_GATE_FINGERPRINT_SCHEMA_VERSION:
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=["fingerprint schema changed"],
                current_fingerprint=current_content,
            )
        )
    expected_metadata = (
        metadata if metadata is not None else long_gate_cache_metadata(root, cache_dir=resolved_cache_dir)
    )
    for untrusted_field, reason in (
        ("runner_version_untrusted_paths", "runner version contains untrusted path"),
        ("tooling_version_untrusted_paths", "tooling version contains untrusted path"),
    ):
        current_untrusted = [str(path) for path in list(expected_metadata.get(untrusted_field) or [])]
        previous_untrusted = [str(path) for path in list(previous.get(untrusted_field) or [])]
        if current_untrusted:
            return _reuse_evaluation(
                _decision(
                    entry_id,
                    "run",
                    reason,
                    invalidated_by=current_untrusted,
                    current_fingerprint=current_content,
                )
            )
        if previous_untrusted:
            return _reuse_evaluation(
                _decision(
                    entry_id,
                    "run",
                    reason,
                    invalidated_by=previous_untrusted,
                    current_fingerprint=current_content,
                )
            )
    for content_field, reason in (
        ("runner_version_content", "runner version changed"),
        ("tooling_version_content", "tooling version changed"),
    ):
        if not content_equal(previous.get(content_field), expected_metadata.get(content_field)):
            return _reuse_evaluation(_decision(entry_id, "run", reason, current_fingerprint=current_content))
    if str(previous.get("cache_dir") or "").replace("\\", "/") != str(expected_metadata.get("cache_dir") or ""):
        return _reuse_evaluation(_decision(entry_id, "run", "cache dir changed", current_fingerprint=current_content))
    for identity_field in ("repo_root_realpath", "git_common_dir_realpath"):
        if os.path.realpath(str(previous.get(identity_field) or "")) != os.path.realpath(
            str(expected_metadata.get(identity_field) or "")
        ):
            return _reuse_evaluation(
                _decision(entry_id, "run", "repo identity changed", current_fingerprint=current_content)
            )
    fingerprint_error = _fingerprint_content_error(previous)
    if fingerprint_error:
        return _reuse_evaluation(_decision(entry_id, "run", fingerprint_error, current_fingerprint=current_content))
    if str(previous.get("entry_id") or "") != entry_id:
        return _reuse_evaluation(
            _decision(entry_id, "run", "cache entry_id changed", current_fingerprint=current_content)
        )
    if str(previous.get("status") or "") != "passed":
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was not successful", current_fingerprint=current_content)
        )
    if bool(previous.get("timed_out")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result timed out", current_fingerprint=current_content)
        )
    if bool(previous.get("interrupted")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was interrupted", current_fingerprint=current_content)
        )
    if bool(previous.get("partial_write")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was partially written", current_fingerprint=current_content)
        )
    previous_fingerprint_obj = previous.get("fingerprint")
    previous_fingerprint = cast(
        Mapping[str, Any], previous_fingerprint_obj if isinstance(previous_fingerprint_obj, dict) else {}
    )
    untrusted_path_reason = _fingerprint_untrusted_path_reason(
        current_fingerprint
    ) or _fingerprint_untrusted_path_reason(previous_fingerprint)
    if untrusted_path_reason:
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint contains untrusted path",
                invalidated_by=[untrusted_path_reason],
                current_fingerprint=current_content,
            )
        )
    collect_nodeids_reason = _fingerprint_invalid_collect_nodeids_reason(
        current_fingerprint
    ) or _fingerprint_invalid_collect_nodeids_reason(previous_fingerprint)
    if collect_nodeids_reason:
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "collect nodeids proof is invalid",
                invalidated_by=[collect_nodeids_reason],
                current_fingerprint=current_content,
            )
        )
    required_reason = _fingerprint_invalid_required_reason(current_fingerprint) or _fingerprint_invalid_required_reason(
        previous_fingerprint
    )
    if required_reason:
        return _reuse_evaluation(_decision(entry_id, "run", required_reason, current_fingerprint=current_content))
    if previous_fingerprint.get("schema_version") != current_fingerprint.get("schema_version"):
        diff = diff_fingerprints(previous_fingerprint, current_fingerprint)
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=["fingerprint schema changed"],
                fingerprint_diff=list(diff.get("components") or []),
                previous_completed_at=str(previous.get("completed_at") or ""),
                previous_result_path=result_rel,
                current_fingerprint=current_content,
            )
        )
    if returncode != 0:
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous returncode was non-zero", current_fingerprint=current_content)
        )
    if not content_equal(previous.get("command"), normalize_quality_gate_command(entry.get("command") or entry)):
        return _reuse_evaluation(
            _decision(entry_id, "run", "command identity changed", current_fingerprint=current_content)
        )
    if not content_equal(previous_fingerprint, current_content):
        diff = diff_fingerprints(previous_fingerprint, current_fingerprint)
        reasons = list(diff.get("reasons") or ["input fingerprint changed"])
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=reasons,
                fingerprint_diff=list(diff.get("components") or []),
                previous_completed_at=str(previous.get("completed_at") or ""),
                previous_result_path=result_rel,
                current_fingerprint=current_content,
            )
        )

    log_texts, log_error = _validated_log_texts(
        root,
        previous,
        cache_dir=resolved_cache_dir,
        entry_id=entry_id,
    )
    if log_error:
        return _reuse_evaluation(_decision(entry_id, "run", log_error, current_fingerprint=current_content))
    output_error = _output_files_exist_and_content_match(root, previous)
    if output_error:
        return _reuse_evaluation(_decision(entry_id, "run", output_error, current_fingerprint=current_content))
    output_coverage_error = _output_files_cover_declared_paths(root, entry, previous)
    if output_coverage_error:
        return _reuse_evaluation(_decision(entry_id, "run", output_coverage_error, current_fingerprint=current_content))

    decision = _decision(
        entry_id,
        "reuse",
        "fingerprint matched previous successful result",
        previous_completed_at=str(previous.get("completed_at") or ""),
        previous_result_path=result_rel,
        current_fingerprint=current_content,
    )
    return _reuse_evaluation(
        decision,
        validated_success=previous,
        stdout=str((log_texts or {}).get("stdout") or ""),
        stderr=str((log_texts or {}).get("stderr") or ""),
    )


def evaluate_failure_reuse(
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> FailureReuseEvaluation:
    root = _repo_root(repo_root)
    resolved_cache_dir = resolve_cache_dir(root, cache_dir)
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    current_content = dict(current_fingerprint)
    environment_decision = _non_reusable_environment_decision(entry_id, current_fingerprint)
    if environment_decision:
        return _failure_reuse_evaluation(environment_decision)
    if not bool(entry.get("reuse_allowed")):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "reuse is disabled for this entry", current_fingerprint=current_content)
        )
    result_rel = _failure_rel_path(entry_id, cache_dir=resolved_cache_dir)
    previous, load_error = _load_json_object(_abs_from_rel(root, result_rel))
    if load_error == "missing":
        legacy_decision = _legacy_cache_decision(root, entry_id, "failure", resolved_cache_dir, current_content)
        return _failure_reuse_evaluation(
            legacy_decision
            or _decision(entry_id, "run", "no previous failure cache", current_fingerprint=current_content)
        )
    if load_error:
        return _failure_reuse_evaluation(_decision(entry_id, "run", load_error, current_fingerprint=current_content))
    assert previous is not None

    required_error = _validate_required_fields(previous)
    if required_error:
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", required_error, current_fingerprint=current_content)
        )
    numeric_values: Dict[str, int] = {}
    for field in ("schema_version", "cache_schema_version", "fingerprint_schema_version", "returncode"):
        value, error = _coerce_plain_int_field(previous, field)
        if error:
            return _failure_reuse_evaluation(_decision(entry_id, "run", error, current_fingerprint=current_content))
        assert value is not None
        numeric_values[field] = value
    _duration_s, duration_error = _coerce_plain_float_field(previous, "duration_s")
    if duration_error:
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", duration_error, current_fingerprint=current_content)
        )
    if (
        numeric_values["schema_version"] != LONG_GATE_CACHE_SCHEMA_VERSION
        or numeric_values["cache_schema_version"] != LONG_GATE_CACHE_SCHEMA_VERSION
    ):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "cache schema changed", current_fingerprint=current_content)
        )
    if numeric_values["fingerprint_schema_version"] != LONG_GATE_FINGERPRINT_SCHEMA_VERSION:
        return _failure_reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=["fingerprint schema changed"],
                current_fingerprint=current_content,
            )
        )
    expected_metadata = long_gate_cache_metadata(root, cache_dir=resolved_cache_dir)
    for untrusted_field, reason in (
        ("runner_version_untrusted_paths", "runner version contains untrusted path"),
        ("tooling_version_untrusted_paths", "tooling version contains untrusted path"),
    ):
        current_untrusted = [str(path) for path in list(expected_metadata.get(untrusted_field) or [])]
        previous_untrusted = [str(path) for path in list(previous.get(untrusted_field) or [])]
        if current_untrusted:
            return _failure_reuse_evaluation(
                _decision(
                    entry_id,
                    "run",
                    reason,
                    invalidated_by=current_untrusted,
                    current_fingerprint=current_content,
                )
            )
        if previous_untrusted:
            return _failure_reuse_evaluation(
                _decision(
                    entry_id,
                    "run",
                    reason,
                    invalidated_by=previous_untrusted,
                    current_fingerprint=current_content,
                )
            )
    for content_field, reason in (
        ("runner_version_content", "runner version changed"),
        ("tooling_version_content", "tooling version changed"),
    ):
        if not content_equal(previous.get(content_field), expected_metadata.get(content_field)):
            return _failure_reuse_evaluation(_decision(entry_id, "run", reason, current_fingerprint=current_content))
    if str(previous.get("cache_dir") or "").replace("\\", "/") != str(expected_metadata.get("cache_dir") or ""):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "cache dir changed", current_fingerprint=current_content)
        )
    for identity_field in ("repo_root_realpath", "git_common_dir_realpath"):
        if os.path.realpath(str(previous.get(identity_field) or "")) != os.path.realpath(
            str(expected_metadata.get(identity_field) or "")
        ):
            return _failure_reuse_evaluation(
                _decision(entry_id, "run", "repo identity changed", current_fingerprint=current_content)
            )
    fingerprint_error = _fingerprint_content_error(previous)
    if fingerprint_error:
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", fingerprint_error, current_fingerprint=current_content)
        )
    if str(previous.get("entry_id") or "") != entry_id:
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "cache entry_id changed", current_fingerprint=current_content)
        )
    if str(previous.get("status") or "") != "failed":
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "previous failure cache status changed", current_fingerprint=current_content)
        )
    if bool(previous.get("timed_out")):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "previous failure timed out", current_fingerprint=current_content)
        )
    if bool(previous.get("interrupted")):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "previous failure was interrupted", current_fingerprint=current_content)
        )
    if bool(previous.get("partial_write")):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "previous failure was partially written", current_fingerprint=current_content)
        )
    previous_fingerprint_obj = previous.get("fingerprint")
    previous_fingerprint = cast(
        Mapping[str, Any], previous_fingerprint_obj if isinstance(previous_fingerprint_obj, dict) else {}
    )
    untrusted_path_reason = _fingerprint_untrusted_path_reason(
        current_fingerprint
    ) or _fingerprint_untrusted_path_reason(previous_fingerprint)
    if untrusted_path_reason:
        return _failure_reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint contains untrusted path",
                invalidated_by=[untrusted_path_reason],
                current_fingerprint=current_content,
            )
        )
    collect_nodeids_reason = _fingerprint_invalid_collect_nodeids_reason(
        current_fingerprint
    ) or _fingerprint_invalid_collect_nodeids_reason(previous_fingerprint)
    if collect_nodeids_reason:
        return _failure_reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "collect nodeids proof is invalid",
                invalidated_by=[collect_nodeids_reason],
                current_fingerprint=current_content,
            )
        )
    if not content_equal(previous.get("command"), normalize_quality_gate_command(entry.get("command") or entry)):
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "command identity changed", current_fingerprint=current_content)
        )
    if numeric_values["returncode"] == 0:
        return _failure_reuse_evaluation(
            _decision(entry_id, "run", "previous failure returncode was zero", current_fingerprint=current_content)
        )
    if not content_equal(previous_fingerprint, current_content):
        diff = diff_fingerprints(previous_fingerprint, current_fingerprint)
        reasons = list(diff.get("reasons") or ["input fingerprint changed"])
        return _failure_reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=reasons,
                fingerprint_diff=list(diff.get("components") or []),
                previous_completed_at=str(previous.get("completed_at") or ""),
                previous_result_path=result_rel,
                current_fingerprint=current_content,
            )
        )

    log_texts, log_error = _validated_log_texts(
        root,
        previous,
        cache_dir=resolved_cache_dir,
        entry_id=entry_id,
    )
    if log_error:
        return _failure_reuse_evaluation(_decision(entry_id, "run", log_error, current_fingerprint=current_content))
    if list(previous.get("output_files") or []):
        return _failure_reuse_evaluation(
            _decision(
                entry_id, "run", "previous failure cache declares output files", current_fingerprint=current_content
            )
        )

    decision = _decision(
        entry_id,
        "cached_failure",
        "fingerprint matched previous failed result",
        previous_completed_at=str(previous.get("completed_at") or ""),
        previous_result_path=result_rel,
        current_fingerprint=current_content,
    )
    return _failure_reuse_evaluation(
        decision,
        validated_failure=previous,
        stdout=str((log_texts or {}).get("stdout") or ""),
        stderr=str((log_texts or {}).get("stderr") or ""),
    )


def decide_failure_reuse(
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> Dict[str, Any]:
    return dict(
        evaluate_failure_reuse(entry, current_fingerprint, repo_root=repo_root, cache_dir=cache_dir)["decision"]
    )


def decide_reuse(
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> Dict[str, Any]:
    return dict(evaluate_reuse(entry, current_fingerprint, repo_root=repo_root, cache_dir=cache_dir)["decision"])


def _log_paths_for_result(
    entry_id: str,
    _command_result: Mapping[str, Any],
    *,
    cache_dir: str = LONG_GATE_CACHE_DIR_REL,
) -> Tuple[str, str]:
    safe_entry_id = _safe_entry_id(entry_id)
    stdout_log_path = _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_LOGS_DIR_NAME, f"{safe_entry_id}.v2.stdout.log"),
    )
    stderr_log_path = _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_LOGS_DIR_NAME, f"{safe_entry_id}.v2.stderr.log"),
    )
    return stdout_log_path, stderr_log_path


def _read_output_files(repo_root: str, output_files: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in list(output_files or []):
        rel_path = _rel_from_path(repo_root, str(path))
        abs_path = _abs_from_rel(repo_root, rel_path)
        if not os.path.isfile(abs_path):
            raise ValueError(f"long gate output file does not exist: {rel_path}")
        rows.append(
            {
                "path": rel_path,
                "content_base64": read_file_content(abs_path),
            }
        )
    return rows


def _assert_output_files_cover_declared_paths(
    repo_root: str, entry: Mapping[str, Any], output_file_rows: Sequence[Mapping[str, Any]]
) -> None:
    declared, error = _declared_output_files(repo_root, entry)
    if error:
        raise ValueError(error)
    cached_paths = {str(row.get("path") or "").replace("\\", "/") for row in list(output_file_rows or [])}
    missing = [path for path in declared if path not in cached_paths]
    if missing:
        raise ValueError(f"long gate output file was not provided: {missing[0]}")


def _assert_success_command_result(command_result: Mapping[str, Any]) -> None:
    if "returncode" not in command_result:
        raise ValueError("long gate success cache requires returncode")
    returncode_value = command_result.get("returncode")
    if not isinstance(returncode_value, int) or isinstance(returncode_value, bool):
        raise ValueError("long gate success cache requires numeric returncode")
    returncode = int(returncode_value)

    if returncode != 0:
        raise ValueError("long gate success cache requires returncode == 0")

    if "duration_s" in command_result:
        duration_value = command_result.get("duration_s")
        if not isinstance(duration_value, (int, float)) or isinstance(duration_value, bool):
            raise ValueError("long gate success cache requires numeric duration_s")

    for field in ("timed_out", "interrupted", "partial_write"):
        if bool(command_result.get(field)):
            raise ValueError(f"long gate success cache requires {field} == False")


def _assert_cache_fingerprint(fingerprint: Mapping[str, Any], cache_kind: str) -> None:
    error = _validate_fingerprint_shape(fingerprint)
    if error:
        raise ValueError(f"long gate {cache_kind} cache requires valid fingerprint: {error}")
    if fingerprint.get("schema_version") != LONG_GATE_FINGERPRINT_SCHEMA_VERSION:
        raise ValueError(f"long gate {cache_kind} cache requires current fingerprint schema_version")
    keys = _non_reusable_environment_keys(fingerprint)
    if keys:
        raise ValueError(f"long gate {cache_kind} cache is unavailable for environment keys: " + ", ".join(keys))


def _assert_success_fingerprint(fingerprint: Mapping[str, Any]) -> None:
    _assert_cache_fingerprint(fingerprint, "success")


def _assert_failure_fingerprint(fingerprint: Mapping[str, Any]) -> None:
    _assert_cache_fingerprint(fingerprint, "failure")


def _assert_failure_command_result(command_result: Mapping[str, Any]) -> None:
    if "returncode" not in command_result:
        raise ValueError("long gate failure cache requires returncode")
    returncode_value = command_result.get("returncode")
    if not isinstance(returncode_value, int) or isinstance(returncode_value, bool):
        raise ValueError("long gate failure cache requires numeric returncode")
    if int(returncode_value) == 0:
        raise ValueError("long gate failure cache requires returncode != 0")
    if "duration_s" in command_result:
        duration_value = command_result.get("duration_s")
        if not isinstance(duration_value, (int, float)) or isinstance(duration_value, bool):
            raise ValueError("long gate failure cache requires numeric duration_s")
    for field in ("timed_out", "interrupted", "partial_write"):
        if bool(command_result.get(field)):
            raise ValueError(f"long gate failure cache requires {field} == False")


def write_success(
    entry: Mapping[str, Any],
    fingerprint: Mapping[str, Any],
    command_result: Mapping[str, Any],
    output_files: Sequence[str],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> None:
    root = _repo_root(repo_root)
    resolved_cache_dir = resolve_cache_dir(root, cache_dir)
    command_result = {
        **command_result,
        "stdout": sanitize_quality_gate_output(str(command_result.get("stdout") or "")),
        "stderr": sanitize_quality_gate_output(str(command_result.get("stderr") or "")),
    }
    _assert_success_command_result(command_result)
    _assert_success_fingerprint(fingerprint)
    if not content_equal(
        fingerprint["components"].get("command"), normalize_quality_gate_command(entry.get("command") or entry)
    ):
        raise ValueError("long gate success cache requires matching command content")
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    collect_nodeids_reason = _fingerprint_invalid_collect_nodeids_reason(fingerprint)
    if collect_nodeids_reason:
        raise ValueError(f"long gate success cache requires valid collect_nodeids proof: {collect_nodeids_reason}")
    required_reason = _fingerprint_invalid_required_reason(fingerprint)
    if required_reason:
        raise ValueError(f"long gate success cache requires valid required evidence: {required_reason}")
    stdout_log_path, stderr_log_path = _log_paths_for_result(
        entry_id,
        command_result,
        cache_dir=resolved_cache_dir,
    )
    _write_text_if_needed(root, stdout_log_path, str(command_result.get("stdout") or ""))
    _write_text_if_needed(root, stderr_log_path, str(command_result.get("stderr") or ""))
    output_file_rows = _read_output_files(root, output_files)
    _assert_output_files_cover_declared_paths(root, entry, output_file_rows)
    payload = {
        "schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        **long_gate_cache_metadata(root, cache_dir=resolved_cache_dir),
        "entry_id": entry_id,
        "status": "passed",
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "duration_s": float(command_result.get("duration_s") or 0.0),
        "display": str(entry.get("display") or ""),
        "args": [str(arg) for arg in list(entry.get("args") or [])],
        "command": normalize_quality_gate_command(entry.get("command") or entry),
        "fingerprint": dict(fingerprint),
        "returncode": int(command_result.get("returncode") or 0),
        "stdout_content": str(command_result.get("stdout") or ""),
        "stderr_content": str(command_result.get("stderr") or ""),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "output_files": output_file_rows,
        "receipt_path": str(command_result.get("receipt_path") or ""),
        "run_id": str(command_result.get("run_id") or ""),
        "command_index": command_result.get("command_index"),
        "timed_out": bool(command_result.get("timed_out")),
        "interrupted": bool(command_result.get("interrupted")),
        "partial_write": bool(command_result.get("partial_write")),
    }
    rel_path = _success_rel_path(entry_id, cache_dir=resolved_cache_dir)
    abs_path = _abs_from_rel(root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)


def write_failure(
    entry: Mapping[str, Any],
    fingerprint: Mapping[str, Any],
    command_result: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> None:
    root = _repo_root(repo_root)
    resolved_cache_dir = resolve_cache_dir(root, cache_dir)
    command_result = {
        **command_result,
        "stdout": sanitize_quality_gate_output(str(command_result.get("stdout") or "")),
        "stderr": sanitize_quality_gate_output(str(command_result.get("stderr") or "")),
    }
    _assert_failure_command_result(command_result)
    _assert_failure_fingerprint(fingerprint)
    if not content_equal(
        fingerprint["components"].get("command"), normalize_quality_gate_command(entry.get("command") or entry)
    ):
        raise ValueError("long gate failure cache requires matching command content")
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    stdout_log_path, stderr_log_path = _log_paths_for_result(
        entry_id,
        command_result,
        cache_dir=resolved_cache_dir,
    )
    _write_text_if_needed(root, stdout_log_path, str(command_result.get("stdout") or ""))
    _write_text_if_needed(root, stderr_log_path, str(command_result.get("stderr") or ""))
    returncode = int(command_result.get("returncode") or 0)
    payload = {
        "schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        **long_gate_cache_metadata(root, cache_dir=resolved_cache_dir),
        "entry_id": entry_id,
        "status": "failed",
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "duration_s": float(command_result.get("duration_s") or 0.0),
        "display": str(entry.get("display") or ""),
        "args": [str(arg) for arg in list(entry.get("args") or [])],
        "command": normalize_quality_gate_command(entry.get("command") or entry),
        "fingerprint": dict(fingerprint),
        "returncode": returncode,
        "stdout_content": str(command_result.get("stdout") or ""),
        "stderr_content": str(command_result.get("stderr") or ""),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "output_files": [],
        "timed_out": bool(command_result.get("timed_out")),
        "interrupted": bool(command_result.get("interrupted")),
        "partial_write": bool(command_result.get("partial_write")),
        "execution_mode": str(command_result.get("execution_mode") or "executed"),
        "receipt_path": str(command_result.get("receipt_path") or ""),
        "run_id": str(command_result.get("run_id") or ""),
        "command_index": command_result.get("command_index"),
    }
    rel_path = _failure_rel_path(entry_id, cache_dir=resolved_cache_dir)
    abs_path = _abs_from_rel(root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
