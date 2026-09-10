"""Exact revision increments caused by the existing resource probe's relationship writes."""

from collections import Counter

PARENTS = {2: (("machine_group", "RT-G"),), 3: (("op_type", "RT-IN"), ("shift_profile", "RT-SH")),
           5: (("op_type", "RT-EX"),)}
FILE_PARENTS = {2: PARENTS[2], 3: PARENTS[3], 4: PARENTS[5]}
STATES = {"1920-light", "1920-dark", "1392-light", "1392-dark"}


def expected_original_revisions(cases):
    expected = Counter()
    evidence, seen = [], set()
    for case in cases:
        identity = (case["state"], case["name"])
        assert identity not in seen and case["state"] in STATES
        seen.add(identity)
        if case["status"] != "passed":
            continue
        changes = {}
        for index, owners in PARENTS.items():
            if case["name"] in ("create-" + str(index), "cancel-update-delete-" + str(index)):
                changes.update({owner: 1 for owner in owners})
        for index, owners in FILE_PARENTS.items():
            if case["name"] in ("resource-files-import-" + str(index), "resource-files-bulk-delete-" + str(index)):
                changes.update({owner: 22 for owner in owners})
        if case["name"] == "nested-edit-uses-child-kind-and-scope":
            changes[("op_type", "RT-EX")] = 2
        if case["name"] == "stock-quick-action-validation-save-and-backdrop-cancel":
            changes[("material", "MAT-001")] = 2
        expected.update(changes)
        evidence.extend({"state": case["state"], "case": case["name"], "kind": kind, "entity_key": code,
                         "expected_increment": count} for (kind, code), count in changes.items())
    return expected, evidence


def verify_original_revisions(before, after, cases):
    expected, evidence = expected_original_revisions(cases)
    identities = {row["ref"]: row for row in after}
    observed = []
    owners = {(row["kind"], row["entity_key"]) for row in before}
    assert set(expected) <= owners
    for old in before:
        current = identities[old["ref"]]
        assert {key: value for key, value in current.items() if key != "revision"} == {
            key: value for key, value in old.items() if key != "revision"}, "Original identity fields changed"
        delta = current["revision"] - old["revision"]
        assert delta == expected[(old["kind"], old["entity_key"])], "Unproven original revision increment: " + old["entity_key"]
        if delta:
            observed.append({"ref": old["ref"], "kind": old["kind"], "entity_key": old["entity_key"], "increment": delta})
    return {"passed": True, "observed": observed, "contributions": evidence,
            "reason": "Exact completed fixture actions and existing relationship/identity triggers; no arbitrary monotonic allowance"}
