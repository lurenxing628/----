import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.models import (
        Batch,
        BatchMaterial,
        BatchOperation,
        ExternalGroup,
        Machine,
        MachineDowntime,
        Material,
        Operator,
        OperatorCalendar,
        PartOperation,
        Schedule,
        Supplier,
        WorkCalendar,
    )

    bo = BatchOperation.from_row(
        {
            "id": 1,
            "op_code": "B001_01",
            "batch_id": "B001",
            "piece_id": None,
            "seq": 1,
            "op_type_id": None,
            "op_type_name": "工序A",
            "source": " INTERNAL  ",
            "machine_id": None,
            "operator_id": None,
            "supplier_id": None,
            "setup_hours": 0,
            "unit_hours": 0,
            "ext_days": None,
            "status": " PENDING ",
        }
    )
    assert bo.source == "internal", f"BatchOperation.source 未规范化：{bo.source!r}"
    assert bo.status == "pending", f"BatchOperation.status 未规范化：{bo.status!r}"

    po = PartOperation.from_row(
        {
            "id": 1,
            "part_no": "P001",
            "seq": 10,
            "op_type_id": None,
            "op_type_name": "外协A",
            "source": " ExTerNal ",
            "supplier_id": None,
            "ext_days": 3,
            "ext_group_id": "G001",
            "setup_hours": 0,
            "unit_hours": 0,
            "status": "ACTIVE",
        }
    )
    assert po.source == "external", f"PartOperation.source 未规范化：{po.source!r}"
    assert po.status == "active", f"PartOperation.status 未规范化：{po.status!r}"

    b = Batch.from_row(
        {
            "batch_id": "B001",
            "part_no": "P001",
            "part_name": "零件",
            "quantity": 1,
            "due_date": None,
            "priority": " URGENT ",
            "ready_status": " YES ",
            "ready_date": None,
            "status": " PENDING ",
        }
    )
    assert b.priority == "urgent", f"Batch.priority 未规范化：{b.priority!r}"
    assert b.ready_status == "yes", f"Batch.ready_status 未规范化：{b.ready_status!r}"
    assert b.status == "pending", f"Batch.status 未规范化：{b.status!r}"

    g = ExternalGroup.from_row(
        {
            "group_id": "G001",
            "part_no": "P001",
            "start_seq": 10,
            "end_seq": 20,
            "merge_mode": " MERGED ",
            "total_days": 5,
        }
    )
    assert g.merge_mode == "merged", f"ExternalGroup.merge_mode 未规范化：{g.merge_mode!r}"

    cal = WorkCalendar.from_row(
        {
            "date": "2026-01-01",
            "day_type": " WORKDAY ",
            "shift_start": "08:00",
            "shift_end": "16:00",
            "shift_hours": 8,
            "efficiency": 1,
            "allow_normal": " YES ",
            "allow_urgent": " No ",
        }
    )
    assert cal.day_type == "workday", f"WorkCalendar.day_type 未规范化：{cal.day_type!r}"
    assert cal.allow_normal == "yes", f"WorkCalendar.allow_normal 未规范化：{cal.allow_normal!r}"
    assert cal.allow_urgent == "no", f"WorkCalendar.allow_urgent 未规范化：{cal.allow_urgent!r}"

    op_cal = OperatorCalendar.from_row(
        {
            "operator_id": "O1",
            "date": "2026-01-01",
            "day_type": " HOLIDAY ",
            "shift_hours": 0,
            "efficiency": 1,
            "allow_normal": "NO",
            "allow_urgent": "YES",
        }
    )
    assert op_cal.day_type == "holiday", f"OperatorCalendar.day_type 未规范化：{op_cal.day_type!r}"
    assert op_cal.allow_normal == "no", f"OperatorCalendar.allow_normal 未规范化：{op_cal.allow_normal!r}"
    assert op_cal.allow_urgent == "yes", f"OperatorCalendar.allow_urgent 未规范化：{op_cal.allow_urgent!r}"

    bm = BatchMaterial.from_row(
        {
            "id": 1,
            "batch_id": "B001",
            "material_id": "M001",
            "required_qty": 1,
            "available_qty": 0,
            "ready_status": " YES ",
        }
    )
    assert bm.ready_status == "yes", f"BatchMaterial.ready_status 未规范化：{bm.ready_status!r}"

    mc = Machine.from_row({"machine_id": "MC1", "name": "机台", "status": " MAINTAIN "})
    assert mc.status == "maintain", f"Machine.status 未规范化：{mc.status!r}"

    op = Operator.from_row({"operator_id": "O1", "name": "张三", "status": " INACTIVE "})
    assert op.status == "inactive", f"Operator.status 未规范化：{op.status!r}"

    sup = Supplier.from_row({"supplier_id": "S1", "name": "供应商", "status": " InActive "})
    assert sup.status == "inactive", f"Supplier.status 未规范化：{sup.status!r}"

    mat = Material.from_row({"material_id": "MAT1", "name": "物料", "status": " InActive "})
    assert mat.status == "inactive", f"Material.status 未规范化：{mat.status!r}"

    dt = MachineDowntime.from_row(
        {"id": 1, "machine_id": "MC1", "scope_type": " CATEGORY ", "start_time": "x", "end_time": "y", "status": "CANCELLED"}
    )
    assert dt.scope_type == "category", f"MachineDowntime.scope_type 未规范化：{dt.scope_type!r}"
    assert dt.status == "cancelled", f"MachineDowntime.status 未规范化：{dt.status!r}"

    s = Schedule.from_row({"id": 1, "op_id": 1, "start_time": "x", "end_time": "y", "lock_status": " LOCKED "})
    assert s.lock_status == "locked", f"Schedule.lock_status 未规范化：{s.lock_status!r}"

    print("OK")


if __name__ == "__main__":
    main()

