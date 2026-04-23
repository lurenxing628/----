from __future__ import annotations

from core.algorithms.objective_specs import objective_choice_labels
from core.services.scheduler.config.config_field_spec import page_metadata_for
from core.services.scheduler.config_service import ConfigService


def test_page_metadata_for_returns_dict_projection() -> None:
    metadata = page_metadata_for(
        [
            "algo_mode",
            "objective",
            "dispatch_mode",
            "dispatch_rule",
            "freeze_window_enabled",
            "freeze_window_days",
        ]
    )
    assert isinstance(metadata, dict)
    assert list(metadata.keys()) == [
        "algo_mode",
        "objective",
        "dispatch_mode",
        "dispatch_rule",
        "freeze_window_enabled",
        "freeze_window_days",
    ]
    assert metadata["objective"].choices[2]["value"] == "min_weighted_tardiness"
    assert metadata["objective"].choices[0]["label"] == "最少超期"
    assert metadata["objective"].choices == tuple(
        {"value": key, "label": label} for key, label in objective_choice_labels().items()
    )
    assert metadata["dispatch_rule"].choices[2]["value"] == "atc"
    assert metadata["freeze_window_enabled"].hint
    assert metadata["freeze_window_days"].unit


def test_config_service_exposes_same_metadata_shape() -> None:
    service = object.__new__(ConfigService)
    metadata = service.get_page_metadata(
        ["algo_mode", "objective", "dispatch_mode", "dispatch_rule", "freeze_window_enabled", "freeze_window_days"],
    )
    assert isinstance(metadata, dict)
    assert metadata["algo_mode"].label
    assert metadata["objective"].choices[0]["value"] == "min_overdue"
    assert metadata["objective"].choices[0]["label"] == "最少超期"
