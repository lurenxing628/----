from __future__ import annotations

from core.models.enums import SOURCE_TYPE_VALUES, MergeMode, SourceType

# 算法层用到的存储值域，值取自 core.models.enums（存储枚举的唯一事实源）。

INTERNAL = SourceType.INTERNAL.value
EXTERNAL = SourceType.EXTERNAL.value
# 工序来源的值域：读取边界 operation_model、种子合同与写库合同都按它精确校验。
OPERATION_SOURCES = frozenset(SOURCE_TYPE_VALUES)

MERGED = MergeMode.MERGED.value
