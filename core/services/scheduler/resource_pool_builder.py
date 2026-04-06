from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import MachineStatus, OperatorStatus, SourceType, YesNo
from core.services.common.enum_normalizers import skill_rank as _skill_rank_common
from core.services.common.safe_logging import safe_warning
from data.repositories import MachineDowntimeRepository

from .number_utils import to_yes_no


def _skill_rank(v: Any) -> int:
    """
    技能等级排序（数值越小越优）。

    兼容：
    - 新口径：beginner/normal/expert（见 OperatorMachineService）
    - 旧口径：low/normal/high（历史数据/脚本）
    - 常见中文：初级/普通/熟练（以及 高级/专家/一般/中级/新手）
    """
    return int(_skill_rank_common(v))


def _active_machine_ids(machines: List[Any]) -> set:
    return {str(m.machine_id or "").strip() for m in machines if m and str(m.machine_id or "").strip()}


def _op_type_ids_for_ops(algo_ops: List[Any]) -> set:
    return {
        str(getattr(o, "op_type_id", "") or "").strip()
        for o in algo_ops
        if (getattr(o, "source", "") or "").strip().lower() == SourceType.INTERNAL.value
        and str(getattr(o, "op_type_id", "") or "").strip()
    }


def _machines_by_op_type(
    machines: List[Any],
    *,
    active_machines: set,
    op_type_ids: set,
) -> Dict[str, List[str]]:
    machines_by_op_type: Dict[str, List[str]] = {}
    for m in machines:
        mid = str(m.machine_id or "").strip()
        ot = str(m.op_type_id or "").strip()
        if not mid or mid not in active_machines:
            continue
        if op_type_ids and ot and ot not in op_type_ids:
            continue
        machines_by_op_type.setdefault(ot, []).append(mid)
    return machines_by_op_type


def _active_operator_ids(svc) -> set:
    return {
        str(o.operator_id or "").strip()
        for o in svc.operator_repo.list(status=OperatorStatus.ACTIVE.value)
        if o and str(o.operator_id or "").strip()
    }


def _build_operator_machine_maps(
    rows: List[Dict[str, Any]],
    *,
    active_machines: set,
    active_ops: set,
) -> Tuple[Dict[str, List[Tuple[int, str]]], Dict[str, List[str]], Dict[Tuple[str, str], int]]:
    operators_by_machine: Dict[str, List[Tuple[int, str]]] = {}  # machine_id -> [(rank, operator_id)]
    machines_by_operator: Dict[str, List[str]] = {}
    pair_rank: Dict[Tuple[str, str], int] = {}

    for r in rows:
        oid = str(r["operator_id"] or "").strip()
        mid = str(r["machine_id"] or "").strip()
        if not oid or not mid:
            continue
        if mid not in active_machines:
            continue
        if oid not in active_ops:
            continue
        is_primary_yes = to_yes_no(r.get("is_primary"), default=YesNo.NO.value) == YesNo.YES.value
        sr = _skill_rank(r.get("skill_level"))
        rank = (0 if is_primary_yes else 1) * 10 + sr
        operators_by_machine.setdefault(mid, []).append((int(rank), oid))
        machines_by_operator.setdefault(oid, []).append(mid)
        pair_rank[(oid, mid)] = int(rank)

    return operators_by_machine, machines_by_operator, pair_rank


def _sort_operators_by_machine(operators_by_machine: Dict[str, List[Tuple[int, str]]]) -> Dict[str, List[str]]:
    # 排序：rank 越小越优（主操优先，其次高技能）
    out: Dict[str, List[str]] = {}
    for mid, items in operators_by_machine.items():
        items.sort(key=lambda x: (x[0], x[1]))
        out[mid] = [oid for _, oid in items]
    return out


def _append_warning(warnings: Optional[List[str]], message: str) -> None:
    if warnings is not None:
        warnings.append(message)


def _warn_service_logger(svc: Any, message: str, *, exc_info: bool = False) -> None:
    safe_warning(getattr(svc, "logger", None), message, exc_info=exc_info)



def load_machine_downtimes(
    svc,
    *,
    algo_ops: List[Any],
    start_dt: datetime,
    warnings: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    预加载停机区间（按设备维度展开后的记录），用于算法避让。
    """
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]] = {}
    if meta is not None:
        # 约定：即使 downtime_map 为空，只要加载流程未抛异常，也认为“加载成功但无停机”
        meta["downtime_load_ok"] = False
        meta["downtime_load_error"] = None
        meta["downtime_partial_fail_count"] = 0
        meta["downtime_partial_fail_machines_sample"] = []

    try:
        dt_repo = MachineDowntimeRepository(svc.conn, logger=svc.logger)
        start_str = svc._format_dt(start_dt)
        machine_ids = sorted(
            {
                (op.machine_id or "").strip()
                for op in algo_ops
                if (op.source or "").strip().lower() == SourceType.INTERNAL.value and (op.machine_id or "").strip()
            }
        )
    except Exception as e:
        downtime_map = {}
        if meta is not None:
            meta["downtime_load_ok"] = False
            meta["downtime_load_error"] = str(e)
        _append_warning(warnings, f"【停机】停机区间加载失败，已降级为忽略停机约束：{e}")
        _warn_service_logger(svc, f"停机区间加载失败，已降级为忽略停机约束：{e}", exc_info=True)
        return downtime_map

    partial_fail_mids: List[str] = []
    for mid in machine_ids:
        try:
            rows = dt_repo.list_active_after(mid, start_str)
            intervals: List[Tuple[datetime, datetime]] = []
            for d in rows:
                st = svc._normalize_datetime(d.start_time)
                et = svc._normalize_datetime(d.end_time)
                if st and et and et > st:
                    intervals.append((st, et))
            if intervals:
                intervals.sort(key=lambda x: x[0])
                downtime_map[mid] = intervals
        except Exception as e:
            partial_fail_mids.append(str(mid))
            _warn_service_logger(svc, f"停机区间加载部分失败，设备 {mid} 已降级为忽略停机约束：{e}", exc_info=True)

    if partial_fail_mids:
        sample = partial_fail_mids[:5]
        sample_text = "、".join(sample)
        msg = f"部分设备停机区间加载失败（{len(partial_fail_mids)} 台"
        if sample_text:
            msg += f"，如：{sample_text}"
        msg += "），这些设备已降级为忽略停机约束"
        if meta is not None:
            meta["downtime_load_ok"] = False
            meta["downtime_load_error"] = msg
            meta["downtime_partial_fail_count"] = int(len(partial_fail_mids))
            meta["downtime_partial_fail_machines_sample"] = list(sample)
        _append_warning(warnings, f"【停机】{msg}")
    else:
        if meta is not None:
            meta["downtime_load_ok"] = True
            meta["downtime_load_error"] = None

    return downtime_map


def build_resource_pool(
    svc,
    *,
    cfg: Any,
    algo_ops: List[Any],
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    构建算法自动分配资源池（可选）。

    Returns:
        (resource_pool, warnings)
    """
    warnings: List[str] = []
    resource_pool: Optional[Dict[str, Any]] = None
    if meta is not None:
        meta["resource_pool_attempted"] = False
        meta["resource_pool_build_ok"] = None
        meta["resource_pool_build_error"] = None

    auto_assign_enabled = to_yes_no(getattr(cfg, "auto_assign_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    if not auto_assign_enabled:
        return None, warnings

    if meta is not None:
        meta["resource_pool_attempted"] = True

    try:
        # 仅考虑 active 资源
        machines = svc.machine_repo.list(status=MachineStatus.ACTIVE.value)
        active_machines = _active_machine_ids(machines)

        # 仅对本次排产涉及的 op_type_id 构建映射（缺省/为空则退化为全量）
        op_type_ids = _op_type_ids_for_ops(algo_ops)
        machines_by_op_type = _machines_by_op_type(machines, active_machines=active_machines, op_type_ids=op_type_ids)

        active_ops = _active_operator_ids(svc)

        # OperatorMachine：一次性取出，按设备聚合（并按“主操/技能”做轻量排序）
        rows = svc.operator_machine_repo.list_simple_rows()
        operators_by_machine, machines_by_operator, pair_rank = _build_operator_machine_maps(
            rows,
            active_machines=active_machines,
            active_ops=active_ops,
        )
        operators_by_machine_sorted = _sort_operators_by_machine(operators_by_machine)

        resource_pool = {
            "machines_by_op_type": machines_by_op_type,
            "operators_by_machine": operators_by_machine_sorted,
            "machines_by_operator": machines_by_operator,
            "pair_rank": pair_rank,
        }
        if meta is not None:
            meta["resource_pool_build_ok"] = True
    except Exception as e:
        resource_pool = None
        if meta is not None:
            meta["resource_pool_build_ok"] = False
            meta["resource_pool_build_error"] = str(e)
        # 不阻断排产：自动分配降级为关闭，但要让用户/日志可观测
        warnings.append("自动分配资源池构建失败，已降级为不自动分配（请查看日志）。")
        _warn_service_logger(svc, f"自动分配资源池构建失败，已降级为不自动分配：{e}")

    return resource_pool, warnings


def extend_downtime_map_for_resource_pool(
    svc,
    *,
    cfg: Any,
    resource_pool: Optional[Dict[str, Any]],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    start_dt: datetime,
    warnings: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    auto-assign 启用时：停机区间需要覆盖“候选设备”，否则算法可能误排到停机段内。
    """
    auto_assign_enabled = to_yes_no(getattr(cfg, "auto_assign_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value
    if not auto_assign_enabled or not resource_pool or not isinstance(resource_pool.get("operators_by_machine"), dict):
        return downtime_map

    if meta is not None:
        meta["downtime_extend_attempted"] = True
        meta["downtime_extend_ok"] = True
        meta["downtime_extend_error"] = None
        meta["downtime_extend_partial_fail_count"] = 0
        meta["downtime_extend_partial_fail_machines_sample"] = []

    try:
        dt_repo = MachineDowntimeRepository(svc.conn, logger=svc.logger)
        start_str = svc._format_dt(start_dt)
        extra_mids = sorted(
            {
                str(mid).strip()
                for mid in (resource_pool.get("operators_by_machine") or {}).keys()
                if str(mid).strip() and str(mid).strip() not in downtime_map
            }
        )
    except Exception as e:
        if meta is not None:
            meta["downtime_extend_ok"] = False
            meta["downtime_extend_error"] = str(e)
        _append_warning(warnings, f"【停机】停机区间扩展加载失败，候选设备可能未覆盖停机约束：{e}")
        _warn_service_logger(svc, f"停机区间扩展加载失败，候选设备可能未覆盖停机约束：{e}", exc_info=True)
        return downtime_map

    partial_fail_mids: List[str] = []
    for mid in extra_mids:
        try:
            rows = dt_repo.list_active_after(mid, start_str)
            intervals: List[Tuple[datetime, datetime]] = []
            for d in rows:
                st = svc._normalize_datetime(d.start_time)
                et = svc._normalize_datetime(d.end_time)
                if st and et and et > st:
                    intervals.append((st, et))
            if intervals:
                intervals.sort(key=lambda x: x[0])
                downtime_map[mid] = intervals
        except Exception as e:
            partial_fail_mids.append(str(mid))
            _warn_service_logger(svc, f"停机区间扩展部分失败，候选设备 {mid} 可能未覆盖停机约束：{e}", exc_info=True)

    if partial_fail_mids:
        sample = partial_fail_mids[:5]
        sample_text = "、".join(sample)
        msg = f"部分候选设备停机区间扩展加载失败（{len(partial_fail_mids)} 台"
        if sample_text:
            msg += f"，如：{sample_text}"
        msg += "），这些候选设备可能未覆盖停机约束"
        if meta is not None:
            meta["downtime_extend_ok"] = False
            meta["downtime_extend_error"] = msg
            meta["downtime_extend_partial_fail_count"] = int(len(partial_fail_mids))
            meta["downtime_extend_partial_fail_machines_sample"] = list(sample)
        _append_warning(warnings, f"【停机】{msg}")

    return downtime_map

