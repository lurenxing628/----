from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .ui_presenters import UiToggleRow, checked_attr


@dataclass(frozen=True)
class UiRunOption:
    toggle: UiToggleRow
    note: str = ""


def build_run_options(*, cfg: Any, config_field_warnings: Dict[str, str]) -> Tuple[UiRunOption, ...]:
    return (
        UiRunOption(
            toggle=UiToggleRow(
                "runEnforceReady",
                "enforce_ready",
                "本次启用齐套检查",
                "默认不启用。启用后，只要所选批次里有未齐套或部分齐套，本次排产会报错并停止；系统不会自动跳过这些批次继续排其它批次，齐套日期只对齐套批次作为最早开工日。",
                checked_attr=checked_attr(getattr(cfg, "enforce_ready_default", None) == "yes"),
            ),
            note=str(config_field_warnings.get("enforce_ready_default") or ""),
        ),
        UiRunOption(
            toggle=UiToggleRow(
                "runStrictMode",
                "strict_mode",
                "发现参数问题就停止排产",
                "配置不合法时直接停下，并提示需要处理的设置。",
                checked_attr="",
                submitted_value="no",
            ),
        ),
    )


__all__ = [
    "UiRunOption",
    "build_run_options",
]
