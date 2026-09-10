"""Build report data from captured output, without rescanning or changing product files."""

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))

from tools.import_cycle_baseline import baseline_scope, compare_with_baseline, default_baseline_path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_dir(name):
    return sorted((OUT / "runs").glob("*-" + name))[-1]


def sorted_comparison(value):
    return {key: sorted(item) if isinstance(item, set) else item for key, item in asdict(value).items()}


def main():
    plan = read_json(OUT / "dispatch-plan.json")
    owners = {}
    for task in plan["tasks"]:
        paths = task["write_set"] + task.get("proposed_new_product_files", []) + [task["new_test"]]
        for path in paths:
            if path in owners:
                raise ValueError("Overlapping write set: " + path)
            owners[path] = task["id"]
        for path in task["regression_tests"]:
            if not (ROOT / path).is_file():
                raise ValueError("Missing regression test: " + path)
    pyright = read_json(run_dir("pyright-product-json") / "stdout.log")
    diagnostics = []
    for row in pyright["generalDiagnostics"]:
        rel = Path(row["file"]).relative_to(ROOT).as_posix()
        diagnostics.append({
            "file": rel, "line": row["range"]["start"]["line"] + 1,
            "column": row["range"]["start"]["character"] + 1,
            "severity": row["severity"], "rule": row.get("rule"), "message": row["message"],
            "owner": owners.get(rel, "FB-related-reserved" if re.search(r"/(actual_gantt|field_)", rel) else "queued-unassigned"),
            "history_status": "cannot_distinguish",
        })
    errors = [row for row in diagnostics if row["severity"] == "error"]
    assert len(errors) == pyright["summary"]["errorCount"]
    write_json("pyright-diagnostics.json", diagnostics)
    per_file = []
    for file in sorted({row["file"] for row in errors}):
        rows = [row for row in errors if row["file"] == file]
        per_file.append({"file": file, "count": len(rows), "lines": sorted({row["line"] for row in rows}),
                         "owner": rows[0]["owner"], "history_status": "cannot_distinguish"})
    write_json("pyright-by-file.json", per_file)

    cycles = {}
    for label, include_tests in (("imports-product-json", False), ("imports-tests-source", True)):
        result = read_json(run_dir(label) / "stdout.log")
        baseline = default_baseline_path(str(ROOT), include_tests=include_tests)
        comparison = compare_with_baseline(baseline, result, expected_scope=baseline_scope(include_tests))
        cycles[label] = {"module_count": result["module_count"], "parse_errors": result["parse_errors"],
                         "hard_dir_count": len(result["hard_dir_cycles"]),
                         "hard_file_count": len(result["hard_file_cycles"]),
                         "explicit_hard_file_count": len(result["explicit_hard_file_cycles"]),
                         "comparison": sorted_comparison(comparison),
                         "baseline": str(Path(baseline).relative_to(ROOT)),
                         "baseline_sha256": hashlib.sha256(Path(baseline).read_bytes()).hexdigest()}
    write_json("import-comparison.json", cycles)

    xml = ET.parse(OUT / "architecture-source.xml")
    failures = []
    for test in xml.iter("testcase"):
        failed = test.find("failure")
        if failed is not None:
            failures.append({"test": test.attrib["name"], "message": failed.attrib.get("message", ""),
                             "details": failed.text or ""})
    complexity_failure = next(item for item in failures if item["test"] == "test_cyclomatic_complexity_threshold")
    complexity = []
    for match in re.finditer(r"^\s*(\S+\.py):(\d+) (\S+) complexity=(\d+) \(rank (\w+)\)", complexity_failure["message"], re.M):
        file, line, symbol, value, rank = match.groups()
        complexity.append({"file": file, "line": int(line), "symbol": symbol, "complexity": int(value),
                           "rank": rank, "owner": owners.get(file, "FB-related-reserved" if re.search(r"/(actual_gantt|field_)", file) else "queued-unassigned"),
                           "history_status": "baseline-external; migration-onset-unknown"})
    write_json("architecture-failures.json", failures)
    write_json("complexity-diagnostics.json", complexity)

    receipts = [read_json(path) for path in sorted((OUT / "runs").glob("*/receipt.json"))]
    for task in plan["tasks"]:
        task["pyright_errors"] = sum(row["owner"] == task["id"] for row in errors)
        task["complexity_entries"] = sum(row["owner"] == task["id"] for row in complexity)
        task["diagnostics"] = [row for row in diagnostics if row["owner"] == task["id"]]
    summary = {"pyright": pyright["summary"], "error_file_count": len(per_file),
               "pyright_tools": {"errors": 0, "warnings": 0, "receipt": str((run_dir("pyright-tools") / "receipt.json").relative_to(OUT))},
               "error_ownership": dict(Counter(row["owner"] for row in errors)),
               "complexity_count": len(complexity),
               "complexity_ownership": dict(Counter(row["owner"] for row in complexity)),
               "architecture_tests": {"failed": len(failures), "passed": sum(test.find("failure") is None for test in xml.iter("testcase"))},
               "cycles": cycles, "disjoint_write_sets": True,
               "receipts": receipts,
               "proof_boundary": "dirty source-sampled static triage; not full gate, not clean proof"}
    write_json("dispatch-evidence.json", plan)
    write_json("summary.json", summary)
    table = ["# Pyright 文件索引", "", "全部为迁移相关现行文件；原有/新增时间归属无法区分。完整报错见 pyright-diagnostics.json。", "",
             "| 文件 | 错误数 | 行号 | 派工 |", "| --- | ---: | --- | --- |"]
    for row in per_file:
        table.append("| `{}` | {} | {} | {} |".format(row["file"], row["count"], ", ".join(map(str, row["lines"])), row["owner"]))
    (OUT / "diagnostic-index.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("pyright", "error_file_count", "error_ownership", "complexity_count", "complexity_ownership", "architecture_tests", "disjoint_write_sets")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
