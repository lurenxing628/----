from __future__ import annotations

from typing import Dict

from core.models.enums import BATCH_PRIORITY_RANKS

# Batch priorities reach the scheduler as their stored enum values (Batches.priority and Schedule.batch_priority
# carry NOT NULL CHECK constraints); the tables below index them directly.

# 越小越优先（critical > urgent > normal）；与批次列表排序共用 enums 的同一份业务序号。
PRIORITY_RANK: Dict[str, int] = BATCH_PRIORITY_RANKS

# 用于 ATC 等规则（越大越紧急）
PRIORITY_WEIGHT: Dict[str, float] = {"critical": 3.0, "urgent": 2.0, "normal": 1.0}

# 用于“权重混合”排序策略的离散分
PRIORITY_SCORE: Dict[str, int] = {"critical": 100, "urgent": 60, "normal": 20}
