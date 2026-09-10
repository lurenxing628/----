"""Current-official analysis uses actual intervals and preserves private source rows."""

from contextlib import closing
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard_analysis import read_dashboard_analysis
from tests.workbench.final_operations_seed import seed


def _fixture(root):
    (root / "backups").mkdir()
    seed(root)
    return root / "aps.db"


def test_final_operations_analysis_projects_actual_bars_and_pending_pool(tmp_path):
    database = _fixture(tmp_path)
    with closing(get_connection(str(database))) as conn:
        before = {name: [tuple(row) for row in conn.execute("SELECT * FROM " + name)] for name in
                  ("Batches", "BatchMaterials", "Schedule", "MachineDowntimes", "WorkbenchDashboardHistory")}
        data, state = read_dashboard_analysis(conn)
        assert data["plan"]["kind"] == "official" and data["plan"]["is_current_official"] is True
        assert len(data["tasks"]) == 1
        task = data["tasks"][0]
        assert task["batch_id"] == "B1" and task["span_hours"] == 2
        assert data["time_scope"]["range_start"] == "2026-09-09T08:00:00"
        assert data["time_scope"]["range_end"] == "2026-09-09T10:00:00"
        stop = data["downtimes"][0]
        assert stop["start"] == "2026-09-09T09:00:00" and stop["end"] == "2026-09-09T11:00:00"
        assert stop["valid"] and stop["recorded_at"] and stop["reason"] == "F maintenance record"
        assert data["overlaps"][0]["source"]["overlap_hours"] == 1
        assert data["resources"][0]["peak_utilization"] == 1
        assert data["pressure"]["count"] == 1
        pending = data["pending"]
        actual = conn.execute("SELECT COUNT(*) FROM Batches WHERE status='pending'").fetchone()[0]
        assert pending["count"] == actual and pending["count"] > 1
        row = next(row for row in pending["items"] if row["batch_id"] == "B1")
        assert row["batch_ref"] == task["batch_ref"] and row["quantity"] == 2
        assert row["ready_status"] == "no" and row["due_date"] == "2026-09-08"
        repeated, another = read_dashboard_analysis(conn, data["plan"]["plan_ref"])
        assert another == state and repeated["tasks"] == data["tasks"]
        for name, rows in before.items():
            assert [tuple(row) for row in conn.execute("SELECT * FROM " + name)] == rows


def test_final_operations_analysis_does_not_substitute_wrong_plan_reference(tmp_path):
    database = _fixture(tmp_path)
    with closing(get_connection(str(database))) as conn, pytest.raises(WorkbenchCommandRejected) as error:
        read_dashboard_analysis(conn, "f" * 48)
    assert error.value.code == "snapshot_stale"
    assert Path(database).exists()
