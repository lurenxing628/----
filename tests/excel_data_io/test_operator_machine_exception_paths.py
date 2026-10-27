"""保留已登记的人员设备异常传播检查。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.services.personnel.operator_machine_normalizers import normalize_skill_level_stored


def test_normalize_skill_level_stored_only_falls_back_for_value_error() -> None:
    assert normalize_skill_level_stored("bad") == "normal"

    with patch(
        "core.services.personnel.operator_machine_normalizers.normalize_skill_level_value",
        side_effect=RuntimeError("normalize exploded"),
    ):
        with pytest.raises(RuntimeError, match="normalize exploded"):
            normalize_skill_level_stored("expert")
