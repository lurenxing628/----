from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    LONG_GATE_MANIFEST_SCHEMA_VERSION,
    LONG_GATE_RUNNER_VERSION_PATHS,
    LONG_GATE_TOOLING_VERSION_PATHS,
)
from tools.quality_gate_shared import GateCheckSpec
from tools.test_registry import scope_matches_path as _scope_matches_path

LONG_GATE_SCHEMA_VERSION = LONG_GATE_MANIFEST_SCHEMA_VERSION

_normalize_command = quality_gate_shared.normalize_quality_gate_command


def _dedupe(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _build_entry(spec: GateCheckSpec) -> Dict[str, Any]:
    normalized = _normalize_command(spec.to_command_dict())
    reuse_allowed = bool(spec.reuse_allowed)
    return {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "cache_schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        "fingerprint_schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "entry_id": spec.check_id,
        "check_id": spec.check_id,
        "entry_type": spec.entry_type,
        "display": spec.display,
        "args": list(spec.args),
        "capture_output": bool(spec.capture_output),
        "output_policy": normalized["output_policy"],
        "env_overlay": normalized["env_overlay"],
        "env_overlay_keys": sorted(normalized["env_overlay"].keys()),
        "command": normalized,
        "input_file_scopes": _dedupe(spec.input_file_scopes),
        "config_file_scopes": _dedupe(spec.config_file_scopes),
        "tool_file_scopes": _dedupe(spec.tool_file_scopes),
        "dependency_file_scopes": _dedupe(spec.dependency_file_scopes),
        "env_keys": _dedupe(spec.env_keys),
        "output_result_files": _dedupe(spec.output_result_files),
        "proof_kind": spec.proof_kind,
        "cache_status": "enabled" if reuse_allowed else "disabled",
        "reuse_policy": spec.reuse_policy,
        "reuse_allowed": reuse_allowed,
        "runner_handler": spec.runner_handler,
    }


def build_manifest_from_quality_gate_plan(
    command_specs: Sequence[GateCheckSpec],
    receipts: Optional[Sequence[Mapping[str, Any]]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)
    entries = [_build_entry(spec) for spec in command_specs]
    commands = [entry["command"] for entry in entries]
    manifest = {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": root,
        "quality_gate_plan": commands,
        "entries": entries,
        "warnings": [],
    }
    if receipts is not None:
        _attach_receipt_observations(manifest, receipts)
    return manifest


def normalize_repo_path(path: str) -> str:
    """Normalize declared scopes and user-typed paths; Git output never passes through here."""
    normalized = str(path or "").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _matches_for_scopes(paths: Sequence[str], scopes: Sequence[str]) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    normalized_scopes = _dedupe([normalize_repo_path(item) for item in scopes])
    for path in _dedupe(paths):
        for scope in normalized_scopes:
            if _scope_matches_path(path, scope):
                matches.append({"path": path, "scope": scope})
    return matches


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
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)
    normalized_paths = _dedupe(changed_paths)
    manifest = build_manifest_from_quality_gate_plan(command_specs, repo_root=root)
    global_scopes = list(LONG_GATE_RUNNER_VERSION_PATHS) + list(LONG_GATE_TOOLING_VERSION_PATHS)
    global_matches = _matches_for_scopes(normalized_paths, global_scopes)
    global_affected = bool(global_matches)
    entries: List[Dict[str, Any]] = []
    for entry in manifest["entries"]:
        if not entry["reuse_allowed"]:
            continue
        matches_by_category = {
            "input": _matches_for_scopes(normalized_paths, entry["input_file_scopes"]),
            "config": _matches_for_scopes(normalized_paths, entry["config_file_scopes"]),
            "tool": _matches_for_scopes(normalized_paths, entry["tool_file_scopes"]),
            "dependency": _matches_for_scopes(normalized_paths, entry["dependency_file_scopes"]),
            "output": _matches_for_scopes(normalized_paths, entry["output_result_files"]),
        }
        matched_categories = [
            category
            for category in ("input", "config", "tool", "dependency", "output")
            if matches_by_category[category]
        ]
        if global_affected:
            matched_categories.insert(0, "global_runner_tooling")
        affected = bool(global_affected or matched_categories)
        entries.append(
            {
                "entry_id": entry["entry_id"],
                "entry_type": entry["entry_type"],
                "display": entry["display"],
                "cache_status": entry["cache_status"],
                "reuse_policy": entry["reuse_policy"],
                "reuse_allowed": entry["reuse_allowed"],
                "affected": affected,
                "reason": _impact_reason(matched_categories, global_affected=global_affected),
                "global_runner_tooling_affected": global_affected,
                "matched_categories": matched_categories,
                "matches_by_category": matches_by_category,
            }
        )
    return {
        "schema_version": 2,
        "mode": "long_gate_impact_explain",
        "repo_root": root,
        "changed_paths": normalized_paths,
        "global_runner_tooling_affected": global_affected,
        "global_matches": global_matches,
        "entries": entries,
    }


def _load_json_file(path: str) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(loaded, dict):
        return None, "top-level value is not an object"
    return loaded, ""


def _coerce_int(value: Any, *, field: str, warnings: List[str]) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        warnings.append(f"invalid numeric field: {field}={value!r}")
        return 0


def _coerce_float(value: Any, *, field: str, warnings: List[str]) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        if value is not None:
            warnings.append(f"invalid numeric field: {field}={value!r}")
        return None


def load_local_quality_gate_receipts(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    root = os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)
    receipts_dir = os.path.join(root, quality_gate_shared.QUALITY_GATE_RECEIPTS_DIR_REL.replace("/", os.sep))
    rows: List[Dict[str, Any]] = []
    for abs_path in sorted(glob.glob(os.path.join(receipts_dir, "*.json"))):
        rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
        payload, error = _load_json_file(abs_path)
        warnings: List[str] = []
        row: Dict[str, Any] = {"path": rel_path}
        if error or payload is None:
            row.update(
                {
                    "load_error": error,
                    "check_id": "",
                    "display": "",
                    "command_index": 0,
                    "duration_s": None,
                    "duration_unknown": True,
                    "duration_kind": "",
                    "original_duration_s": None,
                    "warnings": warnings,
                }
            )
        else:
            duration_s = _coerce_float(payload.get("duration_s"), field="duration_s", warnings=warnings)
            row.update(
                {
                    "check_id": str(payload.get("check_id") or "").strip(),
                    "display": str(payload.get("display") or "").strip(),
                    "command_index": _coerce_int(
                        payload.get("command_index"), field="command_index", warnings=warnings
                    ),
                    "returncode": _coerce_int(payload.get("returncode"), field="returncode", warnings=warnings),
                    "duration_s": duration_s,
                    "duration_unknown": duration_s is None,
                    "duration_kind": str(payload.get("duration_kind") or "").strip(),
                    "original_duration_s": _coerce_float(
                        payload.get("original_duration_s"),
                        field="original_duration_s",
                        warnings=warnings,
                    ),
                    "execution_mode": str(payload.get("execution_mode") or "executed").strip() or "executed",
                    "warnings": warnings,
                }
            )
        rows.append(row)
    return rows


def _attach_receipt_observations(manifest: Dict[str, Any], receipts: Sequence[Mapping[str, Any]]) -> None:
    entries_by_id = {entry["entry_id"]: entry for entry in manifest["entries"]}
    for receipt in receipts:
        check_id = receipt["check_id"]
        if not check_id:
            manifest["warnings"].append(
                f"receipt unreadable or missing check_id: {receipt['path']}"
            )
            continue
        entry = entries_by_id.get(check_id)
        if entry is None:
            manifest["warnings"].append(f"local receipt check_id is not in current plan: {check_id}")
            continue
        entry.setdefault("local_receipts", []).append(receipt)


def _entry_label(entry: Mapping[str, Any]) -> str:
    if bool(entry.get("reuse_allowed")):
        return "CACHE-ENABLED"
    return "PROBE"


def _format_receipt_line(receipt: Mapping[str, Any]) -> str:
    path = receipt["path"]
    duration = "duration_unknown" if receipt["duration_unknown"] else f"{receipt['duration_s']:.3f}s"
    duration_kind = receipt["duration_kind"]
    original_duration = receipt["original_duration_s"]
    if duration_kind and original_duration is not None:
        duration = f"{duration}, kind={duration_kind}, original={original_duration:.3f}s"
    return f"    receipt: {path} ({duration})"


def _format_receipt_warnings(receipt: Mapping[str, Any]) -> List[str]:
    return [f"    warning: {item}" for item in receipt["warnings"]]


def print_long_gate_manifest(manifest: Mapping[str, Any], *, include_local_receipts: bool = False) -> None:
    entries = list(manifest.get("entries") or [])
    print("Long gate manifest")
    print(f"schema_version: {manifest.get('schema_version')}")
    print(f"commands: {len(entries)}")
    print("")
    for index, entry in enumerate(entries, start=1):
        print(f"{index:02d}. [{_entry_label(entry)}] {entry.get('entry_id', '')}: {entry.get('display', '')}")
        if include_local_receipts:
            for receipt in list(entry.get("local_receipts") or []):
                print(_format_receipt_line(receipt))
                for warning in _format_receipt_warnings(receipt):
                    print(warning)
    if include_local_receipts:
        has_receipts = any(entry.get("local_receipts") for entry in entries)
        warnings = [str(item) for item in list(manifest.get("warnings") or [])]
        if not has_receipts and not warnings:
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
    parser.add_argument("--repo-root", default=quality_gate_shared.REPO_ROOT, help="repository root to inspect")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if not bool(args.print_manifest):
        args.print_manifest = True
    receipts = load_local_quality_gate_receipts(args.repo_root) if bool(args.include_local_receipts) else None
    check_specs = quality_gate_shared.build_quality_gate_check_specs(repo_root=args.repo_root)
    manifest = build_manifest_from_quality_gate_plan(check_specs, receipts=receipts, repo_root=args.repo_root)
    print_long_gate_manifest(manifest, include_local_receipts=bool(args.include_local_receipts))
    return 0


__all__ = [
    "LONG_GATE_SCHEMA_VERSION",
    "_scope_matches_path",
    "build_manifest_from_quality_gate_plan",
    "explain_long_gate_impact",
    "load_local_quality_gate_receipts",
    "main",
    "normalize_repo_path",
    "print_long_gate_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
