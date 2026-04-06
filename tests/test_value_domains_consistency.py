from __future__ import annotations


def test_value_domains_consistent_with_model_enums() -> None:
    from core.algorithms import value_domains
    from core.models.enums import MergeMode, SourceType

    assert value_domains.INTERNAL == SourceType.INTERNAL.value
    assert value_domains.EXTERNAL == SourceType.EXTERNAL.value
    assert value_domains.MERGED == MergeMode.MERGED.value
    assert value_domains.SEPARATE == MergeMode.SEPARATE.value

