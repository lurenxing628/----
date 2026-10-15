"""保留已登记的人员设备异常传播检查。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.errors import ValidationError
from core.services.personnel.operator_machine_normalizers import normalize_skill_level_stored
from core.services.personnel.operator_machine_service import OperatorMachineService


def test_normalize_skill_level_optional_only_converts_value_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OperatorMachineService._normalize_skill_level_optional("unknown_level")

    assert "技能等级" in exc_info.value.message

    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=RuntimeError("normalize exploded"),
    ):
        with pytest.raises(RuntimeError, match="normalize exploded"):
            OperatorMachineService._normalize_skill_level_optional("expert")


def test_normalize_skill_level_stored_only_falls_back_for_value_error() -> None:
    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=ValueError("invalid skill"),
    ):
        assert normalize_skill_level_stored("bad") == "normal"

    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=RuntimeError("normalize exploded"),
    ):
        with pytest.raises(RuntimeError, match="normalize exploded"):
            normalize_skill_level_stored("expert")
