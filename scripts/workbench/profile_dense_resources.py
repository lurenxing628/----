"""Bounded developer probe for the original single-resource workbench workload."""

import argparse
import cProfile
import hashlib
import io
import json
import os
import pstats
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def seed(output, batches, operations):
    from core.infrastructure.database import ensure_schema
    from core.services.scheduler.config.config_field_spec import default_snapshot_values
    from tests.workbench.test_run_compute_support import RunCase

    path = output / "case.sqlite"
    ensure_schema(str(path), schema_path=str(ROOT / "schema.sql"))
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = RunCase(conn)
    codes = ["B1"] + [f"CAP-{index:03d}" for index in range(1, batches)]
    for code in codes:
        case.batch(code)
        for seq in range(1, operations + 1):
            case.operation(code, seq, unit_hours=0.001)
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=600,
                ortools_enabled="no", freeze_window_enabled="no")
    return case, codes


def worker(args):
    from core.models.workbench_run_job import durable_value
    from core.services.workbench.run_compute import compute_candidate_run
    from tests.workbench.test_execution_ledger_support import all_rows

    output = Path(args.output)
    started = time.monotonic()
    case, codes = seed(output, args.batches, args.operations)
    seed_seconds = time.monotonic() - started
    before, changes = all_rows(case.conn), case.conn.total_changes
    started = time.monotonic()
    projections = case.projections()
    projection_seconds = time.monotonic() - started
    profile, result, failure = cProfile.Profile(), None, None
    started = time.monotonic()
    try:
        profile.enable()
        legacy = patch("core.algorithm_runtime.internal_slot.advance_busy_block",
                       lambda calendar, **kwargs: kwargs["shift_to"]) if args.legacy_busy_skip else nullcontext()
        with legacy:
            result = compute_candidate_run(case.conn, case.settings(*codes), projections)
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        traceback.print_exc()
    finally:
        profile.disable()
        seconds = time.monotonic() - started
        profile.dump_stats(str(output / "compute.pstats"))
        report = io.StringIO()
        pstats.Stats(profile, stream=report).sort_stats("cumulative").print_stats(50)
        (output / "profile.txt").write_text(report.getvalue(), encoding="utf-8")
    preserved = all_rows(case.conn) == before and case.conn.total_changes == changes
    expected = args.batches * args.operations
    counts = [] if result is None else [len(payload.schedule_rows) for payload in result.candidate_payloads.values()]
    payloads = [] if result is None else [durable_value(payload) for payload in result.candidate_payloads.values()]
    payload_json = json.dumps(payloads, sort_keys=True, separators=(",", ":"))
    (output / "candidate-payloads.json").write_text(payload_json, encoding="utf-8")
    proof = {"python": sys.version, "sqlite": sqlite3.sqlite_version, "schema": case.conn.execute(
        "SELECT version FROM SchemaVersion").fetchone()[0], "batches": args.batches,
        "operations_per_batch": args.operations, "operation_count": expected,
        "resource_pairs": 1, "unit_hours": 0.001, "quantity": 3,
        "seed_seconds": seed_seconds, "projection_seconds": projection_seconds,
        "profiled_compute_seconds": seconds, "failure": failure, "original_database_unchanged": preserved,
        "state": None if result is None else result.state, "candidate_row_counts": counts,
        "busy_block_skip_enabled": not args.legacy_busy_skip,
        "candidate_payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "complete": failure is None and preserved and result is not None and result.state == "complete" and counts == [expected] * 4,
        "timing_scope": "cProfile enabled; shared host, not a dedicated capacity acceptance"}
    (output / "result.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    case.conn.close()
    return 0 if proof["complete"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batches", type=int, default=100)
    parser.add_argument("--operations", type=int, default=2)
    parser.add_argument("--deadline", type=float, default=45)
    parser.add_argument("--legacy-busy-skip", action="store_true", help="Compare with the original one-hop slot path")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.batches <= 100 or not 1 <= args.operations <= 50 or not 1 <= args.deadline <= 180:
        parser.error("Use 1..100 batches, 1..50 operations, and a 1..180 second deadline")
    if args.worker:
        return worker(args)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    timed_out = False
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--output", str(output),
               "--batches", str(args.batches), "--operations", str(args.operations)]
    if args.legacy_busy_skip:
        command.append("--legacy-busy-skip")
    with (output / "stdout.log").open("w", encoding="utf-8") as stdout, (output / "stderr.log").open("w", encoding="utf-8") as stderr:
        child = subprocess.Popen(command, cwd=str(ROOT), stdout=stdout, stderr=stderr)
        try:
            child.wait(timeout=args.deadline)
        except subprocess.TimeoutExpired:
            timed_out = True
            child.send_signal(signal.SIGINT) if os.name != "nt" else child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    status = {"pid": child.pid, "deadline_seconds": args.deadline, "timed_out": timed_out,
              "returncode": child.returncode, "output": str(output), "child_stopped": child.poll() is not None}
    (output / "process.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status))
    return 124 if timed_out else child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
