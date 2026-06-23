from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from core.models.schedule_delay_diagnosis import (
    ConfirmedFact,
    DiagnosisClue,
    DiagnosisTraceMeta,
    OperationClue,
    OverdueDiagnosisItem,
    OverdueDiagnosisReport,
    SuggestedAction,
)
from core.models.schedule_plan_identity import EvidenceLink, PlanIdentity
from core.services.common.overdue_calculations import compute_overdue_bucket_groups, parse_dt

from .schedule_delay_diagnosis_clues import ScheduleDelayDiagnosisClueBuilder
from .schedule_delay_diagnosis_utils import (
    RULE_VERSION,
    all_item_evidences,
    build_trace_meta,
    float_or_default,
    int_or_none,
    plan_link,
    stable_unique,
    text,
    top_clues,
)
from .schedule_plan_query_service import SchedulePlanQueryService


class ScheduleDelayDiagnosisService:
    """只读延期诊断服务。第一版只给事实、线索、证据和缺口，不下唯一根因结论。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.plan_query = SchedulePlanQueryService(conn, logger=logger)
        self.clue_builder = ScheduleDelayDiagnosisClueBuilder(conn, logger=logger)

    def diagnose_resolved_plan_overdue(
        self,
        *,
        version: int,
        resolution: Any,
        as_of_time: Optional[Any] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> OverdueDiagnosisReport:
        identity = resolution.plan_identity
        if identity is None:
            raise ValueError("延期诊断缺少计划身份。")
        as_of_dt = self._as_of(as_of_time)
        generated_at = as_of_dt.strftime("%Y-%m-%d %H:%M:%S")
        base_rows = self.plan_query.list_plan_overdue_base_rows_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        scheduled, unscheduled, invalid_time, as_of_text = compute_overdue_bucket_groups(base_rows, now_dt=as_of_dt)
        detail_rows = self.plan_query.list_plan_detail_rows_all_for_resolution(
            version=int(version),
            source_table=resolution.source_table,
            candidate_id=resolution.candidate_id,
            scenario_id=resolution.scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=batch_id,
        )
        rows_by_batch = self._rows_by_batch(detail_rows)
        overdue_rows = list(scheduled) + list(invalid_time) + list(unscheduled)
        prefetch = self._build_clue_prefetch(overdue_rows=overdue_rows, rows_by_batch=rows_by_batch)
        items = [
            self._diagnose_item(
                row=row,
                rows_by_batch=rows_by_batch,
                plan_identity=identity,
                generated_at=generated_at,
                as_of_text=as_of_text,
                prefetch=prefetch,
            )
            for row in overdue_rows
        ]
        report_trace = build_trace_meta(
            plan_identity=identity,
            generated_at=generated_at,
            as_of_text=as_of_text,
            evidences=all_item_evidences(items),
            ranking_inputs=["overdue_bucket", "delay_hours", "candidate_clue_confidence"],
            clue_selection_trace=["按已排程超期、未排程超期和可追溯证据生成保守线索。"],
        )
        return OverdueDiagnosisReport(
            plan_identity=identity,
            generated_at=generated_at,
            as_of_time=as_of_text,
            total_count=len(items),
            scheduled_count=len(scheduled),
            unscheduled_count=len(unscheduled),
            invalid_time_count=len(invalid_time),
            top_clues=top_clues(items),
            items=items,
            warnings=["没有现场执行反馈时，不判断现场做慢了。"],
            trace_meta=report_trace,
        )


    @staticmethod
    def _as_of(value: Optional[Any]) -> datetime:
        parsed = parse_dt(value)
        return parsed or datetime.now()

    def _build_clue_prefetch(
        self,
        *,
        overdue_rows: Sequence[Mapping[str, Any]],
        rows_by_batch: Mapping[str, Sequence[Mapping[str, Any]]],
    ):
        """循环前一次性批量取齐线索所需数据（齐套/物料/停机），消除 _diagnose_item 内逐批 N+1。"""
        overdue_batch_ids = {text(row.get("batch_id")) for row in overdue_rows}
        overdue_batch_ids.discard("")
        machine_ids: Set[str] = set()
        for batch_id in overdue_batch_ids:
            for plan_row in rows_by_batch.get(batch_id) or []:
                machine_id = text(plan_row.get("machine_id"))
                if machine_id:
                    machine_ids.add(machine_id)
        return self.clue_builder.build_prefetch(batch_ids=overdue_batch_ids, machine_ids=machine_ids)

    @staticmethod
    def _rows_by_batch(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
        out: Dict[str, List[Mapping[str, Any]]] = {}
        for row in rows:
            batch_id = text(row.get("batch_id"))
            if batch_id:
                out.setdefault(batch_id, []).append(row)
        for batch_rows in out.values():
            batch_rows.sort(key=lambda item: (text(item.get("end_time")), text(item.get("start_time")), int(item.get("op_id") or 0)))
        return out

    def _diagnose_item(
        self,
        *,
        row: Mapping[str, Any],
        rows_by_batch: Mapping[str, Sequence[Mapping[str, Any]]],
        plan_identity: PlanIdentity,
        generated_at: str,
        as_of_text: str,
        prefetch,
    ) -> OverdueDiagnosisItem:
        batch_id = text(row.get("batch_id"))
        plan_rows = list(rows_by_batch.get(batch_id) or [])
        last_row = plan_rows[-1] if plan_rows else None
        facts = self._confirmed_facts(row=row, last_row=last_row, plan_identity=plan_identity)
        last_operation = self._operation_clue(last_row, batch_id=batch_id, plan_identity=plan_identity) if last_row else None
        gaps: List[str] = []
        clues = self.clue_builder.candidate_clues(
            batch_id=batch_id,
            plan_rows=plan_rows,
            plan_identity=plan_identity,
            generated_at=generated_at,
            gaps=gaps,
            prefetch=prefetch,
        )
        if text(row.get("bucket")) == "schedule_time_invalid":
            gaps.append("这个批次有排程记录，但计划完成时间写法不对，请先修正排程时间后再判断是否真的晚完。")
        if text(row.get("bucket")) == "due_date_invalid":
            gaps.append("这个批次的交期写法不对，请先修正交期后再判断是否真的超期。")
        if not plan_rows and text(row.get("bucket")) != "due_date_invalid":
            gaps.append("当前方案里没有这个批次的排程明细，只能先确认它已经超过交期。")
        gaps.append("当前还没有现场执行反馈，不能判断是不是现场做慢了。")
        evidences = self._collect_evidences(facts=facts, clues=clues, operation=last_operation)
        leading = self._leading_clue(clues, bool(plan_rows), bucket=text(row.get("bucket")))
        actions = self._suggested_actions(plan_identity=plan_identity, batch_id=batch_id, has_rows=bool(plan_rows))
        trace = build_trace_meta(
            plan_identity=plan_identity,
            generated_at=generated_at,
            as_of_text=as_of_text,
            evidences=evidences,
            ranking_inputs=[f"delay_hours={row.get('delay_hours')}", f"bucket={row.get('bucket')}"],
            clue_selection_trace=["优先给出可追溯事实；缺证据的内容只放在线索或缺口里。"],
        )
        return OverdueDiagnosisItem(
            batch_id=batch_id,
            part_no=row.get("part_no"),
            part_name=row.get("part_name"),
            due_date=row.get("due_date"),
            bucket=text(row.get("bucket")),
            delay_hours=float_or_default(row.get("delay_hours")),
            delay_days=float_or_default(row.get("delay_days")),
            finish_time=row.get("finish_time"),
            as_of_time=text(row.get("as_of_time")),
            suggested_operation_clue=last_operation,
            last_operation=last_operation,
            confirmed_facts=facts,
            candidate_clues=clues,
            leading_clue_code=leading[0],
            leading_clue_label=leading[1],
            confidence=leading[2],
            evidences=evidences,
            data_gaps=stable_unique(gaps),
            suggested_actions=actions,
            links=evidences,
            trace_meta=trace,
        )

    def _confirmed_facts(
        self,
        *,
        row: Mapping[str, Any],
        last_row: Optional[Mapping[str, Any]],
        plan_identity: PlanIdentity,
    ) -> List[ConfirmedFact]:
        batch_id = text(row.get("batch_id"))
        due_text = text(row.get("due_date")) or "未填写"
        delay_hours = float_or_default(row.get("delay_hours"))
        bucket = text(row.get("bucket"))
        schedule_row_id = int_or_none(last_row.get("schedule_id")) if last_row else None
        if schedule_row_id is None:
            evidence = EvidenceLink(
                evidence_type="overdue_bucket",
                evidence_label="超期分桶依据",
                object_type="batch",
                object_id=batch_id,
                plan_identity=plan_identity,
                source_table=None,
                source_row_id=None,
                evidence_scope="aggregate",
                aggregation_key=f"batch:{batch_id}:overdue",
                contributing_count=1,
                source_page="超期清单",
                link=plan_link(plan_identity, "/reports/overdue", scenario_id=plan_identity.scenario_id),
            )
        else:
            last_row = cast(Mapping[str, Any], last_row)
            evidence = EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="计划排程明细",
                object_type="operation",
                object_id=last_row.get("op_id"),
                plan_identity=plan_identity,
                source_table=plan_identity.source_table,
                source_row_id=schedule_row_id,
                evidence_scope="row",
                source_page="甘特图",
                link=plan_link(plan_identity, "/scheduler/gantt", scenario_id=plan_identity.scenario_id),
            )
        if bucket == "scheduled_overdue":
            fact_text = f"批次 {batch_id} 的计划完成时间已经晚于交期 {due_text}，超期 {delay_hours:.2f} 小时。"
        elif bucket == "schedule_time_invalid":
            fact_text = f"批次 {batch_id} 有排程记录，但计划完成时间写法不对，不能把它当作未排程或准时完成。"
        elif bucket == "due_date_invalid":
            fact_text = f"批次 {batch_id} 的交期写法不对，系统不能判断它是否超期。"
        else:
            fact_text = f"批次 {batch_id} 还没有计划完成时间，截至 {row.get('as_of_time')} 已经超过交期 {due_text}。"
        return [ConfirmedFact(text=fact_text, evidences=[evidence])]

    def _operation_clue(
        self,
        row: Optional[Mapping[str, Any]],
        *,
        batch_id: str,
        plan_identity: PlanIdentity,
    ) -> Optional[OperationClue]:
        if row is None:
            return None
        evidence = EvidenceLink(
            evidence_type="schedule_row",
            evidence_label="建议复核的计划工序",
            object_type="operation",
            object_id=row.get("op_id"),
            plan_identity=plan_identity,
            source_table=plan_identity.source_table,
            source_row_id=row.get("schedule_id"),
            evidence_scope="row",
            source_page="甘特图",
            link=plan_link(plan_identity, "/scheduler/gantt", scenario_id=plan_identity.scenario_id),
        )
        return OperationClue(
            op_id=int_or_none(row.get("op_id")),
            op_name=row.get("op_type_name") or row.get("op_code"),
            batch_id=batch_id,
            machine_id=row.get("machine_id"),
            operator_id=row.get("operator_id"),
            planned_start_time=row.get("start_time"),
            planned_end_time=row.get("end_time"),
            actual_start_time=None,
            actual_end_time=None,
            clue_label="建议先复核最后一道已排工序",
            evidences=[evidence],
        )

    @staticmethod
    def _leading_clue(clues: Sequence[DiagnosisClue], has_rows: bool, *, bucket: str = "") -> Tuple[str, str, str]:
        if bucket == "schedule_time_invalid":
            return "schedule_time_invalid", "排程时间异常", "missing_data"
        if bucket == "due_date_invalid":
            return "due_date_invalid", "交期写法异常", "missing_data"
        for clue in clues:
            if clue.confidence == "likely":
                return clue.clue_code, clue.clue_label, "likely"
        if not has_rows:
            return "unscheduled", "暂无计划完成时间", "missing_data"
        for clue in clues:
            if clue.confidence == "missing_data":
                return clue.clue_code, clue.clue_label, "missing_data"
        return "unknown", "证据不足", "weak"

    @staticmethod
    def _suggested_actions(*, plan_identity: PlanIdentity, batch_id: str, has_rows: bool) -> List[SuggestedAction]:
        actions = [
            SuggestedAction(
                label="查看甘特图",
                target_page="甘特图",
                link=plan_link(plan_identity, "/scheduler/gantt", scenario_id=plan_identity.scenario_id) if has_rows else None,
                reason="先核对计划里这批次排到了哪里。",
                priority="high",
            ),
            SuggestedAction(
                label="核对物料明细",
                target_page="物料明细",
                link=f"/material/batches?batch_id={batch_id}",
                reason="第一版只能按批次物料明细给线索。",
                priority="medium",
            ),
        ]
        return actions

    @staticmethod
    def _collect_evidences(
        *,
        facts: Sequence[ConfirmedFact],
        clues: Sequence[DiagnosisClue],
        operation: Optional[OperationClue],
    ) -> List[EvidenceLink]:
        out: List[EvidenceLink] = []
        for fact in facts:
            out.extend(fact.evidences)
        for clue in clues:
            out.extend(clue.evidences)
        if operation is not None:
            out.extend(operation.evidences)
        return out

__all__ = [
    "DiagnosisClue",
    "DiagnosisTraceMeta",
    "OverdueDiagnosisItem",
    "OverdueDiagnosisReport",
    "RULE_VERSION",
    "ScheduleDelayDiagnosisService",
]
