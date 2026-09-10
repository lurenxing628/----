"""Read scopes for permanent run candidates, never formal plan identities."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn, Optional

from core.models.workbench_command import WorkbenchCommandRejected

MAX_FACT_BYTES = 64 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_COLLECTION_BYTES = 128 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_CANDIDATES = 256
MAX_TASKS = 20000


def reject(code, message, status=409) -> NoReturn:
    raise WorkbenchCommandRejected(code, message, status)


def reference(value, *, stored=False):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        reject("candidate_binding_invalid" if stored else "invalid_input",
               "候选或关联记录的永久引用无效，未用编号替代。", 500 if stored else 400)
    return value


def local_time(value):
    if type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", value) is None:
        raise ValueError("Expected factory-local ISO datetime")
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class RunCandidateCatalogScope:
    run_ref: str
    status: str = "all"
    sort: str = "sequence"
    order: str = "asc"
    page: int = 1
    size: int = 20

    def __post_init__(self):
        reference(self.run_ref)
        if (self.status not in ("all", "completed", "partial", "failed", "skipped")
                or self.sort not in ("sequence", "label", "task_count") or self.order not in ("asc", "desc")
                or type(self.page) is not int or not 1 <= self.page <= MAX_CANDIDATES
                or type(self.size) is not int or not 1 <= self.size <= 50):
            reject("invalid_input", "候选目录筛选、排序或页码无效，未忽略条件。", 400)

    def scope(self):
        return {"kind": "run-candidate-catalog", "run_ref": self.run_ref, "status": self.status,
                "sort": self.sort, "order": self.order, "size": self.size}


@dataclass(frozen=True)
class RunCandidateReadScope:
    candidate_ref: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    batch_ref: Optional[str] = None
    sort: str = "sequence"
    order: str = "asc"

    def __post_init__(self):
        reference(self.candidate_ref)
        if self.batch_ref is not None:
            reference(self.batch_ref)
        if self.sort not in ("sequence", "start", "end") or self.order not in ("asc", "desc"):
            reject("invalid_input", "候选任务排序无效。", 400)
        if self.range_start is not None or self.range_end is not None:
            try:
                if local_time(self.range_start) >= local_time(self.range_end):
                    raise ValueError("Empty time range")
            except (ValueError, TypeError):
                reject("invalid_input", "范围须为成对的工厂本地时间，起点早于终点。", 400)

    def scope(self):
        return {"kind": "run-candidate-workspace", **self.__dict__}


def read_capabilities():
    return {"view": True, "export": True, "edit_draft": False, "adopt": False, "report_actual": False}


def blocked_reasons():
    return [
        {"capability": "adopt", "code": "candidate_adoption_preview_required",
         "message": "查看候选不授予采用权限；正式采用须单独预览并重新核对完整安排。"},
        {"capability": "edit_draft", "code": "candidate_draft_not_connected",
         "message": "候选为永久只读结果，尚未接入草稿调整。"},
        {"capability": "report_actual", "code": "candidate_execution_write_not_connected",
         "message": "候选不是正式执行安排，不能据此写入报工或改变唯一执行状态。"},
    ]
