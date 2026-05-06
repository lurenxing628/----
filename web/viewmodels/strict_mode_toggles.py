from __future__ import annotations

from .ui_presenters import UiToggleRow, checked_attr


def build_strict_mode_toggle(element_id: str, *, desc: str, checked: bool = False) -> UiToggleRow:
    return UiToggleRow(
        id=element_id,
        name="strict_mode",
        title="资料不完整就停下",
        desc=desc,
        checked_attr=checked_attr(checked),
    )


__all__ = ["build_strict_mode_toggle"]
