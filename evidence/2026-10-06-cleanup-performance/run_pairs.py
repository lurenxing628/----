"""Alternate equal workloads serially; never overlap benchmark processes."""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

out = Path(__file__).resolve().parent
info = json.loads((out / "environment.json").read_text())
root = Path(info["temporary_root"])
script = out / "measure_backend.py"
records = []
dispatch = os.environ.get("APS_PERF_DISPATCH")
extra = ["--dispatch", dispatch] if dispatch else []
prefix = (dispatch + "-") if dispatch else ""
repetitions = 5 if dispatch else 7
for size, batches, operations in [("medium", 20, 5), ("large", 100, 10)]:
    templates = {}
    for variant, key in [("before", "baseline_checkout"), ("after", "current_checkout")]:
        folder = root / (prefix + size + "-" + variant + "-seed")
        folder.mkdir(exist_ok=True)
        db = folder / "bench.db"
        templates[variant] = db
        args = [
            info["python"],
            str(script),
            "seed",
            "--repo",
            info[key],
            "--db",
            str(db),
            "--batches",
            str(batches),
            "--operations",
            str(operations),
            "--output",
            str(out / (prefix + size + "-" + variant + "-seed.json")),
        ] + extra
        with (out / (prefix + size + "-" + variant + "-seed.log")).open("w") as log:
            subprocess.run(args, stdout=log, stderr=log, check=True)
    for repetition in range(repetitions):
        order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
        pair = {}
        for variant in order:
            folder = root / (prefix + size + "-" + variant + "-" + str(repetition))
            folder.mkdir(exist_ok=True)
            db = folder / "bench.db"
            shutil.copy2(templates[variant], db)
            name = prefix + size + "-" + str(repetition) + "-" + variant
            key = "baseline_checkout" if variant == "before" else "current_checkout"
            args = [
                info["python"],
                str(script),
                "measure",
                "--repo",
                info[key],
                "--db",
                str(db),
                "--batches",
                str(batches),
                "--operations",
                str(operations),
                "--output",
                str(out / (name + ".json")),
            ] + extra
            with (out / (name + ".log")).open("w") as log:
                subprocess.run(args, stdout=log, stderr=log, check=True)
            result = json.loads((out / (name + ".json")).read_text())
            pair[variant] = result
            print(size, repetition, variant, round(result["business_chain_ms"], 2), flush=True)
            records.append(
                {
                    "size": size,
                    "repetition": repetition,
                    "variant": variant,
                    "result_file": name + ".json",
                    "timings_ms": result["timings_ms"],
                    "business_chain_ms": result["business_chain_ms"],
                    "total_startup_and_business_ms": result["total_startup_and_business_ms"],
                    "storage": result["storage"],
                    "search_counts": result.get("search_counts"),
                }
            )
            (out / (prefix + "backend-raw.json")).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        assert pair["before"]["arrangement"] == pair["after"]["arrangement"], (size, repetition, "arrangement")
        assert pair["before"]["report"] == pair["after"]["report"], (size, repetition, "report")
        if dispatch:
            assert pair["before"]["search_counts"] == pair["after"]["search_counts"], (
                size,
                repetition,
                "native decode counts",
            )
        assert pair["before"]["candidate_count"] == pair["after"]["candidate_count"] == 4
if dispatch:
    print("SGS_FIXED_PAIRED_COMPLETE", flush=True)
    sys.exit(0)
info.update(
    {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": subprocess.check_output([info["python"], "--version"], text=True).strip(),
        "workload": {
            "medium": {"batches": 20, "tasks": 100},
            "large": {"batches": 100, "tasks": 1000},
            "machines": 50,
            "operators": 50,
            "parts": 31,
            "materials": 50,
        },
        "repetitions_per_version_per_size": 7,
        "order": "alternating before/after, serial",
        "result_equivalence": "exact task arrangements and report summaries, each pair",
    }
)
(out / "environment.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
print("BACKEND_PAIRED_COMPLETE", flush=True)
