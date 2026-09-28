"""Old candidates use their own frozen facts; missing current facts never authorize fallback."""

import copy
import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.migrations.v32 import run as upgrade_v32
from core.infrastructure.migrations.v33 import run as upgrade_v33
from core.infrastructure.snapshot_connection import ddl_columns
from core.infrastructure.workbench_metadata_schema import canonical_ddl_parts
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.contracts.external_context import context_group_key, context_problem
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.run.jobs_facts import capture_run_facts
from core.services.workbench.trial.archived_external_context import archived_contexts
from core.services.workbench.trial.base import _attach_original_context

EXTERNAL_IDS = frozenset((2, 3, 5, 6))


@pytest.fixture
def legacy_archive():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(Path(__file__).with_name("fixtures").joinpath("schema-v31.sql").read_text(encoding="utf-8"))
    upgrade_v32(conn)
    conn.execute("UPDATE SchemaVersion SET version=32 WHERE id=1")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('ARCH-P','归档零件')")
    conn.executemany("INSERT INTO Suppliers(supplier_id,name) VALUES (?,?)",
                     [("ARCH-S1", "第一次外协厂"), ("ARCH-S2", "第二次外协厂")])
    conn.executemany("""INSERT INTO ExternalGroups
        (group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) VALUES (?,'ARCH-P',?,?,?,?,?)""",
        [("ARCH-G1", 20, 25, "merged", 6.75, "ARCH-S1"), ("ARCH-G2", 40, 40, "separate", None, "ARCH-S2")])
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('ARCH-B','ARCH-P',3)")
    for seq, source, supplier, days, group in (
            (10, "internal", None, None, None), (20, "external", "ARCH-S1", 3.25, "ARCH-G1"),
            (25, "external", "ARCH-S1", 3.5, "ARCH-G1"), (30, "internal", None, None, None),
            (40, "external", "ARCH-S2", 2.25, "ARCH-G2"), (50, "external", "ARCH-S2", .25, None)):
        conn.execute("""INSERT INTO PartOperations
            (part_no,seq,op_type_name,source,supplier_id,ext_days,ext_group_id)
            VALUES ('ARCH-P',?,'归档工序',?,?,?,?)""", (seq, source, supplier, days, group))
        conn.execute("""INSERT INTO BatchOperations
            (op_code,batch_id,seq,op_type_name,source,supplier_id,ext_days)
            VALUES (?,'ARCH-B',?,'归档工序',?,?,?)""", ("ARCH-O" + str(seq), seq, source, supplier, days))
    conn.commit()
    digest, text = capture_run_facts(conn)
    capture = {"facts_hash": digest, "facts_text": text, "execution": []}
    yield conn, capture, stored_json(text)
    conn.close()


def _schema_row(facts, name):
    return next(row for row in facts["schema"] if row[:2] == ["table", name])


def _columns(facts, name):
    return ddl_columns(_schema_row(facts, name)[3], name, restricted=True)


def _change(facts, name, field, value, *, match=None):
    columns = _columns(facts, name)
    for row in facts["tables"][name]:
        if match is None or row[columns.index(match[0])] == match[1]:
            row[columns.index(field)] = value


def _without(facts, name, field, value):
    position = _columns(facts, name).index(field)
    facts["tables"][name] = [row for row in facts["tables"][name] if row[position] != value]


def _candidate_rows(capture):
    facts = GenerationFacts(capture)
    result = []
    for ref, operation_id in sorted(facts.operations.items(), key=lambda item: item[1]):
        if operation_id not in EXTERNAL_IDS:
            continue
        operation = facts.tables["BatchOperations"][operation_id]
        result.append({"operation_ref": ref, "original": {"operation": operation,
            "batch": facts.tables["Batches"][operation["batch_id"]]}})
    assert len(result) == len(EXTERNAL_IDS)
    return result


def test_real_frozen_v32_candidate_capture_decodes_two_stages_and_single_operation(legacy_archive):
    conn, capture, facts = legacy_archive
    verified = GenerationFacts(capture)
    assert verified.tables["BatchOperations"]
    assert conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 32
    assert "BatchExternalContexts" not in facts["tables"]
    assert "WorkbenchOutsourcingSourceConfirmations" in facts["tables"]
    before = copy.deepcopy(facts)
    contexts = archived_contexts(facts, EXTERNAL_IDS)
    assert [row["sequence"] for row in contexts] == [20, 25, 40, 50]
    assert facts == before
    assert all(row["origin"] == "archive_pre_v33" and row["captured_at"] is None for row in contexts)
    assert all("member_refs" not in row for row in contexts)
    first, continuation, second, single = contexts
    assert first["total_days"] == continuation["total_days"] == 6.75
    assert first["start_sequence"] == 20 and first["end_sequence"] == 25
    assert first["supplier_id"] == "ARCH-S1" and second["supplier_id"] == "ARCH-S2"
    assert second["merge_mode"] == "separate" and second["total_days"] is None
    assert single["group_id"] is None and single["group_ref"] is None and single["total_days"] is None
    assert context_group_key(first) == context_group_key(continuation)
    assert context_group_key(first) != context_group_key(second)
    for row in contexts:
        assert row["template_operation_ref"] == verified.entity_refs[("template_operation", str(row["template_operation_id"]))]
        assert context_problem(row, operation_id=row["operation_id"], part_no="ARCH-P", sequence=row["sequence"]) is None
    assert first["group_ref"] == verified.entity_refs[("template_external_group", "ARCH-G1")]


def test_upgrade_and_replacement_live_templates_do_not_change_old_capture(legacy_archive):
    conn, _, facts = legacy_archive
    expected = archived_contexts(facts, EXTERNAL_IDS)
    upgrade_v33(conn)
    conn.execute("UPDATE SchemaVersion SET version=33")
    conn.execute("UPDATE BatchExternalContexts SET total_days=99 WHERE group_id='ARCH-G1'")
    conn.execute("DELETE FROM PartOperations")
    conn.execute("DELETE FROM ExternalGroups")
    conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id)
        VALUES ('ARCH-G1','ARCH-P',20,20,'merged',42,'ARCH-S2')""")
    conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_name,source,ext_group_id)
        VALUES ('ARCH-P',20,'替代模板','external','ARCH-G1')""")
    conn.commit()
    live_ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='template_external_group' "
                            "AND entity_key='ARCH-G1' AND active=1").fetchone()[0]
    assert live_ref != expected[0]["group_ref"]
    assert archived_contexts(facts, EXTERNAL_IDS) == expected
    _, current_text = capture_run_facts(conn)
    assert archived_contexts(stored_json(current_text), EXTERNAL_IDS) is None


def test_non_external_missing_templates_do_not_block_and_empty_external_scope_is_proven(legacy_archive):
    _, _, facts = legacy_archive
    expected = archived_contexts(facts, EXTERNAL_IDS)
    for seq in (10, 30):
        _without(facts, "PartOperations", "seq", seq)
    assert archived_contexts(facts, EXTERNAL_IDS) == expected
    _change(facts, "BatchOperations", "source", "internal")
    facts["tables"]["PartOperations"] = []
    assert archived_contexts(facts, set()) == []


def test_unselected_external_missing_template_does_not_block_a_complete_selected_capture(legacy_archive):
    conn, _, original = legacy_archive
    expected = archived_contexts(original, EXTERNAL_IDS)
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('UNSELECTED-P','未选中零件')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('UNSELECTED-B','UNSELECTED-P',1)")
    cursor = conn.execute("""INSERT INTO BatchOperations
        (op_code,batch_id,seq,op_type_name,source,supplier_id,ext_days)
        VALUES ('UNSELECTED-O','UNSELECTED-B',20,'无模板外协','external','ARCH-S1',2)""")
    unselected_id = cursor.lastrowid
    conn.commit()
    digest, text = capture_run_facts(conn)
    GenerationFacts({"facts_hash": digest, "facts_text": text, "execution": []})
    captured = stored_json(text)
    assert archived_contexts(captured, EXTERNAL_IDS) == expected
    assert archived_contexts(captured, EXTERNAL_IDS | {unselected_id}) is None
    assert archived_contexts(captured, {unselected_id + 100}) is None


def test_unselected_external_missing_group_does_not_block_selected_stage(legacy_archive):
    conn, _, original = legacy_archive
    expected = archived_contexts(original, {2, 3})
    conn.execute("DELETE FROM ExternalGroups WHERE group_id='ARCH-G2'")
    conn.commit()
    _, text = capture_run_facts(conn)
    captured = stored_json(text)
    assert archived_contexts(captured, {2, 3}) == expected
    assert archived_contexts(captured, EXTERNAL_IDS) is None


def test_trial_base_attaches_archive_context_after_upgrade_despite_unselected_incomplete_batch(legacy_archive):
    conn, _, _ = legacy_archive
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('UNSELECTED-B','ARCH-P',1)")
    conn.execute("""INSERT INTO BatchOperations
        (op_code,batch_id,seq,op_type_name,source,supplier_id,ext_days)
        VALUES ('UNSELECTED-O','UNSELECTED-B',999,'未建模板的工序','external','ARCH-S1',2)""")
    conn.commit()
    digest, text = capture_run_facts(conn)
    capture = {"facts_hash": digest, "facts_text": text, "execution": []}
    rows = _candidate_rows(capture)
    upgrade_v33(conn)
    conn.execute("UPDATE SchemaVersion SET version=33")
    conn.execute("UPDATE ExternalGroups SET total_days=99 WHERE group_id='ARCH-G1'")
    conn.execute("UPDATE PartOperations SET ext_group_id=NULL, status='deleted'")
    conn.execute("UPDATE BatchExternalContexts SET total_days=88 WHERE group_id='ARCH-G1'")
    conn.commit()
    live = {"facts": {"tables": {name: [dict(row) for row in conn.execute("SELECT * FROM " + name)]
            for name in ("BatchExternalContexts", "BatchOperations", "PartOperations", "ExternalGroups")}}, "execution": {}}
    _attach_original_context(rows, {"capture": capture}, "candidate_ref", live)
    assert all(row["original"]["external_context_origin"] == "archive_pre_v33" for row in rows)
    assert rows[0]["original"]["external_group"]["total_days"] == 6.75
    assert rows[1]["original"]["external_group"]["total_days"] == 6.75
    assert rows[-1]["original"]["external_group"] is None
    assert capture["facts_text"] == text


@pytest.mark.parametrize("missing", ["table", "rows"])
def test_trial_base_rejects_current_archive_missing_context_even_with_complete_live_context(legacy_archive, missing):
    conn, _, _ = legacy_archive
    upgrade_v33(conn)
    conn.execute("UPDATE SchemaVersion SET version=33")
    live = {"facts": {"tables": {"BatchExternalContexts": [dict(row) for row in conn.execute("SELECT * FROM BatchExternalContexts")]}},
            "execution": {}}
    if missing == "table":
        conn.execute("DROP TABLE BatchExternalContexts")
    else:
        conn.execute("DELETE FROM BatchExternalContexts")
    conn.commit()
    digest, text = capture_run_facts(conn)
    capture = {"facts_hash": digest, "facts_text": text, "execution": []}
    rows = _candidate_rows(capture)
    with pytest.raises(WorkbenchCommandRejected) as error:
        _attach_original_context(rows, {"capture": capture}, "candidate_ref", live)
    assert error.value.code == "trial_base_incomplete"


@pytest.mark.parametrize("selected", [{999}, {1}, {True}, {None}, {"2"}])
def test_selected_ids_must_identify_captured_external_operations(legacy_archive, selected):
    _, _, facts = legacy_archive
    assert archived_contexts(facts, selected) is None


@pytest.mark.parametrize("version", [0, -1, 33, 34, None, True, "32", 32.0])
def test_unknown_or_current_versions_never_get_compatibility(legacy_archive, version):
    _, _, facts = legacy_archive
    _change(facts, "SchemaVersion", "version", version)
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("version", [1, 31, 32])
def test_supported_version_range_also_requires_the_archived_facts(legacy_archive, version):
    _, _, facts = legacy_archive
    _change(facts, "SchemaVersion", "version", version)
    assert len(archived_contexts(facts, EXTERNAL_IDS)) == 4


@pytest.mark.parametrize("problem", ["missing", "duplicate", "wrong_id", "boolean_id"])
def test_schema_version_must_be_one_real_integer_singleton(legacy_archive, problem):
    _, _, facts = legacy_archive
    if problem == "missing":
        facts["tables"]["SchemaVersion"] = []
    elif problem == "duplicate":
        facts["tables"]["SchemaVersion"] *= 2
    else:
        _change(facts, "SchemaVersion", "id", True if problem == "boolean_id" else 2)
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("evidence", ["table_rows", "table_ddl", "columns", "insert_trigger", "update_trigger", "renamed_trigger"])
def test_v33_objects_forbid_fallback_even_with_old_version(legacy_archive, evidence):
    _, _, facts = legacy_archive
    if evidence == "table_rows":
        facts["tables"]["BatchExternalContexts"] = []
    elif evidence == "columns":
        facts["columns"] = {"BatchExternalContexts": ["operation_id"]}
    elif evidence == "table_ddl":
        facts["schema"].append(["table", "BatchExternalContexts", "BatchExternalContexts",
                                "CREATE TABLE BatchExternalContexts(operation_id INTEGER)"])
    else:
        name = {"insert_trigger": "batch_external_context_created", "update_trigger": "batch_external_context_source_changed",
                "renamed_trigger": "renamed_capture"}[evidence]
        facts["schema"].append(["trigger", name, "BatchOperations", "CREATE TRIGGER " + name +
                                " AFTER INSERT ON BatchOperations BEGIN DELETE FROM BatchExternalContexts; END"])
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("version", [0, 32, 33])
def test_new_archive_with_missing_context_table_cannot_masquerade_as_old(legacy_archive, version):
    conn, _, _ = legacy_archive
    upgrade_v33(conn)
    conn.execute("UPDATE SchemaVersion SET version=?", (version,))
    conn.commit()
    _, text = capture_run_facts(conn)
    facts = stored_json(text)
    del facts["tables"]["BatchExternalContexts"]
    facts["schema"] = [row for row in facts["schema"] if row[1] != "BatchExternalContexts"]
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("name", ["SchemaVersion", "BatchOperations", "Batches", "PartOperations", "ExternalGroups", "WorkbenchEntityRefs"])
@pytest.mark.parametrize("missing", ["rows", "ddl"])
def test_missing_required_archive_tables_do_not_become_empty_facts(legacy_archive, name, missing):
    _, _, facts = legacy_archive
    if missing == "rows":
        del facts["tables"][name]
    else:
        facts["schema"].remove(_schema_row(facts, name))
    assert archived_contexts(facts, EXTERNAL_IDS) is None


def test_archived_column_order_is_used_and_optional_columns_must_agree(legacy_archive):
    _, _, facts = legacy_archive
    expected = archived_contexts(facts, EXTERNAL_IDS)
    name = "PartOperations"
    old_order = _columns(facts, name)
    pieces = canonical_ddl_parts(_schema_row(facts, name)[3])
    definitions = {piece.split(" ", 1)[0]: piece for piece in pieces if piece.split(" ", 1)[0] in old_order}
    constraints = [piece for piece in pieces if piece not in definitions.values()]
    order = old_order[3:] + old_order[:3]
    _schema_row(facts, name)[3] = "CREATE TABLE " + name + "(" + ",".join([definitions[key] for key in order] + constraints) + ")"
    facts["tables"][name] = [[row[old_order.index(key)] for key in order] for row in facts["tables"][name]]
    assert archived_contexts(facts, EXTERNAL_IDS) == expected
    required = ("SchemaVersion", "BatchOperations", "Batches", "PartOperations", "ExternalGroups", "WorkbenchEntityRefs")
    facts["columns"] = {table: _columns(facts, table) for table in required}
    assert archived_contexts(facts, EXTERNAL_IDS) == expected
    facts["columns"][name] = old_order
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("problem", ["width", "duplicate_ddl", "missing_column", "wrong_table", "extra_statement",
                                   "broken_catalog", "missing_trigger_sql", "empty_trigger_sql"])
def test_incomplete_or_unparseable_archived_schema_is_refused(legacy_archive, problem):
    _, _, facts = legacy_archive
    ddl = _schema_row(facts, "ExternalGroups")
    if problem == "width":
        facts["tables"]["ExternalGroups"][0].pop()
    elif problem == "duplicate_ddl":
        facts["schema"].append(copy.deepcopy(ddl))
    elif problem == "missing_column":
        ddl[3] = "CREATE TABLE ExternalGroups(group_id TEXT)"
    elif problem == "wrong_table":
        ddl[3] = ddl[3].replace("ExternalGroups", "ReplacementGroups")
    elif problem == "extra_statement":
        ddl[3] += "; CREATE TABLE unwanted(value TEXT)"
    elif problem in ("missing_trigger_sql", "empty_trigger_sql"):
        facts["schema"].append(["trigger", "unknown", "BatchOperations", None if problem == "missing_trigger_sql" else ""])
    else:
        facts["schema"].append(["trigger", "unknown"])
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("name,field,value,match", [
    ("BatchOperations", "batch_id", "missing", ("seq", 20)),
    ("BatchOperations", "seq", "20", ("seq", 20)),
    ("Batches", "part_no", "missing", None),
    ("PartOperations", "status", "deleted", ("seq", 20)),
    ("PartOperations", "ext_group_id", "missing", ("seq", 20)),
    ("PartOperations", "ext_group_id", {"sqlite_blob_base64": ""}, ("seq", 20)),
    ("ExternalGroups", "part_no", "other_part", ("group_id", "ARCH-G1")),
    ("ExternalGroups", "start_seq", 21, ("group_id", "ARCH-G1")),
    ("ExternalGroups", "end_seq", 19, ("group_id", "ARCH-G1")),
    ("ExternalGroups", "merge_mode", "unknown", ("group_id", "ARCH-G1")),
    ("ExternalGroups", "total_days", None, ("group_id", "ARCH-G1")),
    ("ExternalGroups", "total_days", 0, ("group_id", "ARCH-G1")),
    ("ExternalGroups", "total_days", "6.75", ("group_id", "ARCH-G1")),
])
def test_missing_or_conflicting_external_relationships_never_guess(legacy_archive, name, field, value, match):
    _, _, facts = legacy_archive
    _change(facts, name, field, value, match=match)
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("table,key,value", [("PartOperations", "seq", 20), ("ExternalGroups", "group_id", "ARCH-G1"),
                                           ("Batches", "batch_id", "ARCH-B")])
def test_missing_external_entities_refuse_the_whole_capture(legacy_archive, table, key, value):
    _, _, facts = legacy_archive
    _without(facts, table, key, value)
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("kind", ["template_operation", "template_external_group"])
@pytest.mark.parametrize("problem", ["missing", "inactive", "invalid_ref", "duplicate"])
def test_permanent_archive_identities_are_required_and_unambiguous(legacy_archive, kind, problem):
    _, _, facts = legacy_archive
    if problem == "missing":
        _without(facts, "WorkbenchEntityRefs", "kind", kind)
    elif problem == "inactive":
        _change(facts, "WorkbenchEntityRefs", "active", 0, match=("kind", kind))
    elif problem == "invalid_ref":
        _change(facts, "WorkbenchEntityRefs", "ref", "z" * 48, match=("kind", kind))
    else:
        columns = _columns(facts, "WorkbenchEntityRefs")
        row = next(row for row in facts["tables"]["WorkbenchEntityRefs"] if row[columns.index("kind")] == kind)
        facts["tables"]["WorkbenchEntityRefs"].append(copy.deepcopy(row))
    assert archived_contexts(facts, EXTERNAL_IDS) is None


@pytest.mark.parametrize("name", ["BatchOperations", "Batches", "PartOperations", "ExternalGroups"])
def test_duplicate_entities_are_not_silently_overwritten(legacy_archive, name):
    _, _, facts = legacy_archive
    facts["tables"][name].append(copy.deepcopy(facts["tables"][name][0]))
    assert archived_contexts(facts, EXTERNAL_IDS) is None
