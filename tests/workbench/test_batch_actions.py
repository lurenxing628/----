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
    with reader.detached_read_snapshot() as old_fingerprint:
        old = reader.detail(ref_for(client))
        clock[0] = datetime(2026, 10, 8, 0, 0, 30)
        pinned = reader.detail(ref_for(client))
        assert reader.fingerprint() == old_fingerprint
        assert old["display_ready_status"] == pinned["display_ready_status"] == pinned["materials"]["display_status"] == "no"
    with reader.detached_read_snapshot() as new_fingerprint:
        current = reader.detail(ref_for(client))
        assert new_fingerprint != old_fingerprint
        assert current["display_ready_status"] == current["materials"]["display_status"] == "yes"
    assert_error(client.get(BASE, query_string=scope), "snapshot_stale", 409)
    assert_error(client.post(BASE + "/selection", json=scope), "snapshot_stale", 409)
    assert_error(client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": scope}), "snapshot_stale", 409)
    assert_error(client.get(BASE + "/export", query_string={"export_ref": exported["data"]["export_ref"]}), "snapshot_stale", 409)
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
            with reader.command_snapshot():
                first, second = reader.load(), reader.load()
                assert first["Batches"] is second["Batches"]
                assert reader.batch(ref)["remark"] == "keep-hidden"
                old_index = reader._lookups["Batches"]
                conn.execute("UPDATE Batches SET remark='command-current' WHERE batch_id='FREE-001'")
                changed = reader.load()
                assert changed["Batches"] is not first["Batches"]
                assert reader.batch(ref)["remark"] == "command-current"
                assert reader._lookups["Batches"] is not old_index
            assert reader._facts is reader._stamp is None and not reader._lookups
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
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository

    conn = batch_client.batch_conn
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FREE-001'").fetchone()[0]
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,'2026-09-09 08:00:00','2026-09-09 09:00:00',6)", (op_id,))
    candidate = conn.execute("INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status) "
                             "VALUES (6,'batch-test','test','baseline','completed')").lastrowid
    conn.execute("INSERT INTO ScheduleCandidateRows(version,candidate_id,op_id,start_time,end_time) "
                 "VALUES (6,?,?,'2026-09-09 08:00:00','2026-09-09 09:00:00')", (candidate, op_id))
    conn.execute("INSERT INTO ScheduleAdjustmentDraft(draft_id,base_version,base_plan_role) VALUES ('batch-draft',6,'adopted')")
    conn.execute("INSERT INTO ScheduleAdjustmentChange(draft_id,op_id,change_type) VALUES ('batch-draft',?,'move_time')", (op_id,))
    conn.execute("INSERT INTO ScheduleAdjustmentScenario(scenario_id,source_draft_id,base_version,base_plan_role,base_source_table,validation_status) "
                 "VALUES ('batch-scenario','batch-draft',6,'adopted','schedule','valid')")
    conn.execute("INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id,source_table,op_id,start_time,end_time) "
                 "VALUES ('batch-scenario','schedule',?,'2026-09-09 08:00:00','2026-09-09 09:00:00')", (op_id,))
    conn.commit()
    reader, trace = BatchFacts(conn), []
    conn.set_trace_callback(trace.append)
    try:
        facts = reader.load()
    finally:
        conn.set_trace_callback(None)
    assert facts['plan_reference_counts'][op_id] == 4
    assert not {'Schedule', 'ScheduleCandidateRows', 'ScheduleAdjustmentChange', 'ScheduleAdjustmentScenarioRow',
                'OperationExecutionEvents', 'WorkbenchPlanSourceRefs'} & facts.keys()
    batch = next(row for row in facts['Batches'] if row['batch_id'] == 'FREE-001')
    relations = index_relations(facts)['FREE-001']
    entity = BatchProjection(facts).entity(batch)
    assert relations['protected'] and entity['relationships']['plan_reference_count'] == 4
    with pytest.raises(WorkbenchCommandRejected, match='已经进了计划'):
        require_unreferenced(relations)
    assert not any('SELECT * FROM "Schedule"' in sql or 'SELECT * FROM OperationExecutionEvents' in sql or
                   'SELECT * FROM WorkbenchPlanSourceRefs' in sql for sql in trace)
    before = reader.fingerprint()
    conn.execute("UPDATE ScheduleCandidateRows SET start_time='2026-09-09 09:00:00' WHERE candidate_id=?", (candidate,))
    conn.execute("INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status) "
                 "VALUES (100,'unrelated','test','baseline','completed')")
    conn.commit()
    assert reader.fingerprint() == before
    conn.execute("DELETE FROM ScheduleAdjustmentChange WHERE draft_id='batch-draft'")
    conn.commit()
    assert reader.fingerprint() != before
    assert WorkbenchBatchFactsRepository(conn).plan_reference_counts()[op_id] == 3


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
    assert reader.choices() == choices
    assert conn.total_changes == changes
    conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='part' AND entity_key='P1'")
    conn.commit()
    changes = conn.total_changes
    assert_error(client.get(BASE + "/choices"), "storage_failure", 500)
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
    assert '授权' in next(row for row in choices['operators'] if row['business_code'] == 'O1')['unavailable_reason']
    conn.execute("UPDATE BatchOperations SET source='external',machine_id=NULL,operator_id=NULL,supplier_id='S1',ext_days=1 WHERE batch_id='FREE-001'")
    conn.commit()
    # 供应商能力只认 WorkbenchSupplierOpTypes；种子里的 Suppliers.op_type_id 不算能力。
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


def test_bulk_and_import_prepare_all_changes_before_writing(batch_client, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.batch.bulk import WorkbenchBatchBulkService
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.files import WorkbenchBatchFileService
    from data.repositories.batch_repo import BatchRepository
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository

    client, conn = batch_client, batch_client.batch_conn
    original_read, original_update = WorkbenchBatchFactsRepository.whole_tables, BatchRepository.update
    reads, writes = [], []

    def capture(repo):
        assert not writes
        reads.append(True)
        return original_read(repo)

    def update(repo, code, changes):
        writes.append(code)
        return original_update(repo, code, changes)

    monkeypatch.setattr(WorkbenchBatchFactsRepository, 'whole_tables', capture)
    monkeypatch.setattr(BatchRepository, 'update', update)
    refs = [ref_for(client), ref_for(client, key='B1')]
    reader = BatchFacts(conn)
    with TransactionManager(conn).transaction(begin_immediate=True):
        with reader.command_snapshot():
            result = WorkbenchBatchBulkService(conn, reader=reader).apply_normalized(
                {'action': 'update', 'refs': sorted(refs), 'patch': {'remark': 'prepared-bulk'}})
    assert result.result == 'committed' and len(reads) == 1 and set(writes) == {'FREE-001', 'B1'}
    reads.clear()
    writes.clear()
    document = {'operation': 'batch.import_confirm', 'can_confirm': True, 'deleted': [], 'mode': 'overwrite', 'warnings': [],
                'rows': [{'action': 'update', 'entity_ref': ref, 'input': {'fields': {'remark': 'prepared-import'}}} for ref in refs]}
    with TransactionManager(conn).transaction(begin_immediate=True):
        with reader.command_snapshot():
            result = WorkbenchBatchFileService(conn, reader=reader).apply(document)
    assert result.result == 'committed' and len(reads) == 1 and set(writes) == {'FREE-001', 'B1'}


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
    from core.services.workbench.batch.operations import WorkbenchBatchOperationService
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
            WorkbenchBatchOperationService(conn).sync_normalized(ref_for(client))
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
    assert receipt.status_code == 200 and receipt.get_json()['data'] == outcome
    child, source = detail(client, child_ref)['data'], detail(client)['data']
    assert child['fields']['quantity'] == 2 and source['fields']['quantity'] == 3
    requirement = child['materials']['requirements'][0]
    assert (requirement['required_quantity'], requirement['available_quantity']) == (4, 4)
    assert requirement['operation_ref'] == child['operations'][0]['ref'] != operation_ref
    source_requirement = source['materials']['requirements'][0]
    assert (source_requirement['required_quantity'], source_requirement['available_quantity']) == (6, 0)


def test_reopened_batch_page_locates_shared_write_facts_once(batch_client, monkeypatch, record_property):
    from core.services.workbench.batch.facts import BatchFacts

    class SharedFacts(str):
        equalities = 0
        __hash__ = str.__hash__

        def __eq__(self, other):
            SharedFacts.equalities += 1
            return str.__eq__(self, other)

    client = batch_client
    client.batch_conn.executemany("INSERT INTO Batches(batch_id,part_no,quantity,status) VALUES (?,'P1',1,'pending')",
                                 [("REOPEN-" + str(index).zfill(3),) for index in range(100)])
    client.batch_conn.commit()
    fingerprint, captured = BatchFacts.fingerprint, []

    def prepared(reader):
        value = SharedFacts(fingerprint(reader))
        captured.append(value)
        return value

    monkeypatch.setattr(BatchFacts, "fingerprint", prepared)
    first = list_data(client, query="REOPEN-", size=100)
    SharedFacts.equalities = 0
    second = list_data(client, query="REOPEN-", size=100)
    comparisons = SharedFacts.equalities
    assert len(first["data"]["entities"]) == len(second["data"]["entities"]) == 100
    assert captured[0] is not captured[1] and str(captured[0]) == str(captured[1])
    assert comparisons <= 2  # One lookup per read/write namespace, independent of 100 subjects.
    first_tokens = [row["write_context"]["write_token"] for row in first["data"]["entities"]]
    second_tokens = [row["write_context"]["write_token"] for row in second["data"]["entities"]]
    assert first_tokens == second_tokens
    assert first["data"]["create_context"]["write_token"] == second["data"]["create_context"]["write_token"]
    record_property("shared_facts_equalities", comparisons)
    record_property("tokens_reused", first_tokens == second_tokens)


def test_batch_import_preview_rejects_legacy_padded_batch_or_part_without_binding_trimmed_sibling(batch_client):
    from core.services.workbench.batch.files import WorkbenchBatchFileService
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService
    from tests.workbench.identity_metadata_support import insert_row

    client, conn = batch_client, batch_client.batch_conn
    insert_row(conn, "Batches", dict(batch_id=" B1 ", part_no="P1", quantity=5, part_name="spaced-batch",
                                     priority="normal", ready_status="no", status="pending"))
    insert_row(conn, "Parts", dict(part_no=" P1 ", part_name="spaced-part"))
    conn.commit()
    b1_ref = ref_for(client, key="B1")
    reader = WorkbenchBatchQueryService(conn)
    with reader.detached_read_snapshot():
        exported = WorkbenchBatchFileService.export(
            [row for row in reader.matched({}) if row["business_code"] == " B1 "]
        )
    service = WorkbenchBatchFileService(conn)
    upload = service.read(exported, "overwrite")
    preview_doc = service.preview("overwrite", upload)
    assert preview_doc["can_confirm"] is False
    row, = preview_doc["rows"]
    assert row["action"] == "rejected"
    assert row["entity_ref"] is None and row["entity_ref"] != b1_ref
    assert any("批次号或图号存在首尾空格，请先核对原记录。" in err for err in row["errors"])

    part_preview = service.preview("overwrite", ([{"row": 2, "values": {"批次号": "NEW-BATCH", "图号": " P1 ", "数量": 3}, "errors": []}], []))
    assert part_preview["can_confirm"] is False
    part_row, = part_preview["rows"]
    assert part_row["action"] == "rejected"
    assert any("批次号或图号存在首尾空格，请先核对原记录。" in err for err in part_row["errors"])


def test_batch_import_scope_rejects_duplicate_keys_and_non_finite_numbers(batch_client):
    from io import BytesIO

    for raw in ('{"page": 1, "page": 1}', '{"page": NaN}', '{"size": Infinity}', '{"size": 1e999}', '{"query": '):
        response = batch_client.post(BASE + "/import-preview", content_type="multipart/form-data", data={
            "file": (BytesIO(b"never parsed"), "batches.xlsx"), "mode": "overwrite", "scope": raw, "snapshot_ref": "x"})
        value = assert_error(response, "invalid_input", 400)
        assert value["error"]["message"] == "文件导入范围不对，文件还没有导入。请刷新页面后重新点「开始预检」。", raw


def test_strict_json_provider_rejects_duplicate_keys_and_non_finite_numbers_in_get_json(app_client):
    """create_app 挂上的严格 provider：request.get_json() 遇重复键或 NaN，与读不出的请求体同一条文案。"""
    for raw in ('{"request_key": "batch-provider-000001", "request_key": "batch-provider-000002", '
                '"write_token": "x", "input": {"preview_ref": "x"}}',
                '{"request_key": "batch-provider-000001", "write_token": "x", "input": {"preview_ref": NaN}}'):
        response = app_client.post(BASE + "/import-confirm", data=raw, content_type="application/json")
        value = assert_error(response, "invalid_input", 400)
        assert value["error"]["message"] == "提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。", raw


def test_strict_json_provider_refuses_to_write_non_finite_numbers(app_client):
    """同一个 provider 的输出端：合法数据原样写出，NaN / Infinity 直接报错，不写出非法 JSON。"""
    import json

    import pytest

    provider = app_client.application.json
    data = {"value": 1.5, "items": [0, None, False, ""]}
    assert json.loads(provider.dumps(data)) == data
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            provider.dumps({"value": value})
