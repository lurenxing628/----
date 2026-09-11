"""Bind only reviewed, source-bound C proof; leave unexercised gates pending."""

import copy
import json
from pathlib import Path

from tests.workbench.final_master_action_ledger_support import (
    FOLDER,
    VARIANTS,
    coverage,
    digest,
    read_json,
    write_outputs,
)
from tests.workbench.final_master_domain_map_support import ids, process_mappings, resource_mappings

BASE = Path("/private/tmp")
RUNS = {
    "overview": ("aps-workbench-live-uio1t7lq", "final-master-overview.json", "f418656aa80a0d6ee362c362f853a285dc815f0368b171cd629094d6ba0ab106",
                 "final-master-result.json", "7efc24f78fd579f92458026b6fb00d461975c3c3342279b1cc7dc1ab445cf586"),
    "resources": ("aps-workbench-live-5ddb9gm0", "resource-probe-results.json", "8def68cc194b5fab89c23e7c6eb56a23659a69f88b1a209b53c8c05d5e3116b6",
                  "final-master-resource-resume-result.json", "68bb48d5eeef3df6c9f6268b96ae9b18a3fc3109917e06754a8b7404053b59fa"),
    "process": ("aps-workbench-live-su4resfc", "an-process-batch-report.json", "a26c968cfa31b6484b3bfff776f33e683e1ccada3da85b124272419f275b30e0",
                "final-master-process-resume-result.json", "1addaa7ce9f8a391974586ea3bda5bb0a20a3a8ab4e1eda21fc58172f1ecb4e3"),
    "context": ("aps-workbench-live-7iwt2eg8", "final-master-context_restore.json", "ca1a72b40a9853b069d62e94d0fcfbb74a4fbc61b7a49a9bd3dd2206e4e8d866",
                "final-master-result.json", "1f1bbdaeb253667bdac92240cd4ecaf859e01d46a641a0d6a57d2ca3bf34b3a9"),
    "gaps": ("aps-workbench-live-pyixrdav", "final-master-domain_gaps.json", "56da8ac4789d08a5cad80b68fdca6af98a6b1c8e8702d35d6455dc439a5f7409",
             "final-master-result.json", "fbfdec8980cc11cff7f837ee05adb569aa1b4e5d651bbb29f31a90e207020f82"),
}

REMAINING = [
    ("aps-workbench-live-7kvfmq7f", "5990fccc6dbc3d8b6d50a8ee20be5b601d87edbcae53dc3277de42cec4c448a4",
     "01a3895745a64cf7340f98752bcb4d5874f0087e8a560854fabdd89934f251ec", ["process-tab-focus-return", "process-route-nested-close", "calendar-date-disabled"]),
    ("aps-workbench-live-rp8dshb6", "70813e371776a1c317a2d1dc0ddf08bbb699d3b868d7dd182cb4f997313dff67",
     "a6d3ea9e29cfcddc078efe2fce466c440660d60f9b99282713d83111407887b3", ["master-own-header-boundary"]),
]


def proof(name):
    folder, report_name, report_hash, result_name, result_hash = RUNS[name]
    root = BASE / folder
    assert digest(root / report_name) == report_hash and digest(root / result_name) == result_hash
    report, result = read_json(root / report_name), read_json(root / result_name)
    initial = read_json(root / "final-master-result.json")
    assert not initial["source_changes"] and initial["initial_final"]["stopped"]
    if name in ("overview", "context", "gaps"):
        assert initial["browser_returncode"] == initial["restart_browser_returncode"] == 0
        assert initial["read_database_unchanged"] and initial["restart_preservation"]["passed"]
    elif name == "resources":
        assert result["passed"] and result["resource_preservation"]["passed"] and result["restart_preservation"]["passed"]
        assert result["original_browser_sha256"] == report_hash
        assert result["config_restart_preservation"]["rows_exact"] and result["config_restart_preservation"]["attempted_writes"] == 0
    else:
        assert result["passed"] and result["old_results_unchanged"][report_name] == report_hash
        assert digest(Path(result["proof_path"])) == result["proof_sha256"]
        checked = read_json(Path(result["proof_path"]))
        assert checked["summary"]["cases"] == 67 and checked["summary"]["failed"] == 0
        assert {row["id"] for row in checked["cases"] if row["passed"]} == {row["id"] for row in report["cases"]}
        assert all(not row.get("error") and not row.get("runtime_errors") for row in report["cases"])
    imports = list(root.glob("final-master-imports-*.json"))
    assert len(imports) == 2 and all(not read_json(path)["violations"] for path in imports)
    source = root / "final-master-source-before.json"
    evidence = {"proof_path": str(root / report_name), "proof_sha256": report_hash,
                "source_path": str(source), "source_sha256": digest(source),
                "build_id": initial["ready"]["assets"]["build_id"], "preservation_path": str(root / result_name),
                "preservation_sha256": result_hash, "scope": "named sealed source only; not current Main G05 or a clean-worktree proof"}
    return report, evidence


def normalized_cases(report, process=False):
    rows = []
    for case in report["cases"]:
        if process:
            _, width, theme, name = case["id"].split("-", 3)
            variant = width + ("x1080-" if width == "1920" else "x924-") + theme
            row = {"name": name, "variant": variant, "case_id": case["id"], "screenshot": case.get("screenshot")}
        else:
            value = case.get("variant") or case.get("state")
            if "x" not in value:
                width, theme = value.split("-")
                value = width + ("x1080-" if width == "1920" else "x924-") + theme
            assert case.get("passed", case.get("status") == "passed"), "Cannot bind a failed browser case"
            row = {"name": case["name"], "variant": value, "screenshot": case.get("screenshot"),
                   "step_start": case.get("step_start"), "step_end": case.get("step_end")}
        rows.append(row)
    return rows


def bind(ledger, mappings, cases, evidence):
    actions = {row["action_id"]: row for family in ledger["families"] for row in family["actions"]}
    for mapping in mappings:
        selected = [row for row in cases if row["name"] == mapping["case"]]
        assert {row["variant"] for row in selected} == VARIANTS, "Incomplete actual variants: " + mapping["case"]
        for action_id in mapping["actions"]:
            assert action_id in actions, "Unknown action cannot be added by a proof"
            action = actions[action_id]
            for gate in mapping["gates"]:
                state = "not_applicable" if gate == "P" and mapping["persistence"] == "view" else "reused"
                if action["gates"][gate] not in ("pending", state):
                    continue
                reason = {"B": "Named real-host scenario and its production response/database assertions; only this listed action is bound.",
                          "K": "This exact listed input or control action was executed by the named original probe in all four browser variants.",
                          "P": "Actual saved commands, original receipts, final rows and restart were checked. Deliberately deleted test rows are not claimed to survive their own deletion."}[gate]
                if state == "not_applicable":
                    reason = "Unsaved view or input-only action: no business save is claimed. The real host database preservation proof is retained separately."
                if gate == "P" and mapping["persistence"] == "rejected":
                    reason = "Canceled or rejected operation: no committed business change was allowed; saved action snapshots and whole-run preservation verify that boundary."
                item = {"gate": gate, "reason": reason, **evidence, "cases": selected}
                action["gates"][gate] = state
                if item not in action["evidence"]:
                    action["evidence"].append(item)
    return ledger


def bind_remaining(shared):
    for folder, report_hash, result_hash, names in REMAINING:
        root = BASE / folder
        path = root / "final-master-remaining_controls.json"
        assert digest(path) == report_hash and digest(root / "final-master-result.json") == result_hash
        report, result = read_json(path), read_json(root / "final-master-result.json")
        assert not result["source_changes"] and result["read_database_unchanged"]
        assert result["restart_preservation"]["passed"] and result["restart_browser_returncode"] == 0
        assert result["initial_final"]["stopped"] and result["restart_final"]["stopped"]
        assert not report["external"] and not [row for row in report["errors"] if not row.get("expected")]
        selected = [row for row in report["cases"] if row["name"] in names]
        assert all(row["passed"] and row["before_sha256"] == row["after_sha256"] for row in selected)
        source = root / "final-master-source-before.json"
        evidence = {"proof_path": str(path), "proof_sha256": report_hash, "source_path": str(source),
                    "source_sha256": digest(source), "build_id": result["ready"]["assets"]["build_id"],
                    "preservation_path": str(root / "final-master-result.json"), "preservation_sha256": result_hash,
                    "scope": "only named successful cases; original failed cases remain failed in their original report"}
        mappings = [{"case": row["name"], "actions": row["actions"], "gates": "BKP", "persistence": "view"}
                    for row in selected if row["variant"] == "1920x1080-light"]
        bind(shared, mappings, normalized_cases({"cases": selected}), evidence)
        actions = {row["action_id"]: row for family in shared["families"] for row in family["actions"]}
        for decision in report.get("scope_decisions", []):
            for action_id in decision.get("action_ids", [decision.get("action_id")]):
                action = actions[action_id]
                action["scope_decision"] = "needs_main_scope_decision"
                item = {"gate": "B", "reason": decision["reason"], **evidence, "status": "pending",
                        "variant": decision["variant"], "observed": decision["observed"]}
                if item not in action["evidence"]:
                    action["evidence"].append(item)
    return shared


def run():
    domain, shared = read_json(FOLDER / "actions.json"), read_json(FOLDER / "shared-actions.json")
    domain, shared = copy.deepcopy(domain), copy.deepcopy(shared)
    report, evidence = proof("overview")
    excluded = set(ids("MD-001", [4, 5]))
    mappings = [{"case": row["name"], "actions": [item for item in row["actions"] if item not in excluded],
                 "gates": "BKP", "persistence": "view"} for row in report["cases"] if row["variant"] == "1920x1080-light"]
    bind(domain, mappings, normalized_cases(report), evidence)
    report, evidence = proof("resources")
    resource_cases = normalized_cases(report)
    bind(domain, resource_mappings(), resource_cases, evidence)
    bind(shared, [{"case": "real-internal-bindings-nested-back", "actions": ["WBP-SH-009-C09"],
                   "gates": "BKP", "persistence": "view"}], resource_cases, evidence)
    report, evidence = proof("process")
    bind(domain, process_mappings(), normalized_cases(report, process=True), evidence)
    report, evidence = proof("context")
    bind(domain, [{"case": "batch-context-restoration", "actions": ids("BATCH-002", [10]) + ids("BATCH-013", [3]),
                   "gates": "BKP", "persistence": "view"}], normalized_cases(report), evidence)
    report, evidence = proof("gaps")
    mappings = [{"case": row["name"], "actions": row["actions"], "gates": "BKP", "persistence": "view"}
                for row in report["cases"] if row["variant"] == "1920x1080-light"]
    bind(domain, mappings, normalized_cases(report), evidence)
    bind_remaining(shared)
    (FOLDER / "actions.json").write_text(json.dumps(domain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matrix = coverage(domain, shared)
    write_outputs(shared, matrix)
    print(json.dumps({"counts": matrix["counts"], "all_gates_passed": matrix["all_gates_passed"]}))


if __name__ == "__main__":
    run()
