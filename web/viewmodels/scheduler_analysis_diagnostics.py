from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .scheduler_analysis_diagnostic_delay_impact import (
    build_delay_risk_section,
    build_impact_explanation_section,
)
from .scheduler_analysis_diagnostic_health import (
    build_overall_health_section,
    build_resource_bottleneck_section,
)
from .scheduler_analysis_diagnostic_helpers import (
    NonFiniteDiagnosticNumber,
    build_item,
    build_section,
    status_label,
)
from .scheduler_analysis_diagnostic_helpers import (
    graph_diagnostics as _graph_diagnostics,
)
from .scheduler_analysis_diagnostic_helpers import (
    graph_public as _graph_public,
)
from .scheduler_analysis_diagnostic_helpers import (
    safe_dict as _safe_dict,
)
from .scheduler_analysis_diagnostic_helpers import (
    safe_float as _safe_float,
)
from .scheduler_analysis_diagnostic_helpers import (
    safe_int as _safe_int,
)
from .scheduler_analysis_diagnostic_helpers import (
    safe_list as _safe_list,
)
from .scheduler_analysis_diagnostic_helpers import (
    sample_text_values as _sample_text_values,
)
from .scheduler_analysis_diagnostic_helpers import (
    section_status_from_levels as _section_status_from_levels,
)
from .scheduler_analysis_diagnostic_helpers import (
    summary_counts as _summary_counts,
)


def _non_finite_number_section(
    *,
    key: str,
    title: str,
    exc: NonFiniteDiagnosticNumber,
) -> Dict[str, Any]:
    return build_section(
        key=key,
        title=title,
        status="error",
        status_label=status_label("error"),
        summary="当前版本排产摘要包含异常数字，本诊断块无法可靠计算。",
        degraded=True,
        degradation_events=[
            {
                "code": "diagnostic_non_finite_number",
                "message": "诊断摘要包含非有限数字，已停止本诊断块计算。",
            }
        ],
        items=[
            build_item(
                key="diagnostic_non_finite_number",
                label="诊断数据异常",
                value="无法安全展示",
                level="danger",
                message="检测到 NaN/Infinity 等非有限数字；已拒绝把它当作 0 或正常值展示。",
                details=[str(exc)],
            )
        ],
    )


def _build_guarded_diagnostic_section(
    *,
    key: str,
    title: str,
    factory: Callable[[], Optional[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    try:
        return factory()
    except NonFiniteDiagnosticNumber as exc:
        return _non_finite_number_section(key=key, title=title, exc=exc)


def _append_section(sections: List[Dict[str, Any]], section: Optional[Dict[str, Any]]) -> None:
    if section is not None:
        sections.append(section)


def _missing_graph_section() -> Dict[str, Any]:
    return build_section(
        key="diagnostic_unavailable",
        title="排产诊断状态",
        status="empty",
        status_label=status_label("empty"),
        summary="本版本没有生成排产诊断数据，仍可查看排产指标和方案对比。",
        empty_reason="如果这是刚完成的排产，请刷新页面；如果是旧版本，可能当时还没有生成这类诊断。",
    )


def build_diagnostic_sections(
    selected_summary: Optional[Dict[str, Any]],
    selected_ver: Optional[int],
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    _ = (selected_ver, kwargs)
    graph_public = _graph_public(selected_summary)
    if not graph_public:
        return [_missing_graph_section()]

    graph_diagnostics = _graph_diagnostics(selected_summary)
    summary = _safe_dict(selected_summary)
    sections: List[Dict[str, Any]] = []
    _append_section(
        sections,
        _build_guarded_diagnostic_section(
            key="schedule_health",
            title="排产体检",
            factory=lambda: build_overall_health_section(summary, graph_public),
        ),
    )
    _append_section(
        sections,
        _build_guarded_diagnostic_section(
            key="resource_bottleneck",
            title="设备安排情况",
            factory=lambda: build_resource_bottleneck_section(graph_public, graph_diagnostics),
        ),
    )
    _append_section(
        sections,
        _build_guarded_diagnostic_section(
            key="delay_risk",
            title="延期风险",
            factory=lambda: build_delay_risk_section(summary, graph_public),
        ),
    )
    _append_section(
        sections,
        _build_guarded_diagnostic_section(
            key="impact_explanation",
            title="影响解释",
            factory=lambda: build_impact_explanation_section(graph_public, graph_diagnostics),
        ),
    )
    return sections


__all__ = [
    "build_diagnostic_sections",
    "_graph_diagnostics",
    "_graph_public",
    "_safe_dict",
    "_safe_float",
    "_safe_int",
    "_safe_list",
    "_sample_text_values",
    "_section_status_from_levels",
    "_summary_counts",
]
