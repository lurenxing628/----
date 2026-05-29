from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence

from core.infrastructure.errors import ValidationError
from core.models.operation_execution_labels import REASON_LABELS, SEVERITY_LABELS

from .operation_execution_feedback_support import _parse_feedback_datetime
from .resource_dispatch_actual_import_validation import ResourceDispatchActualImportValidator
from .resource_dispatch_actual_records import (
    PAUSE_DETAIL_SHEET,
    TASK_FEEDBACK_SHEET,
    PausePlan,
    PreviewResult,
    TaskPlan,
    TaskRef,
    feedback_person,
    normalize_choice,
    parse_datetime_or_error,
    parse_int_or_error,
    planned_event_count,
    public_raw_row,
    status_label,
    text,
)


@dataclass
class _RowPlan:
    row: Dict[str, Any]
    plan: Optional[TaskPlan]
    messages: List[str]


class ResourceDispatchActualImportPreviewer:
    def __init__(self, feedback_service: Any):
        self.feedback_service = feedback_service
        self.validator = ResourceDispatchActualImportValidator(feedback_service)

    def preview(self, raw_rows: Sequence[Mapping[str, Any]], tasks: Sequence[TaskRef]) -> PreviewResult:
        task_index = self._task_index(tasks)
        row_plans: List[_RowPlan] = []
        raw_public_rows = [public_raw_row(row) for row in raw_rows]

        for row in raw_public_rows:
            messages: List[str] = []
            task = self._task_for_row(row, task_index, messages)
            plan = self._plan_from_row(row, task, messages) if task is not None else None
            row_plans.append(_RowPlan(row=dict(row), plan=plan, messages=messages))

        self._append_cross_row_errors(row_plans)
        return self._build_preview(row_plans, raw_public_rows)

    def _task_index(self, tasks: Sequence[TaskRef]) -> Dict[str, TaskRef]:
        out: Dict[str, TaskRef] = {}
        duplicate_codes = set()
        for task in tasks:
            if task.task_code in out:
                duplicate_codes.add(task.task_code)
                continue
            out[task.task_code] = task
        if duplicate_codes:
            raise ValidationError(
                "当前计划里有重复的任务识别码，请联系计划员重新生成填写模板。",
                field="任务识别码",
                details={"reason": "duplicate_task_code", "task_codes": sorted(duplicate_codes)},
            )
        return out

    def _task_for_row(
        self,
        row: Mapping[str, Any],
        task_index: Mapping[str, TaskRef],
        messages: List[str],
    ) -> Optional[TaskRef]:
        task_code = text(row.get("任务识别码"))
        if not task_code:
            messages.append("任务识别码不能为空。")
            return None
        task = task_index.get(task_code)
        if task is None:
            messages.append("找不到任务，请重新下载填写模板后再导入。")
            return None
        return task

    def _plan_from_row(self, row: Mapping[str, Any], task: TaskRef, messages: List[str]) -> Optional[TaskPlan]:
        sheet = text(row.get("sheet"))
        if sheet == TASK_FEEDBACK_SHEET:
            return self._task_plan_from_feedback_row(task, row, messages)
        if sheet == PAUSE_DETAIL_SHEET:
            pause = self._pause_plan_from_row(row, messages)
            if pause is None:
                return TaskPlan(task=task, row_number=int(row.get("row_number") or 0), pauses=[])
            return TaskPlan(task=task, row_number=pause.row_number, pauses=[pause])
        messages.append("工作表名称不正确，请使用模板里的“任务反馈”或“暂停明细”。")
        return None

    def _task_plan_from_feedback_row(self, task: TaskRef, row: Mapping[str, Any], messages: List[str]) -> TaskPlan:
        return TaskPlan(
            task=task,
            row_number=int(row.get("row_number") or 0),
            actual_start_time=parse_datetime_or_error(row.get("实际开工时间"), field_label="实际开工时间", messages=messages),
            actual_finish_time=parse_datetime_or_error(row.get("实际完工时间"), field_label="实际完工时间", messages=messages),
            quantity_done=row.get("完成数量"),
            quantity_scrapped=row.get("报废数量"),
            exception_time=parse_datetime_or_error(row.get("异常时间"), field_label="异常时间", messages=messages),
            exception_reason_code=normalize_choice(row.get("异常原因"), REASON_LABELS, field_label="异常原因", messages=messages),
            exception_severity=normalize_choice(row.get("异常严重程度"), SEVERITY_LABELS, field_label="异常严重程度", messages=messages),
            exception_remark=text(row.get("异常说明")) or None,
            feedback_person=feedback_person(row.get("反馈人")),
            remark=text(row.get("备注")) or None,
            pauses=[],
        )

    def _pause_plan_from_row(self, row: Mapping[str, Any], messages: List[str]) -> Optional[PausePlan]:
        row_number = int(row.get("row_number") or 0)
        start = parse_datetime_or_error(row.get("暂停开始时间"), field_label="暂停开始时间", messages=messages)
        end = parse_datetime_or_error(row.get("暂停结束时间"), field_label="暂停结束时间", messages=messages)
        duration = parse_int_or_error(row.get("暂停时长分钟"), field_label="暂停时长分钟", messages=messages)
        reason_code = normalize_choice(row.get("暂停原因"), REASON_LABELS, field_label="暂停原因", messages=messages)
        remark = text(row.get("暂停说明"))
        return self.pause_plan_from_values(
            row_number=row_number,
            start=start,
            end=end,
            duration_minutes=duration,
            reason_code=reason_code,
            remark=remark,
            feedback_person_value=row.get("反馈人"),
            messages=messages,
        )

    def pause_plan_from_values(
        self,
        *,
        row_number: int,
        start: Optional[str],
        end: Optional[str],
        duration_minutes: Optional[int],
        reason_code: Optional[str],
        remark: str,
        feedback_person_value: Any,
        messages: List[str],
    ) -> Optional[PausePlan]:
        if not any([start, end, duration_minutes is not None, reason_code, remark]):
            return None
        if not start:
            messages.append("暂停开始时间不能为空。")
            return None
        start_dt = _parse_feedback_datetime(start, field="暂停开始时间")
        base_error_count = len(messages)
        if end and duration_minutes is not None:
            end_dt = _parse_feedback_datetime(end, field="暂停结束时间")
            expected_end = start_dt + timedelta(minutes=duration_minutes)
            if (end_dt - expected_end).total_seconds() != 0:
                messages.append("暂停结束时间和暂停时长对不上，请只保留一个，或改成一致后再导入。")
        elif not end and duration_minutes is not None:
            end = (start_dt + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        if not end:
            messages.append("暂停结束时间和暂停时长分钟至少填写一个。")
            return None
        if _parse_feedback_datetime(end, field="暂停结束时间") <= start_dt:
            messages.append("暂停结束时间必须晚于暂停开始时间。")
        if not reason_code and len(messages) == base_error_count:
            messages.append("暂停原因不能为空。")
        if not remark:
            messages.append("暂停说明不能为空。")
        if messages:
            return None
        return PausePlan(
            row_number=row_number,
            start_time=start,
            end_time=end,
            reason_code=str(reason_code),
            remark=remark,
            feedback_person=feedback_person(feedback_person_value),
        )

    def _append_cross_row_errors(self, row_plans: Sequence[_RowPlan]) -> None:
        for rows in self._feedback_rows_by_task(row_plans).values():
            if len(rows) <= 1:
                continue
            for item in rows:
                item.messages.append("同一个任务在“任务反馈”里出现多行，请合并成一行后再导入。")

        for items in self._row_plans_by_task(row_plans).values():
            self._append_task_plan_errors(items)

    def _feedback_rows_by_task(self, row_plans: Sequence[_RowPlan]) -> Dict[str, List[_RowPlan]]:
        grouped: Dict[str, List[_RowPlan]] = {}
        for item in row_plans:
            if item.plan is not None and text(item.row.get("sheet")) == TASK_FEEDBACK_SHEET:
                grouped.setdefault(item.plan.task.task_code, []).append(item)
        return grouped

    def _row_plans_by_task(self, row_plans: Sequence[_RowPlan]) -> Dict[str, List[_RowPlan]]:
        grouped: Dict[str, List[_RowPlan]] = {}
        for item in row_plans:
            if item.plan is not None:
                grouped.setdefault(item.plan.task.task_code, []).append(item)
        return grouped

    def _append_task_plan_errors(self, items: Sequence[_RowPlan]) -> None:
        plans = [item.plan for item in items if item.plan is not None]
        merged = self._merge_plans(plans)
        messages: List[str] = []
        self.validator.validate_task_plan(merged, messages)
        if not messages:
            return
        for item in items:
            if self._row_should_receive_task_errors(item):
                item.messages.extend(messages)

    def _row_should_receive_task_errors(self, item: _RowPlan) -> bool:
        plan = item.plan
        if plan is None:
            return False
        sheet = text(item.row.get("sheet"))
        if sheet == TASK_FEEDBACK_SHEET:
            return planned_event_count(plan) > 0
        return sheet == PAUSE_DETAIL_SHEET and bool(plan.pauses)

    def _merge_plans(self, plans: Sequence[TaskPlan]) -> TaskPlan:
        base = plans[0]
        merged = TaskPlan(task=base.task, row_number=base.row_number, pauses=[])
        for plan in plans:
            if plan.actual_start_time:
                merged.actual_start_time = plan.actual_start_time
            if plan.actual_finish_time:
                merged.actual_finish_time = plan.actual_finish_time
            if plan.quantity_done not in (None, ""):
                merged.quantity_done = plan.quantity_done
            if plan.quantity_scrapped not in (None, ""):
                merged.quantity_scrapped = plan.quantity_scrapped
            if plan.exception_time:
                merged.exception_time = plan.exception_time
            if plan.exception_reason_code:
                merged.exception_reason_code = plan.exception_reason_code
            if plan.exception_severity:
                merged.exception_severity = plan.exception_severity
            if plan.exception_remark:
                merged.exception_remark = plan.exception_remark
            if plan.feedback_person:
                merged.feedback_person = plan.feedback_person
            if plan.remark:
                merged.remark = plan.remark
            merged.pauses = list(merged.pauses or []) + list(plan.pauses or [])
        return merged

    def _build_preview(self, row_plans: Sequence[_RowPlan], raw_rows: List[Dict[str, Any]]) -> PreviewResult:
        preview_rows = []
        add_total = 0
        skip_total = 0
        conflict_total = 0
        error_total = 0
        clean_plans: List[TaskPlan] = []

        for item in row_plans:
            plan = item.plan
            add_count = planned_event_count(plan)
            status = self._row_status(item.messages, add_count)
            if self._has_conflict_message(item.messages):
                conflict_total += 1
            if status == "error":
                error_total += 1
            elif status == "skip":
                skip_total += 1
            elif status == "ok":
                # status=="ok" 必有 add_count>0，而 add_count 来自 planned_event_count(plan)，
                # plan 为 None 时恒为 0，所以走到这里 plan 一定非空，无需再判空。
                add_total += add_count
                clean_plans.append(plan)
            preview_rows.append(self._preview_row(item.row, status=status, messages=item.messages, add_count=add_count))

        summary = {
            "total_rows": len(preview_rows),
            "matched_rows": sum(1 for item in row_plans if item.plan is not None),
            "add_count": add_total,
            "skip_count": skip_total,
            "conflict_count": conflict_total,
            "error_count": error_total,
            "can_confirm": bool(preview_rows) and error_total == 0 and conflict_total == 0,
        }
        return PreviewResult(rows=preview_rows, raw_rows=raw_rows, summary=summary, task_plans=self._confirm_plans(clean_plans))

    def _confirm_plans(self, clean_plans: Sequence[TaskPlan]) -> List[TaskPlan]:
        grouped: Dict[str, List[TaskPlan]] = {}
        for plan in clean_plans:
            if planned_event_count(plan) <= 0:
                continue
            grouped.setdefault(plan.task.task_code, []).append(plan)
        return [self._merge_plans(plans) for plans in grouped.values()]

    def _row_status(self, messages: Sequence[str], add_count: int) -> str:
        if not messages:
            return "ok" if add_count else "skip"
        if all(self._is_conflict_message(item) for item in messages):
            return "conflict"
        return "error"

    def _has_conflict_message(self, messages: Sequence[str]) -> bool:
        return any(self._is_conflict_message(item) for item in messages)

    def _is_conflict_message(self, message: str) -> bool:
        return "重复" in message or "已记录" in message or "重叠" in message

    def _preview_row(self, row: Mapping[str, Any], *, status: str, messages: Sequence[str], add_count: int) -> Dict[str, Any]:
        unique_messages = list(dict.fromkeys(messages))
        if unique_messages:
            message = "；".join(unique_messages)
        elif add_count:
            message = f"本行可导入 {add_count} 条现场记录。"
        else:
            message = "没有填写可导入的实际情况，已按空白行处理。"
        return {
            "sheet": text(row.get("sheet")),
            "row_number": int(row.get("row_number") or 0),
            "task_code": text(row.get("任务识别码")),
            "status": status,
            "status_label": status_label(status),
            "messages": unique_messages,
            "message": message,
            "add_count": add_count if status == "ok" else 0,
            "skip_count": 1 if status == "skip" else 0,
        }


def preview_payload(preview: PreviewResult, *, preview_token: str) -> Dict[str, Any]:
    return {
        "preview_token": preview_token,
        "can_confirm": bool(preview.summary.get("can_confirm")),
        "summary": preview.summary,
        "rows": preview.rows,
        "raw_rows": preview.raw_rows,
    }


def preview_token(rows: Sequence[Mapping[str, Any]], query_kwargs: Mapping[str, Any]) -> str:
    query = {key: text(value) for key, value in sorted((query_kwargs or {}).items()) if text(value)}
    raw = {"rows": list(rows or []), "query": query}
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["ResourceDispatchActualImportPreviewer", "preview_payload", "preview_token"]
