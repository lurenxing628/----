"""Adapt a batch's frozen context to scheduling; never query live templates."""

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class FrozenExternalContext:
    """输入准备阶段已核对过的一道外协工序的冻结周期记录；排产输入只读它，不回库也不重复核对。"""

    row: Mapping[str, Any]
    group_key: Optional[str]
