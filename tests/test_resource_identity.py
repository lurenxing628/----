"""回归测试：build_resource_identity 在名称以资源 ID 开头重复时剥离出干净 display_label（如“MC-01 一号设备”→name=“一号设备”），但对相似却不同的前缀 ID（MC-01 vs “MC-010 …”）不做误剪，且 identity_label/label 始终保留“ID 名称”全称。"""

from __future__ import annotations

from core.models.resource_identity import build_resource_identity


def test_resource_identity_uses_clean_display_when_name_repeats_id() -> None:
    identity = build_resource_identity("MC-01", "MC-01 一号设备")

    assert identity.id == "MC-01"
    assert identity.name == "一号设备"
    assert identity.display_label == "一号设备"
    assert identity.identity_label == "MC-01 一号设备"
    assert identity.label == "MC-01 一号设备"


def test_resource_identity_does_not_trim_similar_but_different_ids() -> None:
    identity = build_resource_identity("MC-01", "MC-010 一号设备")

    assert identity.name == "MC-010 一号设备"
    assert identity.display_label == "MC-010 一号设备"
    assert identity.identity_label == "MC-01 MC-010 一号设备"
