"""DE-only current linkage assertions; frozen SQL is never relabeled current DDL."""

import hashlib
import re
from pathlib import Path

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.workbench_calibration_adoption_schema import objects as calibration_objects
from core.infrastructure.workbench_dashboard_schema import objects as dashboard_objects

V29_EMPTY_TABLES = (
    "WorkbenchCalibrationAdoptions", "WorkbenchCalibrationQuotaLocks",
    "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
)
V29_MAPPING_TABLES = ("WorkbenchDashboardItems", "WorkbenchDashboardDowntimeRefs")
V29_TABLES = V29_EMPTY_TABLES + V29_MAPPING_TABLES
V28_SHA256 = "2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52"


def missing_v29_issues():
    return ({"missing_calibration_adoption:" + name for name in calibration_objects()} |
            {"missing_dashboard_schema:" + name for name in dashboard_objects()})


def assert_v29_source_maps_only(conn):
    """Installation maps every existing source, without inventing handling facts."""
    for table in V29_EMPTY_TABLES:
        assert conn.execute('SELECT * FROM "' + table + '"').fetchall() == [], table
    batches = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1")]
    tasks = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchTaskRefs")]
    expected = {(category, ref, None) for category in ("delivery", "material") for ref in batches}
    expected |= {(category, None, ref) for category in ("actual", "downtime") for ref in tasks}
    items = list(conn.execute("SELECT item_ref,category,batch_ref,task_ref FROM WorkbenchDashboardItems"))
    assert len(items) == len(expected)
    assert {tuple(row[1:]) for row in items} == expected
    assert len({row[0] for row in items}) == len(items)
    assert all(re.fullmatch("[0-9a-f]{48}", row[0]) for row in items)
    downtimes = list(conn.execute("SELECT ref,source_id,active,revision FROM WorkbenchDashboardDowntimeRefs"))
    expected_downtimes = {(row[0], 1, 1) for row in conn.execute("SELECT id FROM MachineDowntimes")}
    assert len(downtimes) == len(expected_downtimes)
    assert {tuple(row[1:]) for row in downtimes} == expected_downtimes
    assert len({row[0] for row in downtimes}) == len(downtimes)
    assert all(re.fullmatch("[0-9a-f]{48}", row[0]) for row in downtimes)
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.fixture(name="frozen_v28_conn")
def frozen_v28_conn(mem_conn):
    from tests.workbench.identity_metadata_support import seed_resources

    source = Path(__file__).parent / "fixtures" / "schema-v28.sql"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == V28_SHA256
    assert not mem_conn.execute("SELECT name FROM sqlite_master").fetchall()
    mem_conn.executescript(source.read_text(encoding="utf-8"))
    set_schema_version(mem_conn, 28)
    assert get_schema_version(mem_conn) == 28
    assert not (set(calibration_objects()) | set(dashboard_objects())) & {
        row[0] for row in mem_conn.execute("SELECT name FROM sqlite_master")}
    seed_resources(mem_conn, relations=True)
    mem_conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (7,'frozen-v28','success','{}')")
    mem_conn.execute("UPDATE Parts SET remark=? WHERE part_no='P1'", (b"original\x00\xff",))
    mem_conn.commit()
    return mem_conn
