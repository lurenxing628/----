"""回归测试：ConfigService 的各写入入口（set_ortools / set_freeze_window / save_page_config / set_time_budget_seconds）遇到纯空白的时限、冻结天数、优先级权重、交期权重、时间预算时，必须抛 ValidationError 并带正确的中文字段名，且 set_time_budget_seconds 拒绝空白后不得改动配置快照。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


@pytest.fixture()
def config_service(tmp_path):
    test_db = tmp_path / "aps_config_service_blank_contract.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    try:
        yield ConfigService(conn, logger=None, op_logger=None)
    finally:
        conn.close()


def test_set_ortools_rejects_blank_time_limit(config_service: ConfigService) -> None:
    config_service.ensure_defaults()

    with pytest.raises(ValidationError) as exc_info:
        config_service.set_ortools("yes", "   ")

    assert exc_info.value.field == "ortools_time_limit_seconds"


def test_set_freeze_window_rejects_blank_days(config_service: ConfigService) -> None:
    config_service.ensure_defaults()

    with pytest.raises(ValidationError) as exc_info:
        config_service.set_freeze_window("no", "")

    assert exc_info.value.field == "freeze_window_days"


def test_save_page_config_rejects_blank_priority_weight(config_service: ConfigService) -> None:
    config_service.restore_default()

    with pytest.raises(ValidationError) as exc_info:
        config_service.save_page_config(
            {
                "priority_weight": " ",
                "due_weight": "0.5",
            }
        )

    assert exc_info.value.field == "优先级权重"


def test_save_page_config_rejects_blank_due_weight(config_service: ConfigService) -> None:
    config_service.restore_default()

    with pytest.raises(ValidationError) as exc_info:
        config_service.save_page_config(
            {
                "priority_weight": "0.4",
                "due_weight": "",
            }
        )

    assert exc_info.value.field == "交期权重"


def test_save_page_config_rejects_blank_time_budget_seconds(config_service: ConfigService) -> None:
    config_service.restore_default()

    with pytest.raises(ValidationError) as exc_info:
        config_service.save_page_config(
            {
                "priority_weight": "0.4",
                "due_weight": "0.5",
                "time_budget_seconds": " ",
            }
        )

    message = str(exc_info.value)
    assert "不能为空" in message
    assert exc_info.value.field in {"time_budget_seconds", "找更好排法先试多久"}


def test_direct_set_time_budget_rejects_blank_without_changing_snapshot(config_service: ConfigService) -> None:
    config_service.restore_default()
    before = config_service.get_snapshot(strict_mode=True).time_budget_seconds

    with pytest.raises(ValidationError) as exc_info:
        config_service.set_time_budget_seconds(" ")

    message = str(exc_info.value)
    assert "不能为空" in message
    assert exc_info.value.field == "找更好排法先试多久"
    assert config_service.get_snapshot(strict_mode=True).time_budget_seconds == before
