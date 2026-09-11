"""Compare already captured evidence. Does not execute a schedule or benchmark."""

import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    before, after = [json.loads((OUT / name).read_text(encoding="utf-8")) for name in ("before.json", "after.json")]
    pairs = [
        ("core/algorithm_runtime/downtime.py", "__init__"),
        ("core/algorithm_runtime/downtime.py", "_materialize"),
        ("core/algorithm_runtime/downtime.py", "shift_end"),
        ("core/algorithm_runtime/internal_slot.py", "estimate_internal_slot"),
        ("core/algorithms/greedy/auto_assign.py", "_pair_score"),
        ("core/services/scheduler/calendar_engine.py", "add_working_hours"),
    ]
    calls = []
    for file, name in pairs:
        values = [sum(row["calls"] for row in report["profile"] if row["file"] == file and row["name"] == name)
                  for report in (before, after)]
        calls.append(dict(file=file, name=name, before=values[0], after=values[1]))
    comparison = dict(
        exact_payload_equal=before["payload"] == after["payload"],
        excluded_fields=["summary.duration_seconds"],
        payload_sha256=[hashlib.sha256(json.dumps(report["payload"], sort_keys=True).encode()).hexdigest()
                        for report in (before, after)],
        calls=calls, elapsed_seconds=dict(before=before["seconds"], after=after["seconds"]),
        timing_status="exploratory_only_exclusive_window_not_confirmed",
        independent_of_wall_clock="call counts and exact output equality",
    )
    assert comparison["exact_payload_equal"]
    (OUT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
