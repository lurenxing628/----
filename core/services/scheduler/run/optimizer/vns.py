from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from core.errors import ValidationError


@dataclass
class VnsState:
    neighborhoods: Tuple[str, ...]
    neighborhood_index: int = 0

    def __post_init__(self) -> None:
        if not self.neighborhoods:
            raise ValidationError("VNS 邻域列表不能为空。", field="neighborhood")

    def current_neighborhood(self) -> str:
        return self.neighborhoods[int(self.neighborhood_index) % len(self.neighborhoods)]

    def record_round(self, *, best_improved: bool) -> None:
        old_index = int(self.neighborhood_index) % len(self.neighborhoods)
        if best_improved:
            self.neighborhood_index = 0
        else:
            self.neighborhood_index = (old_index + 1) % len(self.neighborhoods)


__all__ = ["VnsState"]
