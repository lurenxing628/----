from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from core.models import MachineDowntime
from core.models.schedule_delay_diagnosis import DiagnosisClue
from core.models.schedule_plan_identity import EvidenceLink, PlanIdentity
from core.services.common.overdue_calculations import parse_dt
from core.services.material.batch_material_service import BatchMaterialService
from data.repositories import BatchRepository, MachineDowntimeRepository

from .schedule_delay_diagnosis_utils import plan_link, text


@dataclass
class DiagnosisPrefetch:
    """诊断循环前一次性预取的只读上下文，替代逐批次/逐机台查询（消除 N+1）。"""

    ready_status_by_batch: Dict[str, str] = field(default_factory=dict)
    materials_by_batch: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    downtimes_by_machine: Dict[str, List[MachineDowntime]] = field(default_factory=dict)


class ScheduleDelayDiagnosisClueBuilder:
    """把物料、停机和排程顺序收成保守线索。"""

    def __init__(self, conn, logger=None):
        self.batch_repo = BatchRepository(conn, logger=logger)
        self.batch_material_service = BatchMaterialService(conn, logger=logger)
        self.downtime_repo = MachineDowntimeRepository(conn, logger=logger)

    def build_prefetch(
        self,
        *,
        batch_ids: Iterable[str],
        machine_ids: Iterable[str],
    ) -> DiagnosisPrefetch:
        """诊断循环前一次性批量取齐齐套状态、物料明细、设备停机，避免循环内逐批/逐机台查询。"""
        batch_id_list = [b for b in {text(x) for x in batch_ids} if b]
        machine_id_list = [m for m in {text(x) for x in machine_ids} if m]
        return DiagnosisPrefetch(
            ready_status_by_batch=self.batch_repo.list_ready_status_by_batch_ids(batch_id_list),
            materials_by_batch=self.batch_material_service.list_for_batches(batch_id_list),
            downtimes_by_machine=self.downtime_repo.list_active_by_machines(machine_id_list),
        )

    def candidate_clues(
        self,
        *,
        batch_id: str,
        plan_rows: Sequence[Mapping[str, Any]],
        plan_identity: PlanIdentity,
        generated_at: str,
        gaps: List[str],
        prefetch: DiagnosisPrefetch,
    ) -> List[DiagnosisClue]:
        clues: List[DiagnosisClue] = []
        clues.extend(
            self._material_clues(
                batch_id=batch_id,
                plan_identity=plan_identity,
                generated_at=generated_at,
                gaps=gaps,
                prefetch=prefetch,
            )
        )
        downtime_clue = self._downtime_clue(plan_rows=plan_rows, plan_identity=plan_identity, prefetch=prefetch)
        if downtime_clue is not None:
            clues.append(downtime_clue)
        if plan_rows:
            clues.append(self._operation_order_clue(plan_rows[-1], plan_identity))
        return clues

    def _operation_order_clue(self, last_row: Mapping[str, Any], plan_identity: PlanIdentity) -> DiagnosisClue:
        return DiagnosisClue(
            clue_code="suggested_operation_clue",
            clue_label="建议先复核的工序",
            plain_text="建议先复核最后一道计划工序：%s。"
            % (last_row.get("op_type_name") or last_row.get("op_code") or "未命名工序"),
            confidence="weak",
            evidences=[
                EvidenceLink(
                    evidence_type="schedule_row",
                    evidence_label="建议复核的计划工序",
                    object_type="operation",
                    object_id=last_row.get("op_id"),
                    plan_identity=plan_identity,
                    source_table=plan_identity.source_table,
                    source_row_id=last_row.get("schedule_id"),
                    evidence_scope="row",
                    source_page="甘特图",
                    link=plan_link(plan_identity, "/scheduler/gantt", scenario_id=plan_identity.scenario_id),
                )
            ],
            data_gaps=["这只是排程顺序线索，不代表已经确认原因。"],
        )

    def _material_clues(
        self,
        *,
        batch_id: str,
        plan_identity: PlanIdentity,
        generated_at: str,
        gaps: List[str],
        prefetch: DiagnosisPrefetch,
    ) -> List[DiagnosisClue]:
        # 等价口径：原 get_ready_snapshot 只用其中的 ready_status；list_ready_status_by_batch_ids
        # 对不存在批次不返回键 → .get(batch_id) 为 None → text() 归一为 ""，与原“快照为空”分支一致。
        ready_status = text(prefetch.ready_status_by_batch.get(batch_id)).lower()
        materials = list(prefetch.materials_by_batch.get(batch_id) or [])
        if not ready_status:
            gap = "批次齐套状态缺失，暂时不能判断是不是物料问题。"
            gaps.append(gap)
            return [
                self._missing_material_clue(
                    batch_id,
                    plan_identity,
                    generated_at,
                    "batch_ready_status_missing",
                    "Batches.ready_status",
                    gap,
                )
            ]
        if not materials:
            gap = "缺少批次物料明细，暂时不能判断是不是物料问题。"
            gaps.append("该批次没有物料明细，不能判断具体缺哪种物料。")
            return [
                self._missing_material_clue(
                    batch_id,
                    plan_identity,
                    generated_at,
                    "batch_materials_missing",
                    "BatchMaterials",
                    gap,
                )
            ]
        if ready_status not in ("no", "partial"):
            return []

        clues: List[DiagnosisClue] = []
        unknown_rows = [row for row in materials if not text(row.get("ready_status"))]
        not_ready_rows = [
            row for row in materials if text(row.get("ready_status")).lower() in ("no", "partial")
        ]
        if unknown_rows:
            gap = "部分物料明细没有填写齐套状态，暂时不能判断这些物料是否影响延期。"
            gaps.append(gap)
            clues.append(
                self._missing_material_clue(
                    batch_id,
                    plan_identity,
                    generated_at,
                    "batch_material_ready_status_missing",
                    "BatchMaterials.ready_status",
                    gap,
                )
            )
        if not_ready_rows:
            clues.append(
                DiagnosisClue(
                    clue_code="material_not_ready",
                    clue_label="物料线索待核对",
                    plain_text="当前批次齐套状态不是已齐套，建议先复核物料明细；系统还不能判定延期一定由物料造成。",
                    confidence="likely",
                    evidences=[self._material_evidence(row, plan_identity) for row in not_ready_rows],
                    data_gaps=["第一版只读取批次齐套和批次物料明细，不追溯采购、库存和在途。"],
                )
            )
        return clues

    def _missing_material_clue(
        self,
        batch_id: str,
        plan_identity: PlanIdentity,
        generated_at: str,
        missing_data_key: str,
        expected_source: str,
        gap_label: str,
    ) -> DiagnosisClue:
        evidence = EvidenceLink(
            evidence_type="material_ready",
            evidence_label="物料数据不足",
            object_type="batch",
            object_id=batch_id,
            plan_identity=plan_identity,
            source_table=None,
            source_row_id=None,
            evidence_scope="missing_data",
            missing_data_key=missing_data_key,
            expected_source=expected_source,
            checked_object_type="batch",
            checked_object_id=batch_id,
            checked_at=generated_at,
            gap_label=gap_label,
            source_page="超期清单",
            confidence="missing_data",
        )
        return DiagnosisClue(
            clue_code="material_status_missing",
            clue_label="物料信息不足",
            plain_text=gap_label,
            confidence="missing_data",
            evidences=[evidence],
            data_gaps=[gap_label],
        )

    def _material_evidence(self, row: Mapping[str, Any], plan_identity: PlanIdentity) -> EvidenceLink:
        return EvidenceLink(
            evidence_type="material_ready",
            evidence_label="批次物料明细",
            object_type="batch_material",
            object_id=row.get("id"),
            plan_identity=plan_identity,
            source_table="batch_materials",
            source_row_id=row.get("id"),
            evidence_scope="row",
            source_page="物料明细",
            link=plan_link(plan_identity, "/material/batches", scenario_id=plan_identity.scenario_id),
            confidence="likely",
            metric_name="material_readiness",
            metric_value={
                "ready_status": row.get("ready_status"),
                "required_qty": row.get("required_qty"),
                "available_qty": row.get("available_qty"),
            },
        )

    def _downtime_clue(
        self,
        *,
        plan_rows: Sequence[Mapping[str, Any]],
        plan_identity: PlanIdentity,
        prefetch: DiagnosisPrefetch,
    ):
        for row in reversed(list(plan_rows)):
            machine_id = text(row.get("machine_id"))
            start_time = text(row.get("start_time"))
            end_time = text(row.get("end_time"))
            if not machine_id or not start_time or not end_time:
                continue
            start_dt = parse_dt(start_time)
            end_dt = parse_dt(end_time)
            if not start_dt or not end_dt or end_dt <= start_dt:
                continue
            clue = self._downtime_clue_for_window(
                machine_id=machine_id,
                start_time=start_time,
                end_time=end_time,
                start_dt=start_dt,
                end_dt=end_dt,
                plan_identity=plan_identity,
                prefetch=prefetch,
            )
            if clue is not None:
                return clue
        return None

    def _downtime_clue_for_window(
        self,
        *,
        machine_id: str,
        start_time: str,
        end_time: str,
        start_dt,
        end_dt,
        plan_identity: PlanIdentity,
        prefetch: DiagnosisPrefetch,
    ):
        # 预取按 machine_id 取全部 active 段（start_time/id 升序）；下方 Python 重叠判定与原
        # list_active_after + 同一过滤逐字一致：重叠成立必有 end_time>窗口起点，候选与首命中顺序不变。
        for downtime in prefetch.downtimes_by_machine.get(machine_id, []):
            d_start = parse_dt(downtime.start_time)
            d_end = parse_dt(downtime.end_time)
            if not d_start or not d_end or d_end <= start_dt or d_start >= end_dt:
                continue
            evidence = EvidenceLink(
                evidence_type="downtime_overlap",
                evidence_label="设备停机记录",
                object_type="machine_downtime",
                object_id=downtime.id,
                plan_identity=plan_identity,
                source_table="machine_downtimes",
                source_row_id=downtime.id,
                evidence_scope="row",
                source_page="停机记录",
                link=plan_link(plan_identity, "/reports/downtime", scenario_id=plan_identity.scenario_id),
                confidence="likely",
                time_range_start=downtime.start_time,
                time_range_end=downtime.end_time,
            )
            return DiagnosisClue(
                clue_code="downtime_impact",
                clue_label="停机线索待核对",
                plain_text="计划工序时间和设备停机时间有重叠，建议先复核停机记录；这还不是已确认原因。",
                confidence="likely",
                evidences=[evidence],
                data_gaps=[],
            )
        return None


__all__ = ["ScheduleDelayDiagnosisClueBuilder"]
