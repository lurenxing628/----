"""Run from the repository root with .venv/bin/python; no database access."""

import argparse
import cProfile
import hashlib
import json
import platform
import pstats
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.algorithm_runtime import downtime, internal_slot  # noqa: E402
from tests._support.sgs_slot_reuse_case import make_case, make_scheduler  # noqa: E402


def run_case(batch_count, *, auto=True):
    scheduler = make_scheduler()
    kwargs = make_case(batch_count=batch_count, auto=auto)
    with patch("sqlite3.connect", side_effect=AssertionError("benchmark must not open a database")):
        start = time.perf_counter()
        results, summary, strategy, params = scheduler.schedule(**kwargs)
        elapsed = time.perf_counter() - start
    summary_data = asdict(summary)
    summary_data.pop("duration_seconds")
    payload = dict(results=[asdict(result) for result in results], summary=summary_data,
                   strategy=str(strategy), params=params, stats=scheduler._last_algo_stats)
    return elapsed, json.loads(json.dumps(payload, default=str, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--batches", type=int, default=36)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--fixed", action="store_true")
    args = parser.parse_args()
    times, payloads = [], []
    run_case(args.batches, auto=not args.fixed)
    for _ in range(args.repeats):
        elapsed, payload = run_case(args.batches, auto=not args.fixed)
        times.append(elapsed)
        payloads.append(payload)
    assert all(payload == payloads[0] for payload in payloads)
    profiler = cProfile.Profile()
    profiler.enable()
    _, profiled_payload = run_case(args.batches, auto=not args.fixed)
    profiler.disable()
    assert profiled_payload == payloads[0]
    rows = []
    for (filename, line, name), (_primitive, calls, own, cumulative, _callers) in pstats.Stats(profiler).stats.items():
        if str(ROOT) in filename and ("algorithm" in filename or "calendar_engine" in filename):
            rows.append(dict(file=str(Path(filename).relative_to(ROOT)), line=line, name=name,
                             calls=calls, own_seconds=own, cumulative_seconds=cumulative))
    rows.sort(key=lambda row: -row["cumulative_seconds"])
    counters = Counter()
    seen = set()
    original_init = downtime.SegmentOverlapIndex.__init__

    def counted_init(self, segments):
        frozen = tuple(segments or ())
        identity = (id(segments), frozen)
        counters["index_init"] += 1
        counters["segments_seen"] += len(frozen)
        if identity in seen:
            counters["repeat_same_sequence_contents"] += 1
        seen.add(identity)
        original_init(self, segments)

    with patch.object(downtime.SegmentOverlapIndex, "__init__", counted_init):
        _, counted_payload = run_case(args.batches, auto=not args.fixed)
    assert counted_payload == payloads[0]
    sources = [ROOT / module.__file__ for module in (downtime, internal_slot)]
    report = dict(label=args.label, python=sys.version, platform=platform.platform(),
                  batches=args.batches, operations=args.batches * 8, machines=12, operators=12, seeds=36,
                  auto=not args.fixed, seconds=times, median_seconds=statistics.median(times),
                  counts=dict(counters), profile=rows, payload=payloads[0],
                  source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
    out = Path(__file__).with_name(args.label + ".json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("label", "seconds", "median_seconds", "counts")}, indent=2))
    print(json.dumps(rows[:18], indent=2))
    print("evidence:", out)


if __name__ == "__main__":
    main()
