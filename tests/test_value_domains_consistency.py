"""回归测试：core.algorithms.value_domains 中的 INTERNAL/EXTERNAL/MERGED/SEPARATE 常量值必须与 core.models.enums 的 SourceType 与 MergeMode 枚举值保持一致（单一真相源，防止两处取值漂移）。"""

from __future__ import annotations


def test_value_domains_consistent_with_model_enums() -> None:
    from core.algorithms import value_domains
    from core.models.enums import MergeMode, SourceType

    assert value_domains.INTERNAL == SourceType.INTERNAL.value
    assert value_domains.EXTERNAL == SourceType.EXTERNAL.value
    assert value_domains.MERGED == MergeMode.MERGED.value
    assert value_domains.SEPARATE == MergeMode.SEPARATE.value

