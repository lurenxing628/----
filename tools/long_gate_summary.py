from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from tools.long_gate_cache import LONG_GATE_CACHE_DIR_REL

SUMMARY_SCHEMA_VERSION = 1
SUMMARY_JSON_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "summary.json").replace("\\", "/")
SUMMARY_MD_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "summary.md").replace("\\", "/")


def tail_text(text: str, max_lines: int = 80) -> str:
    lines = str(text or "").splitlines()
    if not lines:
        return "<empty>"
    return "\n".join(lines[-int(max_lines) :])


def _rel_path(repo_root: str, path: str) -> str:
    raw_path = str(path or "").replace("\\", "/")
    if not raw_path:
        return ""
    root = os.path.realpath(os.path.abspath(repo_root))
    if os.path.isabs(raw_path):
        abs_path = os.path.realpath(raw_path)
    else:
        abs_path = os.path.realpath(os.path.join(root, raw_path.replace("/", os.sep)))
    if abs_path == root or abs_path.startswith(root + os.sep):
        return os.path.relpath(abs_path, root).replace("\\", "/")
    return raw_path


def _command_text_from_display(display: str) -> str:
    return str(display or "").strip()


def _pytest_nodeids_from_text(text: str) -> List[str]:
    nodeids: List[str] = []
    pattern = re.compile(r"(?P<nodeid>(?:[A-Za-z0-9_.\-/]+/)?tests/[^\s:]+\.py::[^\s]+)")
    for match in pattern.finditer(str(text or "")):
        nodeid = match.group("nodeid").strip().rstrip(".,;")
        if nodeid and nodeid not in nodeids:
            nodeids.append(nodeid)
    return nodeids


def _display_is_pytest_command(display: str) -> bool:
    normalized = str(display or "").strip()
    return normalized == "python -m pytest" or normalized.startswith("python -m pytest ")


def extract_copyable_failure(
    *,
    entry_id: str,
    display: str,
    result: Mapping[str, Any],
    receipt_path: str,
    max_lines: int = 80,
) -> Dict[str, Any]:
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    copyable_command = _command_text_from_display(display)
    nodeids = []
    if _display_is_pytest_command(copyable_command):
        nodeids = _pytest_nodeids_from_text("\n".join([copyable_command, stdout, stderr]))
    if nodeids:
        copyable_command = "python -m pytest -q " + " ".join(shlex.quote(nodeid) for nodeid in nodeids)
    return {
        "entry_id": str(entry_id or ""),
        "display": _command_text_from_display(display),
        "copyable_command": copyable_command,
        "copyable_nodeids": nodeids,
        "receipt_path": str(receipt_path or ""),
        "stdout_log_path": str(result.get("stdout_log_path") or ""),
        "stderr_log_path": str(result.get("stderr_log_path") or ""),
        "stdout_tail": tail_text(stdout, max_lines=max_lines),
        "stderr_tail": tail_text(stderr, max_lines=max_lines),
    }


def _result_returncode(result: Optional[Mapping[str, Any]]) -> Optional[int]:
    if result is None or "returncode" not in result:
        return None
    try:
        return int(result.get("returncode"))
    except (TypeError, ValueError):
        return None


def _duration_value(result: Optional[Mapping[str, Any]], key: str) -> float:
    if result is None:
        return 0.0
    try:
        return float(result.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool_value(result: Optional[Mapping[str, Any]], key: str) -> bool:
    if result is None:
        return False
    return bool(result.get(key))


def _summary_execution_mode(
    decision: Mapping[str, Any],
    *,
    result: Optional[Mapping[str, Any]],
    execution_mode: str,
) -> str:
    if execution_mode:
        return execution_mode
    decision_value = str(decision.get("decision") or "")
    if decision_value == "reuse":
        return "reused_success_cache"
    if decision_value in {"planned_only", "disabled"}:
        return decision_value
    if result is not None:
        return str(result.get("execution_mode") or "executed")
    return ""


def build_summary_entry(
    *,
    index: int,
    entry: Mapping[str, Any],
    decision: Mapping[str, Any],
    result: Optional[Mapping[str, Any]] = None,
    receipt_path: str = "",
    output_files: Optional[Sequence[Mapping[str, Any]]] = None,
    execution_mode: str = "",
    failed: bool = False,
) -> Dict[str, Any]:
    invalidated_by = list(decision.get("invalidated_by") or [])
    resolved_execution_mode = _summary_execution_mode(decision, result=result, execution_mode=execution_mode)
    returncode = _result_returncode(result)
    failed_value = bool(failed or (returncode is not None and returncode != 0))
    return {
        "index": int(index),
        "entry_id": str(entry.get("entry_id") or decision.get("entry_id") or ""),
        "entry_type": str(entry.get("entry_type") or ""),
        "display": str(entry.get("display") or ""),
        "cache_status": str(entry.get("cache_status") or ""),
        "decision": str(decision.get("decision") or ""),
        "reason": str(decision.get("reason") or ""),
        "invalidated_by": invalidated_by,
        "execution_mode": resolved_execution_mode,
        "returncode": returncode,
        "failed": failed_value,
        "receipt_path": str(receipt_path or ""),
        "stdout_log_path": str((result or {}).get("stdout_log_path") or ""),
        "stderr_log_path": str((result or {}).get("stderr_log_path") or ""),
        "output_files": [dict(item) for item in list(output_files or [])],
        "current_fingerprint_hash": str(decision.get("current_fingerprint_hash") or ""),
        "previous_result_path": str(decision.get("previous_result_path") or ""),
        "duration_s": _duration_value(result, "duration_s"),
        "original_duration_s": _duration_value(result, "original_duration_s"),
        "timed_out": _bool_value(result, "timed_out"),
        "interrupted": _bool_value(result, "interrupted"),
        "partial_write": _bool_value(result, "partial_write"),
    }


def _empty_counts() -> Dict[str, int]:
    return {
        "executed": 0,
        "reused": 0,
        "failed": 0,
        "planned_only": 0,
        "disabled": 0,
    }


def _count_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = _empty_counts()
    for entry in entries:
        if bool(entry.get("failed")):
            counts["failed"] += 1
            continue
        execution_mode = str(entry.get("execution_mode") or "")
        decision = str(entry.get("decision") or "")
        if execution_mode == "reused_success_cache" or decision == "reuse":
            counts["reused"] += 1
        elif execution_mode == "executed":
            counts["executed"] += 1
        elif decision == "planned_only" or execution_mode == "planned_only":
            counts["planned_only"] += 1
        elif decision == "disabled" or execution_mode == "disabled":
            counts["disabled"] += 1
    return counts


def build_long_gate_summary(
    *,
    run_id: str,
    repo_root: str,
    head_sha: str,
    worktree_clean: bool,
    cache_enabled: bool,
    mode: str,
    entries: Sequence[Mapping[str, Any]],
    failure: Optional[Mapping[str, Any]] = None,
    cache_dir: str = LONG_GATE_CACHE_DIR_REL,
) -> Dict[str, Any]:
    normalized_entries = [dict(entry) for entry in list(entries or [])]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": str(run_id or ""),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": os.path.abspath(repo_root),
        "head_sha": str(head_sha or ""),
        "worktree_clean": bool(worktree_clean),
        "cache_enabled": bool(cache_enabled),
        "cache_dir": str(cache_dir or LONG_GATE_CACHE_DIR_REL).replace("\\", "/"),
        "mode": str(mode or "run"),
        "counts": _count_entries(normalized_entries),
        "entries": normalized_entries,
        "failure": dict(failure) if failure is not None else None,
    }


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    counts = dict(summary.get("counts") or {})
    lines = [
        "# Long gate summary",
        "",
        f"- run_id: {summary.get('run_id') or ''}",
        f"- head_sha: {summary.get('head_sha') or ''}",
        f"- worktree_clean: {bool(summary.get('worktree_clean'))}",
        f"- cache_enabled: {bool(summary.get('cache_enabled'))}",
        f"- cache_dir: {summary.get('cache_dir') or ''}",
        f"- mode: {summary.get('mode') or ''}",
        "",
        "## Counts",
    ]
    for key in ("executed", "reused", "failed", "planned_only", "disabled"):
        lines.append(f"- {key}: {int(counts.get(key) or 0)}")
    lines.extend(
        [
            "",
            "## Entries",
            "",
            "| # | entry | decision | cache | execution | reason | invalidated_by | receipt |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for entry in list(summary.get("entries") or []):
        invalidated_by = "; ".join(str(item) for item in list(entry.get("invalidated_by") or []))
        lines.append(
            "| {index} | {entry_id} | {decision} | {cache_status} | {execution_mode} | {reason} | {invalidated_by} | {receipt_path} |".format(
                index=entry.get("index") or "",
                entry_id=entry.get("entry_id") or "",
                decision=entry.get("decision") or "",
                cache_status=entry.get("cache_status") or "",
                execution_mode=entry.get("execution_mode") or "",
                reason=str(entry.get("reason") or "").replace("|", "\\|"),
                invalidated_by=invalidated_by.replace("|", "\\|"),
                receipt_path=entry.get("receipt_path") or "",
            )
        )
    failure = summary.get("failure")
    if isinstance(failure, Mapping):
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- entry_id: {failure.get('entry_id') or ''}",
                f"- display: {failure.get('display') or ''}",
                f"- copyable_command: {failure.get('copyable_command') or ''}",
                f"- copyable_nodeids: {', '.join(str(item) for item in list(failure.get('copyable_nodeids') or []))}",
                f"- receipt_path: {failure.get('receipt_path') or ''}",
                f"- stdout_log_path: {failure.get('stdout_log_path') or ''}",
                f"- stderr_log_path: {failure.get('stderr_log_path') or ''}",
                "",
                "### stdout tail",
                "",
                "```text",
                str(failure.get("stdout_tail") or ""),
                "```",
                "",
                "### stderr tail",
                "",
                "```text",
                str(failure.get("stderr_tail") or ""),
                "```",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def write_long_gate_summary(summary: Mapping[str, Any], repo_root: str) -> Dict[str, str]:
    root = os.path.abspath(repo_root)
    summary_json_abs = os.path.join(root, SUMMARY_JSON_REL.replace("/", os.sep))
    summary_md_abs = os.path.join(root, SUMMARY_MD_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(summary_json_abs), exist_ok=True)
    with open(summary_json_abs, "w", encoding="utf-8") as handle:
        json.dump(dict(summary), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(summary_md_abs, "w", encoding="utf-8", newline="") as handle:
        handle.write(render_summary_markdown(summary))
    return {
        "summary_json": _rel_path(root, summary_json_abs),
        "summary_md": _rel_path(root, summary_md_abs),
    }
