from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def _render_diagnostic_part(diagnostic_sections):
    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = env.from_string(
        "{% import 'components/ui_macros.html' as ui %}"
        "{% include 'scheduler/analysis_parts/_diagnostic_sections.html' %}"
    )
    return template.render(diagnostic_sections=diagnostic_sections)


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


def test_analysis_template_diagnostic_part_stays_hidden_when_no_sections() -> None:
    html = _render_diagnostic_part([])

    assert "排产诊断" not in html
    assert "aps-diagnostic-section" not in html


def test_analysis_template_diagnostic_part_shows_explicit_empty_state() -> None:
    html = _render_diagnostic_part(
        [
            {
                "key": "diagnostic_unavailable",
                "title": "排产诊断状态",
                "status": "empty",
                "status_label": "暂无可分析",
                "summary": "本版本没有生成排产诊断数据，仍可查看排产指标和方案对比。",
                "items": [],
                "links": [],
                "degraded": False,
                "degradation_events": [],
                "empty_reason": "如果这是刚完成的排产，请刷新页面。",
            }
        ]
    )

    assert "排产诊断" in html
    assert "排产诊断状态" in html
    assert "本版本没有生成排产诊断数据" in html
    assert "如果这是刚完成的排产" in html


def test_analysis_template_places_diagnostics_before_metrics() -> None:
    source = _read(ANALYSIS_TEMPLATE)

    assert source.index('_summary_warnings.html') < source.index('_diagnostic_sections.html')
    assert source.index('_diagnostic_sections.html') < source.index('_metric_cards.html')
    assert source.index('_candidate_comparison.html') < source.index('_optimization_process.html')


def test_analysis_overview_time_labels_use_plain_language() -> None:
    source = _read("templates/scheduler/analysis_parts/_selected_overview.html")

    assert "计算时间上限" not in source
    assert "实际用时" not in source
    assert "软预算" not in source
    assert "找更好排法先试多久" in source
    assert "这次排产总共用了" in source
    assert "不是“到点马上停”" in source
    assert "已经开始算的会算完" in source


def test_analysis_template_renders_diagnostic_status_details_and_links() -> None:
    html = _render_diagnostic_part(
        [
            {
                "key": "resource_bottleneck",
                "title": "设备安排情况",
                "status": "warning",
                "status_label": "需要关注",
                "summary": "第一批可排工序里有 1 道能找到设备，但这轮设备不够同时安排，后面还要继续排。",
                "items": [
                    {
                        "key": "unmatched_operation_count",
                        "label": "这轮还没排上的工序",
                        "value": "1 道",
                        "level": "warning",
                        "message": "这轮还有 1 道没排上，不是没有设备能做，而是同一时间能用的设备不够。",
                        "details": ["这轮还没排上的工序样本：3"],
                        "links": [{"label": "查看明细", "url": "/scheduler/analysis", "kind": "page"}],
                    }
                ],
                "links": [{"label": "查看资源负荷", "url": "/reports/utilization", "kind": "page"}],
                "degraded": True,
                "degradation_events": [],
                "empty_reason": "",
            }
        ]
    )

    assert "排产诊断" in html
    assert "根据当前排产摘要生成，只做解释，不会自动改排产结果。" in html
    assert "设备安排情况" in html
    assert "需要关注" in html
    assert "这块信息不完整，页面先按能确认的内容说明" in html
    assert "这轮还没排上的工序" in html
    assert "1 道" in html
    assert "不是没有设备能做" in html
    assert "同一时间能用的设备不够" in html
    assert "<details" in html
    assert "查看诊断依据" in html
    assert "这轮还没排上的工序样本：3" in html
    assert "找不到可用设备" not in html
    assert "降级" not in html
    assert 'href="/scheduler/analysis"' in html
    assert 'href="/reports/utilization"' in html
    assert "aps-summary-item-warning" in html


def test_analysis_template_maps_diagnostic_item_levels_to_summary_tones() -> None:
    html = _render_diagnostic_part(
        [
            {
                "key": "schedule_health",
                "title": "排产体检",
                "status": "danger",
                "status_label": "存在风险",
                "summary": "测试不同状态颜色。",
                "items": [
                    {"key": "danger", "label": "危险", "value": "1", "level": "danger", "message": ""},
                    {"key": "notice", "label": "提示", "value": "2", "level": "notice", "message": ""},
                    {"key": "ok", "label": "正常", "value": "3", "level": "ok", "message": ""},
                    {"key": "other", "label": "其他", "value": "4", "level": "custom", "message": ""},
                ],
                "links": [],
                "degraded": False,
                "degradation_events": [],
                "empty_reason": "",
            }
        ]
    )

    assert "aps-summary-item-danger" in html
    assert "aps-summary-item-info" in html
    assert "aps-summary-item-success" in html
    assert "aps-summary-item-neutral" in html
