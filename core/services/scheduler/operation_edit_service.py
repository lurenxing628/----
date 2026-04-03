from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models import BatchOperation
from core.models.enums import BatchOperationStatus, MachineStatus, MergeMode, OperatorStatus, SourceType, SupplierStatus
from core.services.common.strict_parse import parse_required_float


def list_batch_operations(svc, batch_id: Any) -> List[BatchOperation]:
    bid = svc._normalize_text(batch_id)
    if not bid:
        raise ValidationError("“批次号”不能为空", field="批次号")
    svc._get_batch_or_raise(bid)
    return svc.op_repo.list_by_batch(bid)


def get_operation(svc, op_id: Any) -> BatchOperation:
    try:
        oid = int(op_id)
    except Exception as e:
        raise ValidationError("工序ID 不合法", field="op_id") from e
    return svc._get_op_or_raise(oid)


def get_external_merge_hint(svc, op_id: Any) -> Dict[str, Any]:
    """
    返回外部工序“合并周期”提示信息（供页面展示）。
    """
    op = get_operation(svc, op_id)
    if (op.source or "").strip().lower() != SourceType.EXTERNAL.value:
        return {"is_external": False}

    tmpl, grp = svc._get_template_and_group_for_op(op)
    if not tmpl or not grp:
        return {"is_external": True, "merge_mode": None}
    return {
        "is_external": True,
        "template_ext_group_id": tmpl.ext_group_id,
        "merge_mode": grp.merge_mode,
        "group_total_days": grp.total_days,
    }


def _normalize_batch_op_status(svc, value: Any) -> Optional[str]:
    st = svc._normalize_text(value)
    if st is None:
        return None
    st = str(st).strip().lower()
    allowed = (
        BatchOperationStatus.PENDING.value,
        BatchOperationStatus.SCHEDULED.value,
        BatchOperationStatus.PROCESSING.value,
        BatchOperationStatus.COMPLETED.value,
        BatchOperationStatus.SKIPPED.value,
    )
    if st not in allowed:
        raise ValidationError("“状态”不正确，请选择：待排 / 已排 / 加工中 / 已完成 / 已跳过。", field="状态")
    return st


def _ensure_internal_operation_editable(op: BatchOperation, *, op_id: Any) -> None:
    if op.id is None:
        raise BusinessError(ErrorCode.NOT_FOUND, f"批次工序（ID={op_id}）不存在")
    if (op.source or "").strip().lower() != SourceType.INTERNAL.value:
        raise ValidationError("只能编辑内部工序的设备/人员/工时信息", field="source")


def _validate_machine_available(svc, mc_id: Optional[str]) -> None:
    if not mc_id:
        return
    m = svc.machine_repo.get(mc_id)
    if not m:
        raise BusinessError(ErrorCode.MACHINE_NOT_FOUND, f"设备“{mc_id}”不存在")
    if (m.status or "").strip().lower() != MachineStatus.ACTIVE.value:
        raise BusinessError(ErrorCode.MACHINE_NOT_AVAILABLE, f"设备“{mc_id}”当前状态为“{m.status}”，不可用于排产。")


def _validate_operator_available(svc, operator_id_text: Optional[str]) -> None:
    if not operator_id_text:
        return
    person = svc.operator_repo.get(operator_id_text)
    if not person:
        raise BusinessError(ErrorCode.OPERATOR_NOT_FOUND, f"人员“{operator_id_text}”不存在")
    if (person.status or "").strip().lower() != OperatorStatus.ACTIVE.value:
        raise BusinessError(ErrorCode.RESOURCE_NOT_AVAILABLE, f"人员“{operator_id_text}”当前状态为“{person.status}”，不可用于排产。")


def _validate_operator_machine_match(svc, *, mc_id: Optional[str], operator_id_text: Optional[str], op: BatchOperation) -> None:
    if not (mc_id and operator_id_text):
        return
    if svc.operator_machine_repo.exists(operator_id_text, mc_id):
        return
    op_code = op.op_code or "-"
    raise ValidationError(
        f"人员“{operator_id_text}”未被配置为可操作设备“{mc_id}”（工序 {op_code} / ID={op.id}）。"
        f"请先在【人员管理】或【设备管理】中维护人机关联（OperatorMachine）后再排产。",
        field="设备/人员",
    )


def _normalize_hours(svc, *, setup_hours: Any, unit_hours: Any) -> Tuple[float, float]:
    sh = svc._normalize_float(setup_hours, field="换型时间(小时)", allow_none=True)
    uh = svc._normalize_float(unit_hours, field="单件工时(小时)", allow_none=True)
    sh2 = 0.0 if sh is None else float(sh)
    uh2 = 0.0 if uh is None else float(uh)
    if sh2 < 0 or uh2 < 0:
        raise ValidationError("工时不能为负数", field="工时")
    return sh2, uh2


def update_internal_operation(
    svc,
    op_id: Any,
    machine_id: Any = None,
    operator_id: Any = None,
    setup_hours: Any = None,
    unit_hours: Any = None,
    status: Any = None,
) -> BatchOperation:
    """
    内部工序补充信息：
    - machine_id/operator_id 可选（允许清空）
    - setup_hours/unit_hours 非负（允许为空，空视为 0）
    """
    op = get_operation(svc, op_id)
    _ensure_internal_operation_editable(op, op_id=op_id)
    assert op.id is not None

    op_id_int = int(op.id)

    mc_id = svc._normalize_text(machine_id)
    operator_id_text = svc._normalize_text(operator_id)

    # 设备存在性 + 可用性（维护/停用时禁止分配）
    _validate_machine_available(svc, mc_id)

    # 人员存在性 + 在岗性
    _validate_operator_available(svc, operator_id_text)

    # 人员-设备匹配性（双向约束）：两者都选择时必须已维护可操作关联
    _validate_operator_machine_match(svc, mc_id=mc_id, operator_id_text=operator_id_text, op=op)

    sh, uh = _normalize_hours(svc, setup_hours=setup_hours, unit_hours=unit_hours)

    updates: Dict[str, Any] = {
        "machine_id": mc_id,
        "operator_id": operator_id_text,
        "setup_hours": float(sh),
        "unit_hours": float(uh),
    }
    if status is not None:
        st = _normalize_batch_op_status(svc, status)
        if st is not None:
            updates["status"] = st

    with svc.tx_manager.transaction():
        svc.op_repo.update(op_id_int, updates)

    return svc._get_op_or_raise(op_id_int)


def update_external_operation(
    svc,
    op_id: Any,
    supplier_id: Any = None,
    ext_days: Any = None,
    status: Any = None,
) -> BatchOperation:
    """
    外部工序补充信息：
    - supplier_id / ext_days 在显式编辑外部工序补充信息时一并校验
    - ext_days 必须 >0（merged 外部组时禁止逐道设置）
    - 仅更新状态时，不应隐式清空 supplier_id / ext_days
    """
    op = get_operation(svc, op_id)
    if op.id is None:
        raise BusinessError(ErrorCode.NOT_FOUND, f"批次工序（ID={op_id}）不存在")
    op_id_int = int(op.id)
    if (op.source or "").strip().lower() != SourceType.EXTERNAL.value:
        raise ValidationError("只能编辑外部工序的供应商/周期信息", field="source")

    supplier_provided = supplier_id is not None
    ext_days_provided = ext_days is not None
    sup_id = svc._normalize_text(supplier_id)
    if sup_id:
        s = svc.supplier_repo.get(sup_id)
        if not s:
            raise BusinessError(ErrorCode.NOT_FOUND, f"供应商“{sup_id}”不存在")
        if (s.status or "").strip().lower() != SupplierStatus.ACTIVE.value:
            raise BusinessError(ErrorCode.RESOURCE_NOT_AVAILABLE, f"供应商“{sup_id}”已停用，不可用于排产。")

    # 合并周期（merged）时：周期不在 BatchOperations.ext_days 上维护
    _tmpl, grp = svc._get_template_and_group_for_op(op)
    merged_group = bool(grp and (str(getattr(grp, "merge_mode", None) or "").strip().lower() == MergeMode.MERGED.value))
    if merged_group:
        if ext_days is not None and svc._normalize_text(ext_days) is not None:
            td = grp.total_days
            td_text = f"{td} 天" if td is not None else "（未设置）"
            raise ValidationError(
                f"该外部工序属于“合并周期”外部组，不能逐道设置周期。请在工艺管理中设置该组的合并周期（当前：{td_text}）。",
                field="周期",
            )
        # merged：保持 ext_days 为 NULL，避免误导
        ext_days_value = None
    else:
        if ext_days_provided:
            dv = parse_required_float(ext_days, field="外协周期(天)")
            if float(dv) <= 0:
                raise ValidationError("“外协周期(天)”必须大于 0", field="外协周期(天)")
            ext_days_value = float(dv)
        elif supplier_provided:
            raise ValidationError("“外协周期(天)”不能为空", field="外协周期(天)")
        else:
            ext_days_value = None

    updates: Dict[str, Any] = {}
    if supplier_provided:
        updates["supplier_id"] = sup_id
    if ext_days_provided or supplier_provided:
        updates["ext_days"] = ext_days_value
    if status is not None:
        st = _normalize_batch_op_status(svc, status)
        if st is not None:
            updates["status"] = st

    with svc.tx_manager.transaction():
        svc.op_repo.update(op_id_int, updates)

    return svc._get_op_or_raise(op_id_int)

