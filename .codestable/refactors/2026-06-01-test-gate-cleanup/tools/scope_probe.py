#!/usr/bin/env python3
"""P0.3 scope-narrowing oracle.

For every tracked source file under the gate-relevant roots, compute the daily
gate impact plan (as if that single file were the only changed path) and report:
  - escalation count (all_required_groups=True  ==  full gate)  <-- must NOT grow
  - per-file group-count distribution (the speed lever)
  - per-source-root breakdown
  - a few named representative files (PLAN P0.3 verification examples)

Run before and after editing the registry to prove: no new escalation + lower
group counts. Pure read-only.
"""
from __future__ import annotations

import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/lurenxing/Documents/GitHub/----")
from scripts import run_daily_quality_gate as d  # noqa: E402

ROOTS = (
    "core/",
    "web/",
    "static/",
    "templates/",
    "data/",
    "templates_excel/",
    "plugins/",
    "web_new_test/",
)
SINGLE = ("app.py", "app_new_ui.py", "config.py", "schema.sql")


def tracked_files():
    raw = subprocess.run(
        ["git", "ls-files", "-z", *ROOTS, *SINGLE],
        cwd="/Users/lurenxing/Documents/GitHub/----",
        capture_output=True,
    ).stdout
    # -z => NUL-separated, raw unquoted paths (non-ASCII names not mojibake-quoted)
    out = raw.decode("utf-8", "surrogateescape").split("\0")
    return [p for p in out if p.strip()]


def plan_for(path):
    # Isolate a single changed file: call _build_impact_plan directly with a
    # synthetic ChangedPathSet so the current branch's git-diff does NOT leak
    # extra changed paths into the result (build_daily_gate_scope appends them).
    changed = d.ChangedPathSet(paths=[path], scope_known=True, reason="probe")
    ip = d._build_impact_plan(changed)
    return ip.all_required_groups, tuple(ip.selected_group_ids), len(d._dedupe_paths(ip.target_paths))


def root_of(path):
    for r in ROOTS:
        if path.startswith(r):
            return r.rstrip("/")
    return "(top)"


def main():
    files = tracked_files()
    escalated = []
    group_count_hist = Counter()
    target_hist = []
    per_root_targets = defaultdict(list)
    per_root_escalation = Counter()
    per_root_total = Counter()

    for f in files:
        full, groups, ntargets = plan_for(f)
        r = root_of(f)
        per_root_total[r] += 1
        if full:
            escalated.append(f)
            per_root_escalation[r] += 1
            group_count_hist["FULL"] += 1
            continue
        group_count_hist[len(groups)] += 1
        target_hist.append(ntargets)
        per_root_targets[r].append(ntargets)

    print(f"=== universe: {len(files)} tracked source files ===")
    print(f"escalated to FULL gate: {len(escalated)}")
    print("\n--- group-count histogram (non-escalated) ---")
    for k in sorted(group_count_hist, key=lambda x: (x == "FULL", x)):
        print(f"  groups={k}: {group_count_hist[k]} files")
    if target_hist:
        target_hist.sort()
        n = len(target_hist)
        print("\n--- target test-file count (non-escalated) ---")
        print(f"  min={target_hist[0]} p50={target_hist[n//2]} "
              f"p90={target_hist[int(n*0.9)]} max={target_hist[-1]} mean={sum(target_hist)//n}")
    print("\n--- per-root: total / escalated / median-targets ---")
    for r in sorted(per_root_total):
        ts = sorted(per_root_targets[r])
        med = ts[len(ts)//2] if ts else 0
        print(f"  {r:18} total={per_root_total[r]:4} escalated={per_root_escalation[r]:4} median_targets={med}")

    print("\n--- representative files (PLAN P0.3 examples) ---")
    reps = [
        "core/services/scheduler/schedule_service.py",
        "core/models/schedule_plan_role.py",
        "web/viewmodels/scheduler_resource_dispatch.py",
        "static/js/resource_execution.js",
        "templates/scheduler/gantt.html",
        "templates/equipment/equipment.html",
        "static/css/ui_contract.css",
        "core/algorithms/__init__.py",
        "data/__init__.py",
    ]
    for f in reps:
        try:
            full, groups, ntargets = plan_for(f)
        except Exception as e:  # noqa: BLE001
            print(f"  {f}: ERROR {e}")
            continue
        tag = "FULL" if full else f"{len(groups)}组/{ntargets}测试"
        print(f"  {f:55} -> {tag}  {sorted(groups) if not full else ''}")

    if escalated:
        print(f"\n--- ALL escalated files ({len(escalated)}) ---")
        for f in escalated:
            print(f"  {f}")


if __name__ == "__main__":
    main()
