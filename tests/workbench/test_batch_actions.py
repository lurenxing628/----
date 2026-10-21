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
            return clock[0]

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


def test_batch_qualification_uses_captured_skills_authorizations_and_supplier_bindings(batch_client, monkeypatch):
    from core.services.personnel.operator_qualification import OperatorQualificationService
    from data.repositories.supplier_repo import SupplierRepository

    client, conn = batch_client, batch_client.batch_conn
    conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='OT1'")
    conn.execute("UPDATE BatchOperations SET machine_id='M1',operator_id='O1' WHERE batch_id='FREE-001'")
    conn.commit()

    def reread(*_args, **_kwargs):
        raise AssertionError('Resource qualification facts were already captured.')

    monkeypatch.setattr(OperatorQualificationService, 'load', reread)
    monkeypatch.setattr(SupplierRepository, 'list_capabilities', reread)
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
    for index, use_primary in enumerate((True, False)):
        if not use_primary:
            conn.execute("UPDATE Suppliers SET op_type_id=NULL WHERE supplier_id='S1'")
            conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','OT1')")
            conn.commit()
        choices = client.get(BASE + '/choices', query_string={'batch_ref': ref_for(client), 'operation_ref': operation_ref}).get_json()['data']
        assert next(row for row in choices['suppliers'] if row['business_code'] == 'S1')['eligible']
        response = post(client, 'operation_update', {'operation_ref': operation_ref, 'fields': {'external_days': index + 2}}, key='captured-supplier-update-00' + str(index))
        assert response.status_code == 200, response.get_json()


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
            result = WorkbenchBatchBulkService(conn, reader=reader).apply({'action': 'update', 'refs': refs, 'patch': {'remark': 'prepared-bulk'}})
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
