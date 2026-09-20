"""合同测试：SQL 排水第二批（plan / trial / piece 簇）新增的仓储方法。

锁定每个方法的 SQL 语义：有界整计划读取、交付风险事实、采用基线原值读取与来源白名单、
试调整表原值快照与簿记表拒绝、试调采用历史事实、分件采用当前原始行。服务层不再持 conn
直接读这些表；裁决（reject/fail/上限）仍留在服务层。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date

import pytest

from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench.run.candidate_adoption_constraints import _TABLES as CONSTRAINT_TABLES
from data.repositories.workbench_piece_adoption_repo import (
    PREFLIGHT_TABLES,
    TEMPLATE_TABLES,
    WorkbenchPieceAdoptionRepository,
)
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from data.repositories.workbench_plan_delivery_repo import WorkbenchPlanDeliveryRepository
from data.repositories.workbench_trial_adoption_history import TrialAdoptionHistoryRepository
from data.repositories.workbench_trial_catalog_repo import WorkbenchTrialCatalogRepository
from data.repositories.workbench_trial_query_repo import BOOKKEEPING_TABLES, WorkbenchTrialQueryRepository
from data.repositories.workbench_trial_raw_repo import WorkbenchTrialRawPlanRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.plan_catalog_support import candidate, history, scenario, seed_operation
from tests.workbench.process_query_support import seed_process

SCHEDULE_COLUMNS = ["id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version", "created_at"]
SECOND_START, SECOND_END = "2026-09-10 08:00:00", "2026-09-10 09:00:00"
RECEIPT = ("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) "
           "VALUES (?,?,?,?,'" + "0" * 64 + "','{}')")
# 永久引用一律 48 位十六进制；request_key 至少 16 字符；receipt_ref 32 位十六进制。
DRAFT, PLAN, ROW, TASK = "d" * 48, "e" * 48, "1" * 48, "2" * 48
SCENARIO, SROW, STASK, RUN, CANDIDATE = "3" * 48, "4" * 48, "5" * 48, "6" * 48, "7" * 48
REQ_CREATE, REQ_SAVE, REQ_RUN = "req-create-00000001", "req-save-0000000001", "req-run-00000000001"


def _seed_plan(conn):
    """一个批次两道工序；正式 v1 两行安排；一个候选角色；一个基于正式计划的活动试调方案。"""
    op1 = seed_operation(conn)
    op2 = conn.execute("INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) "
                       "VALUES ('CAT-OP2', 'CAT-B', 2, 'Second op')").lastrowid
    conn.execute("UPDATE Batches SET due_date='2026-09-25' WHERE batch_id='CAT-B'")
    history(conn, 1, summary='{"source": "seed"}', op_id=op1)
    conn.execute("INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (1, ?, ?, ?)", (op2, SECOND_START, SECOND_END))
    cand = candidate(conn, 1, "critical_best", op_id=op1)
    scenario(conn, "SCN-1", 1, op_id=op1)
    return op1, op2, cand


def _seed_trial(conn, operation_ref):
    """一份草稿、一行原始行、一个已保存方案及其一行永久明细，外加建/存两张回执与一次运行。"""
    conn.execute(RECEIPT, (REQ_CREATE, "a" * 32, "trial.create", PLAN))
    conn.execute(RECEIPT, (REQ_SAVE, "b" * 32, "trial.save", DRAFT))
    conn.execute(RECEIPT, (REQ_RUN, "c" * 32, "scheduling.run", RUN))
    conn.execute("INSERT INTO WorkbenchTrialDrafts(draft_ref,base_kind,base_ref,admission_json,admission_hash,row_count,"
                 "revision,status,validation_json,created_at,updated_at,local_operator,request_key) "
                 "VALUES (?,'plan_ref',?,'{\"input\": 1}','ah',1,1,'editing','{}','t0','t0','op',?)", (DRAFT, PLAN, REQ_CREATE))
    conn.execute("INSERT INTO WorkbenchTrialRows(row_ref,task_ref,draft_ref,operation_ref,source_task_ref,source_row_ref,"
                 "ordinal,original_json,original_hash,current_json) VALUES (?,?,?,?,NULL,'src-1',0,'{}','oh','{}')",
                 (ROW, TASK, DRAFT, operation_ref))
    conn.execute("INSERT INTO WorkbenchTrialScenarios(scenario_ref,draft_ref,name,revision,snapshot_json,snapshot_hash,"
                 "saved_at,local_operator,request_key) VALUES (?,?,'Saved',1,'{}','sh','t1','op',?)", (SCENARIO, DRAFT, REQ_SAVE))
    conn.execute("INSERT INTO WorkbenchTrialScenarioRows(row_ref,task_ref,scenario_ref,source_row_ref,payload_json) "
                 "VALUES (?,?,?,?,'{\"a\":1}')", (SROW, STASK, SCENARIO, ROW))
    conn.execute("INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,facts_hash,facts_json,"
                 "execution_json,baseline_json,accepted_at,state,stage,executor_ref,started_at) "
                 "VALUES (?,?,'in-1','{}','h','{}','{}','{}','t0','running','computing','exec-1','t0')", (RUN, REQ_RUN))
    conn.execute("INSERT INTO WorkbenchRunCandidates(candidate_ref,run_ref,candidate_key,sequence,status,task_count,artifact_json) "
                 "VALUES (?,?,'k',1,'completed',0,'{}')", (CANDIDATE, RUN))


def _source_ref(conn, kind, key):
    return conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind=? AND source_key=? AND active=1",
                        (kind, str(key))).fetchone()[0]


def _schedule_ids(conn):
    return [row[0] for row in conn.execute("SELECT id FROM Schedule WHERE version=1 ORDER BY id")]


# ---------------------------------------------------------------- catalog bounded reads
def test_catalog_bounded_plan_reads(schema_conn) -> None:
    op1, op2, cand = _seed_plan(schema_conn)
    repo = WorkbenchPlanCatalogRepository(schema_conn)
    ids = _schedule_ids(schema_conn)
    official = {"version": 1, "source_table": "schedule", "candidate_id": None}

    assert [row["id"] for row in repo.list_plan_row_ids_bounded(limit=5, **official)] == ids
    assert len(repo.list_plan_row_ids_bounded(limit=1, **official)) == 1, "LIMIT 逐字传入"
    rows = repo.list_plan_rows_bounded(limit=5, **official)
    assert [row["op_id"] for row in rows] == [op1, op2]
    assert set(rows[0]) == {"id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version"}

    detail = repo.list_detail_rows_bounded(limit=5, **official)
    assert [(row["schedule_id"], row["op_id"], row["batch_id"]) for row in detail] == [(ids[0], op1, "CAT-B"), (ids[1], op2, "CAT-B")]
    ranged = repo.list_detail_rows_bounded(range_start="2026-09-10T08:30:00", range_end="2026-09-10T10:00:00", limit=5, **official)
    assert [row["op_id"] for row in ranged] == [op2], "时间窗只捞重叠行"
    assert repo.list_detail_rows_bounded(range_start="2026-09-11T00:00:00", range_end="2026-09-12T00:00:00", limit=5, **official) == []

    assert [row["op_id"] for row in repo.list_plan_rows_bounded(version=1, source_table="candidate_rows", candidate_id=cand, limit=5)] == [op1]
    scenario_ids = repo.list_plan_row_ids_bounded(version=1, source_table="adjustment_scenario_rows", candidate_id=None,
                                                  scenario_id="SCN-1", limit=5)
    assert len(scenario_ids) == 1
    with pytest.raises(ValueError):
        repo.list_plan_row_ids_bounded(version=1, source_table="candidate_rows", candidate_id=None, limit=5)

    raw = WorkbenchTrialRawPlanRepository(schema_conn).list_detail_rows_bounded(limit=5, **official)
    assert [row["op_id"] for row in raw] == [op1, op2] and raw[0]["due_date"] == "2026-09-25", "原值子类沿用同一 SQL"


# ---------------------------------------------------------------- delivery facts
def test_delivery_repository_facts(schema_conn) -> None:
    op1, op2, cand = _seed_plan(schema_conn)
    repo = WorkbenchPlanDeliveryRepository(schema_conn)
    ids = _schedule_ids(schema_conn)
    official = {"version": 1, "source_table": "schedule", "candidate_id": None, "scenario_id": None}

    binding = repo.get_scenario_binding("SCN-1")
    assert set(binding) == {"scenario_id", "base_version", "base_plan_role", "base_source_table", "base_candidate_id",
                            "base_candidate_key", "status", "validation_status", "row_count", "issues_json"}
    assert (binding["status"], binding["base_version"]) == ("active", 1)
    assert repo.get_scenario_binding("NOPE") is None

    assert [row["id"] for row in repo.list_task_ids_bounded(limit=5, **official)] == ids
    assert len(repo.list_task_ids_bounded(limit=1, **official)) == 1
    exact = {"version": 1, "source_table": "adjustment_scenario_rows", "candidate_id": None}
    assert len(repo.list_task_ids_bounded(scenario_id="SCN-1", limit=5, **exact)) == 1
    assert repo.list_task_ids_bounded(scenario_id=" SCN-1 ", limit=5, **exact) == [], "永久键逐字比较，不做 strip"
    assert len(WorkbenchPlanCatalogRepository(schema_conn).list_plan_row_ids_bounded(scenario_id=" SCN-1 ", limit=5, **exact)) == 1

    rows = repo.list_task_rows_with_batch(**official)
    assert [(row["schedule_id"], row["op_id"], row["batch_id"]) for row in rows] == [(ids[0], op1, "CAT-B"), (ids[1], op2, "CAT-B")]
    assert set(rows[0]) == {"schedule_id", "version", "op_id", "start_time", "end_time", "machine_id", "operator_id", "batch_id"}
    assert rows[1]["start_time"] == SECOND_START and type(rows[1]["start_time"]) is str

    batches = repo.list_batches_by_ids(["NOPE", "CAT-B"])
    assert batches == [{"batch_id": "CAT-B", "part_no": "CAT-P", "part_name": None, "due_date": "2026-09-25"}]
    operations = repo.list_batch_operations_by_ids(["CAT-B"], limit=5)
    assert [(row["op_id"], row["seq"]) for row in operations] == [(op1, 1), (op2, 2)]
    assert set(operations[0]) == {"op_id", "batch_id", "seq", "piece_id"}
    assert len(repo.list_batch_operations_by_ids(["CAT-B"], limit=1)) == 1

    assert repo.get_candidate_summary(1, cand) == {"summary_json": None}
    assert repo.get_candidate_summary(1, cand + 99) is None


# ---------------------------------------------------------------- adoption baseline evidence
def test_baseline_repository_raw_reads_and_lineage_facts(schema_conn) -> None:
    op1, op2, _ = _seed_plan(schema_conn)
    _seed_trial(schema_conn, _source_ref(schema_conn, "operation", op1))
    repo = WorkbenchPlanBaselineRepository(schema_conn)
    ids = _schedule_ids(schema_conn)
    official_ref = _source_ref(schema_conn, "official", 1)

    rows = repo.raw_schedule_rows_by_version(1, limit=5)
    assert [list(row) for row in rows] == [SCHEDULE_COLUMNS, SCHEDULE_COLUMNS], "列名来自 pragma_table_info，顺序逐列"
    assert [(row["id"], row["op_id"], row["version"]) for row in rows] == [(ids[0], op1, 1), (ids[1], op2, 1)]
    assert len(repo.raw_schedule_rows_by_version(1, limit=1)) == 1
    assert repo.raw_schedule_rows_by_version(9, limit=5) == []

    row_refs = [_source_ref(schema_conn, "schedule_row", key) for key in ids]
    live = repo.raw_source_refs_by_refs(row_refs)
    assert sorted(row["ref"] for row in live) == sorted(row_refs)
    assert "active" in live[0] and "operation_ref" in live[0]
    tasks = repo.raw_task_refs_by_plan(official_ref)
    assert len(tasks) == 2 and set(tasks[0]) == {"ref", "plan_ref", "row_ref"}
    assert {row["row_ref"] for row in tasks} == set(row_refs)
    assert repo.raw_task_refs_by_plan("nope") == []

    assert repo.source_exists("WorkbenchRunJobs", "run_ref", RUN) is True
    assert repo.source_exists("WorkbenchRunCandidates", "candidate_ref", CANDIDATE) is True
    assert repo.source_exists("WorkbenchTrialScenarios", "scenario_ref", SCENARIO) is True
    assert repo.source_exists("WorkbenchTrialDrafts", "draft_ref", "9" * 48) is False
    with pytest.raises(ValueError):
        repo.source_exists("Batches", "batch_id", "CAT-B")

    assert repo.list_scenario_row_bindings(SCENARIO) == [(SROW, STASK, ROW)]
    assert repo.list_scenario_row_bindings("nope") == []
    assert repo.history_version_exists(1) is True and repo.history_version_exists(9) is False
    assert repo.get_history_result_summary(1) == {"result_summary": '{"source": "seed"}'}
    assert repo.get_history_result_summary(9) is None
    assert set(repo.list_task_refs_by_plan(official_ref)) == {row["ref"] for row in tasks}
    assert repo.list_schedule_identity_rows(1) == [{"schedule_id": ids[0], "op_id": op1, "version": 1},
                                                   {"schedule_id": ids[1], "op_id": op2, "version": 1}]


# ---------------------------------------------------------------- trial raw snapshots and identity facts
def test_trial_query_repository_whole_tables_and_refs(schema_conn) -> None:
    op1, op2, _ = _seed_plan(schema_conn)
    repo = WorkbenchTrialQueryRepository(schema_conn)
    assert BOOKKEEPING_TABLES >= set(TRIAL_TABLES + RUN_TABLES) | {"WorkbenchCommandReceipts", "OperationLogs", "sqlite_sequence"}

    columns, rows = repo.read_whole_table("Batches")
    assert columns[:2] == ["batch_id", "part_no"] and [row["batch_id"] for row in rows] == ["CAT-B"]
    schema_conn.execute('CREATE TABLE "CQ ""raw" ("day ""name" DATE, n INTEGER)')
    schema_conn.execute('INSERT INTO "CQ ""raw" VALUES (?,?)', ("2026-09-09", 7))
    assert WorkbenchTrialQueryRepository(schema_conn).read_whole_table('CQ "raw') == (['day "name', "n"], [{'day "name': "2026-09-09", "n": 7}])
    for name in ("WorkbenchTrialDrafts", "WorkbenchRunJobs", "sqlite_sequence", "NoSuchTable"):
        with pytest.raises(ValueError):
            repo.read_whole_table(name)

    assert [row["id"] for row in repo.raw_batch_operations()] == [op1, op2]
    assert [row["batch_id"] for row in repo.raw_batches()] == ["CAT-B"]
    assert [row["part_no"] for row in repo.raw_parts()] == ["CAT-P"]
    assert {(row["kind"], row["entity_key"]) for row in repo.raw_entity_refs()} >= {("batch", "CAT-B"), ("part", "CAT-P")}
    assert [row["op_id"] for row in repo.raw_schedule()] == [op1, op2]
    assert [row["op_id"] for row in repo.raw_candidate_rows()] == [op1]
    assert [(row["scenario_id"], row["op_id"]) for row in repo.raw_scenario_rows()] == [("SCN-1", op1)]

    assert {int(row["source_key"]): row["ref"] for row in repo.active_operation_source_refs()} == {
        op1: _source_ref(schema_conn, "operation", op1), op2: _source_ref(schema_conn, "operation", op2)}
    assert {int(row["source_key"]) for row in repo.active_source_refs_by_kind("schedule_row")} == set(_schedule_ids(schema_conn))
    assert repo.active_source_refs_by_kind("nope") == []

    assert repo.official_rows_without_history_exist() is False
    schema_conn.execute("INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (7, ?, ?, ?)", (op1, SECOND_START, SECOND_END))
    assert repo.official_rows_without_history_exist() is True


def test_raw_reads_bypass_connection_converters(db_path) -> None:
    from core.infrastructure.database import get_connection

    with closing(sqlite3.connect(db_path)) as seed:
        seed.execute("PRAGMA foreign_keys=ON")
        _seed_plan(seed)
        seed.commit()
    with closing(get_connection(db_path)) as conn:
        assert type(conn.execute("SELECT due_date FROM Batches").fetchone()[0]) is date, "生产连接开着 DECLTYPES 转换"
        rows = WorkbenchPlanBaselineRepository(conn).raw_schedule_rows_by_version(1, limit=5)
        assert [(type(row["start_time"]), type(row["version"])) for row in rows] == [(str, int), (str, int)]
        batches = WorkbenchTrialQueryRepository(conn).raw_batches()
        assert (type(batches[0]["due_date"]), batches[0]["due_date"]) == (str, "2026-09-25")
        assert conn.total_changes == 0


# ---------------------------------------------------------------- trial adoption history / storage
def test_trial_adoption_history_and_scenario_header_facts(schema_conn) -> None:
    op1, _, _ = _seed_plan(schema_conn)
    _seed_trial(schema_conn, _source_ref(schema_conn, "operation", op1))
    repo = TrialAdoptionHistoryRepository(schema_conn)

    assert repo.scenario_row_sizes(SCENARIO) == [len('{"a":1}')]
    assert repo.scenario_row_sizes("nope") == []
    assert repo.draft_admission(DRAFT) == {"admission_json": '{"input": 1}'}
    assert repo.draft_admission("9" * 48) is None
    assert repo.receipt_action(REQ_CREATE) == ("trial.create", PLAN)
    assert repo.receipt_action("req-nope") is None

    header = WorkbenchTrialRepository(schema_conn).scenario_header(SCENARIO)
    assert set(header) == {"scenario_ref", "draft_ref", "name", "revision", "snapshot_json", "snapshot_hash", "saved_at",
                           "local_operator", "request_key"}
    assert (header["name"], header["draft_ref"]) == ("Saved", DRAFT)
    assert WorkbenchTrialRepository(schema_conn).scenario_header("nope") is None


def test_trial_repository_fact_methods_never_rule(schema_conn) -> None:
    """仓储只回草稿头 / 行数 / 原始行 / 永久明细事实；缺失回 None / 0 / []，裁决在 trial_policy。"""
    op1, _, _ = _seed_plan(schema_conn)
    _seed_trial(schema_conn, _source_ref(schema_conn, "operation", op1))
    repo = WorkbenchTrialRepository(schema_conn)

    assert repo.schema_issues() == []
    head = repo.draft_header(DRAFT)
    assert (head["draft_ref"], head["row_count"], head["admission_json"], head["status"]) == (DRAFT, 1, '{"input": 1}', "editing")
    assert repo.draft_header("nope") is None
    assert repo.draft_row_count(DRAFT) == 1 and repo.draft_row_count("nope") == 0
    rows = repo.draft_rows(DRAFT)
    assert [(row["row_ref"], row["ordinal"], row["original_json"], row["current_json"]) for row in rows] == [(ROW, 0, "{}", "{}")]
    assert repo.draft_rows("nope") == []
    assert repo.scenario_rows(SCENARIO) == [{"row_ref": SROW, "payload_json": '{"a":1}'}]
    assert repo.scenario_rows("nope") == []


def test_adoption_history_bounded_fact_methods(schema_conn) -> None:
    """目录扫描按 request_key 升序读 LIMIT 行；回执 / 历史 / 场景头只回字节数，不读大 JSON，也不裁决。"""
    op1, _, _ = _seed_plan(schema_conn)
    _seed_trial(schema_conn, _source_ref(schema_conn, "operation", op1))
    repo = TrialAdoptionHistoryRepository(schema_conn)

    assert not isinstance(repo.receipt_headers(10), list), "目录扫描流式产出，不整体物化"
    assert [row["request_key"] for row in repo.receipt_headers(10)] == [REQ_CREATE, REQ_RUN, REQ_SAVE]
    assert [row["request_key"] for row in repo.receipt_headers(2)] == [REQ_CREATE, REQ_RUN], "LIMIT 逐字传入"
    assert set(next(repo.receipt_headers(1))) == {"request_key", "action", "context_ref"}
    assert repo.receipt_size(REQ_SAVE) == {"bytes": 2} and repo.receipt_size("req-nope") is None
    assert repo.receipt_row(REQ_SAVE)["action"] == "trial.save" and repo.receipt_row("req-nope") is None
    heads = repo.history_heads(1)
    assert len(heads) == 1 and heads[0]["bytes"] == len('{"source": "seed"}')
    assert repo.history_heads(99) == []
    assert set(repo.history_row(heads[0]["id"])) == {"id", "version", "result_status", "result_summary", "created_by"}
    assert repo.history_row(-1) is None
    header = repo.sized_scenario_header(SCENARIO)
    assert header["bytes"] == 2 and "snapshot_json" not in header and header["draft_ref"] == DRAFT
    assert repo.sized_scenario_header("nope") is None
    draft = repo.sized_draft_header(DRAFT)
    assert draft["bytes"] == len('{"input": 1}') and "admission_json" not in draft and draft["status"] == "editing"
    assert repo.sized_draft_header("nope") is None


def test_trial_catalog_streams_one_row_past_the_cap(schema_conn) -> None:
    op1, _, _ = _seed_plan(schema_conn)
    _seed_trial(schema_conn, _source_ref(schema_conn, "operation", op1))
    repo = WorkbenchTrialCatalogRepository(schema_conn)
    rows = list(repo.iter_rows(TrialCatalogScope("drafts"), 5))
    assert [row["draft_ref"] for row in rows] == [DRAFT]
    assert not any(field in row for row in rows for field in ("admission_json", "snapshot_json"))
    assert len(list(repo.iter_rows(TrialCatalogScope("drafts"), 0))) == 1, "读 limit + 1 行，越界由服务层裁决"
    assert list(repo.iter_rows(TrialCatalogScope("scenarios"), 5))[0]["scenario_ref"] == SCENARIO


# ---------------------------------------------------------------- piece adoption current rows
def test_piece_adoption_repository_current_rows(schema_conn) -> None:
    seed_process(schema_conn)
    schema_conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('PIECE-M','Mill')")
    op_a = schema_conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,piece_id) "
                               "VALUES ('PB-1','PROC-B',1,'车削','P1')").lastrowid
    op_b = schema_conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name) VALUES ('PB-2','PROC-B',2,'检验')").lastrowid
    schema_conn.execute("INSERT INTO ScheduleHistory(version, strategy) VALUES (1, 'seed')")
    schedule_id = schema_conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time,lock_status) VALUES (1,?,?,?,'locked')",
                                      (op_a, SECOND_START, SECOND_END)).lastrowid
    repo = WorkbenchPieceAdoptionRepository(schema_conn)

    assert PREFLIGHT_TABLES == CONSTRAINT_TABLES, "白名单必须与候选采用约束读的表一致"
    templates = repo.template_tables()
    assert tuple(templates) == TEMPLATE_TABLES
    assert len(templates["PartOperations"]) == 5 and templates["ExternalGroups"][0]["group_id"] == "PROC-G"
    preflight = repo.preflight_tables()
    assert tuple(preflight) == PREFLIGHT_TABLES
    assert [row["machine_id"] for row in preflight["Machines"]] == ["PIECE-M"]
    assert all(type(rows) is list for rows in preflight.values())

    batch = repo.get_batch("PROC-B")
    assert (batch["part_no"], batch["quantity"]) == ("PROC-001", 17) and "ready_status" in batch
    assert repo.get_batch("NOPE") is None
    expected_ref = schema_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='PROC-B'").fetchone()[0]
    assert repo.active_batch_refs("PROC-B") == [expected_ref]
    assert repo.active_batch_refs("NOPE") == []
    operations = repo.list_batch_operations("PROC-B")
    assert [(row["id"], row["piece_id"]) for row in operations] == [(op_a, "P1"), (op_b, None)]
    assert "op_type_name" in operations[0]
    old = repo.get_schedule_row(schedule_id)
    assert (old["op_id"], old["lock_status"]) == (op_a, "locked")
    assert repo.get_schedule_row(schedule_id + 99) is None
