from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ImportMode(Enum):
    APPEND = "append"  # 追加，不影响已有
    OVERWRITE = "overwrite"  # 相同编号覆盖
    REPLACE = "replace"  # 清空后导入（Phase1 只做预览，真正清空落库在各模块实现）


class RowStatus(Enum):
    NEW = "new"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class ImportPreviewRow:
    """导入预览行；row_num 对应源数据行号。"""

    row_num: int
    status: RowStatus
    data: Dict[str, Any]
    message: str = ""
