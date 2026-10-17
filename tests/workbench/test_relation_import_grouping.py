"""No-op relationship files keep historical primaries with linear row inspections."""

from core.services.workbench.resource.relation_files import files as module


def test_primary_planning_groups_rows_once_and_preserves_unchanged_legacy_groups(monkeypatch):
    count = 300
    rows = [{"errors": [], "values": {"operator_code": f"O{i}", "machine_code": "M1",
             "skill_level": "normal", "is_primary": "no"}} for i in range(count)]
    current = {f"O{i}": {"M1": {"skill_level": "normal", "is_primary": "no"}} for i in range(count)}
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M1", "is_primary": "yes"}})
    rows.append({"errors": [], "values": {"operator_code": "legacy", "machine_code": "M2", "is_primary": "yes"}})
    current["legacy"] = {code: {"skill_level": "normal", "is_primary": "yes"} for code in ("M1", "M2")}
    inspections, original = [], module._blocked

    def captured(row):
        inspections.append(True)
        return original(row)

    monkeypatch.setattr(module, "_blocked", captured)
    result = object.__new__(module.WorkbenchRelationFileService)._final_primaries(rows, current)
    assert all(not result[f"O{i}"] for i in range(count))
    assert result["legacy"] == {"M1", "M2"} and all(not row["errors"] for row in rows)
    assert len(inspections) <= 4 * len(rows)
