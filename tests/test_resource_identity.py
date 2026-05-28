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
