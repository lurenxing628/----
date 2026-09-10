"""Bind exact completed action IDs; never propagate scenario/family success."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FOLDER = REPO / ".codestable/roadmap/workbench-prototype-migration/acceptance-master"
VARIANTS = {"1920x1080-light", "1920x1080-dark", "1392x924-light", "1392x924-dark"}
CONTROL_PROOF = {
    "final-master-controls.json": "2a8af785e8f7470eaef6921fca3bbe29ff7dfb0fad40d796d7fe3ee26bf36755",
    "final-master-result.json": "c1eec0ea22857b1a8acf26b98519a810d81033752d59a90e142f7be8e6802720",
    "final-master-source-before.json": "3ad9bc2c70335c520c5235a6f65835c6baf3c879f3b53a0da52ffcb01d6e30e9",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def case_bindings(report, allowed):
    bindings = {}
    for case in report["cases"]:
        assert case["passed"], "A failed case cannot supply accepted action evidence"
        assert case["variant"] in VARIANTS
        for action_id in case["actions"]:
            assert action_id in allowed, "Unlisted action: " + action_id
            bindings.setdefault(action_id, []).append({key: case[key] for key in (
                "name", "variant", "step_start", "step_end", "screenshot")})
    for action_id, cases in bindings.items():
        assert {row["variant"] for row in cases} == VARIANTS, "Missing actual variant: " + action_id
    return bindings


def bind_shared(ledger, bindings, evidence):
    updated = copy.deepcopy(ledger)
    for family in updated["families"]:
        for action in family["actions"]:
            cases = bindings.get(action["action_id"])
            if not cases:
                continue
            for gate in ("B", "K"):
                if action["gates"][gate] != "pending":
                    continue
                action["gates"][gate] = "reused"
                reason = ("Actual complete Flask/SQLite host and immutable full build; read-only business rows and restart checked"
                          if gate == "B" else "Exact listed action and assertions executed in all four actual browser variants")
                action["evidence"].append({"gate": gate, "reason": reason, **evidence, "cases": cases,
                    "scope": "named sealed source snapshot only; not latest whole-repo clean proof"})
            if action["gates"]["P"] == "pending":
                action["gates"]["P"] = "not_applicable"
                action["evidence"].append({"gate": "P", **evidence,
                    "reason": "These controls only change unsaved view/draft state. No saved command is claimed; database rows stayed exact before/after and across host restart."})
    return updated


def coverage(domain, shared):
    rows = []
    for scope, ledger in (("domain", domain), ("shared", shared)):
        for family in ledger["families"]:
            for action in family["actions"]:
                rows.append({"scope": scope, "family_id": family["family_id"], **action})
    assert sum(row["scope"] == "domain" for row in rows) == 599
    assert sum(row["scope"] == "shared" for row in rows) == 50
    assert len({row["action_id"] for row in rows}) == 649
    counts = {scope: {gate: dict(Counter(row["gates"][gate] for row in rows if row["scope"] == scope))
                      for gate in ("B", "K", "V", "P")} for scope in ("domain", "shared")}
    return {"schema_version": 1, "planning_sha256": domain["planning_sha256"], "counts": counts,
            "status": "in_progress", "all_gates_passed": sum(all(value in ("passed", "reused", "not_applicable")
                for value in row["gates"].values()) for row in rows), "actions": rows,
            "main_decision_reference": ".codestable/roadmap/workbench-prototype-migration/round2-main-decisions.md",
            "visual_boundary": "Main reviewed only the eight named column-width screenshots. Keep other V pending; no family/action-wide visual promotion."}


def write_outputs(shared, matrix):
    (FOLDER / "shared-actions.json").write_text(json.dumps(shared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (FOLDER / "coverage-current.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# C 逐动作覆盖与待办", "", "固定分母：58 领域族 / 599 动作，另 50 共享动作。reused 只指明确冻结源证据，不是最新整仓或最终 V 通过。", "",
             "Main 的 8 图定点 V 只引用 round2-main-decisions.md；这里不把有限看图推广为全部动作 V。", ""]
    previous = None
    for row in matrix["actions"]:
        if row["family_id"] != previous:
            previous = row["family_id"]
            lines.extend(["## " + previous, ""])
        states = ", ".join(gate + "=" + value for gate, value in row["gates"].items())
        lines.append("- `" + row["action_id"] + "` " + row["description"] + "：" + states)
    (FOLDER / "coverage-current.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind-controls", type=Path, required=True)
    args = parser.parse_args()
    root = args.bind_controls.resolve()
    for name, expected in CONTROL_PROOF.items():
        assert digest(root / name) == expected, "Not the reviewed control proof: " + name
    report, result = read_json(root / "final-master-controls.json"), read_json(root / "final-master-result.json")
    assert report["summary"]["cases"] == 28 and report["summary"]["failed"] == 0
    assert result["browser_returncode"] == result["restart_browser_returncode"] == 0
    assert result["read_database_unchanged"] and result["restart_preservation"]["passed"]
    assert not result["source_changes"] and not report["external"]
    assert not [row for row in report["errors"] if not row.get("expected")]
    imports = list(root.glob("final-master-imports-*.json"))
    assert len(imports) == 2 and all(not read_json(file)["violations"] for file in imports)
    domain, shared = read_json(FOLDER / "actions.json"), read_json(FOLDER / "shared-actions.json")
    assert digest(REPO / domain["planning_path"]) == domain["planning_sha256"] == shared["planning_sha256"]
    allowed = {row["action_id"] for family in shared["families"] for row in family["actions"]}
    bindings = case_bindings(report, allowed)
    assert len(bindings) == 41
    evidence = {"proof_path": str(root / "final-master-controls.json"), "proof_sha256": CONTROL_PROOF["final-master-controls.json"],
                "source_path": str(root / "final-master-source-before.json"), "source_sha256": CONTROL_PROOF["final-master-source-before.json"],
                "build_id": result["ready"]["assets"]["build_id"], "source_root": read_json(imports[0])["root"],
                "restart_proof_path": str(root / "final-master-result.json"), "restart_proof_sha256": CONTROL_PROOF["final-master-result.json"]}
    updated = bind_shared(shared, bindings, evidence)
    matrix = coverage(domain, updated)
    write_outputs(updated, matrix)
    print(json.dumps({"bound_shared": len(bindings), "counts": matrix["counts"], "all_gates_passed": matrix["all_gates_passed"]}))


if __name__ == "__main__":
    main()
