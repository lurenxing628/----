"""Index preserved Win7 acceptance results without copying private DBs into Git."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    root, target = map(Path, sys.argv[1:3])
    matrix_runs = ["resource-errors-run01", "resource-size-boundary-run02", "process-errors-run01",
                   "process-errors-run02", "field-errors-run01"]
    passed = {}
    for run in matrix_runs:
        report = json.loads((root / run / "error-matrix-report.json").read_text(encoding="utf-8"))
        for case in report["cases"]:
            if case["passed"]:
                passed[(case["kind"], case["name"])] = run
    manifest = json.loads((root / "error-inputs/manifest.json").read_text(encoding="utf-8"))
    assert set(passed) == {(row["kind"], row["name"]) for row in manifest}
    report_names = ["resources-run02/resource-probe-results.json", "resources-run03/resource-probe-results.json",
                    "resources-xlsx-run01/resource-probe-results.json", "resources-xlsx-run02/resource-probe-results.json",
                    "process-run02/an-process-batch-report.json", "process-run03/an-process-batch-report.json",
                    "process-run04/an-process-batch-report.json", "process-run02/verified-utf8-snapshots/verification.json",
                    "process-run03/verified-utf8-snapshots/verification.json", "batch-modes-run01/batch-modes-initial.json",
                    "batch-modes-run02/batch-modes-initial.json", "batch-modes-run02/batch-modes-restart.json",
                    "field-run03/final-field-initial.json", "field-run04/final-field-initial.json",
                    "field-run04/final-field-restart.json", "field-run04/reported-batch-protection.json",
                    "field-run04/download-content-verification.json", "trial-run02/trial-initial.json",
                    "trial-run02/trial-continue.json", "trial-run02/trial-restart.json",
                    "quota-run02/quota-import.json", "quota-run02/quota-content-verification.json",
                    "field-visual-recheck03/visual-recheck.json", "resource-restart/report.json",
                    "process-restart/report.json", "field-errors-no-write.json", "process-errors-combined-no-write.json"]
    report_names += [run + "/error-matrix-report.json" for run in matrix_runs]
    report_names += [domain + "-restart-verification.json" for domain in
                     ("resources", "process", "batch-modes", "field", "trial", "quota")]
    report_names += ["error-inputs/manifest.json", "exchange/cleanup/complete.txt",
                     "exchange/cleanup/original-health.json", "exchange/cleanup/original-db-byte-identical.sha256"]
    reports = []
    for name in report_names:
        file = root / name
        raw = file.read_bytes()
        reports.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    for name in ("trial-run02/trial-continue.json", "trial-run02/trial-restart.json",
                 "quota-run02/quota-import.json", "quota-run02/quota-content-verification.json",
                 "field-visual-recheck03/visual-recheck.json"):
        assert json.loads((root / name).read_text(encoding="utf-8"))["passed"]
    for domain in ("resources", "process", "batch-modes", "field", "trial", "quota"):
        report = json.loads((root / (domain + "-restart-verification.json")).read_text(encoding="utf-8"))
        assert report["passed"] and len(report["exact_tables"]) == 76
    result = {"scope": "Final frozen d1307cb8 on original Win7 SP1 x64 VM and guest Chrome 109",
              "evidence_root": "output/playwright/win7-workflows-20260927",
              "note": "Original failed reports remain failed. Continuations and independently verified native snapshots provide completion evidence.",
              "matrix_unique_passed": len(passed), "matrix_by_kind": dict(sorted(Counter(key[0] for key in passed).items())),
              "matrix_cases": [{"kind": kind, "case": name, "passed_in": passed[(kind, name)]}
                               for kind, name in sorted(passed)], "reports": reports}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"matrix_unique_passed": len(passed), "indexed_reports": len(reports)}))


if __name__ == "__main__":
    main()
