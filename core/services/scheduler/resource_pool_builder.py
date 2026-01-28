from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import SourceType
from data.repositories import MachineDowntimeRepository


def load_machine_downtimes(
    svc,
    *,
    algo_ops: List[Any],
    start_dt: datetime,
) -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    预加载停机区间（按设备维度展开后的记录），用于算法避让。
    """
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]] = {}
    try:
        dt_repo = MachineDowntimeRepository(svc.conn, logger=svc.logger)
        start_str = svc._format_dt(start_dt)
        machine_ids = sorted(
            {
                (op.machine_id or "").strip()
                for op in algo_ops
                if (op.source or "").strip() == SourceType.INTERNAL.value and (op.machine_id or "").strip()
            }
        )
        for mid in machine_ids:
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
    except Exception:
        downtime_map = {}
    return downtime_map


def build_resource_pool(
    svc,
    *,
    cfg: Any,
    algo_ops: List[Any],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    构建算法自动分配资源池（可选）。

    Returns:
        (resource_pool, warnings)
    """
    warnings: List[str] = []
    resource_pool: Optional[Dict[str, Any]] = None

    auto_assign_enabled = getattr(cfg, "auto_assign_enabled", "no") == "yes"
    if not auto_assign_enabled:
        return None, warnings

    try:
        # 仅考虑 active 资源
        machines = svc.machine_repo.list(status="active")
        active_machines = {str(m.machine_id or "").strip() for m in machines if m and str(m.machine_id or "").strip()}

        # 仅对本次排产涉及的 op_type_id 构建映射（缺省/为空则退化为全量）
        op_type_ids = {
            str(getattr(o, "op_type_id", "") or "").strip()
            for o in algo_ops
            if (getattr(o, "source", "") or "").strip() == SourceType.INTERNAL.value and str(getattr(o, "op_type_id", "") or "").strip()
        }
        machines_by_op_type: Dict[str, List[str]] = {}
        for m in machines:
            mid = str(m.machine_id or "").strip()
            ot = str(m.op_type_id or "").strip()
            if not mid or mid not in active_machines:
                continue
            if op_type_ids and ot and ot not in op_type_ids:
                continue
            machines_by_op_type.setdefault(ot, []).append(mid)

        active_ops = {str(o.operator_id or "").strip() for o in svc.operator_repo.list(status="active") if o and str(o.operator_id or "").strip()}

        # OperatorMachine：一次性取出，按设备聚合（并按“主操/技能”做轻量排序）
        rows = svc.operator_machine_repo.list_simple_rows()
        operators_by_machine: Dict[str, List[Tuple[int, str]]] = {}  # machine_id -> [(rank, operator_id)]
        machines_by_operator: Dict[str, List[str]] = {}
        pair_rank: Dict[Tuple[str, str], int] = {}

        def _skill_rank(v: Any) -> int:
            """
            技能等级排序（数值越小越优）。

            兼容：
            - 新口径：beginner/normal/expert（见 OperatorMachineService）
            - 旧口径：low/normal/high（历史数据/脚本）
            - 常见中文：初级/普通/熟练（以及 高级/专家/一般/中级/新手）
            """
            s0 = str(v or "").strip()
            if s0 == "":
                return 9
            low = s0.lower()
            if low in ("expert", "high", "skilled"):
                return 0
            if low in ("normal",):
                return 1
            if low in ("beginner", "low"):
                return 2
            if s0 in ("熟练", "高级", "专家"):
                return 0
            if s0 in ("普通", "一般", "中级"):
                return 1
            if s0 in ("初级", "新手"):
                return 2
            return 9

        for r in rows:
            oid = str(r["operator_id"] or "").strip()
            mid = str(r["machine_id"] or "").strip()
            if not oid or not mid:
                continue
            if mid not in active_machines:
                continue
            if oid not in active_ops:
                continue
            is_primary = str(r["is_primary"] or "").strip().lower()
            sr = _skill_rank(r["skill_level"])
            rank = (0 if is_primary in ("yes", "y", "true", "1", "on") else 1) * 10 + sr
            operators_by_machine.setdefault(mid, []).append((int(rank), oid))
            machines_by_operator.setdefault(oid, []).append(mid)
            pair_rank[(oid, mid)] = int(rank)

        # 排序：rank 越小越优（主操优先，其次高技能）
        operators_by_machine_sorted: Dict[str, List[str]] = {}
        for mid, items in operators_by_machine.items():
            items.sort(key=lambda x: (x[0], x[1]))
            operators_by_machine_sorted[mid] = [oid for _, oid in items]

        resource_pool = {
            "machines_by_op_type": machines_by_op_type,
            "operators_by_machine": operators_by_machine_sorted,
            "machines_by_operator": machines_by_operator,
            "pair_rank": pair_rank,
        }
    except Exception as e:
        resource_pool = None
        # 不阻断排产：自动分配降级为关闭，但要让用户/日志可观测
        warnings.append("自动分配资源池构建失败，已降级为不自动分配（请查看日志）。")
        if svc.logger:
            try:
                svc.logger.warning(f"自动分配资源池构建失败，已降级为不自动分配：{e}")
            except Exception:
                pass

    return resource_pool, warnings


def extend_downtime_map_for_resource_pool(
    svc,
    *,
    cfg: Any,
    resource_pool: Optional[Dict[str, Any]],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    start_dt: datetime,
) -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    auto-assign 启用时：停机区间需要覆盖“候选设备”，否则算法可能误排到停机段内。
    """
    auto_assign_enabled = getattr(cfg, "auto_assign_enabled", "no") == "yes"
    if not auto_assign_enabled or not resource_pool or not isinstance(resource_pool.get("operators_by_machine"), dict):
        return downtime_map

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
        for mid in extra_mids:
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
    except Exception:
        pass

    return downtime_map

