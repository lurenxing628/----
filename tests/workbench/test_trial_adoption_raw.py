"""Production PARSE_DECLTYPES/COLNAMES must not change durable SQLite evidence."""

from contextlib import closing
from datetime import date, datetime

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import fingerprint
from core.services.workbench.trial_facts import capture_facts
from data.repositories.workbench_trial_raw_repo import WorkbenchTrialRawPlanRepository, read_raw_table
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.trial_adoption_support import INTENT, KEY, assert_retained, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import official, snapshot
from tests.workbench.trial_support import service as trial_service


def test_raw_helper_preserves_all_storage_classes_and_quoted_column_names(trial_case):
    case = trial_case
    case.conn.execute('CREATE TABLE "CQ ""raw" ("day ""name" DATE, stamp TIMESTAMP, "legacy [DATE]" BLOB, n INTEGER, r REAL, optional BLOB)')
    values = ("2026-09-09", "2026-09-09 08:00:00", b"\x00\xffraw", 7, 1.25, None)
    case.conn.execute('INSERT INTO "CQ ""raw" VALUES (?,?,?,?,?,?)', values)
    case.conn.commit()
    with closing(get_connection(str(case.path))) as conn:
        assert type(conn.execute('SELECT "day ""name" FROM "CQ ""raw"').fetchone()[0]) is date
        assert type(conn.execute('SELECT stamp FROM "CQ ""raw"').fetchone()[0]) is datetime
        columns, rows = read_raw_table(conn, 'CQ "raw')
        assert columns == ['day "name', "stamp", "legacy [DATE]", "n", "r", "optional"]
        assert tuple(rows[0][key] for key in columns) == values
        assert tuple(type(rows[0][key]) for key in columns) == (str, str, bytes, int, float, type(None))
        assert read_raw_table(case.conn, 'CQ "raw') == (columns, rows)
        assert capture_facts(conn)[1] == capture_facts(case.conn)[1]
        detail = WorkbenchTrialRawPlanRepository(conn).fetchall('SELECT "day ""name" AS due_date,stamp AS saved_timestamp FROM "CQ ""raw"')
        assert detail == [{"due_date": values[0], "saved_timestamp": values[1]}]
        assert conn.total_changes == 0


@pytest.mark.parametrize("value", ["not-a-date", b"\x00\xff", None, 42, 1.25])
def test_raw_date_column_never_coerces_bad_legacy_values(trial_case, value):
    case = trial_case
    case.conn.execute("CREATE TABLE CQRawDate(value DATE)")
    case.conn.execute("INSERT INTO CQRawDate VALUES (?)", (value,))
    case.conn.commit()
    with closing(get_connection(str(case.path))) as conn:
        _, rows = read_raw_table(conn, "CQRawDate")
        assert rows[0]["value"] == value and type(rows[0]["value"]) is type(value)
        assert fingerprint(capture_facts(conn)[0]) == fingerprint(capture_facts(case.conn)[0])


def test_production_plan_trial_save_and_adopt_are_driver_independent(trial_case):
    case = trial_case
    value = official(case)
    with closing(get_connection(str(case.path))) as conn:
        svc = trial_service(conn)
        context = svc.preview_create(value)["write_context"]
        created = trial_service(case.conn).create(value, context["write_token"], "cq-raw-create-request")["data"]
        head, rows = WorkbenchTrialRepository(conn).get(created["draft_ref"])
        assert type(rows[0]["original"]["batch"]["due_date"]) is str
        assert type(rows[0]["original"]["detail"]["due_date"]) is str
        assert rows[0]["original"]["batch"]["due_date"] == "2026-09-25"
        assert head["admission"]["facts_hash"] == capture_facts(conn)[1] == capture_facts(case.conn)[1]
        draft = svc.get(created["draft_ref"])
        saved = svc.save(draft["draft_ref"], {"name": "Production connection scenario"},
                         draft["write_context"]["write_token"], "cq-raw-save-request")["data"]
        checked = service(conn).preview(saved["scenario_ref"])
        assert checked["validation"]["can_adopt"], checked
        before = snapshot(case.conn)
        result = service(case.conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"], KEY, INTENT)
        assert result["result"] == "committed"
        assert_retained(before, snapshot(case.conn))


def test_real_date_ready_field_can_be_saved_and_revalidated(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-09'")
    case.conn.commit()
    saved = saved_scenario(case)
    with closing(get_connection(str(case.path))) as conn:
        checked = service(conn).preview(saved["scenario_ref"])
        assert checked["validation"]["can_adopt"], checked
        assert service(conn).adopt(saved["scenario_ref"], checked["write_context"]["write_token"], KEY, INTENT)["ok"]


@pytest.mark.parametrize("field,value", [
    ("due_date", "not-a-date"), ("ready_date", "not-a-date"),
    ("due_date", b"\x00\xffbad-date"), ("due_date", 42), ("due_date", 1.25),
    ("start_time", "not-a-time"), ("start_time", "2026-09-09T08:00:00.000001"),
    ("end_time", "2026-09-09T07:00:00"),
])
def test_bad_dates_and_times_reject_without_converter_guessing(trial_case, field, value):
    case = trial_case
    intent = official(case)
    table = "Batches" if field in ("due_date", "ready_date") else "Schedule"
    case.conn.execute('UPDATE "' + table + '" SET "' + field + '"=?', (value,))
    case.conn.commit()
    before = snapshot(case.conn)
    with closing(get_connection(str(case.path))) as conn:
        try:
            result = trial_service(conn).preview_create(intent)
        except WorkbenchCommandRejected as exc:
            assert exc.status in (409, 422)
        else:
            assert result["validation"]["constraints_status"] == "blocked"
        assert conn.total_changes == 0
    assert snapshot(case.conn) == before


def test_bad_blob_date_is_preserved_in_plan_original_and_detail(trial_case):
    case = trial_case
    intent = official(case)
    value = b"\x00\xffbad-date"
    case.conn.execute("UPDATE Batches SET due_date=?", (value,))
    case.conn.commit()
    with closing(get_connection(str(case.path))) as conn:
        svc = trial_service(conn)
        context = svc.preview_create(intent)["write_context"]
        draft = svc.create(intent, context["write_token"], "cq-bad-date-create-request")["data"]
        original = WorkbenchTrialRepository(conn).get(draft["draft_ref"])[1][0]["original"]
        assert original["batch"]["due_date"] == original["detail"]["due_date"] == value
        assert type(original["detail"]["due_date"]) is bytes
        assert draft["validation"]["constraints_status"] == "blocked"
        assert draft["comparison"]["batches"][0]["risk"] == "invalid_data"


def test_saved_bad_date_issue_points_to_scenario_task_not_draft_task(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET due_date='not-a-date'")
    case.conn.commit()
    saved = saved_scenario(case, changed=False)
    checked = service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"] is False
    reason = next(item for item in checked["validation"]["issues"] if item["code"] == "trial_base_date_invalid")
    assert reason["task_ref"] == saved["tasks"][0]["task_ref"]
    assert reason["task_ref"] != saved["tasks"][0]["source_task_ref"]
