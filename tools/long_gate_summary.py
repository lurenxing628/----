from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from tools.long_gate_paths import LONG_GATE_CACHE_DIR_REL
from tools.long_gate_records import CacheDecision, GateEntry, RuntimeEntry, StepOutcome
from tools.long_gate_schema import LONG_GATE_SUMMARY_SCHEMA_VERSION
from tools.quality_gate_shared import sanitize_quality_gate_output

SUMMARY_JSON_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "summary.v2.json").replace("\\", "/")
SUMMARY_MD_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "summary.v2.md").replace("\\", "/")
TAIL_LINES = 80


def tail_text(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return "<empty>"
    return "\n".join(lines[-TAIL_LINES:])


def _input_snapshot_overview(fingerprint: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if fingerprint is None:
        return {}
    return {
        "schema_version": fingerprint["schema_version"],
        "path_count": len(fingerprint["components"]["files"]["files"]),
    }


def fingerprint_change_reference(change: Mapping[str, Any]) -> Dict[str, Any]:
    """摘要与 explain 只引用变化位置，完整内容留在缓存记录里。"""
    return {key: change[key] for key in ("component", "reason", "path", "key", "field") if key in change}


def _compact_values_text(values: Sequence[Any], *, limit: int = 10) -> str:
    shown = [str(item) for item in values[:limit]]
    suffix = f"; ... {len(values) - len(shown)} more" if len(values) > len(shown) else ""
    return "; ".join(shown) + suffix


def _pytest_nodeids_from_text(text: str) -> List[str]:
    nodeids: List[str] = []
    pattern = re.compile(r"(?P<nodeid>(?:[A-Za-z0-9_.\-/]+/)?tests/[^\s:]+\.py::[^\s]+)")
    for match in pattern.finditer(text):
        nodeid = match.group("nodeid").strip().rstrip(".,;")
        if nodeid and nodeid not in nodeids:
            nodeids.append(nodeid)
    return nodeids


def _display_is_pytest_command(display: str) -> bool:
    return display == "python -m pytest" or display.startswith("python -m pytest ")


def copyable_failure(entry: GateEntry, outcome: StepOutcome) -> Dict[str, Any]:
    """失败步骤的可复制重跑信息。"""
    result = outcome.result
    display = entry.spec.display
    stdout = sanitize_quality_gate_output(result.stdout)
    stderr = sanitize_quality_gate_output(result.stderr)
    copyable_command = display
    nodeids: List[str] = []
    if _display_is_pytest_command(display):
        nodeids = _pytest_nodeids_from_text("\n".join([display, stdout, stderr]))
    if nodeids:
        copyable_command = "python -m pytest -q " + " ".join(shlex.quote(nodeid) for nodeid in nodeids)
    return {
        "entry_id": entry.spec.check_id,
        "display": display,
        "copyable_command": copyable_command,
        "copyable_nodeids": nodeids,
        "receipt_path": outcome.receipt_path,
        "stdout_log_path": result.stdout_log_path,
        "stderr_log_path": result.stderr_log_path,
        "stdout_tail": tail_text(stdout),
        "stderr_tail": tail_text(stderr),
    }


def _planned_execution_mode(decision: CacheDecision) -> str:
    """尚未执行的条目按决策给出计划中的执行方式。"""
    if decision.kind == "reuse":
        return "reused_success_cache"
    if decision.kind == "disabled":
        return "disabled"
    return ""


def summary_entry(rt: RuntimeEntry) -> Dict[str, Any]:
    """summary 与 explain 共用的条目投影，由 RuntimeEntry 显式生成。"""
    decision = rt.decision
    spec = rt.entry.spec
    outcome = rt.outcome
    fingerprint_error = decision.fingerprint_error
    row: Dict[str, Any] = {
        "index": rt.entry.index,
        "entry_id": spec.check_id,
        "entry_type": spec.entry_type,
        "proof_kind": spec.proof_kind,
        "display": spec.display,
        "env_overlay_keys": sorted(rt.entry.command["env_overlay"]),
        "cache_status": "cache_unavailable" if decision.cache_unavailable else "enabled",
        "decision": decision.kind,
        "reason": decision.reason,
        "invalidated_by": list(decision.invalidated_by),
        "cache_unavailable": decision.cache_unavailable,
        "fingerprint_error": {}
        if fingerprint_error is None
        else {"message": fingerprint_error.message, "failure_kind": fingerprint_error.failure_kind},
        "fingerprint_diff": [fingerprint_change_reference(change) for change in decision.fingerprint_diff],
        "input_snapshot": _input_snapshot_overview(rt.fingerprint),
        "previous_result_path": decision.previous_result_path,
    }
    if outcome is None:
        row.update(
            execution_mode=_planned_execution_mode(decision),
            returncode=None,
            failed=False,
            receipt_path="",
            stdout_log_path="",
            stderr_log_path="",
            output_files=[],
            duration_s=0.0,
            duration_kind="",
            original_duration_s=0.0,
        )
        return row
    result = outcome.result
    row.update(
        execution_mode=result.execution_mode,
        returncode=result.returncode,
        failed=outcome.failed,
        receipt_path=outcome.receipt_path,
        stdout_log_path=result.stdout_log_path,
        stderr_log_path=result.stderr_log_path,
        output_files=[{"path": path} for path in outcome.output_files],
        duration_s=result.duration_s,
        duration_kind=result.duration_kind,
        original_duration_s=0.0 if result.original_duration_s is None else result.original_duration_s,
    )
    return row


_COUNT_BY_EXECUTION_MODE = {
    "executed": "executed",
    "reused_success_cache": "reused",
    "resumed_success": "reused",
    "disabled": "disabled",
}
SUMMARY_COUNT_KEYS = ("executed", "reused", "failed", "disabled")
#: 复用旧结果（long-gate 缓存或续跑 receipt）本次只付出的开销。
_REUSE_DURATION_KINDS = frozenset({"reuse_overhead", "resume_overhead"})


def _count_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {key: 0 for key in SUMMARY_COUNT_KEYS}
    for entry in entries:
        if entry["failed"]:
            counts["failed"] += 1
        elif entry["execution_mode"] in _COUNT_BY_EXECUTION_MODE:
            counts[_COUNT_BY_EXECUTION_MODE[entry["execution_mode"]]] += 1
    return counts


def _build_duration_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    ranked_entries = sorted(
        [entry for entry in entries if entry["duration_s"] > 0.0 or entry["original_duration_s"] > 0.0],
        key=lambda entry: entry["duration_s"],
        reverse=True,
    )
    return {
        "total_s": sum(entry["duration_s"] for entry in entries),
        "executed_total_s": sum(entry["duration_s"] for entry in entries if entry["execution_mode"] == "executed"),
        "reuse_overhead_total_s": sum(
            entry["duration_s"] for entry in entries if entry["duration_kind"] in _REUSE_DURATION_KINDS
        ),
        "top_entries": [
            {
                "rank": rank,
                "entry_id": entry["entry_id"],
                "display": entry["display"],
                "execution_mode": entry["execution_mode"],
                "duration_s": entry["duration_s"],
                "duration_kind": entry["duration_kind"],
                "original_duration_s": entry["original_duration_s"],
                "reason": entry["reason"],
            }
            for rank, entry in enumerate(ranked_entries[:10], start=1)
        ],
    }


def build_long_gate_summary(
    *,
    run_id: str,
    repo_root: str,
    head_sha: str,
    worktree_clean: bool,
    cache_enabled: bool,
    entries: Sequence[Mapping[str, Any]],
    failure: Optional[Mapping[str, Any]],
    cache_dir: str,
) -> Dict[str, Any]:
    return {
        "schema_version": LONG_GATE_SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": os.path.abspath(repo_root),
        "head_sha": head_sha,
        "worktree_clean": worktree_clean,
        "cache_enabled": cache_enabled,
        "cache_dir": cache_dir,
        "counts": _count_entries(entries),
        "duration": _build_duration_summary(entries),
        "entries": entries,
        "failure": failure,
    }


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _format_original_duration(entry: Mapping[str, Any]) -> str:
    original = entry["original_duration_s"]
    if original <= 0.0 and entry["execution_mode"] == "reused_success_cache":
        return "unknown"
    return f"{original:.3f}"


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    counts = summary["counts"]
    duration = summary["duration"]
    lines = [
        "# Long gate summary",
        "",
        f"- run_id: {summary['run_id']}",
        f"- head_sha: {summary['head_sha']}",
        f"- worktree_clean: {summary['worktree_clean']}",
        f"- cache_enabled: {summary['cache_enabled']}",
        f"- cache_dir: {summary['cache_dir']}",
        "",
        "## Counts",
    ]
    lines.extend(f"- {key}: {counts[key]}" for key in SUMMARY_COUNT_KEYS)
    lines.extend(
        [
            "",
            "## Duration",
            "",
            f"- total_s: {duration['total_s']:.3f}",
            f"- executed_total_s: {duration['executed_total_s']:.3f}",
            f"- reuse_overhead_total_s: {duration['reuse_overhead_total_s']:.3f}",
            "",
            "## Slow entries",
            "",
            "| rank | entry | execution | duration_s | original_duration_s | reason |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in duration["top_entries"]:
        lines.append(
            f"| {entry['rank']} | {_escape_cell(entry['entry_id'])} | {_escape_cell(entry['execution_mode'])} "
            f"| {entry['duration_s']:.3f} | {_format_original_duration(entry)} | {_escape_cell(entry['reason'])} |"
        )
    lines.extend(
        [
            "",
            "## Entries",
            "",
            "| # | entry | decision | cache | execution | env_overlay_keys | reason | invalidated_by | receipt |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for entry in summary["entries"]:
        lines.append(
            f"| {entry['index']} | {entry['entry_id']} | {entry['decision']} | {entry['cache_status']} "
            f"| {entry['execution_mode']} | {_escape_cell(', '.join(entry['env_overlay_keys']))} "
            f"| {_escape_cell(entry['reason'])} | {_escape_cell(_compact_values_text(entry['invalidated_by']))} "
            f"| {entry['receipt_path']} |"
        )
    failure = summary["failure"]
    if failure is not None:
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- entry_id: {failure['entry_id']}",
                f"- display: {failure['display']}",
                f"- copyable_command: {failure['copyable_command']}",
                f"- copyable_nodeids: {', '.join(failure['copyable_nodeids'])}",
                f"- receipt_path: {failure['receipt_path']}",
                f"- stdout_log_path: {failure['stdout_log_path']}",
                f"- stderr_log_path: {failure['stderr_log_path']}",
                "",
                "### stdout tail",
                "",
                "```text",
                failure["stdout_tail"],
                "```",
                "",
                "### stderr tail",
                "",
                "```text",
                failure["stderr_tail"],
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "For local profiling, run the exact final proof command and inspect evidence/QualityGate/long_gate/summary.v2.json.",
            "",
        ]
    )
    return "\n".join(lines)


def write_long_gate_summary(summary: Mapping[str, Any], repo_root: str) -> Dict[str, str]:
    summary_json_abs = os.path.join(repo_root, SUMMARY_JSON_REL.replace("/", os.sep))
    summary_md_abs = os.path.join(repo_root, SUMMARY_MD_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(summary_json_abs), exist_ok=True)
    with open(summary_json_abs, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(summary_md_abs, "w", encoding="utf-8", newline="") as handle:
        handle.write(render_summary_markdown(summary))
    return {"summary_json": SUMMARY_JSON_REL, "summary_md": SUMMARY_MD_REL}
