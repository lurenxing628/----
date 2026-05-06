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
                "启用齐套约束",
                "未齐套批次不进入排产。",
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
