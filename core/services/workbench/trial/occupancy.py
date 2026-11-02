"""Resource occupancy: completed production replaces the reservation it was planned or seeded as.

Occupancy is a tuple of ``(start, end, machine_ref, operator_ref)`` segments keyed by permanent
resource references.
"""

from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from core.models.workbench_execution import ExecutionProjection
from core.services.execution.projection import actual_period, report_segments

Span = Tuple[datetime, datetime]
Segment = Tuple[datetime, datetime, Optional[str], Optional[str]]


class ReportedExecution(NamedTuple):
    """One operation's execution snapshot parsed once: each report with its actual span, and what they occupy.

    A report's span stays None until the whole operation is complete; segments are a completed operation's
    positive report spans on their own resources, in time order.
    """

    execution: Dict[str, Any]
    spans: List[Tuple[Dict[str, Any], Optional[Span]]]
    segments: Tuple[Segment, ...]
    seed: Optional[Span]


def reported_projection(
    projection: ExecutionProjection,
    snapshot: Dict[str, Any],
) -> ReportedExecution:
    """Build current reported execution from a typed ExecutionProjection and its parsed cache."""
    if projection.execution_state == "complete":
        segs: Any = report_segments(projection)
        seed: Any = actual_period(projection)
        span_by_ref = {report.report_ref: (start, end) for start, end, report in segs}
        spans: List[Tuple[Dict[str, Any], Optional[Span]]] = [
            (report_dict, span_by_ref[report_dict["report_ref"]])
            for report_dict in snapshot["reports"]
        ]
        segments = tuple(
            (start, end, report.actual_machine_ref, report.actual_operator_ref)
            for start, end, report in segs
            if start < end
        )
        return ReportedExecution(snapshot, spans, segments, seed)
    spans = [(report_dict, None) for report_dict in snapshot["reports"]]
    return ReportedExecution(snapshot, spans, (), None)


def reported_archive(execution: Dict[str, Any]) -> ReportedExecution:
    """Parse one archived execution snapshot's reports; each stage's snapshot is parsed on its own."""
    if execution["execution_state"] == "complete":
        parsed: Dict[str, datetime] = {}
        spans: List[Tuple[Dict[str, Any], Optional[Span]]] = []
        positive: List[Segment] = []
        for report in execution["reports"]:
            raw_start, raw_end = report["actual_start"], report["actual_end"]
            start = parsed.get(raw_start)
            if start is None:
                start = parsed[raw_start] = datetime.fromisoformat(raw_start)
            end = parsed.get(raw_end)
            if end is None:
                end = parsed[raw_end] = datetime.fromisoformat(raw_end)
            spans.append((report, (start, end)))
            if start < end:
                positive.append((start, end, report["actual_machine_ref"], report["actual_operator_ref"]))
        segments = tuple(sorted(positive, key=lambda segment: segment[:2]))
        seed = (parsed[execution["first_actual_start"]], parsed[execution["confirmed_finish"]])
        return ReportedExecution(execution, spans, segments, seed)
    return ReportedExecution(
        execution,
        [(report, None) for report in execution["reports"]],
        (),
        None,
    )


def arranged_occupancy(span, arrangement, reported: ReportedExecution):
    """What one arranged interval occupies under the parsed execution snapshot of its stage.

    A completed operation still arranged as its execution seed (first actual start, confirmed finish
    and the earliest positive report's resources) occupies its positive report segments. A point
    occupies nothing; any other arrangement occupies its own resources for its whole span.
    """
    start, end = span
    if start == end:
        return ()
    segments = reported.segments
    if segments and (span, arrangement["machine_ref"], arrangement["operator_ref"]) == (
            reported.seed, segments[0][2], segments[0][3]):
        return segments
    return ((start, end, arrangement["machine_ref"], arrangement["operator_ref"]),)
