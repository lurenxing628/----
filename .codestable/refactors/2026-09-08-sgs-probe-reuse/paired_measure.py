"""Alternating enabled/disabled runs in one unchanged checkout; no timing assertions."""

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from measure import ROOT, run_case

from core.algorithms.greedy.dispatch import sgs


def source_hashes():
    paths = [*ROOT.glob("core/algorithm_runtime/*.py"), *ROOT.glob("core/algorithms/greedy/**/*.py"),
             ROOT / "core/services/scheduler/calendar_engine.py", ROOT / "tests/_support/sgs_slot_reuse_case.py"]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def run(enabled, auto, *, batches=36):
    context = nullcontext() if enabled else patch.object(sgs, "sgs_overlap_reuse", lambda timeline: nullcontext())
    with context:
        return run_case(batches, auto=auto)


def profile(enabled, auto):
    profiler = cProfile.Profile()
    profiler.enable()
    _, payload = run(enabled, auto)
    profiler.disable()
    selected = {"estimate_internal_slot", "_slot_segments", "_materialize", "shift_end", "find_overlap_shift_end",
                "_pair_score", "add_working_hours", "index", "__init__"}
    rows = []
    for (filename, _line, name), (_, calls, own, cumulative, _) in pstats.Stats(profiler).stats.items():
        if str(ROOT) in filename and name in selected and ("algorithm" in filename or "calendar_engine" in filename):
            rows.append(dict(file=str(Path(filename).relative_to(ROOT)), name=name, calls=calls,
                             own_seconds=own, cumulative_seconds=cumulative))
    return rows, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exclusive-window-confirmed", action="store_true",
                        help="Confirm the coordinator has stopped other benchmarks and frozen these sources.")
    args = parser.parse_args()
    if not args.exclusive_window_confirmed:
        parser.error("Obtain an exclusive benchmark window from the coordinator first.")
    before_hashes = source_hashes()
    cases = []
    for auto in (True, False):
        timings = {"off": [], "on": []}
        reference = run(False, auto)[1]
        assert run(True, auto)[1] == reference
        for repeat in range(5):
            for enabled in ((False, True) if repeat % 2 == 0 else (True, False)):
                elapsed, payload = run(enabled, auto)
                assert payload == reference
                timings["on" if enabled else "off"].append(elapsed)
        profiles = {}
        for enabled in (False, True):
            rows, payload = profile(enabled, auto)
            assert payload == reference
            profiles["on" if enabled else "off"] = rows
        medians = {mode: statistics.median(values) for mode, values in timings.items()}
        row = dict(auto=auto, batches=36, operations=288, seeds=36, timings=timings, medians=medians,
                   reduction_percent=100 * (1 - medians["on"] / medians["off"]),
                   exact_payload_equal=True, profiles=profiles,
                   payload_sha256=hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest())
        if auto:
            original = json.loads(Path(__file__).with_name("before.json").read_text(encoding="utf-8"))
            row["original_before_payload_equal"] = original["payload"] == reference
            assert row["original_before_payload_equal"]
        cases.append(row)
        print(json.dumps({key: value for key, value in row.items() if key != "profiles"}, indent=2), flush=True)
    after_hashes = source_hashes()
    report = dict(source_sha256=before_hashes, sources_unchanged=before_hashes == after_hashes, cases=cases)
    Path(__file__).with_name("paired.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert report["sources_unchanged"], "Source changed while measuring; repeat the paired run."


if __name__ == "__main__":
    main()
