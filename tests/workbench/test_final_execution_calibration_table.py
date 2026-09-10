"""Current-factory calibration facets and exports operate on the complete read snapshot."""

import csv
import io
import json

import openpyxl
import pytest

from tests.workbench.calibration_adoption_host_support import prepare_calibration
from tests.workbench.final_execution_seed import CalibrationSeedJob
from tests.workbench.live_environment import write_json
from tests.workbench.report_execution_ledger_support import report_ledger_api as report_ledger_api
from tests.workbench.run_live_server_support import database_state

BASE = "/api/workbench/v1/calibration"


@pytest.fixture(name="table_api")
def table_api_fixture(report_ledger_api):
    api = report_ledger_api
    with api.db() as conn:
        conn.execute("DELETE FROM Schedule WHERE version=1")
        conn.execute("DELETE FROM ScheduleHistory WHERE version=1")
        conn.commit()
        job = CalibrationSeedJob(conn)
        job.path = api.path
        prepare_calibration(job)
        for sequence in range(3, 25):
            conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                         "VALUES ('P1',?,'T1',?,'internal',0,?)",
                         (sequence, "Calibration table " + str(sequence), None if sequence == 3 else 0 if sequence == 4 else 10))
        conn.commit()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    return api


def read(api, path="", status=200, **query):
    response = api.client.get(BASE + path, query_string={key: json.dumps(value) if isinstance(value, dict) else value for key, value in query.items()})
    assert response.status_code == status, response.get_json()
    return response.get_json()


def test_full_calibration_facets_are_not_first_page_values_and_all_selection_is_complete(table_api, tmp_path):
    api = table_api
    before = database_state(api.path)
    page = read(api, size=10)
    assert len(page["data"]["items"]) == 10 and page["data"]["summary"]["total"] == 24
    first = read(api, "/facets/old_unit_hours", scope={}, size=2)
    assert first["data"]["row_count"] == 24 and first["data"]["page"]["total"] == 5
    options = list(first["data"]["options"])
    for number in (2, 3):
        response = read(api, "/facets/old_unit_hours", scope={}, size=2, page=number, snapshot_ref=first["meta"]["snapshot_ref"])
        options.extend(response["data"]["options"])
    assert len({row["key"] for row in options}) == 5 and sum(row["count"] for row in options) == 24
    assert {row["label"]: row["count"] for row in options} == {"未提供": 1, "0": 1, "1": 1, "7": 1, "10": 20}
    selected = read(api, "/facet-selection/old_unit_hours", scope={}, size=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert set(selected["data"]["keys"]) == {row["key"] for row in options}
    assert selected["meta"]["snapshot_ref"] == first["meta"]["snapshot_ref"]
    assert database_state(api.path) == before
    write_json(tmp_path / "complete-calibration-facets.json", {"first_page": page, "facet_pages": options, "all_keys": selected})


def test_zero_unknown_and_other_columns_keep_typed_scope_and_threshold_exclusion(table_api):
    api = table_api
    before = database_state(api.path)
    options = read(api, "/facets/old_unit_hours", scope={})["data"]["options"]
    keys = {row["label"]: row["key"] for row in options}
    assert keys["未提供"] != keys["0"]
    for label, expected in (("未提供", None), ("0", 0)):
        filters = {"old_unit_hours": {"mode": "include", "values": [keys[label]]}}
        selected = read(api, column_filters=filters)["data"]
        assert selected["summary"]["total"] == 1 and selected["items"][0]["old_unit_hours"] == expected
        assert selected["items"][0]["deviation_percent"] is None
        assert read(api, deviation="over_20_percent", column_filters=filters)["data"]["summary"]["total"] == 0
        own = read(api, "/facets/old_unit_hours", scope={"column_filters": filters})["data"]
        assert own["row_count"] == 24 and own["page"]["total"] == 5
        other = read(api, "/facets/sample_count", scope={"column_filters": filters})["data"]
        assert other["row_count"] == 1 and other["options"][0]["label"] == "0"
    assert database_state(api.path) == before


def test_filtered_export_and_detail_use_complete_same_scope_not_page_size(table_api, tmp_path):
    api = table_api
    before = database_state(api.path)
    option = next(row for row in read(api, "/facets/sample_count", scope={})["data"]["options"] if row["label"] == "5")
    filters = {"sample_count": {"mode": "exclude", "values": [option["key"]]}}
    result = read(api, size=10, column_filters=filters)
    assert result["data"]["summary"]["total"] == 23 and len(result["data"]["items"]) == 10
    bound = {"size": 10, "column_filters": json.dumps(filters), "snapshot_ref": result["meta"]["snapshot_ref"]}
    rows = []
    for page in (1, 2, 3):
        rows.extend(read(api, size=10, column_filters=filters, snapshot_ref=result["meta"]["snapshot_ref"], page=page)["data"]["items"])
    expected = {row["template_operation_ref"] for row in rows}
    for format in ("csv", "xlsx"):
        response = api.client.get(BASE + "/export", query_string=dict(bound, format=format))
        assert response.status_code == 200 and response.headers["X-Workbench-Row-Count"] == "23"
        content = response.get_data()
        (tmp_path / ("calibration-all-filtered." + format)).write_bytes(content)
        if format == "csv":
            exported = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        else:
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=False)
            try:
                values = workbook["校准建议"].iter_rows(values_only=True)
                headers = next(values)
                exported = [dict(zip(headers, row)) for row in values]
            finally:
                workbook.close()
        references = set()
        for row in exported:
            reference, exported_scope = row["模板工序引用"], row["筛选范围"]
            assert isinstance(reference, str) and isinstance(exported_scope, str)
            references.add(reference)
            assert json.loads(exported_scope)["column_filters"] == filters
        assert len(exported) == 23 and references == expected
    detail = read(api, "/" + rows[-1]["template_operation_ref"], size=10, column_filters=filters, snapshot_ref=result["meta"]["snapshot_ref"])
    assert detail["data"]["suggestion"]["template_operation_ref"] == rows[-1]["template_operation_ref"]
    assert database_state(api.path) == before


def test_facet_snapshot_rejects_content_or_other_filter_change(table_api):
    api = table_api
    first = read(api, "/facets/old_unit_hours", scope={}, size=2)
    wrong = read(api, "/facets/old_unit_hours", status=409, scope={"status": "suggested"}, size=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert wrong["error"]["code"] == "snapshot_stale"
    with api.db() as conn:
        conn.execute("UPDATE PartOperations SET unit_hours=12 WHERE part_no='P1' AND seq=24")
    before = database_state(api.path)
    stale = read(api, "/facets/old_unit_hours", status=409, scope={}, size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert stale["error"]["code"] == "snapshot_stale" and database_state(api.path) == before


@pytest.mark.parametrize("filters", ["[]", '{"unknown":{"mode":"include","values":[]}}',
    '{"sample_count":{"mode":"include","values":["0"]}}', '{"sample_count":{"mode":"include","mode":"exclude","values":[]}}'])
def test_invalid_or_duplicate_filter_json_is_not_silently_ignored(table_api, filters):
    before = database_state(table_api.path)
    failed = read(table_api, status=400, column_filters=filters)
    assert failed["error"]["code"] == "invalid_input"
    assert database_state(table_api.path) == before
