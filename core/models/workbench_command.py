"""Ordinary SQLite command outcomes; not background jobs or file restoration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


class WorkbenchCommandRejected(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status
        self.committed = False


class WorkbenchCommandUncertain(RuntimeError):
    def __init__(self, request_key: str):
        super().__init__("这次提交结果不确定，可能已经生效。请刷新后核对，不要重复提交。")
        self.request_key = request_key
        self.committed = "unknown"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def input_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_request_key(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "操作编号无效，请刷新页面后重新提交。", 400)
    return value


@dataclass(frozen=True)
class WorkbenchCommandOutcome:
    result: str
    data: Any
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    def payload(self) -> Dict[str, Any]:
        if self.result not in ("committed", "unchanged", "partial"):
            raise ValueError("普通数据库命令的结果状态无效。")
        if not isinstance(self.warnings, list):
            raise ValueError("命令警告必须是列表。")
        return {"result": self.result, "data": self.data, "warnings": self.warnings}
