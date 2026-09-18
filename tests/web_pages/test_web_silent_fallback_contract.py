"""回归测试：报表核心层的数值处理不得静默吞坏值——ReportEngine._build_export_decision、利用率导出、执行复盘行与延期文案遇坏值显式抛 ValidationError 而不泄漏原始坏值。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError


def test_report_numeric_helpers_keep_empty_values_but_reject_bad_service_numbers() -> None:
    from core.services.report.delay_diagnosis_presentation import _delay_text
    from core.services.report.execution_review import ExecutionReviewMixin
    from core.services.report.exporters import export_utilization_xlsx
    from core.services.report.report_engine import ReportEngine


    with pytest.raises(ValidationError, match="利用率"):
        export_utilization_xlsx([{"machine_id": "M1", "utilization": "坏数据"}], [])

    engine = ReportEngine.__new__(ReportEngine)
    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("-1")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("2.000")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("坏数据")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="暂停时长"):
        ExecutionReviewMixin._pause_duration_label("坏数据", True)

    class _Review(ExecutionReviewMixin):
        execution_feedback_service = SimpleNamespace(get_execution_state=lambda _op_ids: {})

    with pytest.raises(ValidationError, match="工序编号"):
        _Review()._execution_review_rows([{"op_id": "坏数据"}])

    with pytest.raises(ValidationError, match="延期小时"):
        _delay_text(SimpleNamespace(delay_hours="坏数据", delay_days=0, bucket="scheduled_overdue"))


