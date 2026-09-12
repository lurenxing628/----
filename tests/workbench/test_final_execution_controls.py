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
    required_ids = {f"WBP-FIELD-{group}.A{action:03d}"
                    for group, actions in [("007", [1, 2, 3, 4, 7]), ("008", range(1, 10)),
                                           ("009", [1, 3, 4, 5, 6]), ("013", [3, 4, 5])]
                    for action in actions}
    states = {row["state"] for row in report["actions"]}
    assert states == {width + "-" + theme + "-initial"
                      for width in ["1920", "1392"] for theme in ["light", "dark"]}
    for state in states:
        actions = [row for row in report["actions"] if row["state"] == state]
        assert len(actions) >= 17, (state, "Original keyboard, scroll, focus and cancel actions must remain")
        assert required_ids <= {action_id for row in actions for action_id in row["ids"]}
    assert all(row["passed"] for row in report["actions"])
    assert report["page_errors"] == report["console_errors"] == report["external_requests"] == []
    assert host.state() == before
    write_json(host.root / "final-controls-proof.json", {"actions": report["actions"], "gaps": report["gaps"],
        "strict_changed_tables": [], "screenshots": report["screenshots"]})
    assert report["gaps"] == [], report["gaps"]
