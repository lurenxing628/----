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
        MachineDowntime,
        Material,
        OperationLog,
        OperatorMachine,
        OpType,
        PartOperation,
        Schedule,
        ScheduleConfig,
        ScheduleHistory,
        Supplier,
        SystemConfig,
        SystemJobState,
    )

    # Schedule：op_id 缺失不应默认为 0（避免悬空外键）
    s0 = Schedule.from_row({"id": "1.0", "op_id": "", "start_time": "x", "end_time": "y", "lock_status": "LOCKED", "version": "1.0"})
    assert s0.id == 1, f"Schedule.id 解析异常：{s0.id!r}"
    assert s0.op_id is None, f"Schedule.op_id 空字符串应为 None：{s0.op_id!r}"
    assert s0.version == 1, f"Schedule.version 解析异常：{s0.version!r}"

    s1 = Schedule.from_row({"id": 1, "op_id": "2.0", "start_time": "x", "end_time": "y", "lock_status": "locked"})
    assert s1.op_id == 2, f"Schedule.op_id '2.0' 解析异常：{s1.op_id!r}"

    # Batch：quantity 支持 '1.0'，拒绝非整数
    b1 = Batch.from_row({"batch_id": "B1", "part_no": "P1", "quantity": "1.0"})
    assert b1.quantity == 1, f"Batch.quantity '1.0' 解析异常：{b1.quantity!r}"

    b2 = Batch.from_row({"batch_id": "B2", "part_no": "P2", "quantity": "1.5"})
    assert b2.quantity == 0, f"Batch.quantity '1.5' 应回落 0：{b2.quantity!r}"

    b3 = Batch.from_row({"batch_id": "B3", "part_no": "P3", "quantity": True})
    assert b3.quantity == 0, f"Batch.quantity True 不应被当成 1：{b3.quantity!r}"

    # BatchOperation：int('1.0')/float('') 等不应崩溃
    bo = BatchOperation.from_row(
        {
            "id": "1.0",
            "op_code": "OP1",
            "batch_id": "B1",
            "seq": "2.0",
            "setup_hours": "1.5",
            "unit_hours": "NaN",
            "ext_days": "1e3",
        }
    )
    assert bo.id == 1, f"BatchOperation.id 解析异常：{bo.id!r}"
    assert bo.seq == 2, f"BatchOperation.seq '2.0' 解析异常：{bo.seq!r}"
    assert abs(float(bo.setup_hours) - 1.5) < 1e-9, f"BatchOperation.setup_hours 解析异常：{bo.setup_hours!r}"
    assert float(bo.unit_hours) == 0.0, f"BatchOperation.unit_hours NaN 应回落 0.0：{bo.unit_hours!r}"
    assert float(bo.ext_days or 0.0) == 1000.0, f"BatchOperation.ext_days '1e3' 解析异常：{bo.ext_days!r}"

    bo2 = BatchOperation.from_row({"id": 1, "op_code": "OP2", "batch_id": "B1", "seq": 1, "ext_days": "NaN"})
    assert bo2.ext_days is None, f"BatchOperation.ext_days NaN 应回落 None：{bo2.ext_days!r}"

    # PartOperation：可选/必填浮点字段解析
    po = PartOperation.from_row(
        {
            "id": "1.0",
            "part_no": "P1",
            "seq": "10.0",
            "ext_days": "NaN",
            "setup_hours": "",
            "unit_hours": "2.5",
        }
    )
    assert po.id == 1, f"PartOperation.id 解析异常：{po.id!r}"
    assert po.seq == 10, f"PartOperation.seq '10.0' 解析异常：{po.seq!r}"
    assert po.ext_days is None, f"PartOperation.ext_days NaN 应回落 None：{po.ext_days!r}"
    assert float(po.setup_hours) == 0.0, f"PartOperation.setup_hours 空字符串应回落 0.0：{po.setup_hours!r}"
    assert abs(float(po.unit_hours) - 2.5) < 1e-9, f"PartOperation.unit_hours 解析异常：{po.unit_hours!r}"

    # BatchMaterial / Material：NaN/空字符串不应造成异常
    bm = BatchMaterial.from_row(
        {"id": "1.0", "batch_id": "B1", "material_id": "M1", "required_qty": "NaN", "available_qty": "", "ready_status": "YES"}
    )
    assert bm.id == 1, f"BatchMaterial.id 解析异常：{bm.id!r}"
    assert float(bm.required_qty) == 0.0, f"BatchMaterial.required_qty NaN 应回落 0.0：{bm.required_qty!r}"
    assert float(bm.available_qty) == 0.0, f"BatchMaterial.available_qty 空字符串应回落 0.0：{bm.available_qty!r}"

    mat = Material.from_row({"material_id": "MAT1", "name": "物料", "stock_qty": "NaN"})
    assert float(mat.stock_qty) == 0.0, f"Material.stock_qty NaN 应回落 0.0：{mat.stock_qty!r}"

    # Supplier / OpType：0 值应被保留；NaN 应回落默认/None
    sup0 = Supplier.from_row({"supplier_id": "S0", "name": "供应商", "default_days": "0"})
    assert float(sup0.default_days) == 0.0, f"Supplier.default_days '0' 不应被覆盖为 1.0：{sup0.default_days!r}"

    ot0 = OpType.from_row({"op_type_id": "OT1", "name": "工序", "default_hours": "NaN"})
    assert ot0.default_hours is None, f"OpType.default_hours NaN 应回落 None：{ot0.default_hours!r}"

    ot1 = OpType.from_row({"op_type_id": "OT2", "name": "工序", "default_hours": "1e3"})
    assert float(ot1.default_hours or 0.0) == 1000.0, f"OpType.default_hours '1e3' 解析异常：{ot1.default_hours!r}"

    # History/Logs/Configs：id/version 允许 '1.0'
    hist = ScheduleHistory.from_row({"id": "1.0", "version": "1.0", "batch_count": "", "op_count": "N/A"})
    assert hist.id == 1, f"ScheduleHistory.id 解析异常：{hist.id!r}"
    assert hist.version == 1, f"ScheduleHistory.version 解析异常：{hist.version!r}"
    assert hist.batch_count is None, f"ScheduleHistory.batch_count 空字符串应为 None：{hist.batch_count!r}"
    assert hist.op_count is None, f"ScheduleHistory.op_count 'N/A' 应为 None：{hist.op_count!r}"

    log = OperationLog.from_row({"id": "1.0", "log_level": "INFO"})
    assert log.id == 1, f"OperationLog.id 解析异常：{log.id!r}"

    om = OperatorMachine.from_row({"id": "1.0", "operator_id": "O1", "machine_id": "M1"})
    assert om.id == 1, f"OperatorMachine.id 解析异常：{om.id!r}"

    dt = MachineDowntime.from_row({"id": "1.0", "machine_id": "M1", "start_time": "x", "end_time": "y"})
    assert dt.id == 1, f"MachineDowntime.id 解析异常：{dt.id!r}"

    sc = SystemConfig.from_row({"id": "1.0", "config_key": "k", "config_value": "v"})
    assert sc.id == 1, f"SystemConfig.id 解析异常：{sc.id!r}"

    sj = SystemJobState.from_row({"id": "1.0", "job_key": "job"})
    assert sj.id == 1, f"SystemJobState.id 解析异常：{sj.id!r}"

    cfg = ScheduleConfig.from_row({"id": "1.0", "config_key": "k", "config_value": "v"})
    assert cfg.id == 1, f"ScheduleConfig.id 解析异常：{cfg.id!r}"

    print("OK")


if __name__ == "__main__":
    main()

