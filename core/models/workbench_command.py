"""Ordinary SQLite command outcomes; not background jobs or file restoration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


class WorkbenchCommandRejected(ValueError):
    def __init__(self, code: str, message: str, status: int = 409, *, fields: Sequence[str] = (),
                 conflicts: Optional[List[Dict[str, Any]]] = None, row_number: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.committed = False
        # Input paths the rejection points at (dotted, rooted at the request's input); empty for whole-command
        # rejections. Each becomes one {path, message} row of the envelope, carrying this rejection's message.
        self.fields: Sequence[str] = fields
        # Public business conflicts remain available through every API rejection boundary.
        self.conflicts: List[Dict[str, Any]] = [] if conflicts is None else conflicts
        self.row_number = row_number


# A command or preview body whose keys are not the entry's declared set.
SHAPE_REJECTED = "提交内容缺少必填项或含有多余项，这次操作没有执行。请刷新页面后重试。"


class WorkbenchCommandUncertain(RuntimeError):
    def __init__(self, request_key: str):
        super().__init__("这次提交结果不确定，可能已经生效。请刷新后核对，不要重复提交。")
        self.request_key = request_key
        self.committed = "unknown"


def validate_request_key(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "操作编号无效，请刷新页面后重新提交。", 400)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class WorkbenchCommandOutcome:
    result: str
    data: Any
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    history_revision: Optional[int] = None

    def payload(self, *, normalize: bool = True) -> Dict[str, Any]:
        if self.result not in ("committed", "unchanged", "partial"):
            raise ValueError("普通数据库命令的结果状态无效。")
        if not isinstance(self.warnings, list):
            raise ValueError("命令警告必须是列表。")
        data = _json_value(self.data) if normalize else self.data
        return {"result": self.result, "data": data, "warnings": self.warnings}
