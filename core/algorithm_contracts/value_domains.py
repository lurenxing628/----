from __future__ import annotations

# 算法层值域常量：
# - 目标：消除散落裸字符串，同时保持算法层不依赖 core.models.enums

INTERNAL = "internal"
EXTERNAL = "external"
# 工序来源的唯一值域：读取边界 operation_model、种子合同与写库合同都按它精确校验。
OPERATION_SOURCES = frozenset({INTERNAL, EXTERNAL})

MERGED = "merged"
