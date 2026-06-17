"""回归测试：各 core.models 数据类的 from_row 数字解析——id/version/quantity/seq 等接受 '1.0' 形式、空字符串回落各自旧默认（None 或 0.0），但显式 NaN/Inf/布尔值必须直接 ValueError 并点名字段，绝不静默回落 0 伪装成合法值。"""


def test_models_numeric_parse_hybrid_safe() -> None:

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

    try:
        Batch.from_row({"batch_id": "B2", "part_no": "P2", "quantity": "1.5"})
    except ValueError as exc:
        assert "quantity" in str(exc), f"Batch.quantity 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("Batch.quantity '1.5' 应直接报错，不能静默回落 0")

    try:
        Batch.from_row({"batch_id": "B3", "part_no": "P3", "quantity": True})
    except ValueError as exc:
        assert "quantity" in str(exc), f"Batch.quantity True 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("Batch.quantity True 不能静默回落，也不能被当成 1")

    # BatchOperation：int('1.0')/float('') 等不应崩溃
    try:
        BatchOperation.from_row(
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
    except ValueError as exc:
        assert "unit_hours" in str(exc), f"BatchOperation.unit_hours 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("BatchOperation.unit_hours NaN 应直接报错，不能静默回落 0.0")

    bo = BatchOperation.from_row(
        {
            "id": "1.0",
            "op_code": "OP1",
            "batch_id": "B1",
            "seq": "2.0",
            "setup_hours": "1.5",
            "unit_hours": "2.0",
            "ext_days": "1e3",
        }
    )
    assert bo.id == 1, f"BatchOperation.id 解析异常：{bo.id!r}"
    assert bo.seq == 2, f"BatchOperation.seq '2.0' 解析异常：{bo.seq!r}"
    assert abs(float(bo.setup_hours) - 1.5) < 1e-9, f"BatchOperation.setup_hours 解析异常：{bo.setup_hours!r}"
    assert float(bo.unit_hours) == 2.0, f"BatchOperation.unit_hours 解析异常：{bo.unit_hours!r}"
    assert float(bo.ext_days or 0.0) == 1000.0, f"BatchOperation.ext_days '1e3' 解析异常：{bo.ext_days!r}"

    try:
        BatchOperation.from_row({"id": 1, "op_code": "OP2", "batch_id": "B1", "seq": 1, "ext_days": "NaN"})
    except ValueError as exc:
        assert "ext_days" in str(exc), f"BatchOperation.ext_days 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("BatchOperation.ext_days NaN 应直接报错，不能静默回落 None")

    # PartOperation：可选/必填浮点字段解析
    po = PartOperation.from_row(
        {
            "id": "1.0",
            "part_no": "P1",
            "seq": "10.0",
            "ext_days": "",
            "setup_hours": "",
            "unit_hours": "2.5",
        }
    )
    assert po.id == 1, f"PartOperation.id 解析异常：{po.id!r}"
    assert po.seq == 10, f"PartOperation.seq '10.0' 解析异常：{po.seq!r}"
    assert po.ext_days is None, f"PartOperation.ext_days 空字符串应回落 None：{po.ext_days!r}"
    assert float(po.setup_hours) == 0.0, f"PartOperation.setup_hours 空字符串应回落 0.0：{po.setup_hours!r}"
    assert abs(float(po.unit_hours) - 2.5) < 1e-9, f"PartOperation.unit_hours 解析异常：{po.unit_hours!r}"

    try:
        PartOperation.from_row({"part_no": "P1", "seq": "1", "ext_days": "NaN"})
    except ValueError as exc:
        assert "ext_days" in str(exc), f"PartOperation.ext_days 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("PartOperation.ext_days NaN 应直接报错，不能静默回落 None")

    # BatchMaterial / Material：空字符串保留旧默认；显式 NaN/Inf 必须报错，不能伪装成 0。
    try:
        BatchMaterial.from_row(
            {
                "id": "1.0",
                "batch_id": "B1",
                "material_id": "M1",
                "required_qty": "NaN",
                "available_qty": "",
                "ready_status": "YES",
            }
        )
    except ValueError as exc:
        assert "required_qty" in str(exc), f"BatchMaterial.required_qty 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("BatchMaterial.required_qty NaN 应直接报错，不能静默回落 0.0")

    try:
        BatchMaterial.from_row(
            {
                "id": "1.0",
                "batch_id": "B1",
                "material_id": "M1",
                "required_qty": "1.0",
                "available_qty": "Inf",
                "ready_status": "YES",
            }
        )
    except ValueError as exc:
        assert "available_qty" in str(exc), f"BatchMaterial.available_qty 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("BatchMaterial.available_qty Inf 应直接报错，不能静默回落 0.0")

    bm = BatchMaterial.from_row({"id": "1.0", "batch_id": "B1", "material_id": "M1", "required_qty": "1.0", "available_qty": "", "ready_status": "YES"})
    assert bm.id == 1, f"BatchMaterial.id 解析异常：{bm.id!r}"
    assert float(bm.required_qty) == 1.0, f"BatchMaterial.required_qty '1.0' 解析异常：{bm.required_qty!r}"
    assert float(bm.available_qty) == 0.0, f"BatchMaterial.available_qty 空字符串应回落 0.0：{bm.available_qty!r}"

    try:
        Material.from_row({"material_id": "MAT1", "name": "物料", "stock_qty": "NaN"})
    except ValueError as exc:
        assert "stock_qty" in str(exc), f"Material.stock_qty 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("Material.stock_qty NaN 应直接报错，不能静默回落 0.0")

    mat = Material.from_row({"material_id": "MAT1", "name": "物料", "stock_qty": ""})
    assert float(mat.stock_qty) == 0.0, f"Material.stock_qty 空字符串应回落 0.0：{mat.stock_qty!r}"

    # Supplier / OpType：0 值应被保留；显式 NaN 不能回落默认/None。
    sup0 = Supplier.from_row({"supplier_id": "S0", "name": "供应商", "default_days": "0"})
    assert float(sup0.default_days) == 0.0, f"Supplier.default_days '0' 不应被覆盖为 1.0：{sup0.default_days!r}"

    try:
        Supplier.from_row({"supplier_id": "S1", "name": "供应商", "default_days": "NaN"})
    except ValueError as exc:
        assert "default_days" in str(exc), f"Supplier.default_days 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("Supplier.default_days NaN 应直接报错，不能静默回落默认值")

    try:
        OpType.from_row({"op_type_id": "OT1", "name": "工序", "default_hours": "NaN"})
    except ValueError as exc:
        assert "default_hours" in str(exc), f"OpType.default_hours 错误信息应指出字段：{exc!r}"
    else:
        raise AssertionError("OpType.default_hours NaN 应直接报错，不能静默回落 None")

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
