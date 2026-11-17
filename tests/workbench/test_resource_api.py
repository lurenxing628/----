"""Real Flask resource creation, update, stale-context rejection, replay and deletion."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.facts.table_columns import sql_order
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.table_states import resource_table_states
from core.shared.strict_json import canonical_json
from data.repositories.workbench_resource_metrics_repo import WorkbenchResourceMetricsRepository
from data.repositories.workbench_resource_query_repo import WorkbenchResourceQueryRepository
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.resource_entity_support import (
    create_catalog,
    identity_for,
    resource_database,  # noqa: F401
    run_resource,
)

BASE = "/api/workbench/v1/entities/"


def _list(client, kind, **query):
    response = client.get(BASE + kind, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _detail(client, kind, ref):
    response = client.get(BASE + kind + "/" + ref)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def _create(client, kind, code, *, fields=None, relationships=None):
    token = _list(client, kind)["data"]["create_context"]["write_token"]
    payload = {"business_code": code, "label": "Name-" + code, "fields": fields or {}}
    if relationships is not None:
        payload["relationships"] = relationships
    body = {"request_key": "resource-create-" + kind + "-" + code, "write_token": token, "input": payload}
    response = client.post(BASE + kind + "/create", json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    ref = response.get_json()["data"]["entity_ref"]
    return ref, body


def _command(client, kind, ref, action, payload, *, context=None, key="resource-command-000001"):
    if context is None:
        context = _detail(client, kind, ref)["write_context"]
    return client.post(BASE + kind + "/" + ref + "/" + action,
                       json={"request_key": key, "write_token": context["write_token"], "input": payload})


@pytest.mark.parametrize('kind', ['op_type', 'machine', 'operator', 'supplier', 'machine_group', 'shift_profile'])
def test_update_delete_and_replay_are_real_for_each_kind(app_client, kind):
    fields = {"default_days": 3} if kind == "supplier" else {}
    if kind == "shift_profile":
        fields = {"anchor_date": "2026-09-09", "cycle_days": 1,
                  "pattern": [{"day_offset": 0, "is_rest": False,
                               "periods": [{"start": "08:00", "end": "16:00", "day_offset": 0}]}]}
    ref, create = _create(app_client, kind, "ROW", fields=fields)
    before = _detail(app_client, kind, ref)
    changed = _command(app_client, kind, ref, "update", {"label": "Changed"}, context=before["write_context"], key="resource-update-000001")
    assert changed.status_code == 200 and changed.get_json()["result"] == "committed"
    assert _detail(app_client, kind, ref)["label"] == "Changed"
    stale = _command(app_client, kind, ref, "update", {"label": "Stale"}, context=before["write_context"], key="resource-stale-000001")
    assert stale.status_code == 409 and stale.get_json()["committed"] is False
    replay = app_client.post(BASE + kind + "/create", json=create)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True
    deleted = _command(app_client, kind, ref, "delete", {}, key="resource-delete-000001")
    assert deleted.status_code == 200 and deleted.get_json()["result"] == "committed"
    assert app_client.get(BASE + kind + "/" + ref).status_code == 404
    malformed = app_client.get(BASE + kind + "/" + "z" * 48)
    assert malformed.status_code == 404 and malformed.get_json()["error"]["code"] == "entity_not_found"
    assert "已失效" in malformed.get_json()["error"]["message"]


def test_supplier_default_days_writes_admit_the_external_days_range(app_client):
    # 默认周期会派生成工序和外协组周期，新增、修改都按外协周期的同一值域 (0, 36500] 天准入。
    ref, _ = _create(app_client, "supplier", "S-MAX", fields={"default_days": 36500})
    assert _detail(app_client, "supplier", ref)["fields"]["default_days"] == 36500
    token = _list(app_client, "supplier")["data"]["create_context"]["write_token"]
    created = app_client.post(BASE + "supplier/create", json={
        "request_key": "resource-create-supplier-over-1", "write_token": token,
        "input": {"business_code": "S-OVER", "label": "over", "fields": {"default_days": 36500.5}}})
    updated = [_command(app_client, "supplier", ref, "update", {"fields": {"default_days": value}},
                        key="resource-update-supplier-bad-" + str(index))
               for index, value in enumerate((0, -1, 36500.5, True, "3"))]
    for response in [created] + updated:
        assert response.status_code == 422, response.get_data(as_text=True)
        assert response.get_json()["error"]["message"] == "默认周期必须大于 0 天且不超过 36500 天（100 年）。"
    assert [row["business_code"] for row in _list(app_client, "supplier")["data"]["entities"]] == ["S-MAX"]
    assert _detail(app_client, "supplier", ref)["fields"]["default_days"] == 36500


_SHIFT_DAY = {"start": "08:00", "end": "16:00", "day_offset": 0}
_NIGHT = {"start": "22:00", "end": "06:00", "day_offset": 0}


_DAY0 = "fields.pattern.0"


@pytest.mark.parametrize(("pattern", "message", "path"), [
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": None}], "工作时段必须按列表提交。", _DAY0 + ".periods", id="explicit-null"),
    pytest.param([{"day_offset": 0, "is_rest": False}], "工作时段必须按列表提交。", _DAY0 + ".periods", id="omitted-periods"),
    pytest.param([{"day_offset": 0, "is_rest": True, "periods": None}], "工作时段必须按列表提交。", _DAY0 + ".periods", id="rest-null"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": []}], "工作日请至少填写一个工作时段，或明确改为休息日。",
                 _DAY0 + ".periods", id="workday-empty"),
    pytest.param([{"day_offset": 0, "is_rest": True, "periods": [_SHIFT_DAY]}], "休息日不能填写工作时段。", _DAY0 + ".periods",
                 id="rest-with-periods"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY], "hours": 8}], "提交内容含有不支持的项", _DAY0,
                 id="legacy-hours"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY], "shiftStart": "08:00"}], "提交内容含有不支持的项", _DAY0,
                 id="legacy-shiftStart"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY], "shift_start": "08:00"}], "提交内容含有不支持的项", _DAY0,
                 id="legacy-shift_start"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY], "shift_end": "16:00"}], "提交内容含有不支持的项", _DAY0,
                 id="legacy-shift_end"),
    pytest.param([{"day_offset": 0, "is_rest": "no", "periods": [_SHIFT_DAY]}], "班次日期序号和休息标记不正确。", _DAY0, id="rest-flag"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_NIGHT]},
                  {"day_offset": 1, "is_rest": False, "periods": [{"start": "05:00", "end": "13:00", "day_offset": 0}]}],
                 "相邻轮换日期的班次时间重叠", _DAY0 + ".periods", id="adjacent-overlap"),
    pytest.param([{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY]},
                  {"day_offset": 1, "is_rest": False, "periods": [{"start": "22:00", "end": "09:00", "day_offset": 0}]}],
                 "相邻轮换日期的班次时间重叠", "fields.pattern.1.periods", id="cycle-wrap-overlap"),
    # 提交顺序与日序不同：重叠落在第 0 天，路径仍指回它的提交位置。
    pytest.param([{"day_offset": 1, "is_rest": False, "periods": [{"start": "05:00", "end": "13:00", "day_offset": 0}]},
                  {"day_offset": 0, "is_rest": False, "periods": [_NIGHT]}],
                 "相邻轮换日期的班次时间重叠", "fields.pattern.1.periods", id="unsorted-overlap"),
])
def test_shift_profile_write_entries_reject_invalid_pattern_days(app_client, pattern, message, path):
    fields = {"anchor_date": "2026-09-09", "cycle_days": len(pattern), "pattern": pattern}
    token = _list(app_client, "shift_profile")["data"]["create_context"]["write_token"]
    created = app_client.post(BASE + "shift_profile/create", json={
        "request_key": "resource-create-shift-invalid-1", "write_token": token,
        "input": {"business_code": "BAD", "label": "bad", "fields": fields}})
    assert created.status_code == 422, created.get_data(as_text=True)
    error = created.get_json()["error"]
    assert error["code"] == "invalid_input" and message in error["message"]
    assert error["fields"] == [{"path": path, "message": error["message"]}]
    assert _list(app_client, "shift_profile")["data"]["entities"] == []

    # 更新入口走同一条规则，且不留下任何改动。
    good = [{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY]}]
    ref, _ = _create(app_client, "shift_profile", "GOOD", fields={"anchor_date": "2026-09-09", "cycle_days": 1, "pattern": good})
    updated = _command(app_client, "shift_profile", ref, "update", {"fields": fields}, key="resource-update-shift-invalid-1")
    assert updated.status_code == 422 and message in updated.get_json()["error"]["message"]
    assert updated.get_json()["error"]["fields"] == [{"path": path, "message": updated.get_json()["error"]["message"]}]
    saved = _detail(app_client, "shift_profile", ref)["fields"]["pattern"]
    assert saved == [{"day_offset": 0, "is_rest": False, "periods": [_SHIFT_DAY]}]


def test_shift_profile_pattern_stores_only_periods_and_adjacent_rest_breaks_overlap(app_client):
    pattern = [{"day_offset": 0, "is_rest": False, "periods": [_NIGHT]},
               {"day_offset": 1, "is_rest": True, "periods": []},
               {"day_offset": 2, "is_rest": False, "periods": [{"start": "05:00", "end": "13:00", "day_offset": 0}]}]
    ref, _ = _create(app_client, "shift_profile", "ROT", fields={"anchor_date": "2026-09-09", "cycle_days": 3, "pattern": pattern})
    assert _detail(app_client, "shift_profile", ref)["fields"]["pattern"] == pattern


def test_plain_resource_pages_query_only_current_page_codes_and_lightweight_states(resource_conn, monkeypatch):
    conn = resource_conn
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "second machine"})
    insert_row(conn, "MachineOpTypes", {"machine_id": "M2", "op_type_id": "OT1"})
    insert_row(conn, "Machines", {"machine_id": "M3", "name": "Ä"})
    insert_row(conn, "Operators", {"operator_id": "O2", "name": "second operator"})
    insert_row(conn, "Suppliers", {"supplier_id": "S2", "name": "second supplier", "default_days": 2.0})
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id, op_type_id) VALUES (?, 'EXT')", [("S1",), ("S2",)])
    conn.execute("UPDATE Machines SET name='车床AlPhA' WHERE machine_id IN ('M1','M2')")
    conn.commit()
    group, shift = create_catalog(conn, "machine_group"), create_catalog(conn, "shift_profile")
    op_type = identity_for(conn, "op_type")
    assert op_type is not None
    for code in ("M1", "M2"):
        run_resource(conn, "machine", "update", {"relationships": {"group_ref": group.ref}}, code=code)
    for code in ("O1", "O2"):
        run_resource(conn, "operator", "update", {"relationships": {
            "shift_profile_ref": shift.ref, "skill_refs": [op_type.ref],
        }}, code=code)

    assert not hasattr(WorkbenchResourceQueryRepository, "scope_state")
    counts, relations, member_reads = [], [], []
    assigned_counts = WorkbenchResourceTableRepository.assigned_counts
    page_relations = WorkbenchResourceTableRepository.page_relations
    member_counts = WorkbenchResourceTableRepository.member_counts

    def read_counts(repo, kind, codes):
        counts.append((kind, tuple(codes)))
        return assigned_counts(repo, kind, codes)

    def read_relations(repo, kind, codes):
        relations.append((kind, tuple(codes)))
        return page_relations(repo, kind, codes)

    def read_members(repo, kind, codes):
        member_reads.append((kind, tuple(codes)))
        return member_counts(repo, kind, codes)

    for kind in ("machine", "operator", "supplier", "op_type", "machine_group", "shift_profile"):
        reader = WorkbenchResourceQueryService(conn, kind)
        query = ResourcePageRequest(kind, size=1, direction="desc")
        counts.clear()
        relations.clear()
        member_reads.clear()
        with monkeypatch.context() as scoped:
            with reader.read_snapshot() as scope:
                assert not hasattr(scope, "_ensure_table_snapshot")
                assert not hasattr(scope, "create_snapshot")
                fingerprint = scope.state_fingerprint()
                rows = reader.repo.page_rows(query, sql_order(query))
                total = len(reader.repo.toolbar_keys(query))
                expected = [scope.detail(row["ref"]) for row in rows]
                scoped.setattr(WorkbenchResourceTableRepository, "assigned_counts", read_counts)
                scoped.setattr(WorkbenchResourceTableRepository, "page_relations", read_relations)
                scoped.setattr(WorkbenchResourceTableRepository, "member_counts", read_members)
                records, page = scope.page(query)
                codes = tuple(row["business_code"] for row in rows)
                assert len(codes) == 1
                assert records == expected
                assert page["total"] == total
                assert page["number"] == query.number and page["size"] == query.size
                assert page["sort"] == [{"field": query.sort, "direction": query.direction}]
                assert scope.state_fingerprint() == fingerprint
                assert scope.table_identities is None
                # 依赖计数只有 assigned_counts 一个入口，工种也走它。
                if kind in ("machine", "operator", "supplier", "op_type"):
                    assert counts == [(kind, codes)]
                else:
                    assert counts == []
                if kind in ("machine_group", "shift_profile"):
                    assert member_reads == [(kind, codes)]
                    assert "members" not in records[0].state
                    assert isinstance(records[0].state["member_count"], int)
                if kind == "supplier":
                    assert relations == []
                    assert "references" not in records[0].state["supplier"]
                    assert set(records[0].state["supplier"]["counts"]) == {
                        "part_operations", "batch_operations", "external_groups"
                    }
                if kind != "op_type":
                    states = resource_table_states(scope.table_facts(), kind, codes)
                    assert {record.identity.entity_key: record.state for record in records} == states
                if kind == "machine":
                    advanced, _ = scope.page(ResourcePageRequest(kind, query="车床alpha", sort="group_ref", direction="desc"))
                    assert [record.identity.entity_key for record in advanced] == ["M1", "M2"]
                    matched, _ = scope.page(ResourcePageRequest(kind, query="车床ALPHA", sort="label", direction="desc"))
                    assert matched == advanced
                    counts.clear()
                    unmatched, _ = scope.page(ResourcePageRequest(kind, query="ä"))
                    assert unmatched == [] and counts == []
                if kind == "supplier":
                    ascending, _ = scope.page(ResourcePageRequest(kind, sort="default_days"))
                    descending, _ = scope.page(ResourcePageRequest(kind, sort="default_days", direction="desc"))
                    assert [record.identity.entity_key for record in ascending] == ["S2", "S1"]
                    assert [record.identity.entity_key for record in descending] == ["S1", "S2"]


@pytest.mark.parametrize('kind,code,table,key', [
    ('op_type', 'OT1', 'OpTypes', 'op_type_id'), ('machine', 'M1', 'Machines', 'machine_id'),
    ('operator', 'O1', 'Operators', 'operator_id'), ('supplier', 'S1', 'Suppliers', 'supplier_id'),
])
def test_resource_import_captures_one_batch_and_applies_without_current_row_rereads(resource_conn, monkeypatch, kind, code, table, key):
    from collections import Counter

    from core.services.workbench.resource.files import WorkbenchResourceFileService
    from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository
    from tests.workbench.resource_file_support import confirm, file_bytes

    conn = resource_conn
    other = code + '-SECOND'
    extra = {'default_days': 2.0} if kind == 'supplier' else {}
    insert_row(conn, table, {key: other, 'name': other, **extra})
    conn.commit()
    content = file_bytes([(code, 'prepared-first'), (other, 'prepared-second')], headers=('编号', '名称'))
    service = WorkbenchResourceFileService(conn, kind)
    category = 'internal' if kind == 'op_type' else None
    preview = service.preview_import(content, file_format='csv', mode='upsert', category=category)
    assert preview.as_dict()['summary']['rejected'] == 0, preview.as_dict()
    fact_reads, reference_reads = [], []
    original_facts = WorkbenchResourceMetricsRepository.facts
    original_references = WorkbenchResourceFileRepository.references_many

    def captured(repo, names):
        fact_reads.extend(names)
        return original_facts(repo, names)

    def references(repo, selected_kind, codes):
        reference_reads.append((selected_kind, tuple(codes)))
        return original_references(repo, selected_kind, codes)

    monkeypatch.setattr(WorkbenchResourceMetricsRepository, 'facts', captured)
    monkeypatch.setattr(WorkbenchResourceFileRepository, 'references_many', references)
    result = confirm(conn, kind, preview)
    assert result['result'] == 'committed'
    assert reference_reads == [(kind, tuple(sorted([code, other])))]
    assert all(amount == 1 for amount in Counter(fact_reads).values())
    rows = {row[key]: row['name'] for row in conn.execute('SELECT * FROM ' + table)}
    assert (rows[code], rows[other]) == ('prepared-first', 'prepared-second')


@pytest.mark.parametrize('kind,special', [('operator', 'leave'), ('supplier', 'pending_review')])
def test_reasoned_status_changes_preserve_explicit_reason_then_become_unchanged(app_client, kind, special):
    fields = {'default_days': 2.5} if kind == 'supplier' else {}
    ref, _body = _create(app_client, kind, 'REASONED', fields=fields)
    response = _command(app_client, kind, ref, 'update', {'fields': {'status': special}}, key='resource-reason-special-' + kind)
    assert response.status_code == 200, response.get_json()
    assert _detail(app_client, kind, ref)['status'] == special
    response = _command(app_client, kind, ref, 'update', {'fields': {'status': 'inactive'}}, key='resource-reason-inactive-' + kind)
    assert response.status_code == 200 and response.get_json()['result'] == 'committed'
    entity = _detail(app_client, kind, ref)
    assert entity['status'] == 'inactive'
    response = _command(app_client, kind, ref, 'update', {'fields': {'status': 'inactive'}}, key='resource-reason-unchanged-' + kind)
    assert response.status_code == 200 and response.get_json()['result'] == 'unchanged'


def test_resource_bulk_delete_prepares_one_current_set_and_keeps_rejected_selection_rows(resource_conn):
    from core.services.workbench.resource.bulk import WorkbenchResourceBulkService
    from tests.workbench.resource_file_support import confirm, ref

    conn = resource_conn
    for code in ('DELETE-ONE', 'DELETE-TWO'):
        insert_row(conn, 'Machines', {'machine_id': code, 'name': code})
    conn.commit()
    service = WorkbenchResourceBulkService(conn, 'machine')
    with service.reader.read_snapshot():
        rejected = service.preview_delete(['f' * 48], scope=ResourcePageRequest(kind='machine')).as_dict()
    assert rejected['summary']['rejected'] == 1 and rejected['rows'][0]['entity_ref'] == 'f' * 48
    refs = [ref(conn, 'machine', code) for code in ('DELETE-ONE', 'DELETE-TWO')]
    with service.reader.read_snapshot():
        preview = service.preview_delete(refs, scope=ResourcePageRequest(kind='machine'))
    assert preview.as_dict()['summary']['rejected'] == 0

    result = confirm(conn, 'machine', preview)
    assert result['result'] == 'committed' and result['data']['deleted_count'] == 2
    assert conn.execute("SELECT COUNT(*) FROM Machines WHERE machine_id IN ('DELETE-ONE','DELETE-TWO')").fetchone()[0] == 0


def test_downtime_writes_reject_reversed_windows_and_check_overlap_only_when_the_window_changes(resource_conn):
    from core.infrastructure.transaction import TransactionManager
    from core.models.workbench_downtime import normalize_downtime
    from core.services.workbench.resource.downtimes import WorkbenchDowntimeService

    conn = resource_conn
    service = WorkbenchDowntimeService(conn)
    machine = identity_for(conn, "machine", "M1")
    assert machine is not None

    def window(start, end, reason="maintenance", detail=None, **ref):
        action = "update" if ref else "create"
        return normalize_downtime(action, {**ref, "start_time": start, "end_time": end, "reason_code": reason, "reason_detail": detail})

    def apply(action, payload):
        with TransactionManager(conn).transaction():
            return service.apply_normalized(machine.ref, action, payload, service.snapshot(machine.ref))

    with pytest.raises(WorkbenchCommandRejected, match="停机结束必须晚于开始"):
        window("2026-10-01 16:00", "2026-10-01 15:00")
    stored = {"machine_id": "M1", "scope_type": "machine", "scope_value": "M1", "status": "active"}
    target_id = service.repo.create({**window("2026-10-14 08:00", "2026-10-14 10:00", detail="原说明"), **stored})
    # 两条有效停机历史上重叠（并发写入），只改说明时不受这条已有重叠影响。
    service.repo.create({**window("2026-10-14 09:00:00", "2026-10-14 11:00:00", "breakdown", "历史重叠"), **stored})
    conn.commit()
    target_ref = service.facts.ref_for_id(target_id)
    # 展示文本由微秒生成；同设备的停机按起止排序（夹具里还有一条 2026-09-12 已取消的旧记录）。
    assert [(row["start_time"], row["end_time"], row["status"]) for row in service.snapshot(machine.ref)["rows"]] == [
        ("2026-09-12 22:00:00", "2026-09-13 07:00:00", "cancelled"),
        ("2026-10-14 08:00:00", "2026-10-14 10:00:00", "active"), ("2026-10-14 09:00:00", "2026-10-14 11:00:00", "active")]
    unchanged_window = window("2026-10-14 08:00:00", "2026-10-14 10:00:00", detail="仅改说明", downtime_ref=target_ref)
    assert apply("update", unchanged_window).result == "committed"
    with pytest.raises(WorkbenchCommandRejected, match="重叠"):
        apply("update", window("2026-10-14 07:00", "2026-10-14 09:30", downtime_ref=target_ref))
    created = window("2026-10-14 11:00", "2026-10-14 12:00")
    assert apply("create", created).result == "committed"
    assert tuple(conn.execute("SELECT start_time, end_time, start_us, end_us FROM MachineDowntimes ORDER BY id DESC LIMIT 1").fetchone()) == (
        "2026-10-14 11:00:00", "2026-10-14 12:00:00", created["start_us"], created["end_us"])


@pytest.mark.parametrize(
    "kind,table,key,code,field",
    (
        ("machine", "Machines", "machine_id", "M-REP", "actual_machine_ref"),
        ("operator", "Operators", "operator_id", "O-REP", "actual_operator_ref"),
    ),
)
def test_active_production_report_revision_blocks_resource_deletion_until_voided(resource_conn, kind, table, key, code, field):
    from core.services.workbench.resource.bulk import WorkbenchResourceBulkService

    conn = resource_conn
    insert_row(conn, table, {key: code, "name": code})
    conn.commit()
    target = identity_for(conn, kind, code)
    assert target is not None

    op_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' LIMIT 1").fetchone()[0]
    task_row = conn.execute(
        "SELECT s.task_ref, h.plan_ref FROM Schedule s JOIN ScheduleHistory h ON h.version = s.version LIMIT 1"
    ).fetchone()
    assert task_row is not None
    report_ref = ("a" if kind == "machine" else "b") * 48
    revision_ref = ("c" if kind == "machine" else "d") * 48
    void_ref = ("e" if kind == "machine" else "f") * 48
    req_create = f"report-create-{kind}-0001"
    req_void = f"report-void-{kind}-0001"

    from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository

    report_repo = WorkbenchExecutionReportRepository(conn)
    report_values = {
        "actual_start": "2026-10-01T08:00:00",
        "actual_end": "2026-10-01T10:00:00",
        "completed_quantity": 1,
        "effective_processing_hours": 2.0,
        "actual_machine_ref": target.ref if field == "actual_machine_ref" else None,
        "actual_operator_ref": target.ref if field == "actual_operator_ref" else None,
        "remark": "",
    }
    with conn:
        conn.execute(
            """INSERT INTO WorkbenchCommandReceipts(request_key, receipt_ref, action, context_ref, input_json, outcome_json)
            VALUES (?, ?, 'execution.report_create', ?, '{}', '{}')""",
            (req_create, ("1" if kind == "machine" else "2") * 32, op_ref),
        )
        report_repo.append(
            {
                "report_ref": report_ref,
                "report_no": f"BG-{kind.upper()}-001",
                "operation_ref": op_ref,
                "recorded_against_task_ref": task_row["task_ref"],
                "recorded_against_plan_ref": task_row["plan_ref"],
                "source": "manual",
                "recorded_at": "2026-10-01T10:00:00",
                "revision_ref": revision_ref,
                "sequence": 1,
                "previous_revision_ref": None,
                "action": "create",
                "values": report_values,
                "reason": "initial",
                "local_operator": "admin",
                "declared_operator": "admin",
                "revision_at": "2026-10-01T10:00:00",
            },
            request_key=req_create,
        )

    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        run_resource(conn, kind, "delete", {}, code=code)
    assert exc_info.value.code == "constraint_conflict"

    reader = WorkbenchResourceQueryService(conn, kind)
    bulk_service = WorkbenchResourceBulkService(conn, kind, reader=reader)
    report_sql_queries = []
    revision_sql_queries = []

    def trace_sql(sql):
        if "FROM WorkbenchProductionReports" in sql:
            report_sql_queries.append(sql)
        if "WorkbenchProductionReportRevisions" in sql:
            revision_sql_queries.append(sql)

    conn.set_trace_callback(trace_sql)
    try:
        with reader.read_snapshot():
            preview = bulk_service.preview_delete([target.ref], scope=ResourcePageRequest(kind=kind)).as_dict()
    finally:
        conn.set_trace_callback(None)
    assert len(report_sql_queries) == 1
    assert revision_sql_queries == []
    assert preview["summary"]["rejected"] == 1
    assert preview["rows"][0]["errors"][0]["code"] == "constraint_conflict"

    with conn:
        conn.execute(
            """INSERT INTO WorkbenchCommandReceipts(request_key, receipt_ref, action, context_ref, input_json, outcome_json)
            VALUES (?, ?, 'execution.report_void', ?, '{}', '{}')""",
            (req_void, ("3" if kind == "machine" else "4") * 32, report_ref),
        )
        report_repo.append_void(
            {
                "void_fact_ref": void_ref,
                "report_ref": report_ref,
                "original_revision_ref": revision_ref,
                "reason": "voided for test",
                "local_operator": "admin",
                "declared_operator": "admin",
                "recorded_at": "2026-10-01T11:00:00",
            },
            request_key=req_void,
        )

    with reader.read_snapshot():
        preview_after_void = bulk_service.preview_delete([target.ref], scope=ResourcePageRequest(kind=kind)).as_dict()
    assert preview_after_void["summary"]["rejected"] == 0
    deleted = run_resource(conn, kind, "delete", {}, code=code)
    assert deleted["result"] == "committed"
    assert identity_for(conn, kind, code) is None


def test_unexpected_table_read_failure_logs_the_request_ref_shown_to_the_user(app_client, monkeypatch, caplog):
    """包装成 500 拒绝的未预期错误：日志记下的编号就是用户看到的「下方编号」，原始异常留在日志链里。"""
    import logging

    from web.routes.workbench import resource_table_queries

    def broken(query, token):
        raise RuntimeError("table reader broke")

    monkeypatch.setattr(resource_table_queries, "_resource_table_query", broken)
    with caplog.at_level(logging.ERROR):
        response = app_client.post(BASE + "machine/query", json={})
    assert response.status_code == 500, response.get_data(as_text=True)
    result = response.get_json()
    error = result["error"]
    assert result["committed"] is False
    assert (error["code"], error["message"]) == (
        "storage_failure", "列表没有读出来，数据没有任何改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。")
    record, = [item for item in caplog.records if item.getMessage().startswith("工作台请求失败")]
    assert record.getMessage() == "工作台请求失败 code=storage_failure request_ref=" + error["request_ref"]
    assert isinstance(record.exc_info[1], WorkbenchCommandRejected)
    assert isinstance(record.exc_info[1].__cause__, RuntimeError)


@pytest.mark.parametrize("method,path", [("GET", "bogus"), ("GET", "bogus/" + "a" * 48), ("POST", "bogus/create"),
                                         ("POST", "bogus/" + "a" * 48 + "/update")])
def test_unknown_resource_kind_is_rejected_by_the_entity_routes(app_client, method, path):
    body = {"request_key": "resource-unknown-kind-0001", "write_token": "token", "input": {}} if method == "POST" else None
    response = app_client.open(BASE + path, method=method, json=body)
    assert (response.status_code, response.get_json()["error"]["code"]) == (404, "entity_not_found"), response.get_json()


def test_resource_table_query_honors_explicit_32mib_json_budget_while_default_routes_keep_17mib(app_client):
    import io

    body_18mib = b'{"size":20' + (b" " * (18 * 1024 * 1024)) + b"}"
    ok_response = app_client.post(BASE + "machine/query", data=body_18mib, content_type="application/json")
    assert ok_response.status_code == 200, ok_response.get_data(as_text=True)
    assert ok_response.get_json()["data"]["page"]["size"] == 20

    body_over_32mib = b'{"size":20' + (b" " * (32 * 1024 * 1024)) + b"}"
    cl_response = app_client.post(BASE + "machine/query", data=body_over_32mib, content_type="application/json")
    assert cl_response.status_code == 413
    assert cl_response.get_json()["error"]["code"] == "capacity_exceeded"

    stream_response = app_client.post(
        BASE + "machine/query",
        input_stream=io.BytesIO(body_over_32mib),
        content_type="application/json",
        environ_overrides={"CONTENT_LENGTH": "", "wsgi.input_terminated": True},
    )
    assert stream_response.status_code == 413
    assert stream_response.get_json()["error"]["code"] == "capacity_exceeded"

    default_route_response = app_client.post(
        BASE + "machine/create",
        data=body_18mib,
        content_type="application/json",
    )
    assert default_route_response.status_code == 413
    assert default_route_response.get_json()["error"]["code"] == "invalid_input"


def _counts_from_details(conn, kind, codes):
    """计数的对照：逐条读详情里的对外状态与关系，不经 SQL 状态计数。"""
    from collections import Counter

    from core.models.workbench_resource_status import PUBLIC_STATUS_VALUES

    reader = WorkbenchResourceQueryService(conn, kind)
    with reader.read_snapshot() as scope:
        entities = [scope.detail(identity_for(conn, kind, code).ref).entity for code in codes]
    counts = dict.fromkeys(PUBLIC_STATUS_VALUES[kind], 0)
    counts.update(Counter(entity["status"] for entity in entities))
    counts["total"] = len(entities)
    if kind == "machine":
        counts["groups"] = len({entity["relationships"]["group_ref"] for entity in entities} - {None})
    elif kind == "operator":
        counts["skills"] = sum(len(entity["relationships"]["skill_refs"]) for entity in entities)
    return counts


def test_plain_non_op_type_pages_push_down_scalar_counts_without_facts_or_toolbar_keys(resource_conn, monkeypatch):
    conn = resource_conn
    group_a = create_catalog(conn, "machine_group")
    run_resource(conn, "machine_group", "create", {"business_code": "G2", "label": "G2", "fields": {}})
    group_b = identity_for(conn, "machine_group", "G2")
    assert group_b is not None
    insert_row(conn, "Machines", {"machine_id": "M-ACT", "name": "active lathe", "status": "active", "category": "turning"})
    insert_row(conn, "Machines", {"machine_id": "M-MAINT", "name": "maint lathe", "status": "maintain", "category": "turning"})
    insert_row(conn, "Machines", {"machine_id": "M-IDLE", "name": "idle mill", "status": "inactive", "category": "milling"})
    conn.executemany("INSERT INTO MachineOpTypes(machine_id, op_type_id) VALUES (?, 'OT1')", [("M-ACT",), ("M-MAINT",), ("M-IDLE",)])
    insert_row(conn, "Operators", {"operator_id": "O-LEAVE", "name": "leave operator", "status": "inactive"})
    insert_row(conn, "Operators", {"operator_id": "O-OFF", "name": "disabled operator", "status": "inactive"})
    insert_row(conn, "Suppliers", {"supplier_id": "S-ACT", "name": "active vendor", "status": "active", "default_days": 3.0})
    insert_row(conn, "Suppliers", {"supplier_id": "S-PEND", "name": "pending vendor", "status": "inactive", "default_days": 4.0})
    insert_row(conn, "Suppliers", {"supplier_id": "S-OFF", "name": "disabled vendor", "status": "inactive", "default_days": 5.0})
    conn.execute("UPDATE Machines SET category='turning' WHERE machine_id='M1'")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id, inactive_reason) VALUES ('O-LEAVE', 'leave'), ('O-OFF', 'disabled')")
    conn.execute("INSERT INTO WorkbenchSupplierProfiles(supplier_id, inactive_reason) VALUES ('S-PEND', 'pending_review'), ('S-OFF', 'disabled')")
    conn.execute("INSERT INTO OperatorSkill(operator_id, op_type_id) VALUES ('O-LEAVE', 'OT1')")
    conn.commit()
    run_resource(conn, "machine", "update", {"relationships": {"group_ref": group_a.ref}}, code="M1")
    run_resource(conn, "machine", "update", {"relationships": {"group_ref": group_b.ref}}, code="M-MAINT")

    cases = (
        ("machine", ResourcePageRequest("machine", size=1), {"active", "inactive", "maintain", "total", "groups"}),
        ("machine", ResourcePageRequest("machine", size=1, status="maintain"), {"active", "inactive", "maintain", "total", "groups"}),
        ("machine", ResourcePageRequest("machine", size=1, query="M-"), {"active", "inactive", "maintain", "total", "groups"}),
        ("operator", ResourcePageRequest("operator", size=1), {"active", "inactive", "leave", "total", "skills"}),
        ("operator", ResourcePageRequest("operator", size=1, status="leave"), {"active", "inactive", "leave", "total", "skills"}),
        ("operator", ResourcePageRequest("operator", size=1, query="O-"), {"active", "inactive", "leave", "total", "skills"}),
        ("supplier", ResourcePageRequest("supplier", size=1), {"active", "inactive", "pending_review", "total"}),
        ("supplier", ResourcePageRequest("supplier", size=1, status="pending_review"), {"active", "inactive", "pending_review", "total"}),
        ("supplier", ResourcePageRequest("supplier", size=1, query="vendor"), {"active", "inactive", "pending_review", "total"}),
    )

    unfiltered_counts = {}
    for kind, req, expected_keys in cases:
        expected_counts = _counts_from_details(conn, kind, WorkbenchResourceQueryRepository(conn).toolbar_keys(req))
        assert set(expected_counts) == expected_keys

        reader = WorkbenchResourceQueryService(conn, kind)
        with monkeypatch.context() as guarded:
            guarded.setattr(
                WorkbenchResourceMetricsRepository,
                "facts",
                lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("MetricsRepository.facts forbidden on plain page")),
            )
            guarded.setattr(
                WorkbenchResourceQueryRepository,
                "toolbar_keys",
                lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("QueryRepository.toolbar_keys forbidden on plain page")),
            )
            with reader.read_snapshot() as scope:
                records, page = scope.page(req)
        assert len(records) <= 1
        assert page["metrics"]["scope"] == "filtered" and page["metrics"]["issues"] == []
        assert page["metrics"]["counts"] == expected_counts and page["total"] == expected_counts["total"]
        if req == ResourcePageRequest(kind, size=1):
            unfiltered_counts[kind] = page["metrics"]["counts"]
    assert unfiltered_counts == {
        "machine": {
            "active": 1,
            "inactive": 1,
            "maintain": 2,
            "total": 4,
            "groups": 2,
        },
        "operator": {
            "active": 1,
            "inactive": 2,
            "leave": 1,
            "total": 4,
            "skills": 2,
        },
        "supplier": {
            "active": 1,
            "inactive": 2,
            "pending_review": 1,
            "total": 4,
        },
    }


# 编号顺序、英文代号顺序、中文显示字顺序都和业务序不同：两条路径只要有一条没按共享业务序排，就对不上。
@pytest.mark.parametrize("kind,rows,ascending,descending", [
    ("machine", (("M-A", "inactive"), ("M-B", "active"), ("M-C", "maintain"), ("M-D", "inactive")),
     ["M-B", "M-C", "M-A", "M-D"], ["M-A", "M-D", "M-C", "M-B"]),
    ("operator", (("O-A", "inactive"), ("O-B", "leave"), ("O-C", "active"), ("O-D", "inactive")),
     ["O-C", "O-B", "O-A", "O-D"], ["O-A", "O-D", "O-B", "O-C"]),
    ("supplier", (("S-A", "pending_review"), ("S-B", "inactive"), ("S-C", "active"), ("S-D", "inactive")),
     ["S-C", "S-A", "S-B", "S-D"], ["S-B", "S-D", "S-A", "S-C"]),
    ("material", (("MAT-A", "inactive"), ("MAT-B", "active"), ("MAT-C", "inactive"), ("MAT-D", "active")),
     ["MAT-B", "MAT-D", "MAT-A", "MAT-C"], ["MAT-A", "MAT-C", "MAT-B", "MAT-D"]),
])
def test_status_sort_is_one_business_order_for_plain_pages_and_column_filters(app_client, kind, rows, ascending, descending):
    for code, status in rows:
        _create(app_client, kind, code, fields={"status": status, **({"default_days": 2} if kind == "supplier" else {})})
    for direction, expected in (("asc", ascending), ("desc", descending)):
        plain = _list(app_client, kind, sort="status", direction=direction)["data"]["entities"]
        filtered = app_client.post(BASE + kind + "/query", json={
            "sort": "status", "direction": direction,
            "column_filters": {"business_code": {"mode": "exclude", "values": ["不存在的编号"]}},
        })
        assert filtered.status_code == 200, filtered.get_data(as_text=True)
        assert [entity["business_code"] for entity in plain] == expected
        assert [entity["business_code"] for entity in filtered.get_json()["data"]["entities"]] == expected


def _query_pages(client, kind, body, pages):
    """按 /query 逐页读（第 2 页起带第 1 页的快照），把各页编号接起来。"""
    codes, token = [], None
    for number in range(1, pages + 1):
        response = client.post(BASE + kind + "/query", json=dict(body, page=number, **({"snapshot_ref": token} if token else {})))
        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        token = payload["meta"]["snapshot_ref"]
        codes.extend(entity["business_code"] for entity in payload["data"]["entities"])
    return codes


def _create_rows(client, kind, rows):
    for number, (code, fields) in enumerate(rows, 1):
        token = _list(client, kind)["data"]["create_context"]["write_token"]
        response = client.post(BASE + kind + "/create", json={
            "request_key": f"resource-table-{kind}-{number:02d}", "write_token": token,
            "input": {"business_code": code, "label": "Name-" + code, "fields": fields}})
        assert response.status_code == 200, response.get_data(as_text=True)


# 只差连续空白或 Unicode 写法的编号与名称，归一化后同键：普通分页（SQL）和列筛选（格子索引）同序，平手按原始编号升序。
@pytest.mark.parametrize("kind", ["machine", "supplier", "material"])
@pytest.mark.parametrize("sort", ["business_code", "label"])
def test_normalized_text_ties_page_in_one_order_for_plain_pages_and_column_filters(app_client, kind, sort):
    fields = {"default_days": 2} if kind == "supplier" else {}
    _create_rows(app_client, kind, [(code, fields) for code in ("K  2", "K 1", "K  1", "K\u00e9", "Ke\u0301")])
    expected = {"asc": ["K  1", "K 1", "K  2", "Ke\u0301", "K\u00e9"],
                "desc": ["Ke\u0301", "K\u00e9", "K  2", "K  1", "K 1"]}
    for direction in ("asc", "desc"):
        body = {"sort": sort, "direction": direction, "size": 2}
        filtered = dict(body, column_filters={"business_code": {"mode": "exclude", "values": ["不存在的编号"]}})
        assert _query_pages(app_client, kind, body, 3) == expected[direction]
        assert _query_pages(app_client, kind, filtered, 3) == expected[direction]


# 数字格排序只看数值，筛选身份带单位：240 kg 与 240 件同序、不同值；计数跟工具栏范围加列筛选走，不跟当前页走；
# 筛选值只按工具栏范围列出，不受本列或别的列筛选影响。
def test_number_cells_sort_by_value_but_filter_and_count_by_unit(app_client):
    _create_rows(app_client, "material", [("U-1", {"stock_qty": 240, "unit": "kg"}), ("U-2", {"stock_qty": 240, "unit": "件"}),
                                          ("U-3", {"stock_qty": 7, "unit": "kg"}), ("U-4", {"stock_qty": 0, "unit": "kg", "status": "inactive"})])
    kg240 = canonical_json({"type": "number", "value": "240", "unit": "kg"})
    assert _query_pages(app_client, "material", {"sort": "stock_qty", "direction": "asc", "size": 1}, 4) == ["U-4", "U-3", "U-1", "U-2"]
    for mode, codes, counts in (
        ("include", ["U-1"], {"total": 1, "active": 1, "inactive": 0, "stock_unknown": 0}),
        ("exclude", ["U-4", "U-3", "U-2"], {"total": 3, "active": 2, "inactive": 1, "stock_unknown": 0}),
    ):
        body = {"sort": "stock_qty", "direction": "asc", "size": 1, "column_filters": {"stock_qty": {"mode": mode, "values": [kg240]}}}
        response = app_client.post(BASE + "material/query", json=dict(body, page=1))
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()["data"]["metrics"]["counts"] == counts
        assert _query_pages(app_client, "material", body, len(codes)) == codes
    plain = app_client.post(BASE + "material/query", json={"sort": "stock_qty", "size": 1, "page": 1}).get_json()["data"]
    assert plain["metrics"]["counts"] == {"total": 4, "active": 3, "inactive": 1, "stock_unknown": 0}
    assert plain["page"]["total"] == 4
    facets = app_client.post(BASE + "material/facets", json={
        "scope": {"query": "", "column_filters": {"stock_qty": {"mode": "include", "values": [kg240]}}}, "column": "stock_qty"})
    assert facets.status_code == 200, facets.get_data(as_text=True)
    data = facets.get_json()["data"]
    assert data["row_count"] == 4
    assert [(option["label"], option["count"]) for option in data["options"]] == [
        ("0 kg", 1), ("7 kg", 1), ("240 kg", 1), ("240 件", 1)]
