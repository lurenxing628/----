from __future__ import annotations

import pytest


def test_normalize_skill_level_canonical3_and_legacy_aliases() -> None:
    """
    契约：skill_level 的归一化输出必须只可能是 beginner/normal/expert，并兼容 legacy alias。
    """
    from core.services.common.enum_normalizers import normalize_skill_level

    cases = [
        ("beginner", "beginner"),
        ("Beginner", "beginner"),
        (" normal ", "normal"),
        ("EXPERT", "expert"),
        ("high", "expert"),
        ("LOW", "beginner"),
        ("skilled", "expert"),
        ("初级", "beginner"),
        ("新手", "beginner"),
        ("普通", "normal"),
        ("一般", "normal"),
        ("中级", "normal"),
        ("熟练", "expert"),
        ("高级", "expert"),
        ("专家", "expert"),
    ]
    for raw, expected in cases:
        got = normalize_skill_level(raw, default="normal", allow_none=False)
        assert got == expected, f"normalize_skill_level({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert normalize_skill_level(None, default="normal", allow_none=False) == "normal"
    assert normalize_skill_level("", default="normal", allow_none=False) == "normal"
    assert normalize_skill_level("   ", default="normal", allow_none=False) == "normal"

    assert normalize_skill_level(None, default="normal", allow_none=True) is None
    assert normalize_skill_level("", default="normal", allow_none=True) is None

    with pytest.raises(Exception):
        normalize_skill_level("unknown_level", default="normal", allow_none=False)

