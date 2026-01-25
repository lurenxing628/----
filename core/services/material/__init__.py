"""
物料管理相关服务（/material）。

最小闭环：
- 物料主数据（Materials）
- 批次物料需求（BatchMaterials）
- 齐套判定并回写到 Batches.ready_status / ready_date
"""

from .material_service import MaterialService
from .batch_material_service import BatchMaterialService

__all__ = ["MaterialService", "BatchMaterialService"]

