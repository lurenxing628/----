from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 保留在原始行数据中的导入元数据键。
SOURCE_ROW_NUM_KEY = "__source_row_num"
SOURCE_SHEET_NAME_KEY = "__source_sheet_name"


class TabularBackend(ABC):
    """
    表格后端抽象接口。

    约束（V1）：业务层统一只使用 List[Dict[str, Any]]，不出现 DataFrame。
    行级元数据通过保留键传递，供预览/确认阶段保真源行号。
    """

    @abstractmethod
    def read(self, file_path: str, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def write(self, rows: List[Dict[str, Any]], file_path: str, sheet: str = "Sheet1") -> None:
        raise NotImplementedError
