"""Real Flask resource creation, update, stale-context rejection, replay and deletion."""
import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.resource.metrics import ResourceMetricFactsError
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
    for code in ("M1", "M2"):
        run_resource(conn, "machine", "update", {"relationships": {"group_ref": group.ref}}, code=code)
    for code in ("O1", "O2"):
        run_resource(conn, "operator", "update", {"relationships": {
            "shift_profile_ref": shift.ref, "skill_refs": [identity_for(conn, "op_type").ref],
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

    def read_scope(repo, kind):
        scopes.append(kind)
        return scope_state(repo, kind)

    for kind in ("machine", "operator", "supplier", "op_type", "machine_group", "shift_profile"):
        reader = WorkbenchResourceQueryService(conn, kind)
        query = ResourcePageRequest(kind, size=20, direction="desc")
        counts.clear()
        relations.clear()
        type_counts.clear()
        scopes.clear()
        with monkeypatch.context() as scoped:
            scoped.setattr(WorkbenchResourceTableRepository, "assigned_counts", read_counts)
            scoped.setattr(WorkbenchResourceTableRepository, "page_relations", read_relations)
            scoped.setattr(WorkbenchResourceMetricsRepository, "op_type_dependencies", read_type_counts)
            scoped.setattr(WorkbenchResourceQueryRepository, "scope_state", read_scope)
            with reader.read_snapshot() as fingerprint:
                rows, total = reader.repo.page(query)
                expected = [reader.detail(row["ref"]) for row in rows]
                expected_metrics = reader.metrics(query)
                records, page = reader.page(query)
                codes = tuple(row["business_code"] for row in rows)
                assert records == expected
                assert page["total"] == total and page["metrics"] == expected_metrics
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
                assert page["metrics"] == reader.metrics(query)
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
    from data.repositories.workbench_resource_state_repo import WorkbenchResourceStateRepository
    from data.repositories.workbench_supplier_state_repo import WorkbenchSupplierStateRepository
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

    def references(repo, selected_kind, codes):
        reference_reads.append((selected_kind, tuple(codes)))
        return original_references(repo, selected_kind, codes)

    def old_row_read(*_args, **_kwargs):
        raise AssertionError('Current resource rows and relations were already captured.')

    monkeypatch.setattr(WorkbenchResourceMetricsRepository, 'facts', captured)
    monkeypatch.setattr(WorkbenchResourceFileRepository, 'references_many', references)
    for name in ('get_raw', 'get_profile', 'skills', 'machine_capabilities'):
        monkeypatch.setattr(WorkbenchResourceStateRepository, name, old_row_read)
    monkeypatch.setattr(WorkbenchSupplierStateRepository, 'get_by_ref', old_row_read)
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


def test_resource_bulk_delete_prepares_one_current_set_and_keeps_rejected_selection_rows(resource_conn, monkeypatch):
    from core.services.workbench.resource.bulk import WorkbenchResourceBulkService
    from core.services.workbench.resource.entities import WorkbenchResourceService
    from data.repositories.workbench_resource_state_repo import WorkbenchResourceStateRepository
    from tests.workbench.resource_file_support import confirm, ref

    conn = resource_conn
    for code in ('DELETE-ONE', 'DELETE-TWO'):
        insert_row(conn, 'Machines', {'machine_id': code, 'name': code})
    conn.commit()
    service = WorkbenchResourceBulkService(conn, 'machine')
    rejected = service.preview_delete(['f' * 48], scope={}).as_dict()
    assert rejected['summary']['rejected'] == 1 and rejected['rows'][0]['entity_ref'] == 'f' * 48
    refs = [ref(conn, 'machine', code) for code in ('DELETE-ONE', 'DELETE-TWO')]
    preview = service.preview_delete(refs, scope={})
    assert preview.as_dict()['summary']['rejected'] == 0

    def old_row_read(*_args, **_kwargs):
        raise AssertionError('Bulk apply must use its prepared current set.')

    monkeypatch.setattr(WorkbenchResourceService, 'apply', old_row_read)
    monkeypatch.setattr(WorkbenchResourceStateRepository, 'get_raw', old_row_read)
    result = confirm(conn, 'machine', preview)
    assert result['result'] == 'committed' and result['data']['deleted_count'] == 2
    assert conn.execute("SELECT COUNT(*) FROM Machines WHERE machine_id IN ('DELETE-ONE','DELETE-TWO')").fetchone()[0] == 0
