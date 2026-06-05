from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Sequence, Tuple

from .operation_execution_feedback_support import _parse_feedback_datetime
from .operation_execution_scope_read import events_for_task_ref, state_for_task_ref
from .resource_dispatch_actual_records import PausePlan, TaskPlan, parse_int_or_error, text


class ResourceDispatchActualImportValidator:
    def __init__(self, feedback_service: Any):
        self.feedback_service = feedback_service

    def validate_task_plan(self, plan: TaskPlan, messages: List[str]) -> None:
        state = state_for_task_ref(self.feedback_service, plan.task)
        events = events_for_task_ref(self.feedback_service, plan.task)
        start_time = plan.actual_start_time or state.actual_start_time
        finish_time = plan.actual_finish_time or state.actual_end_time
        pauses = sorted(plan.pauses or [], key=lambda item: item.start_time)
        latest_pause_end = pauses[-1].end_time if pauses else None
        self._validate_existing_actual_times(plan, state, messages)
        self._validate_finish(plan, start_time, finish_time, latest_pause_end, messages)
        self._validate_exception(plan, start_time, latest_pause_end, messages)
        self._validate_pause_ranges(pauses, existing_events=events, messages=messages)
        self._validate_event_times_after_state(plan, state.last_event_time, messages)
        self._validate_pauses_against_task(plan, pauses, state.current_status, start_time, finish_time, messages)

    def _validate_existing_actual_times(self, plan: TaskPlan, state: Any, messages: List[str]) -> None:
        if plan.actual_start_time and state.actual_start_time:
            messages.append("已记录实际开工，如需改错请走后续纠错流程。")
        if plan.actual_finish_time and state.actual_end_time:
            messages.append("已记录实际完工，如需改错请走后续纠错流程。")

    def _validate_finish(
        self,
        plan: TaskPlan,
        start_time: Optional[str],
        finish_time: Optional[str],
        latest_pause_end: Optional[str],
        messages: List[str],
    ) -> None:
        if plan.actual_finish_time and not start_time:
            messages.append("填写实际完工前，请先填写实际开工。")
        if plan.actual_finish_time and plan.quantity_done in (None, ""):
            messages.append("填写实际完工时，完成数量不能为空。")
        if plan.actual_finish_time:
            self._normalize_finish_quantities(plan, messages)
        elif plan.quantity_done not in (None, "") or plan.quantity_scrapped not in (None, ""):
            messages.append("填写完成数量或报废数量时，也要填写实际完工时间。")
        if start_time and finish_time:
            self._validate_finish_after_start(start_time, finish_time, messages)
        if plan.actual_finish_time:
            self._validate_finish_after_imported_events(plan, latest_pause_end, messages)

    def _validate_finish_after_start(self, start_time: str, finish_time: str, messages: List[str]) -> None:
        finish_dt = _parse_feedback_datetime(finish_time, field="实际完工时间")
        start_dt = _parse_feedback_datetime(start_time, field="实际开工时间")
        if finish_dt < start_dt:
            messages.append("实际完工时间不能早于实际开工时间。")

    def _validate_finish_after_imported_events(
        self,
        plan: TaskPlan,
        latest_pause_end: Optional[str],
        messages: List[str],
    ) -> None:
        latest_before_finish = plan.exception_time or latest_pause_end
        if not latest_before_finish:
            return
        finish_dt = _parse_feedback_datetime(plan.actual_finish_time, field="实际完工时间")
        latest_dt = _parse_feedback_datetime(latest_before_finish, field="实际情况时间")
        if finish_dt < latest_dt:
            messages.append("实际完工时间不能早于本次填写的暂停或异常记录时间。")

    def _normalize_finish_quantities(self, plan: TaskPlan, messages: List[str]) -> None:
        parsed_done = parse_int_or_error(plan.quantity_done, field_label="完成数量", messages=messages)
        if parsed_done is not None:
            plan.quantity_done = parsed_done
        parsed_scrapped = parse_int_or_error(plan.quantity_scrapped, field_label="报废数量", messages=messages)
        if parsed_scrapped is not None:
            plan.quantity_scrapped = parsed_scrapped

    def _validate_exception(
        self,
        plan: TaskPlan,
        start_time: Optional[str],
        latest_pause_end: Optional[str],
        messages: List[str],
    ) -> None:
        if not plan.exception_time:
            return
        if not start_time:
            messages.append("填写异常记录前，请先填写实际开工。")
        if not plan.exception_reason_code:
            messages.append("异常原因不能为空。")
        if not plan.exception_severity:
            messages.append("异常严重程度不能为空。")
        if not plan.exception_remark:
            messages.append("异常说明不能为空。")
        if latest_pause_end and _parse_feedback_datetime(plan.exception_time, field="异常时间") < _parse_feedback_datetime(latest_pause_end, field="暂停结束时间"):
            messages.append("异常时间不能早于本次填写的暂停结束时间。")

    def _validate_pause_ranges(self, pauses: Sequence[PausePlan], *, existing_events: Sequence[Any], messages: List[str]) -> None:
        ranges: List[Tuple[datetime, datetime, str]] = []
        for pause in pauses:
            ranges.append(
                (
                    _parse_feedback_datetime(pause.start_time, field="暂停开始时间"),
                    _parse_feedback_datetime(pause.end_time, field="暂停结束时间"),
                    "本次导入",
                )
            )
        for start, end in self._existing_pause_ranges(existing_events):
            ranges.append((start, end, "已有记录"))
        ranges.sort(key=lambda item: item[0])
        for index in range(1, len(ranges)):
            self._append_pause_overlap_message(ranges[index - 1], ranges[index], messages)
            if messages:
                return

    def _append_pause_overlap_message(
        self,
        previous: Tuple[datetime, datetime, str],
        current: Tuple[datetime, datetime, str],
        messages: List[str],
    ) -> None:
        if current[0] >= previous[1]:
            return
        if previous[2] == "已有记录" or current[2] == "已有记录":
            messages.append("暂停时间和已有记录重叠，可能重复导入。")
            return
        messages.append("本次填写的暂停时间段有重叠，请检查后再导入。")

    def _existing_pause_ranges(self, events: Sequence[Any]) -> List[Tuple[datetime, datetime]]:
        ranges: List[Tuple[datetime, datetime]] = []
        start: Optional[datetime] = None
        for event in events:
            event_type = getattr(event, "event_type", None)
            if event_type == "pause":
                start = _parse_feedback_datetime(getattr(event, "event_time", None), field="暂停开始时间")
                continue
            if start is not None and event_type in ("resume", "finish", "exception"):
                end = _parse_feedback_datetime(getattr(event, "event_time", None), field="暂停结束时间")
                ranges.append((start, end))
                start = None
        return ranges

    def _validate_event_times_after_state(self, plan: TaskPlan, last_event_time: Any, messages: List[str]) -> None:
        last_time = text(last_event_time)
        if not last_time:
            return
        last_dt = _parse_feedback_datetime(last_time, field="上一条现场记录时间")
        for label, value in (
            ("实际开工时间", plan.actual_start_time),
            ("异常时间", plan.exception_time),
            ("实际完工时间", plan.actual_finish_time),
        ):
            if value and _parse_feedback_datetime(value, field=label) < last_dt:
                messages.append(f"{label}不能早于上一条现场记录时间。")
        for pause in plan.pauses or []:
            if _parse_feedback_datetime(pause.start_time, field="暂停开始时间") < last_dt:
                messages.append("暂停开始时间不能早于上一条现场记录时间。")

    def _validate_pauses_against_task(
        self,
        plan: TaskPlan,
        pauses: Sequence[PausePlan],
        current_status: str,
        start_time: Optional[str],
        finish_time: Optional[str],
        messages: List[str],
    ) -> None:
        if pauses and not plan.actual_start_time and current_status != "processing":
            messages.append("当前状态不能填写暂停时间，请刷新后重试。")
        for pause in pauses:
            if self._validate_pause_after_start(pause, start_time, messages):
                break
            self._validate_pause_before_finish(pause, finish_time, messages)

    def _validate_pause_after_start(self, pause: PausePlan, start_time: Optional[str], messages: List[str]) -> bool:
        if not start_time:
            messages.append("填写暂停时间前，请先填写实际开工。")
            return True
        pause_start = _parse_feedback_datetime(pause.start_time, field="暂停开始时间")
        actual_start = _parse_feedback_datetime(start_time, field="实际开工时间")
        if pause_start < actual_start:
            messages.append("暂停开始时间不能早于实际开工时间。")
        return False

    def _validate_pause_before_finish(self, pause: PausePlan, finish_time: Optional[str], messages: List[str]) -> None:
        if not finish_time:
            return
        pause_end = _parse_feedback_datetime(pause.end_time, field="暂停结束时间")
        finish_dt = _parse_feedback_datetime(finish_time, field="实际完工时间")
        if pause_end > finish_dt:
            messages.append("暂停结束时间不能晚于实际完工时间。")
