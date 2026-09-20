"""合同测试：SQL 排水第三批（run 簇）新增的仓储方法——排产记录目录读模型、永久候选读模型、接收事实读模型、
候选输入读模型，以及 WorkbenchRunRepository 的回执动作 / 候选存在探针。锁定每个方法的 SQL 语义、返回类型与行序，
服务层不再持 conn 直接读这些表。"""

from __future__ import annotations

import json

from core.infrastructure.workbench_run_schema import RUN_TABLES
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository
from data.repositories.workbench_run_input_repo import (
    ADOPTION_CHECK_TABLES,
    CALENDAR_TABLES,
    WorkbenchRunInputRepository,
)
from data.repositories.workbench_run_query_repo import DIRECTORY_DOCUMENT_TABLES, WorkbenchRunHistoryQueryRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository

RUN, CAND, CAND2, TASK, RECEIPT, ORPHAN = ("a" * 48, "b" * 48, "c" * 48, "d" * 48, "e" * 48, "9" * 48)
REQ, ADOPT = "run-request-00000001", "scheduling.candidate.adopt"
INPUT_JSON, EXEC_JSON, BASELINE_JSON, FACTS_JSON = '{"a":1}', "[]", "{}", '{"f":1}'
RESULT_JSON, ARTIFACT_JSON, PAYLOAD_JSON = '{"state":"complete"}', '{"x":1}', '{"p":1}'


def _receipt(conn, request_key, receipt_ref, action, context_ref, outcome, committed_at):
    conn.execute("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json,committed_at_utc) "
                 "VALUES (?,?,?,?,?,?,?)", (request_key, receipt_ref, action, context_ref, "0" * 64, outcome, committed_at))


def _seed_master(conn):
    """两张批次：B1 普通工序、B2 带分件工序；返回两道工序的 BatchOperations.id。"""
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('T1','车削','internal')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','车床','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','张三')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','轴')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',5)")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',5)")
    conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name) VALUES ('B1-10','B1',10,'T1','车削')")
    conn.execute("INSERT INTO BatchOperations(op_code,batch_id,piece_id,seq,op_type_id,op_type_name) VALUES ('B2-10','B2','PC1',10,'T1','车削')")
    op1, op2 = (row[0] for row in conn.execute("SELECT id FROM BatchOperations ORDER BY id"))
    return op1, op2


def _seed_ledger(conn, op_id):
    """一条已完成排产：接收回执 + 作业 + 结果回执 + 两个候选（一个带一条明细）；返回明细用到的工序 ref。"""
    _receipt(conn, REQ, "f" * 32, "scheduling.run", "in-1", json.dumps({"data": {"run_ref": RUN}}), "2026-09-20T00:00:00.000Z")
    conn.execute("INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,facts_hash,facts_json,"
                 "execution_json,baseline_json,accepted_at,state,stage,executor_ref,started_at,finished_at) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (RUN, REQ, "in-1", INPUT_JSON, "h", FACTS_JSON, EXEC_JSON, BASELINE_JSON, "2026-09-20T08:00:00",
                  "complete", "finished", "exec-1", "2026-09-20T08:00:01", "2026-09-20T08:00:05"))
    conn.execute("INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)", (RECEIPT, RUN, "complete", RESULT_JSON, "2026-09-20T08:00:05"))
    conn.execute("INSERT INTO WorkbenchRunCandidates VALUES (?,?,?,?,?,?,?)", (CAND, RUN, "k1", 0, "completed", 1, ARTIFACT_JSON))
    conn.execute("INSERT INTO WorkbenchRunCandidates VALUES (?,?,?,?,?,?,?)", (CAND2, RUN, "k2", 1, "failed", 0, "{}"))
    op_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 AND source_key=?",
                          (str(op_id),)).fetchone()[0]
    conn.execute("INSERT INTO WorkbenchRunCandidateTasks VALUES (?,?,?,?,?)", (TASK, CAND, op_ref, 0, PAYLOAD_JSON))
    return op_ref


def test_run_repository_receipt_action_and_candidate_probe(schema_conn) -> None:
    op1, _ = _seed_master(schema_conn)
    _seed_ledger(schema_conn, op1)
    repo = WorkbenchRunRepository(schema_conn)
    assert repo.command_receipt_action(REQ) == "scheduling.run"
    assert repo.command_receipt_action("run-request-missing-1") is None
    assert repo.has_candidates(RUN) is True
    assert repo.has_candidates("0" * 48) is False


def test_history_query_repository_capacity_orphans_and_directory(schema_conn) -> None:
    op1, _ = _seed_master(schema_conn)
    _seed_ledger(schema_conn, op1)
    # 非 scheduling.run 的命令回执不计入目录容量
    _receipt(schema_conn, "adopt-request-000001", "1" * 32, ADOPT, CAND, '{"r":1}', "2026-09-20T00:00:01.000Z")
    repo = WorkbenchRunHistoryQueryRepository(schema_conn)

    capacity = repo.directory_capacity()
    assert tuple(capacity) == tuple(table for table, _ in DIRECTORY_DOCUMENT_TABLES)
    assert capacity["WorkbenchRunJobs"] == {"rows": 1, "bytes": len(INPUT_JSON), "max_document_bytes": len(INPUT_JSON)}
    assert capacity["WorkbenchRunReceipts"] == {"rows": 1, "bytes": len(RESULT_JSON), "max_document_bytes": len(RESULT_JSON)}
    outcome = len(json.dumps({"data": {"run_ref": RUN}}))
    assert capacity["WorkbenchCommandReceipts"] == {"rows": 1, "bytes": outcome, "max_document_bytes": outcome}
    assert repo.candidate_count() == 2

    probe = repo.orphan_probe()
    assert probe == {"receipts_without_job": False, "candidates_without_job": False,
                     "tasks_without_candidate": False, "admissions_without_job": False}

    jobs = repo.list_jobs()
    assert len(jobs) == 1 and isinstance(jobs[0], dict)
    assert (jobs[0]["run_ref"], jobs[0]["admission_action"], jobs[0]["admission_context"], jobs[0]["receipt_state"]) == (RUN, "scheduling.run", "in-1", "complete")
    assert "facts_json" not in jobs[0]

    candidates = repo.list_candidates()
    assert [(row["candidate_ref"], row["actual_count"], row["first_ordinal"], row["last_ordinal"]) for row in candidates] == [
        (CAND, 1, 0, 0), (CAND2, 0, None, None)]

    # 旧写入方关掉 foreign_keys 留下的孤儿回执必须被反连接探针发现（PRAGMA 只能在事务外改）
    schema_conn.commit()
    schema_conn.execute("PRAGMA foreign_keys=OFF")
    schema_conn.execute("INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)", ("7" * 48, ORPHAN, "failed", "{}", "t"))
    assert repo.orphan_probe()["receipts_without_job"] is True


def test_candidate_repository_reads_bounded_facts(schema_conn) -> None:
    op1, _ = _seed_master(schema_conn)
    op_ref = _seed_ledger(schema_conn, op1)
    _receipt(schema_conn, "adopt-request-000002", "2" * 32, ADOPT, CAND, '{"r":22}', "2026-09-20T00:00:02.000Z")
    _receipt(schema_conn, "adopt-request-000001", "1" * 32, ADOPT, CAND, '{"r":1}', "2026-09-20T00:00:02.000Z")
    _receipt(schema_conn, "adopt-request-000003", "3" * 32, ADOPT, CAND2, '{"r":3}', "2026-09-20T00:00:00.000Z")
    repo = WorkbenchRunCandidateRepository(schema_conn)

    assert repo.job_summary(RUN) == (RUN, "complete", "2026-09-20T08:00:00", "2026-09-20T08:00:05",
                                     len(INPUT_JSON), len(EXEC_JSON), len(BASELINE_JSON), len(FACTS_JSON))
    assert repo.job_summary("0" * 48) is None
    assert repo.receipt_size(RUN) == len(RESULT_JSON)
    assert repo.receipt_size("0" * 48) is None
    assert repo.receipt_state_and_result(RUN) == ("complete", RESULT_JSON)
    assert repo.receipt_state_and_result("0" * 48) is None

    assert repo.candidate_sizes(RUN, 1) == [(CAND, len(ARTIFACT_JSON), 1)]
    assert repo.candidate_sizes(RUN, 5) == [(CAND, len(ARTIFACT_JSON), 1), (CAND2, 2, 0)]
    assert repo.candidate_task_counts(RUN) == {CAND: 1}
    assert repo.candidate_rows(RUN) == [(CAND, RUN, "completed", 1, 0, ARTIFACT_JSON), (CAND2, RUN, "failed", 0, 1, "{}")]
    assert repo.candidate_run_ref(CAND) == RUN
    assert repo.candidate_run_ref("0" * 48) is None
    assert repo.job_capture(RUN) == (INPUT_JSON, EXEC_JSON, BASELINE_JSON, FACTS_JSON, "h")
    assert repo.job_capture("0" * 48) is None
    assert repo.task_sizes(CAND) == (1, len(PAYLOAD_JSON), len(PAYLOAD_JSON))
    assert repo.task_sizes(CAND2) == (0, 0, 0)
    assert repo.task_rows(CAND) == [(TASK, op_ref, 0, PAYLOAD_JSON)]
    assert repo.task_rows(CAND2) == []

    assert repo.adoption_receipt_capacity(ADOPT, CAND) == (2, len('{"r":22}') + len('{"r":1}'))
    assert repo.adoption_receipt_capacity("scheduling.run", CAND) == (0, 0)
    receipts = repo.adoption_receipts(ADOPT, CAND)
    assert [row["request_key"] for row in receipts] == ["adopt-request-000001", "adopt-request-000002"], "同一时刻按 request_key 排序"
    assert isinstance(receipts[0], dict) and receipts[0]["outcome_json"] == '{"r":1}'


def test_facts_repository_snapshot_identities_and_baseline(schema_conn) -> None:
    op1, op2 = _seed_master(schema_conn)
    _seed_ledger(schema_conn, op1)
    _receipt(schema_conn, "adopt-request-000001", "1" * 32, ADOPT, CAND, '{"r":1}', "2026-09-20T00:00:01.000Z")
    repo = WorkbenchRunFactsRepository(schema_conn)

    schema, tables = repo.admission_facts()
    assert schema and all(type(item) is tuple and len(item) == 4 for item in schema)
    assert not set(tables) & set(RUN_TABLES)
    assert tables["Machines"] and type(tables["Machines"][0]) is tuple and tables["Machines"][0][0] == "M1"
    assert [row[0] for row in tables["WorkbenchCommandReceipts"]] == ["adopt-request-000001"], "scheduling.run 回执不入事实快照"
    assert [row[1] for row in tables["BatchOperations"]] == ["B1-10", "B2-10"], "按 rowid 排序"

    identities = repo.operation_identity_refs()
    assert {row[0] for row in identities} == {str(op1), str(op2)} and all(type(row) is tuple for row in identities)
    batch_refs = {"B1": schema_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B1' AND active=1").fetchone()[0],
                  "B2": schema_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B2' AND active=1").fetchone()[0]}
    assert repo.batch_operation_batch_refs() == [(op1, batch_refs["B1"]), (op2, batch_refs["B2"])]
    assert repo.piece_batch_refs() == [batch_refs["B2"]]

    assert repo.latest_history_version() is None
    assert repo.schedule_has_rows() is False
    schema_conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (1,'fixture','success','{\"s\":1}')")
    schema_conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1','2026-09-10 08:00:00','2026-09-10 10:00:00')", (op1,))
    assert repo.latest_history_version() == 1
    official = repo.official_plan_refs(1)
    assert len(official) == 1 and type(official[0]) is str and len(official[0]) == 48
    assert repo.official_plan_refs(2) == []
    rows = repo.schedule_rows_for_version(1)
    assert len(rows) == 1 and isinstance(rows[0], dict) and (rows[0]["op_id"], rows[0]["version"]) == (op1, 1)
    assert repo.schedule_rows_for_version(2) == []
    assert repo.history_result_summaries(1) == ['{"s":1}']
    assert repo.history_result_summaries(2) == []
    assert repo.schedule_has_rows() is True
    assert repo.schedule_has_rows_without_history() is False
    schema_conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (2,?,'M1','O1','2026-09-11 08:00:00','2026-09-11 10:00:00')", (op2,))
    assert repo.schedule_has_rows_without_history() is True


def test_input_repository_runtime_rows_and_points(schema_conn) -> None:
    op1, op2 = _seed_master(schema_conn)
    schema_conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'fixture')")
    schema_conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (2,'fixture')")
    schema_conn.executemany("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time,lock_status) VALUES (?,?,'M1','O1',?,?,?)", [
        (1, op1, "2026-09-10 08:00:00", "2026-09-10 08:00:00", "locked"),
        (1, op2, "2026-09-10 08:00:00", "2026-09-10 10:00:00", "unlocked"),
        (2, op1, "2026-09-12 08:00:00", "2026-09-12 09:00:00", "locked"),
    ])
    repo = WorkbenchRunInputRepository(schema_conn)

    rows = repo.schedule_rows_through_version(1)
    assert [(row["version"], row["op_id"], row["lock_status"]) for row in rows] == [(1, op1, "locked"), (1, op2, "unlocked")]
    assert [(row["version"], row["op_id"]) for row in repo.schedule_rows_through_version(2)] == [(1, op1), (1, op2), (2, op1)]

    schema_conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end) VALUES ('2026-09-10','workday','08:00',NULL)")
    schema_conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type) VALUES ('O1','2026-09-10','weekend')")
    calendars = repo.calendar_rows()
    assert tuple(calendars) == CALENDAR_TABLES
    assert [row["day_type"] for row in calendars["WorkCalendar"]] == ["workday"]
    assert [(row["operator_id"], row["day_type"]) for row in calendars["OperatorCalendar"]] == [("O1", "weekend")]

    assert repo.machine_downtime_rows() == []
    schema_conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES ('M1','2026-09-10T08:00:00','2026-09-10T09:00:00','cancelled')")
    downtimes = repo.machine_downtime_rows()
    assert len(downtimes) == 1 and isinstance(downtimes[0], dict) and downtimes[0]["status"] == "cancelled"

    checks = repo.adoption_check_tables()
    assert tuple(checks) == ADOPTION_CHECK_TABLES
    assert [row["machine_id"] for row in checks["Machines"]] == ["M1"]
    assert checks["BatchMaterials"] == []

    # 零工时冻结点：只取开工=完工=start_time 的行；901 个 op_id 跨两片仍只命中一行，不去重
    points = repo.point_rows_at(version=1, op_ids=[op1, op2] + [999999] * 899, start_time="2026-09-10 08:00:00")
    assert [(row["op_id"], row["start_time"], row["end_time"]) for row in points] == [(op1, "2026-09-10 08:00:00", "2026-09-10 08:00:00")]
    assert repo.point_rows_at(version=2, op_ids=[op1], start_time="2026-09-10 08:00:00") == []
    assert repo.point_rows_at(version=1, op_ids=[], start_time="2026-09-10 08:00:00") == []
