"""验证人员设备存储侧枚举字段在损坏或越界时直接抛错，不再静默回退。"""

from __future__ import annotations

import pytest

from core.services.personnel.operator_machine_normalizers import (
    normalize_skill_level_stored,
    normalize_yes_no_stored,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("beginner", "beginner"),
        ("normal", "normal"),
        ("expert", "expert"),
        ("low", "beginner"),
        ("high", "expert"),
        ("初级", "beginner"),
        ("普通", "normal"),
        ("熟练", "expert"),
    ],
)
def test_normalize_skill_level_stored_accepts_valid_values(raw: str, expected: str) -> None:
    assert normalize_skill_level_stored(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", "yes"),
        ("no", "no"),
        ("是", "yes"),
        ("否", "no"),
        ("主操", "yes"),
        ("非主操", "no"),
    ],
)
def test_normalize_yes_no_stored_accepts_valid_values(raw: str, expected: str) -> None:
    assert normalize_yes_no_stored(raw) == expected
