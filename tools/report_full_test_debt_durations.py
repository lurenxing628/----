from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DEFAULT_PAYLOAD_REL = os.path.join("evidence", "QualityGate", "current_full_test_debt.json")


def _load_payload(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("full-test-debt payload 顶层必须是对象")
    return payload


def _report_duration(report: Mapping[str, Any]) -> float:
    try:
        return float(report.get("duration") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _nodeid_path(nodeid: str) -> str:
    return str(nodeid or "").split("::", 1)[0].replace("\\", "/")


def _payload_reports(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    reports = payload.get("reports")
    if not isinstance(reports, list):
        raise ValueError("full-test-debt payload 缺少 reports 列表")
    return [dict(report) for report in reports if isinstance(report, dict)]


def _category_for_path(path: str) -> str:
    rel_path = str(path or "").replace("\\", "/")
    if rel_path == "tests/app_runtime/test_ui_browser_geometry_smoke.py":
        return "browser"
    if rel_path == "tests/gate_meta/test_architecture_fitness.py":
        return "architecture"
    if rel_path.startswith("tests/gate_meta/test_long_gate_"):
        return "long_gate"
    if "scheduler_batches" in rel_path:
        return "scheduler_batches"
    return "other"


def _sum_by_file(reports: Iterable[Mapping[str, Any]], *, when: Optional[str] = None) -> List[Tuple[str, float]]:
    totals: DefaultDict[str, float] = defaultdict(float)
    for report in reports:
        if when is not None and str(report.get("when") or "") != when:
            continue
        nodeid = str(report.get("nodeid") or "")
        path = _nodeid_path(nodeid)
        if not path:
            continue
        totals[path] += _report_duration(report)
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def _sum_call_by_nodeid(reports: Iterable[Mapping[str, Any]]) -> List[Tuple[str, float]]:
    totals: DefaultDict[str, float] = defaultdict(float)
    for report in reports:
        if str(report.get("when") or "") != "call":
            continue
        nodeid = str(report.get("nodeid") or "")
        if not nodeid:
            continue
        totals[nodeid] += _report_duration(report)
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def _category_totals(reports: Iterable[Mapping[str, Any]]) -> List[Tuple[str, float]]:
    totals: DefaultDict[str, float] = defaultdict(float)
    for path, duration in _sum_by_file(reports):
        totals[_category_for_path(path)] += duration
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def _format_rows(rows: Sequence[Tuple[str, float]], *, limit: int) -> List[str]:
    if not rows:
        return ["- <none>"]
    rendered = []
    for index, (name, duration) in enumerate(rows[:limit], start=1):
        rendered.append(f"{index:>2}. {duration:>8.3f}s  {name}")
    return rendered


def build_duration_report(payload: Mapping[str, Any], *, top_nodeids: int = 50, top_files: int = 30) -> str:
    reports = _payload_reports(payload)
    lines = [
        "Full-test-debt duration report",
        "",
        f"reports: {len(reports)}",
        f"collected_count: {dict(payload.get('summary') or {}).get('collected_count', '-')}",
        "",
        f"Top {top_nodeids} call nodeids",
        *_format_rows(_sum_call_by_nodeid(reports), limit=top_nodeids),
        "",
        f"Top {top_files} files by setup/call/teardown duration",
        *_format_rows(_sum_by_file(reports), limit=top_files),
        "",
        f"Top {top_files} files by call duration",
        *_format_rows(_sum_by_file(reports, when="call"), limit=top_files),
        "",
        "Category totals",
        *_format_rows(_category_totals(reports), limit=20),
    ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Report slow full-test-debt nodeids and files.")
    parser.add_argument("payload", nargs="?", default=DEFAULT_PAYLOAD_REL)
    parser.add_argument("--top-nodeids", type=int, default=50)
    parser.add_argument("--top-files", type=int, default=30)
    args = parser.parse_args(argv)

    payload = _load_payload(str(args.payload))
    sys.stdout.write(
        build_duration_report(
            payload,
            top_nodeids=max(1, int(args.top_nodeids)),
            top_files=max(1, int(args.top_files)),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
