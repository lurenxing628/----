"""配置字段性质测试 —— 防止默认值/choices/coercion 漂移。打在真 API 上。

真 API(已核验)：core/services/scheduler/config/config_field_spec.py
  list_config_fields / get_field_spec / coerce_config_field(strict_mode=, source=)
未知 enum 在 strict_mode 下 raise core.infrastructure.errors.ValidationError。
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config import config_field_spec as cfs


def test_all_config_defaults_are_self_valid():
    # 每个字段的 default 必须能被自己的 strict coerce 接受 —— 否则就是“默认值即非法”。
    for spec in cfs.list_config_fields():
        value = cfs.coerce_config_field(
            spec.key, spec.default, strict_mode=True, source="semantic_property.default_self_valid"
        )
        assert value == spec.default, spec.key


def test_enum_choices_are_self_valid():
    for spec in cfs.list_config_fields():
        if spec.field_type != "enum":
            continue
        for choice in spec.choices:
            value = cfs.coerce_config_field(
                spec.key, choice, strict_mode=True, source="semantic_property.enum_choice"
            )
            assert value == choice, (spec.key, choice)


def test_graph_analysis_mode_contract():
    spec = cfs.get_field_spec("graph_analysis_mode")
    assert spec.field_type == "enum"
    assert spec.default == "on"
    assert spec.choices == ("off", "report", "on")


@given(st.text(min_size=1, max_size=40))
def test_graph_analysis_mode_rejects_unknown_values(text):
    if text in ("off", "report", "on"):
        return
    # 未知 enum 必须 loud(raise)，不准有的报错有的静默回落 —— 灵魂线。
    with pytest.raises(ValidationError):
        cfs.coerce_config_field(
            "graph_analysis_mode", text, strict_mode=True,
            source="semantic_property.graph_analysis_mode.unknown",
        )
