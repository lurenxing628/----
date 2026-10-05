"""Real SQLite CRUD, fields, receipts, rollback, stale and capability boundaries."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import start_workflow
from tests.workbench.batch_support import (
    BASE,
    assert_error,
    batch_database,
    create_input,
    detail,
    list_data,
    post,
    ref_for,
    state,
)

_batch_fixture = batch_database


def test_reads_do_not_write_and_use_current_part_and_real_operation_refs(batch_client):
    client = batch_client
    before = state(client)
    result = list_data(client)
    record = detail(client)["data"]
    assert result["data"]["page"]["total"] == 2
    assert record["label"] == "part" and record["fields"]["quantity"] == 5
    assert record["operations"][0]["setup_hours"] is None and record["operations"][0]["unit_hours"] == 0
    expected = client.batch_conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND alternate_key='FREE-001_01'").fetchone()[0]
    assert record["operations"][0]["operation_ref"] == expected
    assert record["all_operations_complete"] is False
    assert state(client) == before


def test_create_empty_operations_then_replay_expired_token_and_conflict(batch_client):
    client = batch_client
    context = list_data(client)["data"]["create_context"]
    payload = create_input(client)
    first = post(client, "create", payload, context=context)
    assert first.status_code == 200, first.get_json()
    receipt = first.get_json()
    assert receipt["result"] == "committed" and not receipt["replayed"]
    row = detail(client, receipt["data"]["entity_ref"])["data"]
    assert row["operations"] == [] and row["fields"]["due_date"] is None
    before = state(client)
    again = post(client, "create", payload, context={"write_token": "expired"})
    assert again.get_json()["receipt_ref"] == receipt["receipt_ref"] and again.get_json()["replayed"]
    assert state(client) == before
    assert_error(post(client, "create", create_input(client, "OTHER"), context=context), "request_key_conflict", 409)
    assert state(client) == before


@pytest.mark.parametrize("field,bad", [("quantity", value) for value in (0, -1, None, True, 1.5, "2", 9007199254740992)] +
                         [("due_date", value) for value in ("2026-02-29", "2026-2-01", "", "2026-01-01T01:00:00", 0)] +
                         [("priority", None), ("ready_status", "bogus")])
def test_invalid_input_has_no_side_effect(batch_client, field, bad):
    payload = create_input(batch_client)
    payload["fields"][field] = bad
    before = state(batch_client)
    assert_error(post(batch_client, "create", payload), "invalid_input")
    assert state(batch_client) == before


def test_updates_only_sent_fields_preserve_all_other_tables_and_hidden_columns(batch_client):
    client = batch_client
    before = state(client)
    response = post(client, "update", {"fields": {"due_date": "2028-02-29", "remark": None}})
    assert response.status_code == 200, response.get_json()
    after = state(client)
    assert before[0] == after[0]
    for table in before[1]:
        if table not in ("Batches", "WorkbenchEntityRefs", "WorkbenchCommandReceipts"):
            assert before[1][table] == after[1][table], table
    row = client.batch_conn.execute("SELECT * FROM Batches WHERE batch_id='FREE-001'").fetchone()
    assert row["quantity"] == 5 and row["part_name"] == "historical-copy-name" and row["remark"] is None
    context = detail(client)["data"]["write_context"]
    first = post(client, "update", {"fields": {"due_date": None}}, key="batch-update-00000002", context=context)
    assert first.status_code == 200
    changed = state(client)
    assert_error(post(client, "update", {"fields": {"remark": "late"}}, key="batch-update-00000003", context=context), "stale_write")
    assert state(client) == changed


def test_hidden_fields_and_state_cannot_be_changed(batch_client):
    for fields in ({"part_name": "new"}, {"status": "completed"}, {"created_at": "old"}):
        before = state(batch_client)
        assert_error(post(batch_client, "update", {"fields": fields}), "invalid_input")
        assert state(batch_client) == before


def test_receipt_insert_failure_rolls_back_all_tables(batch_client, monkeypatch):
    from data.repositories.workbench_command_repo import WorkbenchCommandRepository

    def fail(*args, **kwargs):
        raise RuntimeError("fixture receipt failed")

    monkeypatch.setattr(WorkbenchCommandRepository, "insert", fail)
    before = state(batch_client)
    response = post(batch_client, "create", create_input(batch_client))
    assert response.status_code == 500 and response.get_json()["committed"] == "unknown"
    assert state(batch_client) == before
    assert batch_client.get("/api/workbench/v1/commands/batch-request-00000001").get_json()["state"] == "not_recorded"


def test_protected_delete_and_quantity_are_denied_without_cascades(batch_client):
    client, ref = batch_client, ref_for(batch_client, key="B1")
    record = detail(client, ref)["data"]
    assert not record["write_context"]["capabilities"]["batch.delete"]
    assert record["materials"]["requirements"][0]["available_quantity"] == 4.25
    before = state(client)
    assert_error(post(client, "delete", {}, ref=ref), "stale_write")
    assert_error(post(client, "update", {"fields": {"quantity": 3}}, ref=ref), "constraint_conflict")
    assert state(client) == before


def test_wrong_subject_wrong_action_deleted_ref_and_read_snapshot_stale(batch_client):
    client = batch_client
    old = list_data(client, size=1)
    wrong = detail(client, ref_for(client, key="B1"))["data"]["write_context"]
    before = state(client)
    assert_error(post(client, "update", {"fields": {"remark": "x"}}, context=wrong), "stale_write")
    assert_error(post(client, "delete", {}, context=old["data"]["create_context"]), "stale_write")
    assert state(client) == before
    ref = ref_for(client)
    assert post(client, "delete", {}).status_code == 200
    assert_error(client.get(BASE + "/" + ref), "entity_not_found", 404)
    assert_error(client.get(BASE, query_string={"page": 2, "size": 1, "snapshot_ref": old["meta"]["snapshot_ref"]}), "snapshot_stale")
    assert post(client, "create", create_input(client, "FREE-001"), key="batch-recreate-000001").status_code == 200
    assert ref_for(client) != ref


def test_unconfirmed_template_does_not_prevent_draft_batch_creation(batch_client):
    with TransactionManager(batch_client.batch_conn).transaction():
        start_workflow(batch_client.batch_conn, "P1")
    assert post(batch_client, "create", create_input(batch_client)).status_code == 200


def test_receipt_and_permanent_refs_survive_file_reopen(batch_client, tmp_path):
    import sqlite3

    from core.services.workbench.commands import WorkbenchCommandService
    from tests.workbench.process_workflow_support import stored_state

    client = batch_client
    result = post(client, "create", create_input(client)).get_json()
    expected = state(client)
    path = str(tmp_path / "batch-durable.sqlite3")
    with sqlite3.connect(path) as copy:
        client.batch_conn.backup(copy)
    with sqlite3.connect(path) as reopened:
        reopened.row_factory = sqlite3.Row
        assert stored_state(reopened) == expected
        receipt = WorkbenchCommandService(reopened).lookup("batch-request-00000001")
        assert receipt["receipt_ref"] == result["receipt_ref"] and receipt["data"] == result["data"]
        assert reopened.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='NEW-001' AND active=1").fetchone()[0] == result["data"]["entity_ref"]


def test_delete_preserves_every_unrelated_table_and_other_batch(batch_client):
    client = batch_client
    batch_ref = ref_for(client)
    operation = dict(client.batch_conn.execute("SELECT * FROM BatchOperations WHERE batch_id='FREE-001'").fetchone())
    operation_ref = client.batch_conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND source_key=?",
                                            (str(operation["id"]),)).fetchone()[0]
    before = state(client)
    assert post(client, "delete", {}).status_code == 200
    after = state(client)
    assert after[0] == before[0]
    affected = {"Batches", "BatchOperations", "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "WorkbenchPlanIdentityClock",
                "WorkbenchCommandReceipts", "WorkbenchTemplateLineageEvents", "sqlite_sequence"}
    for table in before[1]:
        if table not in affected:
            assert before[1][table] == after[1][table], table
    assert after[1]["Batches"] == [row for row in before[1]["Batches"] if row[0] != "FREE-001"]
    assert after[1]["BatchOperations"] == [row for row in before[1]["BatchOperations"] if row[0] != operation["id"]]
    for table, retired_ref in (("WorkbenchEntityRefs", batch_ref), ("WorkbenchPlanSourceRefs", operation_ref)):
        columns = [row[1] for row in client.batch_conn.execute('PRAGMA table_info("' + table + '")')]
        expected = []
        for row in before[1][table]:
            record = dict(zip(columns, row))
            if record["ref"] == retired_ref:
                record["active"] = 0
                if table == "WorkbenchEntityRefs":
                    record["revision"] += 1
            expected.append(tuple(record[column] for column in columns))
        assert after[1][table] == expected, table
    assert after[1]["WorkbenchPlanIdentityClock"] == [(1, before[1]["WorkbenchPlanIdentityClock"][0][1] + 1)]
    receipts = before[1]["WorkbenchCommandReceipts"]
    assert after[1]["WorkbenchCommandReceipts"][:-1] == receipts
    receipt = dict(client.batch_conn.execute("SELECT * FROM WorkbenchCommandReceipts WHERE request_key='batch-request-00000001'").fetchone())
    assert receipt["action"] == "batch.delete" and receipt["context_ref"] == batch_ref
    events = before[1]["WorkbenchTemplateLineageEvents"]
    assert after[1]["WorkbenchTemplateLineageEvents"][:-1] == events
    retired = dict(client.batch_conn.execute("SELECT * FROM WorkbenchTemplateLineageEvents ORDER BY event_id DESC LIMIT 1").fetchone())
    assert retired["operation_ref"] == operation_ref and retired["event_type"] == "retired"
    assert retired["affects_calibration"] == 1 and retired["batch_ref"] == batch_ref
    for column, value in operation.items():
        assert retired[column] == value, column
    before_seq, after_seq = dict(before[1]["sqlite_sequence"]), dict(after[1]["sqlite_sequence"])
    assert after_seq.pop("WorkbenchTemplateLineageEvents") == before_seq.pop("WorkbenchTemplateLineageEvents") + 1
    assert after_seq == before_seq
    assert client.batch_conn.execute("SELECT quantity,part_name FROM Batches WHERE batch_id='B1'").fetchone()[:] == (17, "historical-name")
    assert client.batch_conn.execute("SELECT COUNT(*) FROM Schedule WHERE op_id=31").fetchone()[0] == 1


def _confirm_request(client, command):
    from tests.workbench.test_batch_actions import confirm, sync_preview

    if command == "split_confirm":
        from tests.workbench.test_batch_quantity_split import prepare, preview

        prepare(client)
        proposal = preview(client)
        return lambda: confirm(client, proposal, path="/" + ref_for(client) + "/split-confirm", key="batch-split-load-00001")
    if command == "sync_confirm":
        # This case counts reads for a valid template update, including outsourcing.
        client.batch_conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id IN "
                                  "(SELECT op_type_id FROM PartOperations WHERE part_no='P1' AND source='external')")
        client.batch_conn.commit()
        response = sync_preview(client)
        path = "/" + ref_for(client) + "/sync-confirm"
    elif command == "import_confirm":
        from tests.workbench.test_batch_files import uploaded

        response = uploaded(client, [["FREE-002", "P1", 4, None, None, None, None, None], ["FREE-003", "P1", 5, None, None, None, None, None]])
        path = "/import-confirm"
    else:
        action = command[len("bulk_"):]
        codes = ["FREE-002", "FREE-003"] if action == "delete" else ["FREE-001", "FREE-002"]
        data = {"action": action, "refs": [ref_for(client, key=code) for code in codes], **({"patch": {"remark": "x"}} if action == "update" else {})}
        response = client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": list_data(client)["meta"]["snapshot_ref"], "input": data})
        path = "/bulk-confirm"
    assert response.status_code == 200, response.get_json()
    return lambda: confirm(client, response.get_json()["data"], path=path, key="batch-confirm-load-0001")


def _command_request(client, command):
    if command.endswith("_confirm") or command.startswith("bulk_"):
        return _confirm_request(client, command)
    conn = client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    if command == "create":
        context = list_data(client)["data"]["create_context"]
        return lambda: post(client, "create", create_input(client), key="batch-command-load-001", context=context)
    operation = detail(client)["data"]["operations"][0]["ref"]
    action, payload = {"update_quantity": ("update", {"fields": {"quantity": 6}}), "update_remark": ("update", {"fields": {"remark": "x"}}),
                       "delete": ("delete", {}), "materials_update": ("materials_update", {"removed_keys": [], "rows": [{"row_key": None,
                           "material_ref": ref_for(client, "material", "MAT1"), "required_quantity": 5, "available_quantity": 1}]}),
                       "operation_update": ("operation_update", {"operation_ref": operation, "fields": {
                           "machine_ref": ref_for(client, "machine", "M1"), "operator_ref": ref_for(client, "operator", "O1")}})}[command]
    context = detail(client)["data"]["write_context"]
    return lambda: post(client, action, payload, key="batch-command-load-001", context=context)


@pytest.mark.parametrize("command,loads", [
    ("create", 1), ("update_quantity", 1), ("update_remark", 1), ("delete", 1), ("materials_update", 1), ("operation_update", 1),
    ("split_confirm", 1), ("sync_confirm", 1), ("bulk_update", 1), ("bulk_copy", 1),
    # 删多批、文件导入在第一次写入前就校验完全部行，写入过程中不再逐行重读整本批次数据。
    ("bulk_delete", 1), ("import_confirm", 1)])
def test_commands_reuse_the_guard_load_until_their_own_first_write(batch_client, monkeypatch, command, loads):
    from core.services.workbench.batch.facts import BatchFacts
    from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository

    conn = batch_client.batch_conn
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-002','P1',2),('FREE-003','P1',3)")
    conn.commit()
    send = _command_request(batch_client, command)
    original_tables, original_load, seen = WorkbenchBatchFactsRepository.whole_tables, BatchFacts.load, []

    def whole_tables(repo):
        assert repo.conn.in_transaction
        seen.append(True)
        return original_tables(repo)

    def load(reader):
        facts = original_load(reader)
        # A reload must not leave an index that still holds the previous ledger alive.
        assert all(entry[0] is facts for entry in reader._lookups.values())
        return facts

    monkeypatch.setattr(WorkbenchBatchFactsRepository, "whole_tables", whole_tables)
    monkeypatch.setattr(BatchFacts, "load", load)
    response = send()
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["result"] == "committed"
    assert len(seen) == loads


def _count_relation_indexes(monkeypatch):
    from core.services.workbench.batch import facts as batch_facts

    original, built = batch_facts._index_outsourcing_receipts, []

    def counted(facts, result):
        built.append(facts)
        return original(facts, result)

    # Called exactly once per index_relations, whichever module imported it.
    monkeypatch.setattr(batch_facts, "_index_outsourcing_receipts", counted)
    return built


@pytest.mark.parametrize("command", ["split_confirm", "bulk_update", "bulk_copy", "bulk_delete", "import_confirm"])
def test_confirms_build_the_relations_index_once(batch_client, monkeypatch, command):
    """确认时预检投影已按同一份数据建好关联索引：删除校验、导入改数量和复制都沿用它，不按同一份数据再建。"""
    conn = batch_client.batch_conn
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-002','P1',2),('FREE-003','P1',3)")
    conn.commit()
    send = _command_request(batch_client, command)
    built = _count_relation_indexes(monkeypatch)
    response = send()
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["result"] == "committed"
    assert len(built) == 1


def test_bulk_delete_and_import_previews_build_the_relations_index_once(batch_client, monkeypatch):
    from core.services.workbench.batch.bulk import WorkbenchBatchBulkService
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.file_preview import BatchImportPreview

    conn = batch_client.batch_conn
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-002','P1',2),('FREE-003','P1',3)")
    conn.commit()
    refs = [ref_for(batch_client, key=code) for code in ("FREE-002", "FREE-003")]
    built = _count_relation_indexes(monkeypatch)
    plan = WorkbenchBatchBulkService(conn).plan({"action": "delete", "refs": refs})
    assert plan["count"] == 2 and len(built) == 1
    facts = BatchFacts(conn).load()
    del built[:]
    preview = BatchImportPreview(facts, "replace")
    # 替换模式：改数量的校验和整份删除清单都用投影那一份索引。
    preview._readiness({"quantity": 9}, next(row for row in facts["Batches"] if row["batch_id"] == "FREE-002"))
    deleted = preview.deleted()
    assert len(deleted) == len(facts["Batches"]) and len(built) == 1 and built[0] is facts


def test_command_snapshot_is_dropped_by_own_writes_and_transaction_end(batch_client):
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService

    conn = batch_client.batch_conn
    ref = ref_for(batch_client)
    reader = WorkbenchBatchQueryService(conn)
    with reader.command_snapshot():
        assert reader.load() is not reader.load()
        with TransactionManager(conn).transaction(begin_immediate=True):
            first = reader.load()
            assert reader.load() is first and reader.batch(ref)["remark"] == "keep-hidden"
            assert reader._lookups and all(entry[0] is first for entry in reader._lookups.values())
            conn.execute("UPDATE Batches SET remark='own-write' WHERE batch_id='FREE-001'")
            assert reader.batch(ref)["remark"] == "own-write" and reader._lookups == {}
            second = reader.load()
            assert second is not first and reader.load() is second
            assert reader.batch(ref)["remark"] == "own-write" and all(entry[0] is second for entry in reader._lookups.values())
            assert next(row for row in second["Batches"] if row["batch_id"] == "FREE-001")["remark"] == "own-write"
        assert reader.load() is not second and reader._facts is None
        with TransactionManager(conn).transaction(begin_immediate=True):
            pinned = reader.load()
    assert pinned is not second and reader._facts is None and not reader._command
