"""静默回退严格门禁与清点 CLI（`python -m tools.quality_gate_scan`）；扫描原语在 `quality_gate_scan_primitives`。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from .architecture_scan_cache import scan_files_with_cache
from .long_gate_paths import GateContext, resolve_repo_root
from .quality_gate_ledger import load_ledger, silent_entry_content_equal, silent_entry_key
from .quality_gate_operations import architecture_silent_scan_entries
from .quality_gate_scan_primitives import validate_startup_samples
from .quality_gate_shared import (
    QualityGateError,
    collect_globbed_files,
    collect_quality_rule_files,
    is_startup_scope_path,
    repo_abs,
    repo_rel,
)


def _strict_silent_fallback_summary(
    entries: Sequence[Dict[str, Any]],
    ledger_entries: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    by_kind: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for entry in entries:
        kind = entry["fallback_kind"]
        by_kind[kind] = by_kind.get(kind, 0) + 1
    for entry in ledger_entries:
        status = entry["status"]
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "scan_entry_count": len(entries),
        "ledger_entry_count": len(ledger_entries),
        "by_fallback_kind": dict(sorted(by_kind.items())),
        "ledger_by_status": dict(sorted(by_status.items())),
    }


def run_strict_silent_fallback_gate(ctx: GateContext, *, emit_json: bool) -> int:
    """Validate the current strict silent-fallback gate against the debt ledger.

    Exit code ``0`` means the strict scan and ledger are aligned; drift or malformed ledger data raises
    ``QualityGateError`` (the CLI maps it to ``2``). Success is silent unless ``emit_json`` asks for the
    reproducible count summary.

    The strict gate covers every quality-rule file through the same scope view that
    ``sync_debt_ledger.py check`` and ``refresh-auto-fields`` compare against.
    """
    ledger = load_ledger(ctx.ledger_path)
    scan_entries = architecture_silent_scan_entries(ctx.repo_root, collect_quality_rule_files(ctx.repo_root))
    # The strict scan already holds every startup-scope entry unchanged; validate samples on them.
    validate_startup_samples([entry for entry in scan_entries if is_startup_scope_path(entry["path"])])
    ledger_entries = ledger["silent_fallback"]["entries"]

    scan_by_key = {silent_entry_key(entry): entry for entry in scan_entries}
    active_ledger_entries = [entry for entry in ledger_entries if entry["status"] != "fixed"]
    ledger_by_key = {silent_entry_key(entry): entry for entry in active_ledger_entries}
    missing_in_ledger = sorted(set(scan_by_key) - set(ledger_by_key))
    missing_in_scan = sorted(set(ledger_by_key) - set(scan_by_key))
    if missing_in_ledger or missing_in_scan:
        raise QualityGateError(
            "strict silent-fallback gate drift: "
            f"missing_in_ledger={missing_in_ledger[:10]} "
            f"missing_in_scan={missing_in_scan[:10]}"
        )
    for key, current in scan_by_key.items():
        stored = ledger_by_key[key]
        if not silent_entry_content_equal(current, stored):
            raise QualityGateError("strict silent-fallback gate handler content drift: {}".format(stored["id"]))
        if current["fallback_kind"] != stored["fallback_kind"]:
            raise QualityGateError("strict silent-fallback gate fallback_kind drift: {}".format(stored["id"]))

    if emit_json:
        print(json.dumps(_strict_silent_fallback_summary(scan_entries, ledger_entries), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _production_inventory_paths(repo_root: str) -> List[str]:
    roots = ("core", "data", "web", "desktop")
    return sorted({*collect_globbed_files(repo_root, [f"{root}/**/*.py" for root in roots]), "app.py"})


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APS quality-gate scan utilities")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="validate the current strict silent-fallback gate against 开发文档/技术债务治理台账.md",
    )
    parser.add_argument("--json", action="store_true", help="print JSON summary for --strict or --inventory-summary")
    parser.add_argument(
        "--inventory-summary",
        action="store_true",
        help="print the historical production-scope silent-fallback inventory summary",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        help="explicit Python files to scan for --inventory-summary; defaults to production inventory scope",
    )
    return parser


def _run_inventory_summary(repo_root: str, paths: Optional[Sequence[str]], *, emit_json: bool) -> int:
    # --paths 是唯一的外部路径入口，在这里规范成仓库相对路径一次。
    scan_paths = (
        [repo_rel(repo_root, repo_abs(repo_root, path)) for path in paths]
        if paths
        else _production_inventory_paths(repo_root)
    )
    facts = scan_files_with_cache(repo_root, scan_paths, fact_kinds=("silent",))
    entries = [entry for fact in facts for entry in fact["silent_fallback_entries"]]
    by_kind: Dict[str, int] = {}
    for entry in entries:
        kind = entry["fallback_kind"]
        by_kind[kind] = by_kind.get(kind, 0) + 1
    strict_count = sum(
        1 for entry in entries if entry["fallback_kind"] in {"silent_swallow", "silent_default_fallback"}
    )
    payload = {
        "scanned_file_count": len(facts),
        "entry_count": len(entries),
        "strict_candidate_count": strict_count,
        "by_fallback_kind": dict(sorted(by_kind.items())),
    }
    if emit_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "production inventory summary: "
            f"files={payload['scanned_file_count']} entries={payload['entry_count']} "
            f"strict_candidates={payload['strict_candidate_count']} "
            f"by_fallback_kind={payload['by_fallback_kind']}"
        )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    ctx = GateContext(resolve_repo_root())
    try:
        if args.strict:
            return run_strict_silent_fallback_gate(ctx, emit_json=args.json)
        if args.inventory_summary:
            return _run_inventory_summary(ctx.repo_root, args.paths, emit_json=args.json)
        parser.print_help()
        return 0
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


__all__ = [
    "run_strict_silent_fallback_gate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
