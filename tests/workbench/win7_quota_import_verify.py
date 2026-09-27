"""Independently verify exact native snapshots around locked quota imports."""
import json
import sqlite3
import sys
from pathlib import Path

from tests.workbench.win7_restart_compare import snapshot


def parts(file):
    with sqlite3.connect(file.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return {row["id"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations")}


def main():
    root = Path(sys.argv[1])
    before_file = root / "after-adoption.db"
    schema, baseline = snapshot(before_file)
    expected = parts(before_file)
    locked_id = next(key for key, row in expected.items() if row["part_no"] == "P1" and row["seq"] == 1)
    other_id = next(key for key, row in expected.items() if row["part_no"] == "P1" and row["seq"] == 2)
    assert expected[locked_id]["unit_hours"] == 3
    checked = []
    for name, setup in (("mixed-xlsx", None), ("allskip-xlsx", None), ("setup-csv", 9), ("setup_blank-csv", 10)):
        file = root / (name + ".db")
        current_schema, current = snapshot(file)
        assert schema == current_schema
        for table, rows in baseline.items():
            if table not in ("PartOperations", "WorkbenchEntityRefs", "WorkbenchCommandReceipts"):
                assert current[table] == rows, (name, table)
        expected[other_id]["unit_hours"] = 8
        if setup is not None:
            expected[locked_id]["setup_hours"] = setup
        assert parts(file) == expected, name
        checked.append({"phase": name, "locked_unit_hours": 3, "allowed_setup_hours": expected[locked_id]["setup_hours"],
                        "other_unit_hours": 8, "locks_adoption_and_other_tables_unchanged": True})
    (root / "quota-content-verification.json").write_text(
        json.dumps({"passed": True, "checks": checked}, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "snapshots": len(checked)}))


if __name__ == "__main__":
    main()
