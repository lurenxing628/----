from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_TEMPLATE = "templates/scheduler/analysis.html"
ANALYSIS_PARTS = (
    "templates/scheduler/analysis_parts/_version_picker.html",
    "templates/scheduler/analysis_parts/_selected_overview.html",
    "templates/scheduler/analysis_parts/_summary_warnings.html",
    "templates/scheduler/analysis_parts/_metric_cards.html",
    "templates/scheduler/analysis_parts/_candidate_comparison.html",
    "templates/scheduler/analysis_parts/_diagnostic_sections.html",
    "templates/scheduler/analysis_parts/_optimization_process.html",
    "templates/scheduler/analysis_parts/_trend_charts.html",
)


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _analysis_page_source() -> str:
    return "\n".join([_read(ANALYSIS_TEMPLATE), *(_read(path) for path in ANALYSIS_PARTS)])


def test_analysis_template_main_shell_includes_expected_parts() -> None:
    source = _read(ANALYSIS_TEMPLATE)

    assert "aps_page_hero" in source
    assert "selected_history_resolution.message" in source
    for part in ANALYSIS_PARTS:
        include_path = part[len("templates/") :]
        assert f'{{% include "{include_path}" with context %}}' in source


def test_analysis_template_parts_preserve_existing_contract_markers() -> None:
    page_source = _analysis_page_source()

    for token in (
        "aps-version-picker-form",
        "aps-version-link-actions",
        "aps-summary-grid--version-overview",
        "selected_summary_display.error_total",
        "selected_summary_display.display_secondary_degradation_messages",
        "analysisCandidateComparisonTable",
        "candidate_comparison_display.rows",
        "analysisAttemptsTable",
        "v3_analysisAttemptsTable",
        "版本趋势（最近",
        "diagnostic_sections",
    ):
        assert token in page_source


def test_analysis_template_diagnostic_part_stays_hidden_when_empty() -> None:
    diagnostic_part = _read("templates/scheduler/analysis_parts/_diagnostic_sections.html")

    assert "{% if diagnostic_sections %}" in diagnostic_part
    assert "诊断摘要" in diagnostic_part
