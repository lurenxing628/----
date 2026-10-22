from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models import BatchOperation
from core.models.enums import BatchOperationStatus, MachineStatus, MergeMode, OperatorStatus, SupplierStatus
from core.services.personnel.operator_qualification import OperatorQualificationService, require_machine_authorization
from core.shared.strict_parse import parse_optional_float, parse_required_float

_OPERATION_NOT_FOUND_MESSAGE = "这道工序不存在或已被删除，请刷新批次详情后重试。"


def get_operation(svc, op_id: Any) -> BatchOperation:
    try:
        oid = int(op_id)
    except Exception as e:
        raise ValidationError("工序编号不正确，请刷新批次详情后重试。", field="op_id") from e
    return svc._get_op_or_raise(oid)


def _normalize_batch_op_status(svc, value: Any) -> Optional[str]:
    st = svc._normalize_text(value)
    if st is None:
        return None
    st = st.lower()
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


def _ensure_internal_operation_editable(op: BatchOperation) -> int:
    if op.id is None:
        raise BusinessError(ErrorCode.NOT_FOUND, _OPERATION_NOT_FOUND_MESSAGE)
    if not op.is_internal():
        raise ValidationError("只能编辑内部工序的设备/人员/工时信息", field="source")
    return int(op.id)


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
    if not operator_id_text:
        return
    require_machine_authorization(svc.operator_machine_repo, operator_id_text, mc_id)
    OperatorQualificationService(svc.conn, logger=svc.logger).require(
        operator_id=operator_id_text, op_type_id=op.op_type_id, machine_id=None,
    )


def _normalize_hours(*, setup_hours: Any, unit_hours: Any) -> Tuple[float, float]:
    sh = parse_optional_float(setup_hours, field="换型时间(小时)")
    uh = parse_optional_float(unit_hours, field="单件工时(小时)")
    sh2 = 0.0 if sh is None else float(sh)
    uh2 = 0.0 if uh is None else float(uh)
    if sh2 < 0 or uh2 < 0:
        raise ValidationError("工时不能为负数", field="工时")
    return sh2, uh2


def _ensure_external_operation_editable(op: BatchOperation) -> int:
    if op.id is None:
        raise BusinessError(ErrorCode.NOT_FOUND, _OPERATION_NOT_FOUND_MESSAGE)
    if not op.is_external():
        raise ValidationError("只能编辑外协工序的供应商/周期信息", field="source")
    return int(op.id)


def _validate_supplier_available(svc, sup_id: Optional[str]) -> None:
    if not sup_id:
        return
    supplier = svc.supplier_repo.get(sup_id)
    if not supplier:
        raise BusinessError(ErrorCode.NOT_FOUND, f"供应商“{sup_id}”不存在")
    if (supplier.status or "").strip().lower() != SupplierStatus.ACTIVE.value:
        raise BusinessError(ErrorCode.RESOURCE_NOT_AVAILABLE, f"供应商“{sup_id}”已停用，不可用于排产。")


def _is_merged_external_group(group: Any) -> bool:
    return bool(group and (str(getattr(group, "merge_mode", None) or "").strip().lower() == MergeMode.MERGED.value))


def _raise_merged_ext_days_error(group: Any) -> None:
    total_days = getattr(group, "total_days", None)
    total_days_text = f"{total_days} 天" if total_days is not None else "（未设置）"
    raise ValidationError(
        f"该外协工序属于“合并周期”外协组，不能逐道设置周期。请在工艺管理中设置该组的合并周期（当前：{total_days_text}）。",
        field="周期",
    )


def _normalize_positive_ext_days(ext_days: Any) -> float:
    value = parse_required_float(ext_days, field="外协周期(天)")
    if float(value) <= 0:
        raise ValidationError("“外协周期(天)”必须大于 0", field="外协周期(天)")
    return float(value)


def _resolve_external_ext_days_value(
    svc,
    *,
    op: BatchOperation,
    supplier_provided: bool,
    ext_days_provided: bool,
    ext_days: Any,
) -> Optional[float]:
    _tmpl, group = svc._get_template_and_group_for_op(op)
    if _is_merged_external_group(group):
        if ext_days_provided and svc._normalize_text(ext_days) is not None:
            _raise_merged_ext_days_error(group)
        return None
    if ext_days_provided:
        return _normalize_positive_ext_days(ext_days)
    if supplier_provided:
        raise ValidationError("“外协周期(天)”不能为空", field="外协周期(天)")
    return None


def _build_external_operation_updates(
    svc,
    *,
    supplier_provided: bool,
    ext_days_provided: bool,
    sup_id: Optional[str],
    ext_days_value: Optional[float],
    status: Any,
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if supplier_provided:
        updates["supplier_id"] = sup_id
    if ext_days_provided or supplier_provided:
        updates["ext_days"] = ext_days_value
    if status is not None:
        st = _normalize_batch_op_status(svc, status)
        if st is not None:
            updates["status"] = st
    return updates


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
    op_id_int = _ensure_internal_operation_editable(op)

    mc_id = svc._normalize_text(machine_id)
    operator_id_text = svc._normalize_text(operator_id)

    # 设备存在性 + 可用性（维护/停用时禁止分配）
    _validate_machine_available(svc, mc_id)

    # 人员存在性 + 在岗性
    _validate_operator_available(svc, operator_id_text)

    sh, uh = _normalize_hours(setup_hours=setup_hours, unit_hours=unit_hours)

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
        _validate_operator_machine_match(svc, mc_id=mc_id, operator_id_text=operator_id_text, op=op)
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
    op_id_int = _ensure_external_operation_editable(op)

    supplier_provided = supplier_id is not None
    ext_days_provided = ext_days is not None
    sup_id = svc._normalize_text(supplier_id)
    _validate_supplier_available(svc, sup_id)
    ext_days_value = _resolve_external_ext_days_value(
        svc,
        op=op,
        supplier_provided=supplier_provided,
        ext_days_provided=ext_days_provided,
        ext_days=ext_days,
    )
    updates = _build_external_operation_updates(
        svc,
        supplier_provided=supplier_provided,
        ext_days_provided=ext_days_provided,
        sup_id=sup_id,
        ext_days_value=ext_days_value,
        status=status,
    )

    with svc.tx_manager.transaction():
        svc.op_repo.update(op_id_int, updates)

    return svc._get_op_or_raise(op_id_int)
