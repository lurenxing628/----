"""Real Flask resource creation, update, stale-context rejection, replay and deletion."""
import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.resource.metrics import ResourceMetricFactsError, WorkbenchResourceMetricsService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.table_states import resource_table_states
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
                  "pattern": [{"day_offset": 0, "is_rest": False, "shift_start": "08:00", "shift_end": "16:00"}]}
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


def test_plain_resource_pages_share_batch_states_and_read_dependencies_once(resource_conn, monkeypatch):
    conn = resource_conn
    insert_row(conn, "Machines", {"machine_id": "M2", "name": "second machine", "op_type_id": "OT1"})
    insert_row(conn, "Machines", {"machine_id": "M3", "name": "Ä"})
    insert_row(conn, "Operators", {"operator_id": "O2", "name": "second operator"})
    insert_row(conn, "Suppliers", {"supplier_id": "S2", "name": "second supplier", "op_type_id": "EXT", "default_days": None})
    conn.execute("UPDATE Suppliers SET op_type_id='EXT' WHERE supplier_id='S1'")
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

    counts, relations, type_counts, scopes = [], [], [], []
    assigned_counts, page_relations = WorkbenchResourceTableRepository.assigned_counts, WorkbenchResourceTableRepository.page_relations
    op_type_dependencies, scope_state = WorkbenchResourceMetricsRepository.op_type_dependencies, WorkbenchResourceQueryRepository.scope_state

    def read_counts(repo, kind, codes):
        counts.append((kind, tuple(codes)))
        return assigned_counts(repo, kind, codes)

    def read_relations(repo, kind, codes):
        relations.append((kind, tuple(codes)))
        return page_relations(repo, kind, codes)

    def read_type_counts(repo, codes):
        type_counts.append(tuple(codes))
        return op_type_dependencies(repo, codes)

    def read_scope(repo, kind, **kwargs):
        scopes.append(kind)
        return scope_state(repo, kind, **kwargs)

    for kind in ("machine", "operator", "supplier", "op_type", "machine_group", "shift_profile"):
        reader = WorkbenchResourceQueryService(conn, kind)
        query = ResourcePageRequest(kind, size=20, direction="desc")
        counts.clear()
        relations.clear()
        type_counts.clear()
        scopes.clear()
        with monkeypatch.context() as scoped:
            scoped.setattr(WorkbenchResourceTableRepository, "assigned_counts", read_counts)
            scoped.setattr(WorkbenchResourceMetricsRepository, "op_type_dependencies", read_type_counts)
            scoped.setattr(WorkbenchResourceQueryRepository, "scope_state", read_scope)
            with reader.read_snapshot() as fingerprint:
                rows, total = reader.repo.page(query)
                expected = [reader.detail(row["ref"]) for row in rows]
                scoped.setattr(WorkbenchResourceTableRepository, "page_relations", read_relations)
                records, page = reader.page(query)
                codes = tuple(row["business_code"] for row in rows)
                assert records == expected
                assert page["total"] == total
                assert page["number"] == query.number and page["size"] == query.size
                assert page["sort"] == [{"field": query.sort, "direction": query.direction}]
                assert counts == type_counts == [] and scopes == [kind]
                assert relations == ([('supplier', codes)] if kind == "supplier" else [])
                assert reader.state_fingerprint() == fingerprint and scopes == [kind]
                if kind != "op_type":
                    states = resource_table_states(reader._table_reader(), kind, codes)
                    assert {record.identity.entity_key: record.state for record in records} == states
                if kind == "machine":
                    advanced, _ = reader.page(ResourcePageRequest(kind, query="车床alpha", sort="group_ref", direction="desc"))
                    assert [record.identity.entity_key for record in advanced] == ["M1", "M2"]
                    matched, _ = reader.page(ResourcePageRequest(kind, query="车床ALPHA", sort="label", direction="desc"))
                    assert matched == advanced
                    unmatched, _ = reader.page(ResourcePageRequest(kind, query="ä"))
                    assert unmatched == [] and counts == [] and scopes == [kind]
                if kind == "supplier":
                    ascending, _ = reader.page(ResourcePageRequest(kind, sort="default_days"))
                    descending, _ = reader.page(ResourcePageRequest(kind, sort="default_days", direction="desc"))
                    assert [record.identity.entity_key for record in ascending] == ["S2", "S1"]
                    assert [record.identity.entity_key for record in descending] == ["S1", "S2"]
                if kind in ("operator", "op_type"):
                    counts.clear()
                    relations.clear()
                    type_counts.clear()
                    with reader.read_snapshot(capture_fingerprint=False) as inner_fingerprint:
                        assert inner_fingerprint is None
                        inner_records, inner_page = reader.page(query)
                        assert inner_records == expected and inner_page == page
                        assert counts == ([(kind, codes)] if kind == "operator" else [])
                        assert type_counts == ([codes] if kind == "op_type" else [])
                        assert relations == ([('shift_profile', (shift.entity_key,))] if kind == "operator" else [])
                        assert scopes == [kind]
                    counts.clear()
                    relations.clear()
                    type_counts.clear()
                    restored, restored_page = reader.page(query)
                    assert restored == expected and restored_page == page
                    assert counts == relations == type_counts == [] and scopes == [kind]

    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    try:
        conn.backup(memory)
        insert_row(memory, "OpTypes", {"op_type_id": "", "name": "unused blank code", "category": "internal"})
        memory.commit()
        for kind, column in (("machine", "group_ref"), ("operator", "skill_refs")):
            reader = WorkbenchResourceQueryService(memory, kind)
            query = ResourcePageRequest(kind, size=20)
            with reader.read_snapshot():
                rows, total = reader.repo.page(query)
                expected = [reader.detail(row["ref"]) for row in rows]
                records, page = reader.page(query)
                assert records == expected and page["total"] == total
                assert "counts" in page["metrics"]
            with pytest.raises(ResourceMetricFactsError):
                with reader.read_snapshot():
                    reader.page(ResourcePageRequest(kind, sort=column))
        memory.execute("DELETE FROM OpTypes WHERE op_type_id='OT1'")
        memory.commit()
        for kind in ("machine", "operator"):
            reader = WorkbenchResourceQueryService(memory, kind)
            query = ResourcePageRequest(kind, size=20)
            with reader.read_snapshot():
                rows, _ = reader.repo.page(query)
                with pytest.raises(WorkbenchCommandRejected) as original:
                    [reader.detail(row["ref"]) for row in rows]
                with pytest.raises(WorkbenchCommandRejected) as batched:
                    reader.page(query)
                assert (batched.value.code, batched.value.status) == (original.value.code, original.value.status)
                assert batched.value.code == "storage_failure" and batched.value.status == 500
        memory.execute("DELETE FROM OpTypes WHERE op_type_id=''")
        insert_row(memory, "OpTypes", {"op_type_id": "BOTH1", "name": "both work type", "category": "both"})
        memory.commit()
        both_metrics = WorkbenchResourceMetricsService(memory).metrics("op_type", ["BOTH1"])
        assert [issue["code"] for issue in both_metrics["issues"]] == ["resource_availability_unavailable"]
        assert both_metrics["issues"][0]["unavailable_fields"] == ["linked_machines", "available_operators", "without_machines"]
    finally:
        memory.close()


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
    content = file_bytes([(code, 'prepared-first'), (other, 'prepared-second')], headers=('business_code', 'label'))
    service = WorkbenchResourceFileService(conn, kind)
    scope = {'category': 'internal'} if kind == 'op_type' else {}
    preview = service.preview_import(content, file_format='csv', scope=scope)
    assert preview.as_dict()['summary']['rejected'] == 0, preview.as_dict()
    fact_reads, reference_reads = [], []
    original_facts = WorkbenchResourceMetricsRepository.facts
    original_references = WorkbenchResourceFileRepository.references_many

    def captured(repo, names):
        fact_reads.extend(names)
        return original_facts(repo, names)

    def references(repo, selected_kind, codes, *, report_revisions=None):
        reference_reads.append((selected_kind, tuple(codes)))
        return original_references(repo, selected_kind, codes, report_revisions=report_revisions)

    monkeypatch.setattr(WorkbenchResourceMetricsRepository, 'facts', captured)
    monkeypatch.setattr(WorkbenchResourceFileRepository, 'references_many', references)
    result = confirm(conn, kind, preview, content)
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
        rejected = service.preview_delete(['f' * 48], scope={}).as_dict()
    assert rejected['summary']['rejected'] == 1 and rejected['rows'][0]['entity_ref'] == 'f' * 48
    refs = [ref(conn, 'machine', code) for code in ('DELETE-ONE', 'DELETE-TWO')]
    with service.reader.read_snapshot():
        preview = service.preview_delete(refs, scope={})
    assert preview.as_dict()['summary']['rejected'] == 0

    result = confirm(conn, 'machine', preview)
    assert result['result'] == 'committed' and result['data']['deleted_count'] == 2
    assert conn.execute("SELECT COUNT(*) FROM Machines WHERE machine_id IN ('DELETE-ONE','DELETE-TWO')").fetchone()[0] == 0


def test_downtime_create_ignores_reversed_active_legacy_interval(resource_conn):
    from core.services.workbench.resource.downtimes import WorkbenchDowntimeService

    conn = resource_conn
    service = WorkbenchDowntimeService(conn)
    machine = identity_for(conn, "machine", "M1")
    assert machine is not None
    service.repo.create({
        "machine_id": "M1", "scope_type": "machine", "scope_value": "M1",
        "start_time": "2026-10-01 16:00", "end_time": "2026-10-01 15:00",
        "reason_code": "maintenance", "reason_detail": None, "status": "active",
    })
    state = service.snapshot(machine.ref)
    with conn:
        outcome = service.apply_normalized(machine.ref, "create", {
            "start_time": "2026-10-01 14:00", "end_time": "2026-10-01 17:00",
            "reason_code": "maintenance", "reason_detail": None,
        }, state)
    assert outcome.result == "committed"

    target_id = service.repo.create({
        "machine_id": "M1", "scope_type": "machine", "scope_value": "M1",
        "start_time": "2026-10-14 08:00", "end_time": "2026-10-14 10:00",
        "reason_code": "maintenance", "reason_detail": "原说明", "status": "active",
    })
    service.repo.create({
        "machine_id": "M1", "scope_type": "machine", "scope_value": "M1",
        "start_time": "2026-10-14 09:00:00", "end_time": "2026-10-14 11:00:00",
        "reason_code": "fault", "reason_detail": "历史重叠", "status": "active",
    })
    target_ref = service.facts.ref_for_id(target_id)
    overlap_state = service.snapshot(machine.ref)
    with conn:
        updated = service.apply_normalized(machine.ref, "update", {
            "downtime_ref": target_ref,
            "start_time": "2026-10-14 08:00:00", "end_time": "2026-10-14 10:00:00",
            "reason_code": "maintenance", "reason_detail": "仅改说明",
        }, overlap_state)
    assert updated.result == "committed"


@pytest.mark.parametrize(
    "kind,table,key,code,field",
    (
        ("machine", "Machines", "machine_id", "M-REP", "actual_machine_ref"),
        ("operator", "Operators", "operator_id", "O-REP", "actual_operator_ref"),
    ),
)
def test_active_production_report_revision_blocks_resource_deletion_until_voided(resource_conn, kind, table, key, code, field):
    import json

    from core.services.workbench.resource.bulk import WorkbenchResourceBulkService

    conn = resource_conn
    insert_row(conn, table, {key: code, "name": code})
    conn.execute("INSERT INTO ScheduleHistory(version, schedule_time, strategy) VALUES (7, '2026-09-09 08:00:00', 'greedy')")
    conn.commit()
    target = identity_for(conn, kind, code)
    assert target is not None

    op_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' LIMIT 1").fetchone()[0]
    task_row = conn.execute("SELECT ref, plan_ref FROM WorkbenchTaskRefs LIMIT 1").fetchone()
    assert task_row is not None
    report_ref = ("a" if kind == "machine" else "b") * 48
    revision_ref = ("c" if kind == "machine" else "d") * 48
    void_ref = ("e" if kind == "machine" else "f") * 48
    req_create = f"report-create-{kind}-0001"
    req_void = f"report-void-{kind}-0001"

    with conn:
        conn.execute(
            """INSERT INTO WorkbenchCommandReceipts(request_key, receipt_ref, action, context_ref, input_hash, outcome_json)
            VALUES (?, ?, 'execution.report_create', ?, ?, '{}')""",
            (req_create, ("1" if kind == "machine" else "2") * 32, op_ref, "0" * 64),
        )
        conn.execute(
            """INSERT INTO WorkbenchProductionReports
            (report_ref, report_no, operation_ref, recorded_against_task_ref, recorded_against_plan_ref, source, recorded_at)
            VALUES (?, ?, ?, ?, ?, 'manual', '2026-10-01T10:00:00')""",
            (report_ref, f"BG-{kind.upper()}-001", op_ref, task_row["ref"], task_row["plan_ref"]),
        )
        conn.execute(
            """INSERT INTO WorkbenchProductionReportRevisions
            (revision_ref, report_ref, sequence, previous_revision_ref, action, values_json, reason,
             local_operator, declared_operator, recorded_at, request_key)
            VALUES (?, ?, 1, NULL, 'create', ?, 'initial', 'admin', 'admin', '2026-10-01T10:00:00', ?)""",
            (revision_ref, report_ref, json.dumps({field: target.ref}), req_create),
        )

    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        run_resource(conn, kind, "delete", {}, code=code)
    assert exc_info.value.code == "constraint_conflict"

    reader = WorkbenchResourceQueryService(conn, kind)
    bulk_service = WorkbenchResourceBulkService(conn, kind, reader=reader)
    report_sql_queries = []
    conn.set_trace_callback(
        lambda sql: report_sql_queries.append(sql) if "FROM WorkbenchProductionReportRevisions" in sql else None
    )
    try:
        with reader.read_snapshot():
            preview = bulk_service.preview_delete([target.ref], scope={}).as_dict()
    finally:
        conn.set_trace_callback(None)
    assert len(report_sql_queries) == 1
    assert preview["summary"]["rejected"] == 1
    assert preview["rows"][0]["errors"][0]["code"] == "constraint_conflict"

    with conn:
        conn.execute(
            """INSERT INTO WorkbenchCommandReceipts(request_key, receipt_ref, action, context_ref, input_hash, outcome_json)
            VALUES (?, ?, 'execution.report_void', ?, ?, '{}')""",
            (req_void, ("3" if kind == "machine" else "4") * 32, report_ref, "0" * 64),
        )
        conn.execute(
            """INSERT INTO WorkbenchProductionReportVoids
            (void_fact_ref, report_ref, original_revision_ref, reason, local_operator, declared_operator, recorded_at, request_key)
            VALUES (?, ?, ?, 'voided for test', 'admin', 'admin', '2026-10-01T11:00:00', ?)""",
            (void_ref, report_ref, revision_ref, req_void),
        )

    with reader.read_snapshot():
        preview_after_void = bulk_service.preview_delete([target.ref], scope={}).as_dict()
    assert preview_after_void["summary"]["rejected"] == 0
    deleted = run_resource(conn, kind, "delete", {}, code=code)
    assert deleted["result"] == "committed"
    assert identity_for(conn, kind, code) is None


_UNREADABLE_TABLE_QUERY = "查询条件读不出来，当前列表没有变化。请点「清除筛选」后重新选择。"


@pytest.mark.parametrize("suffix", ("query", "facets"))
@pytest.mark.parametrize("raw,message", [
    ('{"query": "a", "query": "b"}', "查询条件里有重复项，当前列表没有变化。请刷新页面后重新选择。"),
    ('{"query": "", "page": NaN}', _UNREADABLE_TABLE_QUERY),
    ('{"query": "", "size": -Infinity}', _UNREADABLE_TABLE_QUERY),
    ('{"query": "", "size": 1e999}', _UNREADABLE_TABLE_QUERY),
    ('{"query": ', _UNREADABLE_TABLE_QUERY),
    ('[]', "查询条件不完整，当前列表没有变化。请刷新页面后重新选择。"),
], ids=("duplicate", "nan", "infinity", "overflow", "syntax", "not_object"))
def test_table_query_body_rejects_duplicate_keys_and_non_finite_numbers(app_client, suffix, raw, message):
    response = app_client.post(BASE + "machine/" + suffix, data=raw, content_type="application/json")
    assert response.status_code == 400, response.get_data(as_text=True)
    error = response.get_json()["error"]
    assert (error["code"], error["message"]) == ("invalid_input", message)


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
