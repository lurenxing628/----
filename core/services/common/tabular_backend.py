from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class TabularBackend(ABC):
    """
    表格后端抽象接口。

    约束（V1）：业务层统一只使用 List[Dict[str, Any]]，不出现 DataFrame。
    """

    @abstractmethod
    def read(self, file_path: str, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def write(self, rows: List[Dict[str, Any]], file_path: str, sheet: str = "Sheet1") -> None:
        raise NotImplementedError

