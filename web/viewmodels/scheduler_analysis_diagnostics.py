from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_analysis_diagnostic_delay_impact import (
    build_delay_risk_section,
    build_impact_explanation_section,
)
from .scheduler_analysis_diagnostic_health import (
    build_overall_health_section,
    build_resource_bottleneck_section,
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


def build_diagnostic_sections(
    selected_summary: Optional[Dict[str, Any]],
    selected_ver: Optional[int],
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    _ = (selected_ver, kwargs)
    graph_public = _graph_public(selected_summary)
    if not graph_public:
        return []

    graph_diagnostics = _graph_diagnostics(selected_summary)
    summary = _safe_dict(selected_summary)
    sections: List[Dict[str, Any]] = [
        build_overall_health_section(summary, graph_public),
    ]
    resource_section = build_resource_bottleneck_section(graph_public, graph_diagnostics)
    if resource_section is not None:
        sections.append(resource_section)
    sections.append(build_delay_risk_section(summary, graph_public))
    sections.append(build_impact_explanation_section(graph_public, graph_diagnostics))
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
