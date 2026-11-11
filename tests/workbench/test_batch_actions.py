"""Batch atomic previews, template copies and actual resource constraints."""

from tests.workbench.batch_support import (
    BASE,
    assert_error,
    batch_database,
    body,
    detail,
    list_data,
    post,
    ref_for,
    state,
)

_batch_fixture = batch_database


def preview(client, action="update", refs=None, patch=None):
    response = client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
        "input": {"action": action, "refs": refs or [ref_for(client)], "patch": patch or {}}})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def confirm(client, data, path="/bulk-confirm", key="batch-preview-confirm-001"):
    return client.post(BASE + path, json=body(data["write_context"], {"preview_ref": data["preview_ref"]}, key))


def test_bulk_modify_copy_delete_actual_records_atomic(batch_client):
    client = batch_client
    before = state(client)
    p = preview(client, patch={"priority": "urgent", "remark": "bulk"})
    assert state(client) == before and p["count"] == 1 and p["commit_policy"] == "atomic"
    assert confirm(client, p).status_code == 200
    assert detail(client)["data"]["fields"]["remark"] == "bulk"
    p = preview(client, "copy")
    assert p["rows"][0]["after"]["business_code"] == "FREE-002"
    response = confirm(client, p, key="batch-copy-confirm-0001")
    assert response.status_code == 200, response.get_json()
    created = response.get_json()["data"]["items"][0]["entity_ref"]
    row = detail(client, created)["data"]
    assert row["status"] == "pending" and not row["all_operations_complete"]
    assert row["operations"][0]["setup_hours"] is None and row["operations"][0]["unit_hours"] == 0
    assert row["operations"][0]["ref"] != detail(client)["data"]["operations"][0]["ref"]
    p = preview(client, "delete", [created])
    assert confirm(client, p, key="batch-delete-confirm-01").status_code == 200
    assert_error(client.get(BASE + "/" + created), "entity_not_found")


def test_preview_drift_and_injected_second_write_rollback(batch_client, monkeypatch):
    from data.repositories.batch_repo import BatchRepository

    client = batch_client
    p = preview(client, patch={"remark": "x"})
    client.batch_conn.execute("UPDATE Parts SET remark='concurrent'")
    client.batch_conn.commit()
    before = state(client)
    assert_error(confirm(client, p), "stale_write")
    assert state(client) == before
    p = preview(client, refs=[ref_for(client), ref_for(client, key="B1")], patch={"remark": "x"})
    original, calls = BatchRepository.update, []

    def fail_second(svc, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("fixture second-row failure")
        return original(svc, *args, **kwargs)

    monkeypatch.setattr(BatchRepository, "update", fail_second)
    before = state(client)
    assert confirm(client, p).get_json()["committed"] == "unknown"
    assert len(calls) == 2 and state(client) == before

    # 到料日也会改变有效齐套筛选；午夜前后的 60 秒仍在 900 秒口令有效期内。
    from datetime import date, datetime

    from core.services.workbench.batch import facts as batch_facts
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService
    from web import public_token_registry
    from web.routes.workbench import read_context

    monkeypatch.setattr(BatchRepository, "update", original)
    clock = [datetime(2026, 10, 7, 23, 59, 30)]

    class LocalDate(date):
        @classmethod
        def today(cls):
            return clock[0].date()

    class LocalDateTime(datetime):
        @classmethod
        def now(cls):
            return cls.fromtimestamp(clock[0].timestamp())

    monkeypatch.setattr(batch_facts, "date", LocalDate)
    monkeypatch.setattr(read_context, "datetime", LocalDateTime)
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0].timestamp())
    client.batch_conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    client.batch_conn.commit()
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": None, "material_ref": ref_for(client, "material", "MAT1"), "required_quantity": 10,
        "available_quantity": 0, "arrivals": [{"arrival_date": "2026-10-08", "quantity": 10}]}]},
        key="batch-midnight-material-001")
    assert response.status_code == 200, response.get_json()
    listed = list_data(client, query="FREE-001", ready_status="no")
    scope = {"query": "FREE-001", "ready_status": "no", "snapshot_ref": listed["meta"]["snapshot_ref"]}
    assert listed["data"]["page"]["total"] == 1 and listed["meta"]["as_of"] == "2026-10-07T23:59:30"
    exported = client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": scope}).get_json()
    assert exported["data"]["count"] == 1
    before = state(client)
    changes = client.batch_conn.total_changes
    reader = WorkbenchBatchQueryService(client.batch_conn)
    target_ref = ref_for(client)
    with reader.facts.detached_read_snapshot(mode="single_template", target_ref=target_ref) as old_scope:
        old_fingerprint = old_scope.fingerprint()
        old = reader.detail(old_scope, target_ref)
        clock[0] = datetime(2026, 10, 8, 0, 0, 30)
        pinned = reader.detail(old_scope, target_ref)
        assert old_scope.fingerprint() == old_fingerprint
        assert old["display_ready_status"] == pinned["display_ready_status"] == pinned["materials"]["display_status"] == "no"
    with reader.facts.detached_read_snapshot(mode="single_template", target_ref=target_ref) as new_scope:
        new_fingerprint = new_scope.fingerprint()
        current = reader.detail(new_scope, target_ref)
        assert new_fingerprint != old_fingerprint
        assert current["display_ready_status"] == current["materials"]["display_status"] == "yes"
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
    stale_table_reads = []
    with monkeypatch.context() as stale_patch:
        stale_patch.setattr(WorkbenchBatchFactsRepository, "whole_tables", lambda _repo: stale_table_reads.append("whole"))
        stale_patch.setattr(WorkbenchBatchFactsRepository, "single_batch_tables", lambda *_a, **_kw: stale_table_reads.append("single"))
        stale_patch.setattr(WorkbenchBatchFactsRepository, "closure_batch_tables", lambda *_a, **_kw: stale_table_reads.append("closure"))
        stale_patch.setattr(WorkbenchBatchFactsRepository, "filtered_batch_tables", lambda *_a, **_kw: stale_table_reads.append("filtered"))
        assert_error(client.get(BASE, query_string=scope), "snapshot_stale", 409)
        assert_error(client.post(BASE + "/selection", json=scope), "snapshot_stale", 409)
        assert_error(client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": scope}), "snapshot_stale", 409)
        assert_error(client.get(BASE + "/export", query_string={"export_ref": exported["data"]["export_ref"]}), "snapshot_stale", 409)
    assert stale_table_reads == []
    fresh = list_data(client, query="FREE-001", ready_status="yes")
    assert fresh["data"]["page"]["total"] == 1 and fresh["meta"]["as_of"] == "2026-10-08T00:00:30"
    assert state(client) == before and client.batch_conn.total_changes == changes


def test_command_facts_reuse_without_version_probe_and_reload_after_write(batch_client, record_property):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.batch.facts import BatchFacts

    conn = batch_client.batch_conn
    reader, trace = BatchFacts(conn), []
    ref = ref_for(batch_client)
    conn.set_trace_callback(trace.append)
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            with reader.command_snapshot() as scope:
                first, second = scope.load(), scope.load()
                assert first["Batches"] is second["Batches"]
                assert scope.batch(ref)["remark"] == "keep-hidden"
                old_index = scope.lookups["Batches"]
                conn.execute("UPDATE Batches SET remark='command-current' WHERE batch_id='FREE-001'")
                changed = scope.load()
                assert changed["Batches"] is not first["Batches"]
                assert scope.batch(ref)["remark"] == "command-current"
                assert scope.lookups["Batches"] is not old_index
            assert not hasattr(reader, "active_scope") and scope.current_facts() is None and not scope.lookups
    finally:
        conn.set_trace_callback(None)
    probes = sum("PRAGMA DATA_VERSION" in sql.upper() for sql in trace)
    record_property("batch_command_data_version", probes)
    assert probes == 0


def test_plan_counts_protect_batches_without_binding_plan_contents(batch_client):
    import pytest

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.batch.facts import BatchFacts, index_relations, require_unreferenced
    from core.services.workbench.batch.projection import BatchProjection
    from core.services.workbench.batch.scope import BatchFactScope
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository

    conn = batch_client.batch_conn
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0]
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,'2026-09-09 08:00:00','2026-09-09 09:00:00',6)", (op_id,))
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,'2026-09-09 09:00:00','2026-09-09 10:00:00',7)", (op_id,))
    conn.commit()
    reader, trace = BatchFacts(conn), []
    conn.set_trace_callback(trace.append)
    try:
        facts = BatchFactScope(reader).load()
    finally:
        conn.set_trace_callback(None)
    assert facts['plan_reference_counts'][op_id] == 2
    assert not {'Schedule', 'WorkbenchPlanSourceRefs'} & facts.keys()
    batch = next(row for row in facts['Batches'] if row['batch_id'] == 'FREE-001')
    relations = index_relations(facts)['FREE-001']
    entity = BatchProjection(facts).entity(batch)
    assert relations['protected'] and entity['relationships']['plan_reference_count'] == 2
    with pytest.raises(WorkbenchCommandRejected, match='已经进了计划'):
        require_unreferenced(relations)
    assert not any('SELECT * FROM "Schedule"' in sql or
                   'SELECT * FROM WorkbenchPlanSourceRefs' in sql for sql in trace)
    before = BatchFactScope(reader).fingerprint()
    conn.execute("UPDATE Schedule SET start_time='2026-09-09 08:30:00' WHERE version=6 AND op_id=?", (op_id,))
    conn.commit()
    assert BatchFactScope(reader).fingerprint() == before
    conn.execute("DELETE FROM Schedule WHERE version=6 AND op_id=?", (op_id,))
    conn.commit()
    assert BatchFactScope(reader).fingerprint() != before
    assert WorkbenchBatchFactsRepository(conn).plan_reference_counts()[op_id] == 1


def test_batch_creation_choices_read_only_base_catalogs(batch_client):
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService

    client, conn = batch_client, batch_client.batch_conn
    changes, trace = conn.total_changes, []
    conn.set_trace_callback(trace.append)
    try:
        response = client.get(BASE + "/choices")
    finally:
        conn.set_trace_callback(None)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    choices = result["data"]
    assert set(choices) == {"parts", "machines", "operators", "suppliers", "authorizations"}
    assert choices["parts"] == [{"ref": ref_for(client, "part", "P1"), "business_code": "P1", "label": "part"}]
    assert next(row for row in choices["machines"] if row["business_code"] == "M1")["ref"] == ref_for(client, "machine", "M1")
    assert next(row for row in choices["operators"] if row["business_code"] == "O1")["ref"] == ref_for(client, "operator", "O1")
    assert next(row for row in choices["suppliers"] if row["business_code"] == "S1")["ref"] == ref_for(client, "supplier", "S1")
    assert choices["authorizations"] == [{"machine_ref": ref_for(client, "machine", "M1"), "operator_ref": ref_for(client, "operator", "O1")}]
    assert result["meta"]["snapshot_ref"] and result["meta"]["as_of"]
    assert conn.total_changes == changes
    reads = [sql for sql in trace if sql.lstrip().upper().startswith("SELECT")]
    assert len(reads) == 6, reads
    assert all(any('"' + table + '"' in sql for table in (
        "Parts", "Machines", "Operators", "Suppliers", "OperatorMachine", "WorkbenchEntityRefs")) for sql in reads)
    reader = WorkbenchBatchQueryService(conn)
    assert reader.choices_catalog() == choices
    assert conn.total_changes == changes


def test_batch_qualification_uses_captured_skills_authorizations_and_supplier_bindings(batch_client, monkeypatch):
    from core.services.personnel.operator_qualification import OperatorQualificationService

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='OT1'")
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE batch_id='FREE-001'")
    conn.commit()

    def reread(*_args, **_kwargs):
        raise AssertionError('Resource qualification facts were already captured.')

    monkeypatch.setattr(OperatorQualificationService, 'load', reread)
    entity = detail(client)['data']
    operation_ref = entity['operations'][0]['ref']
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert next(row for row in choices['operators'] if row['business_code'] == 'O1')['eligible']
    response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'unit_hours': 1}}, key='captured-skills-update-001')
    assert response.status_code == 200, response.get_json()
    # An undeclared legacy profile with no explicit skills keeps the original authorization policy.
    conn.execute("DELETE FROM OperatorSkill WHERE operator_id='O1'")
    conn.commit()
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert next(row for row in choices['operators'] if row['business_code'] == 'O1')['eligible']
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('O1',1)")
    conn.commit()
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert not next(row for row in choices['operators'] if row['business_code'] == 'O1')['eligible']
    response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'unit_hours': 2}}, key='captured-skills-update-002')
    assert response.status_code >= 400 and '资格' in response.get_json()['error']['message']
    conn.execute("DELETE FROM WorkbenchOperatorProfiles WHERE operator_id='O1'")
    conn.execute("DELETE FROM OperatorMachine WHERE operator_id='O1'")
    conn.commit()
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    # 候选资格只看人员自身；人机配对由前端按草稿判断、由提交校验兜住。
    assert next(row for row in choices['operators'] if row['business_code'] == 'O1')['eligible']
    assert {'machine_ref': ref_for(client, 'machine', 'M1'), 'operator_ref': ref_for(client, 'operator', 'O1')} not in choices['authorizations']
    response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'unit_hours': 3}}, key='captured-skills-update-003')
    assert response.status_code >= 400 and '未被配置为可操作设备' in response.get_json()['error']['message']
    conn.execute("UPDATE BatchOperations SET source='external',machine_id=NULL,operator_id=NULL,supplier_id='S1',ext_days=1 WHERE batch_id='FREE-001'")
    conn.commit()
    # 供应商能力只认 WorkbenchSupplierOpTypes。
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert not next(row for row in choices['suppliers'] if row['business_code'] == 'S1')['eligible']
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','OT1')")
    conn.commit()
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert next(row for row in choices['suppliers'] if row['business_code'] == 'S1')['eligible']
    response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'external_days': 3}}, key='captured-supplier-update-001')
    assert response.status_code == 200, response.get_json()
    conn.execute("UPDATE BatchExternalContexts SET merge_mode='merged',total_days=NULL")
    conn.commit()
    rejected = assert_error(post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'external_days': 5}},
                                 key='captured-supplier-update-corrupt-001'), 'constraint_conflict')
    assert '整组外协周期未填写或无效' in rejected['error']['message']
    conn.execute("UPDATE BatchExternalContexts SET total_days=4,supplier_id='S1'")
    conn.commit()
    unchanged = post(client, 'operation_update', {
        'operation_ref': operation_ref,
        'fields': {'supplier_ref': ref_for(client, 'supplier', 'S1'), 'external_days': 3},
    }, key='captured-supplier-update-merged-unchanged')
    assert unchanged.status_code == 200 and unchanged.get_json()['result'] == 'unchanged'
    rejected = assert_error(post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'external_days': 5}},
                                 key='captured-supplier-update-merged-days'), 'constraint_conflict')
    assert '合并外协组不能逐道改周期' in rejected['error']['message']
    conn.execute("UPDATE BatchExternalContexts SET supplier_id='S2'")
    conn.commit()
    rejected = assert_error(post(client, 'operation_update', {
        'operation_ref': operation_ref,
        'fields': {'supplier_ref': ref_for(client, 'supplier', 'S1')},
    }, key='captured-supplier-update-merged-conflict'), 'constraint_conflict')
    assert '合并外协段的供应商与保存的规则不一致' in rejected['error']['message']


def test_choices_offer_a_new_authorized_pair_that_operation_update_commits(batch_client):
    from tests.workbench.identity_metadata_support import insert_row

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE batch_id='FREE-001'")
    insert_row(conn, 'Machines', dict(machine_id='M2', name='second-lathe', op_type_id='OT1', status='active'))
    insert_row(conn, 'Operators', dict(operator_id='O2', name='second-operator', status='active'))
    insert_row(conn, 'OperatorMachine', dict(operator_id='O2', machine_id='M2'))
    insert_row(conn, 'OperatorSkill', dict(operator_id='O2', op_type_id='OT1'))
    conn.commit()
    operation_ref = detail(client)['data']['operations'][0]['ref']
    choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
    assert next(row for row in choices['machines'] if row['business_code'] == 'M2')['eligible']
    assert next(row for row in choices['operators'] if row['business_code'] == 'O2')['eligible']
    response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {
        'machine_ref': ref_for(client, 'machine', 'M2'), 'operator_ref': ref_for(client, 'operator', 'O2')}}, key='new-authorized-pair-001')
    assert response.status_code == 200 and response.get_json()['result'] == 'committed', response.get_json()
    rejected = post(
        client,
        'operation_update',
        {'operation_ref': operation_ref, 'fields': {'supplier_ref': ref_for(client, 'supplier', 'S1')}},
        key='internal-supplier-rejected-001',
    )
    assert_error(rejected, 'invalid_input', 422)
    assert conn.execute("SELECT supplier_id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0] is None


def test_bulk_and_import_prepare_all_changes_before_writing(batch_client, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.batch.bulk import WorkbenchBatchBulkService
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.files import WorkbenchBatchFileService
    from data.repositories.batch_repo import BatchRepository
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository

    client, conn = batch_client, batch_client.batch_conn
    original_read, original_update = WorkbenchBatchFactsRepository.whole_tables, BatchRepository.update
    original_entity_read = WorkbenchBatchFactsRepository.entity_tables
    original_scoped_entity_read = WorkbenchBatchFactsRepository.scoped_entity_tables
    reads, entity_reads, scoped_entity_reads, writes = [], [], [], []

    def capture(repo):
        assert not writes
        reads.append(True)
        return original_read(repo)

    def capture_entities(repo):
        assert not writes
        entity_reads.append(True)
        return original_entity_read(repo)

    def capture_scoped_entities(repo, target_refs):
        assert not writes
        scoped_entity_reads.append(tuple(target_refs))
        return original_scoped_entity_read(repo, target_refs)

    def update(repo, code, changes):
        writes.append(code)
        return original_update(repo, code, changes)

    monkeypatch.setattr(WorkbenchBatchFactsRepository, 'whole_tables', capture)
    monkeypatch.setattr(WorkbenchBatchFactsRepository, 'entity_tables', capture_entities)
    monkeypatch.setattr(WorkbenchBatchFactsRepository, 'scoped_entity_tables', capture_scoped_entities)
    monkeypatch.setattr(BatchRepository, 'update', update)
    refs = [ref_for(client), ref_for(client, key='B1')]
    reader = BatchFacts(conn)
    with TransactionManager(conn).transaction(begin_immediate=True):
        with reader.command_snapshot(mode='batch_closure', target_refs=tuple(sorted(refs))) as scope:
            result = WorkbenchBatchBulkService(conn).apply_normalized(
                scope, {'action': 'update', 'refs': sorted(refs), 'patch': {'remark': 'prepared-bulk'}})
    assert (
        result.result == 'committed'
        and len(reads) == 0
        and len(entity_reads) == 0
        and len(scoped_entity_reads) == 1
        and set(writes) == {'FREE-001', 'B1'}
    )
    reads.clear()
    entity_reads.clear()
    scoped_entity_reads.clear()
    writes.clear()
    document = {'operation': 'batch.import_confirm', 'can_confirm': True, 'deleted': [], 'mode': 'overwrite', 'warnings': [],
                'rows': [{'action': 'update', 'entity_ref': ref, 'input': {'fields': {'remark': 'prepared-import'}}} for ref in refs]}
    with TransactionManager(conn).transaction(begin_immediate=True):
        with reader.command_snapshot() as scope:
            result = WorkbenchBatchFileService(conn).apply(scope, document)
    assert result.result == 'committed' and len(reads) == 0 and len(entity_reads) == 1 and set(writes) == {'FREE-001', 'B1'}
    reads.clear()
    entity_reads.clear()
    scoped_entity_reads.clear()
    writes.clear()
    single_resp = post(client, 'update', {'fields': {'remark': 'single-instance-direct'}}, key='single-no-entity-tables-01')
    assert single_resp.status_code == 200 and single_resp.get_json()['result'] == 'committed'
    assert reads == [] and entity_reads == [] and scoped_entity_reads == [] and writes == ['FREE-001']


def test_sync_confirm_applies_templates_without_rebuilding_preview(batch_client, monkeypatch):
    from core.services.workbench.batch import operations

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE PartOperations SET source='internal',supplier_id=NULL,ext_group_id=NULL,setup_hours=0,unit_hours=1 WHERE part_no='P1'")
    conn.commit()
    context = detail(client)
    response = client.post(BASE + '/' + ref_for(client) + '/sync-preview', json={'input': {}, 'snapshot_ref': context['meta']['snapshot_ref']})
    assert response.status_code == 200, response.get_json()
    document = response.get_json()['data']

    def preview_projection(*_args, **_kwargs):
        raise AssertionError('Confirm must apply the prepared change without producing display rows.')

    monkeypatch.setattr(operations, 'BatchProjection', preview_projection)
    response = confirm(client, document, path='/' + ref_for(client) + '/sync-confirm', key='batch-sync-without-preview-01')
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['data']['operation_count'] == 1


def test_legacy_batch_sync_rejects_cross_part_external_group(batch_client):
    from core.infrastructure.transaction import TransactionManager
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.operations import WorkbenchBatchOperationService
    from core.services.workbench.batch.scope import BatchFactScope
    from tests.workbench.identity_metadata_support import insert_row

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("DELETE FROM WorkbenchProcessWorkflow")
    conn.execute("UPDATE OpTypes SET category='external' WHERE op_type_id='OT1'")
    conn.execute("UPDATE Suppliers SET status='active' WHERE supplier_id='S1'")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','OT1')")
    conn.execute("UPDATE PartOperations SET source='external', supplier_id='S1', ext_days=2, ext_group_id='EG1' WHERE part_no='P1'")
    conn.execute("UPDATE ExternalGroups SET part_no='P1', start_seq=1, end_seq=1, merge_mode='separate', supplier_id='S1' WHERE group_id='EG1'")
    insert_row(conn, "Parts", dict(part_no="P-CROSS", part_name="cross-part"))
    insert_row(conn, "PartOperations", dict(part_no="P-CROSS", seq=1, op_type_id="OT1", op_type_name="turning",
                                            source="external", supplier_id="S1", ext_days=2, ext_group_id="EG1", status="active"))
    conn.commit()
    before = state(client)
    context = detail(client)
    template = context["data"]["template"]
    assert template["origin"] == "legacy" and template["complete"] is False
    assert any("的外协组被其他零件引用" in row["message"] for row in template["diagnostics"])
    preview_resp = client.post(BASE + "/" + ref_for(client) + "/sync-preview",
                               json={"input": {}, "snapshot_ref": context["meta"]["snapshot_ref"]})
    rejected = assert_error(preview_resp, "constraint_conflict", 409)
    assert "的外协组被其他零件引用" in rejected["error"]["message"]
    with TransactionManager(conn).transaction(begin_immediate=True):
        try:
            target_ref = ref_for(client)
            scope = BatchFactScope(BatchFacts(conn), command=True, mode="single_template", target_ref=target_ref)
            WorkbenchBatchOperationService(conn).sync_normalized(scope, target_ref)
        except WorkbenchCommandRejected as exc:
            assert exc.code == "constraint_conflict" and "的外协组被其他零件引用" in str(exc)
        else:
            raise AssertionError("Expected sync_normalized to reject cross-part external group")
    assert state(client) == before


def test_quantity_split_with_bound_material_returns_the_created_batch_reference(batch_client):
    from datetime import date

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    operation_ref = detail(client)['data']['operations'][0]['ref']
    response = post(client, 'materials_update', {'removed_keys': [], 'rows': [{
        'row_key': None, 'material_ref': ref_for(client, 'material', 'MAT1'), 'operation_ref': operation_ref,
        'required_quantity': 10, 'available_quantity': 4}]}, key='batch-split-bound-material-01')
    assert response.status_code == 200, response.get_json()
    context = detail(client)
    response = client.post(BASE + '/' + ref_for(client) + '/split-preview', json={
        'input': {'as_of_date': date.today().isoformat()}, 'snapshot_ref': context['meta']['snapshot_ref']})
    assert response.status_code == 200, response.get_json()
    preview = response.get_json()['data']
    assert preview['quantity'] == 2 and len(preview['materials']) == 1
    response = confirm(client, preview, path='/' + ref_for(client) + '/split-confirm', key='batch-split-bound-confirm-01')
    assert response.status_code == 200, response.get_json()
    outcome = response.get_json()['data']
    child_ref = outcome['child_ref']
    assert child_ref == ref_for(client, key='FREE-002')
    assert outcome['quantity'] == 2 and outcome['remaining_quantity'] == 3
    receipt = client.get('/api/workbench/v1/commands/batch-split-bound-confirm-01')
    receipt_json = receipt.get_json()
    assert receipt.status_code == 200
    assert receipt_json["state"] == "recorded"
    assert receipt_json["may_be_in_flight"] is False
    assert receipt_json["resolution"] == "recorded"
    assert receipt_json["receipt"]["data"] == outcome
    child, source = detail(client, child_ref)['data'], detail(client)['data']
    assert child['fields']['quantity'] == 2 and source['fields']['quantity'] == 3
    requirement = child['materials']['requirements'][0]
    assert (requirement['required_quantity'], requirement['available_quantity']) == (4, 4)
    assert requirement['operation_ref'] == child['operations'][0]['ref'] != operation_ref
    source_requirement = source['materials']['requirements'][0]
    assert (source_requirement['required_quantity'], source_requirement['available_quantity']) == (6, 0)


_COPY_BATCH_KEYS = ("business_code", "label", "status", "stored_status", "fields",
                    "display_ready_status", "relationships", "all_operations_complete", "issues", "protected")


def _comparable_operation(operation):
    """新工序在预览里还没有引用；其余字段连同执行情况都应与提交后的详情一致。"""
    execution = {key: value for key, value in operation["execution"].items() if key != "operation_ref"}
    return {**{key: value for key, value in operation.items() if key not in ("ref", "operation_ref")}, "execution": execution}


def _assert_copy_preview_matches_commit(after, committed):
    assert after["ref"] is None and set(after) - {"ref", "write_context", "operations"} == set(_COPY_BATCH_KEYS)
    assert {key: after[key] for key in _COPY_BATCH_KEYS} == {key: committed[key] for key in _COPY_BATCH_KEYS}
    assert all(op["ref"] is None and op["execution"]["operation_ref"] is None for op in after["operations"])
    assert all(op["execution"]["operation_ref"] == op["ref"] for op in committed["operations"])
    assert [_comparable_operation(op) for op in after["operations"]] == [
        _comparable_operation(op) for op in committed["operations"]
    ]


def test_copy_preview_after_matches_committed_detail_and_leaves_source_unchanged(batch_client):
    from datetime import date

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    source_ref = ref_for(client)
    operation_ref = detail(client, source_ref)["data"]["operations"][0]["ref"]
    mat_resp = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": None, "material_ref": ref_for(client, "material", "MAT1"), "operation_ref": operation_ref,
        "required_quantity": 10, "available_quantity": 4}]}, key="copy-parity-mat-01", ref=source_ref)
    assert mat_resp.status_code == 200, mat_resp.get_json()

    split_prev = client.post(BASE + "/" + source_ref + "/split-preview", json={
        "input": {"as_of_date": date.today().isoformat()},
        "snapshot_ref": detail(client, source_ref)["meta"]["snapshot_ref"],
    }).get_json()["data"]
    assert confirm(client, split_prev, path="/" + source_ref + "/split-confirm", key="copy-parity-split-01").status_code == 200

    source_row_key = detail(client, source_ref)["data"]["materials"]["requirements"][0]["row_key"]
    ready_resp = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": source_row_key, "material_ref": ref_for(client, "material", "MAT1"), "operation_ref": operation_ref,
        "required_quantity": 6, "available_quantity": 6}]}, key="copy-parity-mat-02", ref=source_ref)
    assert ready_resp.status_code == 200, ready_resp.get_json()
    assert post(client, "update", {"fields": {"due_date": "2026-10-15", "ready_date": "2026-10-05"}},
                key="copy-parity-upd-01", ref=source_ref).status_code == 200

    source_before = detail(client, source_ref)["data"]
    assert source_before["display_ready_status"] == "yes"
    assert source_before["relationships"]["quantity_split_reference_count"] == 1

    copy_prev = preview(client, "copy", [source_ref])
    after = copy_prev["rows"][0]["after"]
    assert after["display_ready_status"] == "no"
    assert after["relationships"]["quantity_split_reference_count"] == 0
    assert after["relationships"]["material_requirement_count"] == 1

    confirmed = confirm(client, copy_prev, key="copy-parity-confirm-01")
    assert confirmed.status_code == 200, confirmed.get_json()
    created_ref = confirmed.get_json()["data"]["items"][0]["entity_ref"]
    committed = detail(client, created_ref)["data"]
    source_after = detail(client, source_ref)["data"]

    assert {k: v for k, v in source_after.items() if k != "write_context"} == {
        k: v for k, v in source_before.items() if k != "write_context"
    }
    _assert_copy_preview_matches_commit(after, committed)
    assert committed["operations"][0]["execution"]["target_quantity"] == committed["fields"]["quantity"] == 3


def test_copy_preview_projects_fresh_execution_for_external_piece_and_completed_operations(batch_client):
    from tests.workbench.identity_metadata_support import insert_row

    client, conn = batch_client, batch_client.batch_conn
    source_ref = ref_for(client)
    conn.execute("UPDATE BatchOperations SET source='external', machine_id=NULL, operator_id=NULL, supplier_id='S1', "
                 "ext_days=2, status='completed' WHERE batch_id='FREE-001'")
    for piece in ("1", "2"):
        insert_row(conn, "BatchOperations", dict(op_code="FREE-001_02_" + piece, batch_id="FREE-001", piece_id=piece, seq=2,
                                                 op_type_id="OT1", op_type_name="inspect", source="internal", machine_id="M1",
                                                 operator_id="O1", setup_hours=0, unit_hours=1, status="pending"))
    conn.commit()
    source_before = detail(client, source_ref)["data"]
    external = source_before["operations"][0]
    assert external["external_group"]["business_code"] == "EG1"
    assert external["status"] == "completed" and external["data_quality"] == "invalid"

    copy_prev = preview(client, "copy", [source_ref])
    after = copy_prev["rows"][0]["after"]
    assert [(op["business_code"], op["status"], op["execution_state"]) for op in after["operations"]] == [
        ("FREE-002_01", "pending", "unreported"), ("FREE-002_02_1", "pending", "unreported"),
        ("FREE-002_02_2", "pending", "unreported")]
    assert [(op["execution"]["target_basis"], op["execution"]["target_quantity"], op["execution"]["remaining_quantity"])
            for op in after["operations"]] == [("batch", 5, 5), ("piece", 1, 1), ("piece", 1, 1)]

    confirmed = confirm(client, copy_prev, key="copy-multi-op-confirm-01")
    assert confirmed.status_code == 200, confirmed.get_json()
    committed = detail(client, confirmed.get_json()["data"]["items"][0]["entity_ref"])["data"]
    _assert_copy_preview_matches_commit(after, committed)
    assert {k: v for k, v in detail(client, source_ref)["data"].items() if k != "write_context"} == {
        k: v for k, v in source_before.items() if k != "write_context"
    }


def test_copy_and_split_previews_reject_invalid_source_batch_fields(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    source_ref = ref_for(client)
    mat_resp = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": None, "material_ref": ref_for(client, "material", "MAT1"),
        "required_quantity": 10, "available_quantity": 4}]}, key="preview-guard-mat-01", ref=source_ref)
    assert mat_resp.status_code == 200, mat_resp.get_json()

    baseline = dict(conn.execute(
        "SELECT due_date, priority, part_name, ready_date FROM Batches WHERE batch_id='FREE-001'"
    ).fetchone())
    fix = "请先打开这个批次，把{label}核对改好后再{verb}。"
    for column, invalid_value, field, label, remedy in (
        ("due_date", "2026/10/01", "fields.due_date", "交期", fix),
        ("priority", "high", "fields.priority", "优先级", fix),
        ("part_name", "", "part_name", "零件名称", "零件名称在批次里改不了，请联系维护人员核对这个批次的资料。"),
    ):
        conn.execute(
            "UPDATE Batches SET due_date=?, priority=?, part_name=?, ready_date=? WHERE batch_id='FREE-001'",
            (baseline["due_date"], baseline["priority"], baseline["part_name"], baseline["ready_date"]),
        )
        conn.execute(f"UPDATE Batches SET {column}=? WHERE batch_id='FREE-001'", (invalid_value,))
        conn.commit()
        before = state(client)
        conflicts = [{"entity_ref": source_ref, "business_code": "FREE-001", "field": field}]

        # 同时复制一个资料正常的批次：报错只点名库里有坏值的那一个原批次。
        bulk_resp = client.post(BASE + "/bulk-preview", json={
            "scope": {},
            "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
            "input": {"action": "copy", "refs": [ref_for(client, key="B1"), source_ref], "patch": {}},
        })
        bulk_err = assert_error(bulk_resp, "constraint_conflict", 409)["error"]
        assert bulk_err["message"] == ("原批次“FREE-001”在系统里存的" + label + "不对，这次没有复制。"
                                       + remedy.format(label=label, verb="复制"))
        assert bulk_err["conflicts"] == conflicts and bulk_err["fields"] == []

        split_resp = client.post(BASE + "/" + source_ref + "/split-preview", json={
            "input": {"as_of_date": "2026-10-08"},
            "snapshot_ref": detail(client, source_ref)["meta"]["snapshot_ref"],
        })
        split_err = assert_error(split_resp, "constraint_conflict", 409)["error"]
        assert split_err["message"] == ("原批次“FREE-001”在系统里存的" + label + "不对，这次没有拆分。"
                                        + remedy.format(label=label, verb="拆分"))
        assert split_err["conflicts"] == conflicts
        assert state(client) == before

    conn.execute(
        "UPDATE Batches SET due_date=?, priority=?, part_name=?, ready_date='2026-10-01 08:00:00' WHERE batch_id='FREE-001'",
        (baseline["due_date"], baseline["priority"], baseline["part_name"]),
    )
    conn.commit()
    before = state(client)
    split_resp = client.post(BASE + "/" + source_ref + "/split-preview", json={
        "input": {"as_of_date": "2026-10-08"},
        "snapshot_ref": detail(client, source_ref)["meta"]["snapshot_ref"],
    })
    split_err = assert_error(split_resp, "constraint_conflict", 409)["error"]
    assert split_err["message"] == "原批次“FREE-001”在系统里存的齐套日期不对，这次没有拆分。请先打开这个批次，把齐套日期核对改好后再拆分。"
    assert split_err["conflicts"] == [{"entity_ref": source_ref, "business_code": "FREE-001", "field": "fields.ready_date"}]
    assert state(client) == before


def test_copy_and_split_previews_reject_missing_external_context_and_cross_batch_material_stage(batch_client):
    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    source_ref = ref_for(client)
    source_op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0]
    other_op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='B1'").fetchone()[0]
    operation_ref = detail(client, source_ref)["data"]["operations"][0]["ref"]
    mat_resp = post(
        client,
        "materials_update",
        {
            "removed_keys": [],
            "rows": [
                {
                    "row_key": None,
                    "material_ref": ref_for(client, "material", "MAT1"),
                    "operation_ref": operation_ref,
                    "required_quantity": 10,
                    "available_quantity": 4,
                }
            ],
        },
        key="preview-guard-stage-001",
        ref=source_ref,
    )
    assert mat_resp.status_code == 200, mat_resp.get_json()

    conn.execute("UPDATE BatchMaterialStages SET operation_id=? WHERE operation_id=?", (other_op_id, source_op_id))
    conn.commit()
    before = state(client)
    bulk_stage_resp = client.post(
        BASE + "/bulk-preview",
        json={
            "scope": {},
            "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
            "input": {"action": "copy", "refs": [source_ref], "patch": {}},
        },
    )
    assert_error(bulk_stage_resp, "material_stage_invalid", 409)
    split_stage_resp = client.post(
        BASE + "/" + source_ref + "/split-preview",
        json={
            "input": {"as_of_date": "2026-10-08"},
            "snapshot_ref": detail(client, source_ref)["meta"]["snapshot_ref"],
        },
    )
    assert_error(split_stage_resp, "material_stage_invalid", 409)
    assert state(client) == before

    conn.execute("UPDATE BatchMaterialStages SET operation_id=? WHERE operation_id=?", (source_op_id, other_op_id))
    conn.execute(
        "UPDATE BatchOperations SET source='external', machine_id=NULL, operator_id=NULL, supplier_id='S1', ext_days=2 "
        "WHERE id=?",
        (source_op_id,),
    )
    conn.execute("DELETE FROM BatchExternalContexts WHERE operation_id=?", (source_op_id,))
    conn.commit()
    before = state(client)
    bulk_ext_resp = client.post(
        BASE + "/bulk-preview",
        json={
            "scope": {},
            "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
            "input": {"action": "copy", "refs": [source_ref], "patch": {}},
        },
    )
    assert_error(bulk_ext_resp, "external_context_missing", 409)
    split_ext_resp = client.post(
        BASE + "/" + source_ref + "/split-preview",
        json={
            "input": {"as_of_date": "2026-10-08"},
            "snapshot_ref": detail(client, source_ref)["meta"]["snapshot_ref"],
        },
    )
    assert_error(split_ext_resp, "external_context_missing", 409)
    assert state(client) == before


def test_production_decltypes_connection_preserves_raw_batch_dates_end_to_end(tmp_path):
    from datetime import date

    from core.infrastructure.database import ensure_schema, get_connection
    from tests.workbench.batch_support import create_batch_client

    db_path = str(tmp_path / "production_decltypes_batches.sqlite")
    ensure_schema(db_path)
    conn = get_connection(db_path)
    try:
        client = create_batch_client(conn)
        source_ref = ref_for(client)
        initial = post(
            client,
            "update",
            {"fields": {"due_date": "2026-10-15", "ready_date": "2026-10-05"}},
            key="prod-decltypes-init-0001",
            ref=source_ref,
        )
        assert initial.status_code == 200 and initial.get_json()["result"] == "committed", initial.get_json()
        raw_decl = conn.execute("SELECT due_date, ready_date FROM Batches WHERE batch_id='FREE-001'").fetchone()
        assert (raw_decl["due_date"], raw_decl["ready_date"]) == (date(2026, 10, 15), date(2026, 10, 5))

        unchanged = post(
            client,
            "update",
            {"fields": {"due_date": "2026-10-15", "ready_date": "2026-10-05"}},
            key="prod-decltypes-noop-0001",
            ref=source_ref,
        )
        assert unchanged.status_code == 200 and unchanged.get_json()["result"] == "unchanged", unchanged.get_json()

        copy_prev = preview(client, "copy", [source_ref])
        assert copy_prev["rows"][0]["after"]["fields"]["due_date"] == "2026-10-15"
        copy_resp = confirm(client, copy_prev, key="prod-decltypes-copy-0001")
        assert copy_resp.status_code == 200, copy_resp.get_json()
        copied_ref = copy_resp.get_json()["data"]["items"][0]["entity_ref"]
        assert detail(client, copied_ref)["data"]["fields"]["due_date"] == "2026-10-15"

        conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
        conn.commit()
        operation_ref = detail(client, source_ref)["data"]["operations"][0]["ref"]
        mat_resp = post(
            client,
            "materials_update",
            {
                "removed_keys": [],
                "rows": [
                    {
                        "row_key": None,
                        "material_ref": ref_for(client, "material", "MAT1"),
                        "operation_ref": operation_ref,
                        "required_quantity": 10,
                        "available_quantity": 4,
                    }
                ],
            },
            key="prod-decltypes-mat-00001",
            ref=source_ref,
        )
        assert mat_resp.status_code == 200, mat_resp.get_json()
        split_ctx = detail(client, source_ref)
        split_prev_resp = client.post(
            BASE + "/" + source_ref + "/split-preview",
            json={"input": {"as_of_date": "2026-10-08"}, "snapshot_ref": split_ctx["meta"]["snapshot_ref"]},
        )
        assert split_prev_resp.status_code == 200, split_prev_resp.get_json()
        split_prev = split_prev_resp.get_json()["data"]
        split_confirm_resp = confirm(
            client, split_prev, path="/" + source_ref + "/split-confirm", key="prod-decltypes-split-001"
        )
        assert split_confirm_resp.status_code == 200, split_confirm_resp.get_json()
        split_child_ref = split_confirm_resp.get_json()["data"]["child_ref"]
        split_child = detail(client, split_child_ref)["data"]
        assert split_child["fields"]["due_date"] == "2026-10-15"
        assert split_child["fields"]["ready_date"] == "2026-10-08"

        conn.execute("UPDATE Batches SET due_date='bad-date' WHERE batch_id='FREE-001'")
        conn.commit()
        listed = list_data(client)
        listed_item = next(row for row in listed["data"]["entities"] if row["business_code"] == "FREE-001")
        assert listed_item["fields"]["due_date"] == "bad-date"
        assert {"code": "data_gap", "message": "交期原值不合法，请核对。"} in listed_item["issues"]
        det = detail(client, source_ref)["data"]
        assert det["fields"]["due_date"] == "bad-date"
        assert {"code": "data_gap", "message": "交期原值不合法，请核对。"} in det["issues"]
        dirty_copy = client.post(
            BASE + "/bulk-preview",
            json={
                "scope": {},
                "snapshot_ref": listed["meta"]["snapshot_ref"],
                "input": {"action": "copy", "refs": [source_ref], "patch": {}},
            },
        )
        dirty_err = assert_error(dirty_copy, "constraint_conflict", 409)["error"]
        assert dirty_err["conflicts"] == [
            {"entity_ref": source_ref, "business_code": "FREE-001", "field": "fields.due_date"}
        ]
    finally:
        conn.close()


def test_batch_import_preserves_legacy_spaced_codes_in_overwrite_and_replace_and_rejects_spaced_new_codes(batch_client):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.file_codec import write_batch_file
    from core.services.workbench.batch.files import WorkbenchBatchFileService
    from core.services.workbench.batch.scope import BatchFactScope
    from tests.workbench.identity_metadata_support import insert_row

    _client, conn = batch_client, batch_client.batch_conn
    insert_row(conn, "Parts", dict(part_no=" P1 ", part_name="spaced-part"))
    insert_row(
        conn,
        "Batches",
        dict(
            batch_id=" B1 ",
            part_no=" P1 ",
            part_name="spaced-part",
            quantity=7,
            due_date="2026-10-20",
            priority="normal",
            status="pending",
            ready_status="yes",
            ready_date=None,
            remark="spaced-batch",
        ),
    )
    conn.commit()
    service = WorkbenchBatchFileService(conn)
    facts_reader = BatchFacts(conn)

    # 1) 不存在的带空格批次号或带空格图号必须被拒绝，不串改无空格兄弟
    bad_xlsx = write_batch_file(
        [
            [" B1 ", " P1 ", 12, "2026-10-20", "普通", "齐套", "", "updated-spaced", "待排", "齐套"],
            [" B-NEW ", "P1", 5, "2026-10-20", "普通", "齐套", "", "", "待排", "齐套"],
            ["B-GOOD", " P-NONE ", 5, "2026-10-20", "普通", "齐套", "", "", "待排", "齐套"],
        ]
    )
    bad_preview = service.preview(BatchFactScope(facts_reader), "overwrite", service.read(bad_xlsx, "overwrite"))
    assert bad_preview["can_confirm"] is False
    assert bad_preview["rows"][0]["business_code"] == " B1 "
    assert bad_preview["rows"][0]["action"] == "update"
    assert bad_preview["rows"][0]["errors"] == []
    assert bad_preview["rows"][1]["errors"] == ["[1001] 批次号不能有首尾空格，请修正后重新导入。"]
    assert bad_preview["rows"][2]["errors"] == ["[1001] 图号“ P-NONE ”不存在，请先在工艺管理中维护零件。"]

    # 2) overwrite 模式下更新存量 " B1 "，保持无空格兄弟 "B1" 不动
    overwrite_xlsx = write_batch_file(
        [[" B1 ", " P1 ", 12, "2026-10-20", "普通", "齐套", "", "updated-spaced", "待排", "齐套"]]
    )
    overwrite_doc = service.preview(
        BatchFactScope(facts_reader), "overwrite", service.read(overwrite_xlsx, "overwrite")
    )
    assert overwrite_doc["can_confirm"] is True, overwrite_doc
    with TransactionManager(conn).transaction(begin_immediate=True):
        with facts_reader.command_snapshot() as scope:
            outcome = service.apply(scope, overwrite_doc)
    assert outcome.result == "committed"
    quantities = dict(
        conn.execute("SELECT batch_id, quantity FROM Batches WHERE batch_id IN ('B1', ' B1 ')").fetchall()
    )
    assert quantities == {"B1": 17, " B1 ": 12}

    # 3) replace 模式下重导存量 " B1 " 与 "B1"，" B1 " 必须保留原编号而不被 strip
    for table in ("Schedule", "BatchMaterials", "BatchOperations"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM Batches WHERE batch_id NOT IN ('B1', ' B1 ')")
    conn.commit()
    replace_xlsx = write_batch_file(
        [
            ["B1", "P1", 8, "2026-10-20", "普通", "齐套", "", "trimmed-replaced", "待排", "齐套"],
            [" B1 ", " P1 ", 15, "2026-10-20", "急件", "齐套", "", "spaced-replaced", "待排", "齐套"],
        ]
    )
    replace_doc = service.preview(
        BatchFactScope(facts_reader), "replace", service.read(replace_xlsx, "replace")
    )
    assert replace_doc["can_confirm"] is True, replace_doc
    assert [row["input"]["business_code"] for row in replace_doc["rows"]] == ["B1", " B1 "]
    with TransactionManager(conn).transaction(begin_immediate=True):
        with facts_reader.command_snapshot() as scope:
            replace_outcome = service.apply(scope, replace_doc)
    assert replace_outcome.result == "committed"
    replaced = {
        row["batch_id"]: (row["part_no"], row["quantity"], row["remark"])
        for row in conn.execute("SELECT batch_id, part_no, quantity, remark FROM Batches").fetchall()
    }
    assert replaced == {
        "B1": ("P1", 8, "trimmed-replaced"),
        " B1 ": (" P1 ", 15, "spaced-replaced"),
    }


def test_single_delete_route_minimal_closure_bulk_delete_isolation_replay_and_protection_priority(
    batch_client, monkeypatch
):
    import time

    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
    from tests.workbench.identity_metadata_support import insert_row
    from web import public_token_registry

    client, conn = batch_client, batch_client.batch_conn
    for code in ("DEL-SINGLE", "DEL-BULK", "UNRELATED-HEAVY"):
        insert_row(
            conn,
            "Batches",
            dict(
                batch_id=code,
                part_no="P1",
                part_name="part",
                quantity=4,
                due_date="2026-10-20",
                priority="normal",
                status="pending",
                ready_status="yes",
                ready_date=None,
                remark=None,
            ),
        )
    conn.commit()
    single_ref = ref_for(client, key="DEL-SINGLE")
    bulk_ref = ref_for(client, key="DEL-BULK")

    # 1) Public route POST /api/workbench/v1/entities/batch/<ref>/delete uses single_instance closure (no whole/entity scan).
    single_det = detail(client, single_ref)["data"]
    assert single_det["write_context"]["capabilities"]["batch.delete"] is True
    with monkeypatch.context() as bounded:
        bounded.setattr(
            WorkbenchBatchFactsRepository,
            "whole_tables",
            lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("whole_tables forbidden on single delete")),
        )
        bounded.setattr(
            WorkbenchBatchFactsRepository,
            "entity_tables",
            lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("entity_tables forbidden on single delete")),
        )
        del_resp = client.post(
            BASE + "/" + single_ref + "/delete",
            json=body(single_det["write_context"], {}, "single-delete-route-0001"),
        )
    assert del_resp.status_code == 200 and del_resp.get_json()["result"] == "committed"
    assert_error(client.get(BASE + "/" + single_ref), "entity_not_found", 404)

    # 2) Selected export + bulk-preview(delete) + bulk-confirm(delete) use batch_closure without scanning unrelated batches.
    snap_ref = list_data(client, query="DEL-BULK")["meta"]["snapshot_ref"]
    scoped_calls = []
    original_closure = WorkbenchBatchFactsRepository.closure_batch_tables

    def record_closure(repo, target_refs):
        tables = original_closure(repo, target_refs)
        scoped_calls.append([row["batch_id"] for row in tables["Batches"]])
        return tables

    now = [time.time()]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: now[0])
    with monkeypatch.context() as closure_guard:
        closure_guard.setattr(
            WorkbenchBatchFactsRepository,
            "whole_tables",
            lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("whole_tables forbidden on scoped delete/export")),
        )
        closure_guard.setattr(
            WorkbenchBatchFactsRepository,
            "entity_tables",
            lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("entity_tables forbidden on scoped delete/export")),
        )
        closure_guard.setattr(
            WorkbenchBatchFactsRepository,
            "filtered_batch_tables",
            lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("filtered_batch_tables forbidden on scoped delete/export")),
        )
        closure_guard.setattr(WorkbenchBatchFactsRepository, "closure_batch_tables", record_closure)

        exp_prev = client.post(
            BASE + "/export-preview",
            json={
                "selection": "selected",
                "scope": {"query": "DEL-BULK", "snapshot_ref": snap_ref},
                "refs": [bulk_ref],
            },
        )
        assert exp_prev.status_code == 200, exp_prev.get_json()
        exp_dl = client.get(BASE + "/export", query_string={"export_ref": exp_prev.get_json()["data"]["export_ref"]})
        assert exp_dl.status_code == 200 and exp_dl.headers["X-Workbench-Row-Count"] == "1"

        bulk_del_prev_resp = client.post(
            BASE + "/bulk-preview",
            json={
                "scope": {"query": "DEL-BULK"},
                "snapshot_ref": snap_ref,
                "input": {"action": "delete", "refs": [bulk_ref], "patch": {}},
            },
        )
        assert bulk_del_prev_resp.status_code == 200, bulk_del_prev_resp.get_json()
        bulk_del_prev = bulk_del_prev_resp.get_json()["data"]
        bulk_del_confirm = confirm(client, bulk_del_prev, key="bulk-delete-closure-replay-01")
        assert bulk_del_confirm.status_code == 200, bulk_del_confirm.get_json()
    assert scoped_calls == [["DEL-BULK"], ["DEL-BULK"], ["DEL-BULK"], ["DEL-BULK"]]
    assert all("UNRELATED-HEAVY" not in batch_ids for batch_ids in scoped_calls)

    # 3) Idempotent replay in batch_confirm runs BEFORE load_preview expiry check.
    now[0] += 1200
    replayed = confirm(client, bulk_del_prev, key="bulk-delete-closure-replay-01")
    assert replayed.status_code == 200 and replayed.get_json()["replayed"] is True
    expired_new = confirm(client, bulk_del_prev, key="bulk-delete-expired-fresh-01")
    assert_error(expired_new, "stale_write", 409)

    # 4) Unified protection priority (layered bottom-up so every higher blocker overrides all lower ones):
    #    materials -> quantity_splits -> protected -> outsourcing.
    from data.repositories.batch_material_stage_repo import BatchMaterialStageRepository

    target_ref = ref_for(client)
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0]

    def assert_delete_blocked(expected_cmd_sub, expected_policy_sub):
        det = detail(client, target_ref)["data"]
        wc = det["write_context"]
        assert wc["capabilities"]["batch.delete"] is False
        reasons = [r["message"] for r in wc["blocked_reasons"] if r["action"] == "batch.delete"]
        assert len(reasons) == 1 and expected_policy_sub in reasons[0]
        snap = list_data(client)["meta"]["snapshot_ref"]
        bulk_rej = client.post(
            BASE + "/bulk-preview",
            json={"scope": {}, "snapshot_ref": snap, "input": {"action": "delete", "refs": [target_ref], "patch": {}}},
        )
        err = assert_error(bulk_rej, "constraint_conflict", 409)
        assert expected_cmd_sub in err["error"]["message"]

    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.execute(
        "INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) "
        "VALUES ('FREE-001','MAT1',5,0,'no')"
    )
    conn.commit()
    assert_delete_blocked("挂着物料需求", "挂着物料需求")

    BatchMaterialStageRepository(conn).record_split("FREE-001", "UNRELATED-HEAVY", 5, 1, "2026-10-08")
    conn.commit()
    assert_delete_blocked("数量拆分记录", "数量拆分记录")

    conn.execute(
        "INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,'2026-09-09 08:00:00','2026-09-09 09:00:00',9)",
        (op_id,),
    )
    conn.commit()
    assert_delete_blocked("已经进了计划", "已有排产、报工或执行状态记录")

    conn.execute(
        "INSERT INTO WorkbenchOutsourcingReceipts("
        "outsourcing_ref,target_kind,batch_ref,supplier_ref,origin_json,identity_json,created_at"
        ") VALUES (?,'single',?,?,'{}','{}','2026-10-01T08:00:00')",
        ("c" * 48, target_ref, ref_for(client, "supplier", "S1")),
    )
    conn.commit()
    assert_delete_blocked("外协发出或回厂登记", "外协发出或回厂登记")


def test_chunked_rowid_union_reads_integer_pk_tables_identically_in_list_and_bulk_preview(
    batch_client, monkeypatch
):
    from core.models.workbench_batch_query import batch_scope
    from data.repositories import workbench_batch_facts_repo
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
    from tests.workbench.identity_metadata_support import insert_row

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    insert_row(conn, "Materials", dict(material_id="MAT2", name="aluminum", unit="kg", status="active"))
    insert_row(
        conn,
        "BatchOperations",
        dict(
            op_code="FREE-001_02",
            batch_id="FREE-001",
            seq=2,
            op_type_id="OT1",
            op_type_name="turning",
            source="internal",
            setup_hours=0,
            unit_hours=1,
            status="pending",
        ),
    )
    conn.commit()

    source_ref = ref_for(client)
    op_refs = [op["ref"] for op in detail(client, source_ref)["data"]["operations"]]
    assert len(op_refs) == 2
    mat_resp = post(
        client,
        "materials_update",
        {
            "removed_keys": [],
            "rows": [
                {
                    "row_key": None,
                    "material_ref": ref_for(client, "material", "MAT1"),
                    "operation_ref": op_refs[0],
                    "required_quantity": 10,
                    "available_quantity": 4,
                    "arrivals": [{"arrival_date": "2026-10-08", "quantity": 6}],
                },
                {
                    "row_key": None,
                    "material_ref": ref_for(client, "material", "MAT2"),
                    "operation_ref": op_refs[1],
                    "required_quantity": 8,
                    "available_quantity": 2,
                    "arrivals": [{"arrival_date": "2026-10-09", "quantity": 6}],
                },
            ],
        },
        key="chunked-rowid-materials-001",
        ref=source_ref,
    )
    assert mat_resp.status_code == 200, mat_resp.get_json()

    refs = sorted([source_ref, ref_for(client, key="B1")])
    query = batch_scope({})
    repo = WorkbenchBatchFactsRepository(conn)
    baseline_filtered = repo.filtered_batch_tables(query)
    baseline_closure = repo.closure_batch_tables(refs)
    assert len(baseline_filtered["BatchOperations"]) == 3
    assert len(baseline_filtered["BatchMaterials"]) == 3
    assert len(baseline_filtered["BatchMaterialStages"]) == 2
    assert len(baseline_closure["BatchMaterialStages"]) == 2

    baseline_list = list_data(client)["data"]
    baseline_preview = preview(client, "update", refs=refs, patch={"remark": "chunked-check"})

    monkeypatch.setattr(workbench_batch_facts_repo, "QUERY_PARAM_CHUNK", 1)

    assert repo.filtered_batch_tables(query) == baseline_filtered
    assert repo.closure_batch_tables(refs) == baseline_closure

    chunked_list = list_data(client)["data"]
    assert [
        {k: v for k, v in row.items() if k != "write_context"} for row in chunked_list["entities"]
    ] == [
        {k: v for k, v in row.items() if k != "write_context"} for row in baseline_list["entities"]
    ]
    assert chunked_list["page"] == baseline_list["page"]
    assert chunked_list["metrics"] == baseline_list["metrics"]

    chunked_preview = preview(client, "update", refs=refs, patch={"remark": "chunked-check"})
    assert chunked_preview["count"] == baseline_preview["count"] == 2
    assert chunked_preview["commit_policy"] == baseline_preview["commit_policy"]
    assert [
        {**row, "before": {k: v for k, v in row["before"].items() if k != "write_context"}}
        for row in chunked_preview["rows"]
    ] == [
        {**row, "before": {k: v for k, v in row["before"].items() if k != "write_context"}}
        for row in baseline_preview["rows"]
    ]

