"""Full main entry controls use actual keyboard, picker and untouched SQLite."""

import json

from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_cases import final_execution_host as final_execution_host
from tests.workbench.live_environment import write_json


def test_full_main_field_number_date_and_cancel_controls(final_execution_host):
    host = final_execution_host
    before = host.state()
    host.browser("final_execution_controls.cjs")
    report = json.loads((host.root / "final-controls-initial.json").read_text(encoding="utf-8"))
    assert all(row["passed"] for row in report["actions"])
    assert report["page_errors"] == report["console_errors"] == report["external_requests"] == []
    assert host.state() == before
    write_json(host.root / "final-controls-proof.json", {"actions": report["actions"], "gaps": report["gaps"],
        "strict_changed_tables": [], "screenshots": report["screenshots"]})
    assert report["gaps"] == [], report["gaps"]
