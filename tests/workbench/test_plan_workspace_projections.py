"""Real four-projection API snapshots and strict backend-to-JS DTO evidence."""

import copy

import pytest

from core.models.workbench_command import canonical_json
from core.services.workbench import plan_projection, plan_workspace_dto
from tests.workbench.plan_delivery_support import add_batch, add_operation
from tests.workbench.plan_read_support import NIGHT_END, NIGHT_START, assert_error, plan_read_api
from tests.workbench.test_plan_transport import run_probe, workspace_fixture


def prepare(api):
    with api.db() as conn:
        conn.execute("UPDATE Batches SET due_date='2026-09-10',part_name='Exact part'")
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('INT','Turning','internal')")
        conn.execute("UPDATE BatchOperations SET op_type_id='INT',source='internal'")
        conn.execute("UPDATE Machines SET op_type_id='INT'")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('PRIVATE-O1','PRIVATE-M1')")
        conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('PRIVATE-O1','INT')")
        conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('PRIVATE-O1',1)")
        conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_hours) VALUES ('2026-09-09','22:00',8)")


@pytest.mark.parametrize("role,scenario", [("adopted", None), ("baseline_best", None), ("critical_best", None), ("adopted", "PRIVATE-ACTIVE")])
def test_four_projections_have_one_scope_and_transaction(plan_api, tmp_path, monkeypatch, role, scenario):
    prepare(plan_api)
    observed = []
    for name in ("build_plan_baseline", "project_plan_calendar", "project_plan_occupancy", "read_plan_delivery"):
        original = getattr(plan_workspace_dto, name)

        def capture(conn, _name=name, _original=original, **kwargs):
            assert conn.in_transaction
            observed.append((_name, id(conn), kwargs["scope"]))
            return _original(conn, **kwargs)

        monkeypatch.setattr(plan_workspace_dto, name, capture)
    ref = plan_api.ref(role=role, scenario_id=scenario)
    scope = {"range_start": "2026-09-09T00:00:00", "range_end": "2026-09-14T00:00:00"}
    before = plan_api.state()
    fixture = workspace_fixture(plan_api, "four projections " + role + str(scenario), ref, **scope)
    d = fixture["payload"]["data"]
    assert len(observed) == 4 and len({row[1] for row in observed}) == 1
    assert all(row[2].scope() == d["scope"] for row in observed)
    assert d["projections"]["calendar"]["time_scope"] == d["projections"]["occupancy"]["time_scope"] == d["time_scope"]
    assert d["projections"]["delivery_risks"]["scope"] == d["scope"]
    baseline = d["projections"]["baseline"]
    if scenario:
        assert baseline["state"] == "available" and baseline["comparison_scope"]["scope"] == d["scope"]
    else:
        assert baseline["state"] == "unavailable" and baseline["reason_code"] == "not_recorded"
    assert plan_api.state() == before
    assert run_probe(tmp_path, [fixture])["checks"] == 1


def test_public_resource_directory_joins_only_permanent_refs(plan_api, tmp_path):
    prepare(plan_api)
    fixture = workspace_fixture(plan_api, "directory", plan_api.ref())
    d = fixture["payload"]["data"]
    assert {(row["kind"], row["business_code"], row["label"]) for row in d["resources"]} == {
        ("machine", "PRIVATE-M1", "Machine one"), ("operator", "PRIVATE-O1", "Operator one")}
    directory = {row["ref"]: row for row in d["resources"]}
    assert directory[d["tasks"][0]["machine_ref"]]["kind"] == "machine"
    assert directory[d["tasks"][0]["operator_ref"]]["kind"] == "operator"
    assert run_probe(tmp_path, [fixture])["checks"] == 1


def test_external_supplier_and_range_unavailable_are_real_joint_shapes(plan_api, tmp_path):
    prepare(plan_api)
    with plan_api.db() as conn:
        conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('00001','External supplier')")
        conn.execute("UPDATE BatchOperations SET supplier_id='00001',source='external'")
    ref = plan_api.ref()
    fixtures = [workspace_fixture(plan_api, "external supplier directory", ref)]
    data = fixtures[0]['payload']['data']
    assert next(row for row in data['resources'] if row['kind'] == 'supplier')['business_code'] == '00001'
    assert data['projections']['occupancy']['resources'] == []
    fixtures.append(workspace_fixture(plan_api, "range limit explicit unavailable", ref,
                                     range_start='2000-01-01T00:00:00', range_end='2030-01-01T00:00:00'))
    calendar = fixtures[-1]['payload']['data']['projections']['calendar']
    assert calendar['state'] == 'unavailable' and calendar['resources'] is None
    assert calendar['global']['available_hours'] is None
    assert run_probe(tmp_path, fixtures)['checks'] == 2


def test_narrow_task_window_delivery_finish_uses_full_selected_batch(plan_api, tmp_path):
    prepare(plan_api)
    with plan_api.db() as conn:
        op = add_operation(conn, version=3, start='2026-09-11 01:00:00', end='2026-09-11 03:00:00')
    ref = plan_api.ref()
    scope = {'range_start': NIGHT_START, 'range_end': NIGHT_END}
    fixture = workspace_fixture(plan_api, 'narrow delivery full batch', ref, **scope)
    data = fixture['payload']['data']
    assert data['task_count'] == 1
    item = data['projections']['delivery_risks']['items'][0]
    assert item['task_count'] == 2 and item['planned_finish'] == '2026-09-11T03:00:00'
    assert run_probe(tmp_path, [fixture])['checks'] == 1
    with plan_api.db() as conn:
        conn.execute("UPDATE Schedule SET end_time='2026-09-11 05:00:00' WHERE version=3 AND op_id=?", (op,))
    assert_error(plan_api.get('/' + ref + '/workspace', snapshot_ref=fixture['payload']['meta']['snapshot_ref'], **scope), 'snapshot_stale')


@pytest.mark.parametrize("sql", [
    "UPDATE WorkCalendar SET shift_hours=7 WHERE date='2026-09-09'",
    "UPDATE WorkCalendar SET remark='PRIVATE-note-only' WHERE date='2026-09-09'",
    "INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('PRIVATE-O1','2026-09-09','23:00',4)",
    "UPDATE Batches SET due_date='2026-09-11' WHERE batch_id='CAT-B'",
    "UPDATE Batches SET part_name='Other part' WHERE batch_id='CAT-B'",
    "INSERT INTO MachineDowntimes(machine_id,start_time,end_time) VALUES ('PRIVATE-M1','2026-09-09 23:00:00','2026-09-10 01:00:00')",
    "DELETE FROM OperatorMachine WHERE machine_id='PRIVATE-M1'",
])
def test_changed_projection_facts_stale_workspace_and_export(plan_api, sql):
    prepare(plan_api)
    ref = plan_api.ref()
    token = plan_api.read('/' + ref + '/workspace')["meta"]["snapshot_ref"]
    with plan_api.db() as conn:
        conn.execute(sql)
    assert_error(plan_api.get('/' + ref + '/workspace', snapshot_ref=token), "snapshot_stale")
    for fmt in ("csv", "xlsx"):
        assert_error(plan_api.get('/' + ref + '/export', format=fmt, snapshot_ref=token), "snapshot_stale")


def test_private_calendar_fact_changes_snapshot_without_changing_dto(plan_api):
    prepare(plan_api)
    path = '/' + plan_api.ref() + '/workspace'
    first = plan_api.read(path)
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkCalendar SET remark='PRIVATE-calendar-audit'")
    second = plan_api.read(path)
    assert first["data"] == second["data"]
    assert_error(plan_api.get(path, snapshot_ref=first["meta"]["snapshot_ref"]), "snapshot_stale")


def test_concurrent_writer_cannot_split_four_projection_snapshot(plan_api, monkeypatch):
    prepare(plan_api)
    with plan_api.db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    original = plan_workspace_dto.project_plan_calendar

    def change_after_calendar(conn, **kwargs):
        result = original(conn, **kwargs)
        with plan_api.db() as writer:
            writer.execute("UPDATE Batches SET due_date='2026-09-11'")
            writer.execute("UPDATE WorkCalendar SET shift_hours=3")
        return result

    monkeypatch.setattr(plan_workspace_dto, "project_plan_calendar", change_after_calendar)
    ref = plan_api.ref()
    first = plan_api.read('/' + ref + '/workspace')
    assert first["data"]["projections"]["delivery_risks"]["items"][0]["due_date"] == '2026-09-10'
    monkeypatch.setattr(plan_workspace_dto, "project_plan_calendar", original)
    assert_error(plan_api.get('/' + ref + '/workspace', snapshot_ref=first["meta"]["snapshot_ref"]), "snapshot_stale")


def test_delivery_partial_full_batch_and_unavailable_calendar_joint_dto(plan_api, tmp_path):
    prepare(plan_api)
    ref = plan_api.ref()
    fixtures = []
    with plan_api.db() as conn:
        add_batch(conn, "SECOND", due=None, version=3)
    fixtures.append(workspace_fixture(plan_api, "partial delivery", ref))
    assert fixtures[-1]["payload"]["data"]["projections"]["delivery_risks"]["state"] == "partial"
    with plan_api.db() as conn:
        add_operation(conn, version=None, seq=8)
        conn.execute("UPDATE WorkCalendar SET efficiency=NULL")
    fixtures.append(workspace_fixture(plan_api, "unknown capacity incomplete delivery", ref))
    p = fixtures[-1]["payload"]["data"]["projections"]
    assert p["delivery_risks"]["state"] == "unavailable"
    assert p["calendar"]["global"]["available_hours"] is None
    assert p["occupancy"]["resources"][0]["available_hours"] is None
    assert run_probe(tmp_path, fixtures)["checks"] == 2


def test_narrow_scope_keeps_offscreen_baseline_and_full_batch_finish(plan_api, tmp_path):
    prepare(plan_api)
    ref = plan_api.ref(scenario_id="PRIVATE-ACTIVE")
    fixture = workspace_fixture(plan_api, "before only baseline", ref, range_start=NIGHT_START, range_end=NIGHT_END)
    d = fixture["payload"]["data"]
    assert d["tasks"] == []
    item = d["projections"]["baseline"]["items"][0]
    assert item["before_in_scope"] and not item["after_in_scope"] and item["after"]["start"] > NIGHT_END
    assert run_probe(tmp_path, [fixture])["checks"] == 1


def test_aggregate_workspace_limit_after_individual_projections(plan_api, monkeypatch):
    prepare(plan_api)
    ref = plan_api.ref(scenario_id="PRIVATE-ACTIVE")
    data = plan_api.read('/' + ref + '/workspace')["data"]
    budget = max(len(canonical_json(value).encode('utf-8')) for value in data["projections"].values()) + 1
    assert len(canonical_json(data).encode('utf-8')) > budget
    monkeypatch.setattr(plan_projection, "MAX_PLAN_RESPONSE_BYTES", budget)
    assert_error(plan_api.get('/' + ref + '/workspace'), "query_too_large", 413)


def test_real_dto_unknown_null_privatefacts_scope_mutations_rejected(plan_api, tmp_path):
    prepare(plan_api)
    base = workspace_fixture(plan_api, "original", plan_api.ref())
    mutations = [
        (['resources', 0], None), (['projections', 'delivery_risks', 'items', 0], None),
        (['resources', 0, 'entity_key'], 'PRIVATE-key'), (['resources', 0, 'ref'], 'b' * 48),
        (['projections', 'calendar', 'time_scope', 'range_start'], '2026-01-01T00:00:00'),
        (['projections', 'calendar', 'global', 'sources'], {}),
        (['projections', 'calendar', 'resources', 0, 'resource_ref'], 'b' * 48),
        (['projections', 'occupancy', 'resources', 0, 'utilization'], 2),
        (['projections', 'occupancy', 'resources', 0, 'arranged_hours'], None),
        (['projections', 'delivery_risks', 'scope', 'plan_ref'], 'b' * 48),
        (['projections', 'delivery_risks', 'items', 0, 'is_overdue'], True),
        (['projections', 'delivery_risks', 'items', 0, 'delay_days'], None),
        (['projections', 'delivery_risks', 'items', 0, 'completion_record'], {}),
        (['projections', 'delivery_risks', 'state'], 'loaded'), (['plan', 'capabilities', 'export'], False),
    ]
    fixtures = [base]
    for index, (keys, value) in enumerate(mutations):
        fixture = copy.deepcopy(base)
        fixture.update(name='mutated ' + str(index), contract_error=True)
        node = fixture['payload']['data']
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
        fixtures.append(fixture)
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkCalendar SET efficiency=NULL")
        conn.execute("UPDATE Batches SET due_date=NULL")
    unknown = workspace_fixture(plan_api, "unknown original", plan_api.ref())
    fixtures.append(unknown)
    for index, keys in enumerate([
        ['calendar', 'global', 'available_hours'], ['occupancy', 'resources', 0, 'available_hours'],
        ['delivery_risks', 'items', 0, 'delay_hours'], ['delivery_risks', 'items', 0, 'delay_days'],
    ]):
        fixture = copy.deepcopy(unknown)
        fixture.update(name='null to zero ' + str(index), contract_error=True)
        node = fixture['payload']['data']['projections']
        for key in keys[:-1]:
            node = node[key]
        assert node[keys[-1]] is None
        node[keys[-1]] = 0
        fixtures.append(fixture)
    assert run_probe(tmp_path, fixtures)['checks'] == len(fixtures)
