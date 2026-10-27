"""验证人员设备存储侧枚举字段在损坏或越界时直接抛错，不再静默回退。"""

from __future__ import annotations

import pytest

from core.services.personnel.operator_machine_normalizers import (
    normalize_operator_machine_row,
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


@pytest.mark.parametrize("corrupt", ["bad", "mystery", "", "   ", None, True, False])
def test_normalize_skill_level_stored_rejects_corrupt_values(corrupt: object) -> None:
    with pytest.raises(ValueError):
        normalize_skill_level_stored(corrupt)


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


@pytest.mark.parametrize("corrupt", ["bad", "maybe", "", "   ", None, True, False])
def test_normalize_yes_no_stored_rejects_corrupt_values(corrupt: object) -> None:
    with pytest.raises(ValueError):
        normalize_yes_no_stored(corrupt)


def test_normalize_operator_machine_row_propagates_corrupt_storage_errors() -> None:
    with pytest.raises(ValueError):
        normalize_operator_machine_row({"operator_id": "O1", "machine_id": "M1", "skill_level": "bad", "is_primary": "no"})
    with pytest.raises(ValueError):
        normalize_operator_machine_row({"operator_id": "O1", "machine_id": "M1", "skill_level": "normal", "is_primary": "bad"})
