from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Set, Tuple

from flask import current_app, g, render_template, request, url_for

from core.models.enums import MachineStatus, OperatorStatus, SourceType, SupplierStatus, YesNo
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.report.calculation_helpers import is_valid_interval
from core.services.scheduler._sched_display_utils import display_machine, display_operator, parse_dt
from core.services.scheduler.execution_fact_presentation import execution_detail_meta
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.gantt_task_labels import public_task_label
from web.viewmodels.scheduler_batch_schedule_placement import build_schedule_placement
from web.viewmodels.scheduler_history_summary import format_public_datetime
from web.viewmodels.strict_mode_toggles import build_strict_mode_toggle

from ...navigation_utils import _safe_next_url
from .scheduler_bp import _batch_status_zh, _priority_zh, _ready_zh, bp
from .scheduler_ops import operation_update_token

if TYPE_CHECKING:
    from core.services.equipment import MachineService
    from core.services.personnel import OperatorService
    from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
    from core.services.process import SupplierService


class _MergeHintService(Protocol):
    def get_external_merge_hint(self, op_id: Any) -> Dict[str, Any]:
        ...



def _count_internal_ops(ops: List[Any]) -> int:
    cnt = 0
    for op in ops or []:
        src = (getattr(op, "source", "") or "").strip().lower()
        if src == SourceType.INTERNAL.value:
            cnt += 1
    return cnt


def _collect_selected_resource_ids(ops: List[Any]) -> Tuple[Set[str], Set[str], Set[str]]:
    selected_machine_ids: Set[str] = set()
    selected_operator_ids: Set[str] = set()
    selected_supplier_ids: Set[str] = set()
    for op in ops or []:
        src = (getattr(op, "source", "") or "").strip().lower()
        if src == SourceType.INTERNAL.value:
            if getattr(op, "machine_id", None):
                selected_machine_ids.add(str(op.machine_id))
            if getattr(op, "operator_id", None):
                selected_operator_ids.add(str(op.operator_id))
        elif src == SourceType.EXTERNAL.value:
            if getattr(op, "supplier_id", None):
                selected_supplier_ids.add(str(op.supplier_id))
    return selected_machine_ids, selected_operator_ids, selected_supplier_ids


def _build_machine_options(machine_svc: MachineService, selected_machine_ids: Set[str]) -> List[Dict[str, Any]]:
    machines_active = machine_svc.list(status=MachineStatus.ACTIVE.value)
    machines_by_id = {m.machine_id: m for m in machines_active}
    missing_machine_ids: Set[str] = set()
    for mid in sorted(selected_machine_ids):
        if mid in machines_by_id:
            continue
        extra = machine_svc.get_optional(mid)
        if extra:
            machines_by_id[extra.machine_id] = extra
        else:
            missing_machine_ids.add(mid)

    machine_options: List[Dict[str, Any]] = []
    for m in sorted(
        machines_by_id.values(),
        key=lambda x: ((x.status or "").strip() != MachineStatus.ACTIVE.value, x.machine_id),
    ):
        status_text = (m.status or "").strip()
        disabled = status_text != MachineStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        machine_options.append(
            {"value": m.machine_id, "label": f"{m.machine_id} {m.name}{status_note}", "disabled": disabled}
        )
    for mid in sorted(missing_machine_ids):
        machine_options.append({"value": mid, "label": f"{mid}（已删除）", "disabled": True, "orphan": True})
    return machine_options


def _build_operator_options(operator_svc: OperatorService, selected_operator_ids: Set[str]) -> List[Dict[str, Any]]:
    operators_active = operator_svc.list(status=OperatorStatus.ACTIVE.value)
    operators_by_id = {o.operator_id: o for o in operators_active}
    missing_operator_ids: Set[str] = set()
    for oid in sorted(selected_operator_ids):
        if oid in operators_by_id:
            continue
        extra = operator_svc.get_optional(oid)
        if extra:
            operators_by_id[extra.operator_id] = extra
        else:
            missing_operator_ids.add(oid)

    operator_options: List[Dict[str, Any]] = []
    for o in sorted(
        operators_by_id.values(),
        key=lambda x: ((x.status or "").strip() != OperatorStatus.ACTIVE.value, x.operator_id),
    ):
        status_text = (o.status or "").strip()
        disabled = status_text != OperatorStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        operator_options.append(
            {"value": o.operator_id, "label": f"{o.operator_id} {o.name}{status_note}", "disabled": disabled}
        )
    for oid in sorted(missing_operator_ids):
        operator_options.append({"value": oid, "label": f"{oid}（已删除）", "disabled": True, "orphan": True})
    return operator_options


def _build_supplier_options(supplier_svc: SupplierService, selected_supplier_ids: Set[str]) -> List[Dict[str, Any]]:
    suppliers_active = supplier_svc.list(status=SupplierStatus.ACTIVE.value)
    suppliers_by_id = {s.supplier_id: s for s in suppliers_active}
    missing_supplier_ids: Set[str] = set()
    for sid in sorted(selected_supplier_ids):
        if sid in suppliers_by_id:
            continue
        extra = supplier_svc.get_optional(sid)
        if extra:
            suppliers_by_id[extra.supplier_id] = extra
        else:
            missing_supplier_ids.add(sid)

    supplier_options: List[Dict[str, Any]] = []
    for s in sorted(
        suppliers_by_id.values(),
        key=lambda x: ((x.status or "").strip() != SupplierStatus.ACTIVE.value, x.supplier_id),
    ):
        status_text = (s.status or "").strip()
        disabled = status_text != SupplierStatus.ACTIVE.value
        status_note = f"（不可用：{status_text}）" if disabled else ""
        name = (s.name or "").strip()
        label = f"{s.supplier_id} {name}".strip() + status_note
        supplier_options.append({"value": s.supplier_id, "label": label, "disabled": disabled})
    for sid in sorted(missing_supplier_ids):
        supplier_options.append({"value": sid, "label": f"{sid}（已删除）", "disabled": True})
    return supplier_options


def _resolve_lazy_select_enabled(
    internal_op_count: int,
    machine_options: List[Dict[str, Any]],
    operator_options: List[Dict[str, Any]],
) -> bool:
    lazy_q = (request.args.get("lazy_select") or "").strip().lower()
    if lazy_q in ("1", "true", "yes", "y", "on"):
        return True
    if lazy_q in ("0", "false", "no", "n", "off"):
        return False
    return bool(internal_op_count > 30 or len(machine_options) > 80 or len(operator_options) > 80)


def _build_machine_operator_maps(
    *,
    machine_options: List[Dict[str, Any]],
    operator_options: List[Dict[str, Any]],
    selected_machine_ids: Set[str],
    selected_operator_ids: Set[str],
    prefer_primary_skill: str,
    om_q: OperatorMachineQueryService,
) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Dict[str, Any]]]]:
    active_machine_ids = [x["value"] for x in machine_options if not x.get("disabled")]
    active_operator_ids = [x["value"] for x in operator_options if not x.get("disabled")]
    machine_ids_needed = set(active_machine_ids) | set(selected_machine_ids)
    operator_ids_needed = set(active_operator_ids) | set(selected_operator_ids)

    machine_operators: Dict[str, List[str]] = {}
    machine_operator_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    if not machine_ids_needed or not operator_ids_needed:
        return machine_operators, machine_operator_meta

    m_list = sorted(machine_ids_needed)
    o_list = sorted(operator_ids_needed)
    link_rows = om_q.list_simple_rows_for_machine_operator_sets(m_list, o_list)
    for r in link_rows:
        mc_id = r.get("machine_id")
        op_id = r.get("operator_id")
        if not mc_id or not op_id:
            continue
        machine_operators.setdefault(mc_id, []).append(op_id)
        if prefer_primary_skill == YesNo.YES.value:
            machine_operator_meta.setdefault(mc_id, {})[op_id] = {
                "skill_level": r.get("skill_level"),
                "is_primary": r.get("is_primary"),
            }
    return machine_operators, machine_operator_meta


def _build_view_ops(ops: List[Any], sch_svc: _MergeHintService) -> List[Dict[str, Any]]:
    view_ops: List[Dict[str, Any]] = []
    # 快速路径是可选能力：
    # - 新实现优先提供 get_external_merge_hint_for_op(op)
    # - 旧实现只要求满足 fallback 契约 get_external_merge_hint(op_id)
    # 因此这里用动态探测，而不是把快速路径硬塞进基础协议，避免把 fallback-only 调用方判为类型不兼容。
    merge_hint_getter = getattr(sch_svc, "get_external_merge_hint_for_op", None)
    merge_hint_fallback = sch_svc.get_external_merge_hint
    for op in ops or []:
        d = op.to_dict()
        source = (d.get("source") or "").strip().lower()
        d["source"] = source
        if source != SourceType.EXTERNAL.value:
            d["merge_hint"] = {"is_external": False}
        elif callable(merge_hint_getter):
            d["merge_hint"] = merge_hint_getter(op)
        else:
            d["merge_hint"] = merge_hint_fallback(op.id)
        view_ops.append(d)
    return view_ops


# 排程去向卡只下传 4.10 公开 *_label/has_* 键，不含裸 actual_start_time/actual_end_time
_PLACEMENT_OP_LABEL_KEYS = (
    "execution_status_label",
    "actual_start_time_label",
    "actual_end_time_label",
    "actual_summary_label",
    "has_execution_record",
)


def _placement_op_row(row: Dict[str, Any], facts: Dict[int, Any]) -> Dict[str, Any]:
    # 现场事实经 4.10 单源 execution_detail_meta；计划设备/人员走全站单源 display_*（含外协兜底）；
    # 工序名走 public_task_label 单源。最终只出公开 label，不外显 op_id/machine_id 等 raw 计划内部身份。
    # int 强转对齐被抽取源 gantt_tasks 惯例：facts 字典以 int(op_id) 为键，显式强转把
    # 「op_id 是 int」的 DB 列类型假设变成显式契约，防未来 op_id 走字符串路径时静默 miss 退化成空。
    meta = execution_detail_meta(facts.get(int(row.get("op_id") or 0)))
    out: Dict[str, Any] = {
        "op_label": public_task_label(row),
        "plan_machine_label": display_machine(
            row.get("machine_id"), row.get("machine_name"), row.get("supplier_name")
        ),
        "plan_operator_label": display_operator(row.get("operator_id"), row.get("operator_name")),
    }
    for key in _PLACEMENT_OP_LABEL_KEYS:
        out[key] = meta[key]
    return out


@dataclass(frozen=True)
class PlacementSpan:
    from_date: Optional[str]
    to_date: Optional[str]
    label: str
    status: str
    bad_time_count: int = 0
    notice: str = ""

    def __iter__(self):
        yield self.from_date
        yield self.to_date
        yield self.label

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tuple):
            return tuple(self) == other
        return super().__eq__(other)


def _has_text(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _batch_detail_return_url() -> str:
    next_raw = (request.args.get("next") or "").strip()
    next_url = _safe_next_url(next_raw) if next_raw else None
    return next_url or url_for("scheduler.batches_manage_page")


def _placement_span(rows: List[Dict[str, Any]]) -> PlacementSpan:
    # 只有同一行 start/end 都可解析且区间有效时才参与窗口，避免半条坏时间撑大跨度。
    # 返回给甘特链接的 YYYY-MM-DD 日期窗口 + 含时分的中文 span_label。
    starts: List[Tuple[Any, Any]] = []
    ends: List[Tuple[Any, Any]] = []
    bad_time_count = 0
    for row in rows:
        row_bad = False
        s_raw = row.get("start_time")
        s_dt = parse_dt(s_raw)
        if s_dt is None:
            row_bad = True
        e_raw = row.get("end_time")
        e_dt = parse_dt(e_raw)
        if e_dt is None:
            row_bad = True
        if s_dt is not None and e_dt is not None and not is_valid_interval(s_dt, e_dt):
            row_bad = True
        if row_bad:
            bad_time_count += 1
            continue
        starts.append((s_dt, s_raw))
        ends.append((e_dt, e_raw))
    if not starts or not ends:
        notice = ""
        if bad_time_count > 0:
            notice = f"有 {bad_time_count} 条排程记录的开始或结束时间缺失或写法不对，时间跨度无法计算；已排工序数量仍是全量。"
        return PlacementSpan(None, None, "时间记录异常", "error", bad_time_count=bad_time_count, notice=notice)
    min_start_dt, min_start_raw = min(starts, key=lambda p: p[0])
    max_end_dt, max_end_raw = max(ends, key=lambda p: p[0])
    span_label = f"{format_public_datetime(min_start_raw)} ～ {format_public_datetime(max_end_raw)}"
    status = "partial" if bad_time_count > 0 else "ok"
    notice = ""
    if bad_time_count > 0:
        notice = f"有 {bad_time_count} 条排程记录的开始或结束时间缺失或写法不对，时间跨度只按可解析记录计算；已排工序数量仍是全量。"
    return PlacementSpan(
        min_start_dt.date().isoformat(),
        max_end_dt.date().isoformat(),
        span_label,
        status,
        bad_time_count=bad_time_count,
        notice=notice,
    )


def _resolve_schedule_placement(services: Any, batch_id: str) -> Dict[str, Any]:
    """批次详情排程去向卡取数（整段含 get_latest_version 与 g.db/provider 构造一并 try）。

    诚实五态：无版本→no_official_plan；本批次无行但版本级有明细→not_placed；版本级也无明细→
    plan_empty；正常→ok；任何异常→logger.exception 留栈 + error 态（不静默吞，只本卡降级、整页不 500）。
    现场事实走 4.10 唯一入口、硬钉 adopted、不传 include_op_ids（缺事实工序自然走「暂未记录现场实际」）。
    """
    try:
        history_svc = services.schedule_history_query_service
        version = history_svc.get_latest_version()
        if version <= 0:
            return build_schedule_placement(state="no_official_plan")
        plan_svc = services.schedule_plan_query_service
        resolution = plan_svc.resolve_plan(version, ROLE_ADOPTED)
        rows = plan_svc.list_plan_detail_rows_all_for_resolution(
            version=version,
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            batch_id=batch_id,
        )
        if not rows:
            version_span = plan_svc.get_plan_time_span_for_resolution(
                version=version,
                source_table=resolution.source_table,
                candidate_id=resolution.candidate_id,
                scenario_id=resolution.scenario_id,
            )
            return build_schedule_placement(
                state="plan_empty" if version_span is None else "not_placed"
            )
        hist = history_svc.get_by_version(version)
        plan_fields = {
            "version": version,
            "source_table": resolution.source_table,
            "effective_plan_role": resolution.selected_role,
            "scenario_id": resolution.scenario_id,
        }
        facts = ExecutionFactProvider(g.db, logger=current_app.logger).facts_by_op_id_for_plan_rows(
            rows, plan_fields
        )
        span = _placement_span(rows)
        return build_schedule_placement(
            state="ok",
            batch_id=batch_id,
            version=version,
            op_count=len(rows),
            op_rows=[_placement_op_row(row, facts) for row in rows],
            span_from_date=span.from_date,
            span_to_date=span.to_date,
            span_label=span.label,
            span_status=span.status,
            span_bad_time_count=span.bad_time_count,
            span_notice=span.notice,
            generated_at=hist.schedule_time if hist is not None else None,
            strategy=hist.strategy if hist is not None else None,
            history_present=hist is not None,
        )
    except Exception:
        current_app.logger.exception("批次详情排程去向卡取数失败：batch_id=%s", batch_id)
        return build_schedule_placement(state="error")


@bp.get("/batches/<batch_id>")
def batch_detail(batch_id: str):
    services = g.services
    batch_svc = services.batch_service
    sch_svc = services.schedule_service
    batch_return_url = _batch_detail_return_url()

    b = batch_svc.get(batch_id)
    ops = sch_svc.list_batch_operations(batch_id=b.batch_id)

    internal_op_count = _count_internal_ops(ops)
    selected_machine_ids, selected_operator_ids, selected_supplier_ids = _collect_selected_resource_ids(ops)

    machine_svc = services.machine_service
    operator_svc = services.operator_service
    supplier_svc = services.supplier_service

    machine_options = _build_machine_options(machine_svc, selected_machine_ids)
    operator_options = _build_operator_options(operator_svc, selected_operator_ids)
    supplier_options = _build_supplier_options(supplier_svc, selected_supplier_ids)

    lazy_select_enabled = _resolve_lazy_select_enabled(internal_op_count, machine_options, operator_options)

    prefer_primary_skill = services.config_service.get_snapshot().prefer_primary_skill
    om_q = services.operator_machine_query_service
    machine_operators, machine_operator_meta = _build_machine_operator_maps(
        machine_options=machine_options,
        operator_options=operator_options,
        selected_machine_ids=selected_machine_ids,
        selected_operator_ids=selected_operator_ids,
        prefer_primary_skill=prefer_primary_skill,
        om_q=om_q,
    )

    view_ops = _build_view_ops(ops, sch_svc)
    operation_update_actions = {}
    for index, op in enumerate(view_ops, start=1):
        form_key = f"opform_{index}"
        op["form_key"] = form_key
        operation_update_actions[form_key] = url_for(
            "scheduler.update_op_by_token",
            token=operation_update_token(int(op.get("id") or 0)),
            next=batch_return_url,
        )
    schedule_placement = _resolve_schedule_placement(services, b.batch_id)

    return render_template(
        "scheduler/batch_detail.html",
        title=f"批次详情 - {b.batch_id}",
        batch=b.to_dict(),
        batch_status_zh=_batch_status_zh(b.status),
        priority_zh=_priority_zh(b.priority),
        ready_status_zh=_ready_zh(b.ready_status),
        operations=view_ops,
        machine_options=machine_options,
        operator_options=operator_options,
        supplier_options=supplier_options,
        machine_operators=machine_operators,
        # operatorMachines 可在前端由 machineOperators 反推，避免双份映射带来的 HTML 膨胀
        operator_machines=None,
        machine_operator_meta=machine_operator_meta,
        prefer_primary_skill=prefer_primary_skill,
        lazy_select_enabled=lazy_select_enabled,
        batch_detail_strict_toggle=build_strict_mode_toggle(
            "batchDetailStrictMode",
            desc="工艺模板资料不完整时，不刷新本批次工序。",
        ),
        schedule_placement=schedule_placement,
        operation_update_actions=operation_update_actions,
        batch_return_url=batch_return_url,
        batch_return_next=batch_return_url,
    )
