from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, TypedDict

from tools.long_gate_fingerprint import diff_fingerprints, stable_json_hash
from tools.long_gate_manifest import LONG_GATE_SCHEMA_VERSION
from tools.quality_gate_shared import REPO_ROOT

LONG_GATE_CACHE_DIR_REL = os.path.join("evidence", "QualityGate", "long_gate").replace("\\", "/")
LONG_GATE_RESULTS_DIR_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "results").replace("\\", "/")
LONG_GATE_LOGS_DIR_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "logs").replace("\\", "/")
LONG_GATE_RESULTS_DIR_NAME = "results"
LONG_GATE_LOGS_DIR_NAME = "logs"


class ReuseEvaluation(TypedDict):
    decision: Dict[str, Any]
    validated_success: Optional[Dict[str, Any]]
    stdout: str
    stderr: str


def _safe_entry_id(entry_id: str) -> str:
    return str(entry_id or "").replace("\\", "_").replace("/", "_").strip() or "unknown"


def _repo_root(repo_root: Optional[str]) -> str:
    return os.path.realpath(repo_root or REPO_ROOT)


def _abs_from_rel(repo_root: str, rel_path: str) -> str:
    root = os.path.realpath(repo_root)
    raw_path = str(rel_path or "").replace("\\", "/")
    if not raw_path:
        raise ValueError("cache path is empty")
    if os.path.isabs(raw_path):
        abs_path = os.path.realpath(raw_path)
    else:
        abs_path = os.path.realpath(os.path.join(root, raw_path.replace("/", os.sep)))
    if abs_path != root and not abs_path.startswith(root + os.sep):
        raise ValueError(f"cache path escapes repo root: {raw_path}")
    return abs_path


def _rel_from_path(repo_root: str, path: str) -> str:
    root = os.path.realpath(repo_root)
    raw_path = str(path or "").replace("\\", "/")
    if os.path.isabs(raw_path):
        abs_path = _abs_from_rel(root, raw_path)
        return os.path.relpath(abs_path, root).replace("\\", "/")
    _abs_from_rel(root, raw_path)
    if raw_path.startswith("./"):
        raw_path = raw_path[2:]
    return raw_path


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
        raise ValueError(
            f"long gate cache dir must be under {LONG_GATE_CACHE_DIR_REL}: {raw_path}"
        )
    return os.path.relpath(abs_path, root).replace("\\", "/")


def _cache_child_rel(cache_dir: str, child: str) -> str:
    return os.path.join(str(cache_dir or LONG_GATE_CACHE_DIR_REL), child).replace("\\", "/")


def _sha256_bytes(path: str) -> str:
    import hashlib

    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_text_if_needed(repo_root: str, rel_path: str, text: str) -> None:
    abs_path = _abs_from_rel(repo_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(str(text or ""))


def _success_rel_path(entry_id: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> str:
    return _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_RESULTS_DIR_NAME, f"{_safe_entry_id(entry_id)}.success.json"),
    )


def _failure_rel_path(entry_id: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> str:
    return _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_RESULTS_DIR_NAME, f"{_safe_entry_id(entry_id)}.failure.json"),
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


def _decision(
    entry_id: str,
    decision: str,
    reason: str,
    *,
    invalidated_by: Optional[Sequence[str]] = None,
    previous_completed_at: Optional[str] = None,
    previous_result_path: Optional[str] = None,
    current_fingerprint_hash: str = "",
) -> Dict[str, Any]:
    return {
        "entry_id": entry_id,
        "decision": decision,
        "reuse_allowed": decision == "reuse",
        "reason": reason,
        "invalidated_by": list(invalidated_by or []),
        "previous_completed_at": previous_completed_at,
        "previous_result_path": previous_result_path,
        "current_fingerprint_hash": current_fingerprint_hash,
    }


def _missing_field(payload: Mapping[str, Any], field: str) -> Optional[str]:
    if field not in payload:
        return f"cache unreadable/corrupt/missing required field: {field}"
    return None


def _validate_required_fields(payload: Mapping[str, Any]) -> Optional[str]:
    for field in (
        "schema_version",
        "entry_id",
        "status",
        "command_hash",
        "fingerprint_hash",
        "fingerprint",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
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
    for field in ("timed_out", "interrupted", "partial_write"):
        if not isinstance(payload.get(field), bool):
            return f"cache unreadable/corrupt/missing required field: {field}"
    return None


def _fingerprint_hash_is_self_consistent(previous: Mapping[str, Any]) -> Optional[str]:
    fingerprint = previous.get("fingerprint")
    if not isinstance(fingerprint, dict):
        return "cache unreadable/corrupt: fingerprint is not an object"
    embedded_hash = str(fingerprint.get("hash") or "")
    top_level_hash = str(previous.get("fingerprint_hash") or "")
    if not embedded_hash or embedded_hash != top_level_hash:
        return "cache unreadable/corrupt: fingerprint hash mismatch"
    without_hash = {key: value for key, value in fingerprint.items() if key != "hash"}
    recomputed = f"sha256:{stable_json_hash(without_hash)}"
    if embedded_hash != recomputed:
        return "cache unreadable/corrupt: fingerprint hash mismatch"
    return None


def _file_hash_match_error(repo_root: str, rel_path: str, expected_hash: str, *, missing_message: str) -> Optional[str]:
    try:
        abs_path = _abs_from_rel(repo_root, rel_path)
    except ValueError as exc:
        return str(exc)
    if not os.path.isfile(abs_path) or _sha256_bytes(abs_path) != str(expected_hash or ""):
        return missing_message
    return None


def _read_text_file_after_hash_check(
    repo_root: str,
    rel_path: str,
    expected_hash: str,
    *,
    missing_message: str,
) -> Tuple[str, Optional[str]]:
    try:
        abs_path = _abs_from_rel(repo_root, rel_path)
    except ValueError as exc:
        return "", str(exc)

    if not os.path.isfile(abs_path):
        return "", missing_message

    with open(abs_path, "rb") as handle:
        data = handle.read()

    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != str(expected_hash or ""):
        return "", missing_message

    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return "", f"previous logs unreadable as utf-8: {rel_path}: {exc}"


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

    for path_key, hash_key, output_key in (
        ("stdout_log_path", "stdout_sha256", "stdout"),
        ("stderr_log_path", "stderr_sha256", "stderr"),
    ):
        rel_path = str(previous.get(path_key) or "").replace("\\", "/")
        if not rel_path:
            return None, "previous logs missing or hash mismatch"
        path_error = _cache_log_path_error(
            repo_root,
            rel_path,
            cache_dir=cache_dir,
            expected_rel_path=expected_paths[path_key],
        )
        if path_error:
            return None, path_error
        text, error = _read_text_file_after_hash_check(
            repo_root,
            rel_path,
            str(previous.get(hash_key) or ""),
            missing_message="previous logs missing or hash mismatch",
        )
        if error:
            return None, error

        texts[output_key] = text

    return texts, None


def _output_files_exist_and_hash_match(repo_root: str, previous: Mapping[str, Any]) -> Optional[str]:
    for row in list(previous.get("output_files") or []):
        if not isinstance(row, dict):
            return "previous output files missing or hash mismatch"
        rel_path = str(row.get("path") or "").replace("\\", "/")
        if not rel_path:
            return "previous output files missing or hash mismatch"
        error = _file_hash_match_error(
            repo_root,
            rel_path,
            str(row.get("sha256") or ""),
            missing_message="previous output files missing or hash mismatch",
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


def _output_files_cover_declared_paths(repo_root: str, entry: Mapping[str, Any], previous: Mapping[str, Any]) -> Optional[str]:
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


def evaluate_reuse(
    entry: Mapping[str, Any],
    current_fingerprint: Mapping[str, Any],
    *,
    repo_root: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> ReuseEvaluation:
    root = _repo_root(repo_root)
    resolved_cache_dir = resolve_cache_dir(root, cache_dir)
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    current_hash = str(current_fingerprint.get("hash") or "")
    if not bool(entry.get("reuse_allowed")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "reuse is disabled for this entry", current_fingerprint_hash=current_hash)
        )
    result_rel = _success_rel_path(entry_id, cache_dir=resolved_cache_dir)
    previous, load_error = _load_json_object(_abs_from_rel(root, result_rel))
    if load_error == "missing":
        return _reuse_evaluation(
            _decision(entry_id, "run", "no previous success cache", current_fingerprint_hash=current_hash)
        )
    if load_error:
        return _reuse_evaluation(_decision(entry_id, "run", load_error, current_fingerprint_hash=current_hash))
    assert previous is not None

    required_error = _validate_required_fields(previous)
    if required_error:
        return _reuse_evaluation(_decision(entry_id, "run", required_error, current_fingerprint_hash=current_hash))
    try:
        schema_version = int(previous.get("schema_version") or 0)
        returncode = int(previous.get("returncode") or 0)
    except (TypeError, ValueError):
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "cache unreadable/corrupt: numeric field has invalid type",
                current_fingerprint_hash=current_hash,
            )
        )
    if schema_version != LONG_GATE_SCHEMA_VERSION:
        return _reuse_evaluation(_decision(entry_id, "run", "cache schema changed", current_fingerprint_hash=current_hash))
    fingerprint_error = _fingerprint_hash_is_self_consistent(previous)
    if fingerprint_error:
        return _reuse_evaluation(_decision(entry_id, "run", fingerprint_error, current_fingerprint_hash=current_hash))
    if str(previous.get("entry_id") or "") != entry_id:
        return _reuse_evaluation(_decision(entry_id, "run", "cache entry_id changed", current_fingerprint_hash=current_hash))
    if str(previous.get("status") or "") != "passed":
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was not successful", current_fingerprint_hash=current_hash)
        )
    if bool(previous.get("timed_out")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result timed out", current_fingerprint_hash=current_hash)
        )
    if bool(previous.get("interrupted")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was interrupted", current_fingerprint_hash=current_hash)
        )
    if bool(previous.get("partial_write")):
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous result was partially written", current_fingerprint_hash=current_hash)
        )
    previous_fingerprint = previous.get("fingerprint") if isinstance(previous.get("fingerprint"), dict) else {}
    if previous_fingerprint.get("schema_version") != current_fingerprint.get("schema_version"):
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=["fingerprint schema changed"],
                previous_completed_at=str(previous.get("completed_at") or ""),
                previous_result_path=result_rel,
                current_fingerprint_hash=current_hash,
            )
        )
    if returncode != 0:
        return _reuse_evaluation(
            _decision(entry_id, "run", "previous returncode was non-zero", current_fingerprint_hash=current_hash)
        )
    if str(previous.get("command_hash") or "") != str(entry.get("command_hash") or ""):
        return _reuse_evaluation(
            _decision(entry_id, "run", "command identity changed", current_fingerprint_hash=current_hash)
        )
    if str(previous.get("fingerprint_hash") or "") != current_hash:
        diff = diff_fingerprints(previous_fingerprint, current_fingerprint)
        reasons = list(diff.get("reasons") or ["input fingerprint changed"])
        return _reuse_evaluation(
            _decision(
                entry_id,
                "run",
                "input fingerprint changed",
                invalidated_by=reasons,
                previous_completed_at=str(previous.get("completed_at") or ""),
                previous_result_path=result_rel,
                current_fingerprint_hash=current_hash,
            )
        )

    log_texts, log_error = _validated_log_texts(
        root,
        previous,
        cache_dir=resolved_cache_dir,
        entry_id=entry_id,
    )
    if log_error:
        return _reuse_evaluation(_decision(entry_id, "run", log_error, current_fingerprint_hash=current_hash))
    output_error = _output_files_exist_and_hash_match(root, previous)
    if output_error:
        return _reuse_evaluation(_decision(entry_id, "run", output_error, current_fingerprint_hash=current_hash))
    output_coverage_error = _output_files_cover_declared_paths(root, entry, previous)
    if output_coverage_error:
        return _reuse_evaluation(
            _decision(entry_id, "run", output_coverage_error, current_fingerprint_hash=current_hash)
        )

    decision = _decision(
        entry_id,
        "reuse",
        "fingerprint matched previous successful result",
        previous_completed_at=str(previous.get("completed_at") or ""),
        previous_result_path=result_rel,
        current_fingerprint_hash=current_hash,
    )
    return _reuse_evaluation(
        decision,
        validated_success=previous,
        stdout=str((log_texts or {}).get("stdout") or ""),
        stderr=str((log_texts or {}).get("stderr") or ""),
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
        os.path.join(LONG_GATE_LOGS_DIR_NAME, f"{safe_entry_id}.stdout.log"),
    )
    stderr_log_path = _cache_child_rel(
        cache_dir,
        os.path.join(LONG_GATE_LOGS_DIR_NAME, f"{safe_entry_id}.stderr.log"),
    )
    return stdout_log_path, stderr_log_path


def _hash_output_files(repo_root: str, output_files: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in list(output_files or []):
        rel_path = _rel_from_path(repo_root, str(path))
        abs_path = _abs_from_rel(repo_root, rel_path)
        if not os.path.isfile(abs_path):
            raise ValueError(f"long gate output file does not exist: {rel_path}")
        rows.append(
            {
                "path": rel_path,
                "sha256": _sha256_bytes(abs_path),
            }
        )
    return rows


def _assert_output_files_cover_declared_paths(repo_root: str, entry: Mapping[str, Any], output_file_rows: Sequence[Mapping[str, Any]]) -> None:
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
    try:
        returncode = int(command_result.get("returncode"))
    except (TypeError, ValueError) as exc:
        raise ValueError("long gate success cache requires numeric returncode") from exc

    if returncode != 0:
        raise ValueError("long gate success cache requires returncode == 0")

    for field in ("timed_out", "interrupted", "partial_write"):
        if bool(command_result.get(field)):
            raise ValueError(f"long gate success cache requires {field} == False")


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
    _assert_success_command_result(command_result)
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    stdout_log_path, stderr_log_path = _log_paths_for_result(
        entry_id,
        command_result,
        cache_dir=resolved_cache_dir,
    )
    _write_text_if_needed(root, stdout_log_path, str(command_result.get("stdout") or ""))
    _write_text_if_needed(root, stderr_log_path, str(command_result.get("stderr") or ""))
    output_file_rows = _hash_output_files(root, output_files)
    _assert_output_files_cover_declared_paths(root, entry, output_file_rows)
    payload = {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "entry_id": entry_id,
        "status": "passed",
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "duration_s": float(command_result.get("duration_s") or 0.0),
        "display": str(entry.get("display") or ""),
        "args": [str(arg) for arg in list(entry.get("args") or [])],
        "command_hash": str(entry.get("command_hash") or ""),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "fingerprint": dict(fingerprint),
        "returncode": int(command_result.get("returncode")),
        "stdout_sha256": _sha256_bytes(_abs_from_rel(root, stdout_log_path)),
        "stderr_sha256": _sha256_bytes(_abs_from_rel(root, stderr_log_path)),
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "output_files": output_file_rows,
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
    entry_id = _safe_entry_id(str(entry.get("entry_id") or ""))
    payload = {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "entry_id": entry_id,
        "status": "failed",
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "display": str(entry.get("display") or ""),
        "args": [str(arg) for arg in list(entry.get("args") or [])],
        "command_hash": str(entry.get("command_hash") or ""),
        "fingerprint_hash": str(fingerprint.get("hash") or ""),
        "fingerprint": dict(fingerprint),
        "returncode": int(command_result.get("returncode") or 0),
        "result_hash": stable_json_hash(dict(command_result)),
    }
    rel_path = _failure_rel_path(entry_id, cache_dir=resolved_cache_dir)
    abs_path = _abs_from_rel(root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
