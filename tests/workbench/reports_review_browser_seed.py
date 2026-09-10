"""EI fixture extends existing real ledger helpers; no fabricated HTTP payloads."""

from tests.workbench.execution_ledger_support import LedgerCase

LONG_REMARK = "复核记录：尺寸、设备与人员已经核对；保留完整原始备注供追溯。" * 14
LONG_CODE = "EI-LONG-" + "连续加工工序长名称" * 7


def seed(api):
    with api.db() as conn:
        case = LedgerCase(conn)
        conn.execute("UPDATE Machines SET name='一号精加工设备' WHERE machine_id='M1'")
        conn.execute("UPDATE Operators SET name='一班操作人员' WHERE operator_id='O1'")
        conn.execute("UPDATE Batches SET due_date='2026-09-08' WHERE batch_id='B1'")
        ids = []
        for number in range(2, 67):
            op = case.op(LONG_CODE if number == 66 else f'EI-OP-{number:03d}', seq=number)
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                         "VALUES (1,?,'M1','O1','2026-09-09 08:00:00','2026-09-09 10:00:00')", (op,))
            ids.append(op)
        conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) "
                     "VALUES ('M1','2026-09-09 08:00:00','2026-09-09 08:30:00','active')")
        for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
            conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?, 'no')", (key,))
    with api.db() as conn:
        case = LedgerCase(conn)
        def create(values, op=1):
            return case.command("create", case.task(1, op), values)["data"]["rows"][0]

        first = create(case.values(0, effective_processing_hours=0, remark="=1+1"))
        case.command("correct", first["report_ref"], {"original_revision_ref": first["revision_ref"],
                     "reason": "EI verified original remark", "remark": LONG_REMARK})
        for number in range(12):
            create(case.values(0, effective_processing_hours=.125, remark="=1+1" if number == 0 else f"EI-{number:02d}"))
        create({"actual_start": "2026-09-09T08:00:00"}, op=ids[0])
        for op in ids[1:13]:
            create(case.values(10, effective_processing_hours=.5, remark="实际完整报工"), op=op)
        create(case.values(0, effective_processing_hours=0, remark=LONG_REMARK), op=ids[-1])
        for op in ids[13:16]:
            case.event(op, "start")
            case.event(op, "finish", quantity=10)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    return {"operations": 66, "reports": 27, "legacy_events": 6, "records": 33,
            "long_code": LONG_CODE, "long_remark": LONG_REMARK,
            "first_report": first["report_ref"], "fixture_source": "report_ledger_api + LedgerCase + production command service"}
