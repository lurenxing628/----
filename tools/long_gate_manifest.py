from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import quality_gate_shared
from tools.long_gate_paths import resolve_repo_root
from tools.long_gate_records import GateEntry, Receipt, Rejection, admit_receipt, gate_entries
from tools.long_gate_schema import (
    LONG_GATE_MANIFEST_SCHEMA_VERSION,
    LONG_GATE_RUNNER_VERSION_PATHS,
    LONG_GATE_TOOLING_VERSION_PATHS,
)
from tools.quality_gate_shared import GateCheckSpec
from tools.test_registry import scope_matches_path

LocalReceipt = Tuple[str, Union[Receipt, Rejection]]


def _dedupe(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(items))


def normalize_repo_path(path: str) -> str:
    """规范化用户在命令行给的路径；声明的范围与 Git 输出都不经过这里。"""
    normalized = str(path or "").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _matches_for_scopes(paths: Sequence[str], scopes: Sequence[str]) -> List[Dict[str, str]]:
    return [{"path": path, "scope": scope} for path in paths for scope in scopes if scope_matches_path(path, scope)]


def _impact_reason(categories: Sequence[str], *, global_affected: bool) -> str:
    pieces: List[str] = []
    if global_affected:
        pieces.append("global runner/tooling changed")
    pieces.extend(category + " scope changed" for category in categories if category != "global_runner_tooling")
    if not pieces:
        return "no matching changed paths"
    return "; ".join(_dedupe(pieces))


def explain_long_gate_impact(
    command_specs: Sequence[GateCheckSpec],
    changed_paths: Sequence[str],
    *,
    repo_root: str,
) -> Dict[str, Any]:
    normalized_paths = _dedupe(changed_paths)
    global_matches = _matches_for_scopes(
        normalized_paths, (*LONG_GATE_RUNNER_VERSION_PATHS, *LONG_GATE_TOOLING_VERSION_PATHS)
    )
    global_affected = bool(global_matches)
    entries: List[Dict[str, Any]] = []
    for entry in gate_entries(command_specs):
        spec = entry.spec
        if not spec.reuse_allowed:
            continue
        matches_by_category = {
            "input": _matches_for_scopes(normalized_paths, spec.input_file_scopes),
            "config": _matches_for_scopes(normalized_paths, spec.config_file_scopes),
            "tool": _matches_for_scopes(normalized_paths, spec.tool_file_scopes),
            "dependency": _matches_for_scopes(normalized_paths, spec.dependency_file_scopes),
            "existence": _matches_for_scopes(normalized_paths, spec.existence_file_scopes),
            "output": _matches_for_scopes(normalized_paths, spec.output_result_files),
        }
        matched_categories = [category for category, matches in matches_by_category.items() if matches]
        if global_affected:
            matched_categories.insert(0, "global_runner_tooling")
        entries.append(
            {
                "entry_id": spec.check_id,
                "entry_type": spec.entry_type,
                "display": spec.display,
                "reuse_policy": spec.reuse_policy,
                "affected": bool(matched_categories),
                "reason": _impact_reason(matched_categories, global_affected=global_affected),
                "global_runner_tooling_affected": global_affected,
                "matched_categories": matched_categories,
                "matches_by_category": matches_by_category,
            }
        )
    return {
        "schema_version": LONG_GATE_MANIFEST_SCHEMA_VERSION,
        "mode": "long_gate_impact_explain",
        "repo_root": os.path.abspath(repo_root),
        "changed_paths": normalized_paths,
        "global_runner_tooling_affected": global_affected,
        "global_matches": global_matches,
        "entries": entries,
    }


def load_local_quality_gate_receipts(repo_root: str) -> List[LocalReceipt]:
    """本机 receipts 目录里的每份 receipt 都走唯一的结构准入；被拒的作为警告列出。"""
    receipts_dir = os.path.join(repo_root, quality_gate_shared.QUALITY_GATE_RECEIPTS_DIR_REL.replace("/", os.sep))
    rows: List[LocalReceipt] = []
    for abs_path in sorted(glob.glob(os.path.join(receipts_dir, "*.json"))):
        rel_path = os.path.relpath(abs_path, repo_root).replace("\\", "/")
        rows.append((rel_path, admit_receipt(repo_root, rel_path)))
    return rows


def group_local_receipts(
    entries: Sequence[GateEntry], local_receipts: Sequence[LocalReceipt]
) -> Tuple[Dict[str, List[Receipt]], List[str]]:
    by_entry: Dict[str, List[Receipt]] = {entry.spec.check_id: [] for entry in entries}
    warnings: List[str] = []
    for rel_path, admitted in local_receipts:
        if isinstance(admitted, Rejection):
            warnings.append(f"receipt rejected: {rel_path}: {admitted.reason}")
            continue
        check_id = admitted.command["check_id"]
        if check_id not in by_entry:
            warnings.append(f"local receipt check_id is not in current plan: {check_id}")
            continue
        by_entry[check_id].append(admitted)
    return by_entry, warnings


def _format_receipt_line(receipt: Receipt) -> str:
    duration = f"{receipt.duration_s:.3f}s"
    if receipt.original_duration_s is not None:
        duration = f"{duration}, kind={receipt.duration_kind}, original={receipt.original_duration_s:.3f}s"
    return f"    receipt: {receipt.path} ({duration})"


def print_long_gate_manifest(entries: Sequence[GateEntry], *, local_receipts: Optional[Sequence[LocalReceipt]]) -> None:
    """local_receipts 为 None 表示没有要求读取本机 receipts。"""
    receipts_by_entry, warnings = group_local_receipts(entries, () if local_receipts is None else local_receipts)
    print("Long gate manifest")
    print(f"schema_version: {LONG_GATE_MANIFEST_SCHEMA_VERSION}")
    print(f"commands: {len(entries)}")
    print("")
    for entry in entries:
        label = "CACHE-ENABLED" if entry.spec.reuse_allowed else "PROBE"
        print(f"{entry.index:02d}. [{label}] {entry.spec.check_id}: {entry.spec.display}")
        for receipt in receipts_by_entry[entry.spec.check_id]:
            print(_format_receipt_line(receipt))
    if local_receipts is None:
        return
    if not any(receipts_by_entry.values()) and not warnings:
        print("")
        print(
            "No local QualityGate receipts found. Slow-command ranking unavailable; "
            "using command-plan based long-gate candidates."
        )
    if warnings:
        print("")
        print("Warnings")
        for warning in warnings:
            print(f"- {warning}")


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print the long-gate manifest derived from the real QualityGate plan.")
    parser.add_argument(
        "--print", dest="print_manifest", action="store_true", help="print the current long-gate manifest"
    )
    parser.add_argument(
        "--include-local-receipts",
        action="store_true",
        help="read local evidence/QualityGate receipts and include duration hints when available",
    )
    parser.add_argument("--repo-root", default=resolve_repo_root(), help="repository root to inspect")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    local_receipts = load_local_quality_gate_receipts(args.repo_root) if args.include_local_receipts else None
    check_specs = quality_gate_shared.build_quality_gate_check_specs(args.repo_root)
    print_long_gate_manifest(gate_entries(check_specs), local_receipts=local_receipts)
    return 0


__all__ = [
    "explain_long_gate_impact",
    "group_local_receipts",
    "load_local_quality_gate_receipts",
    "main",
    "normalize_repo_path",
    "print_long_gate_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
