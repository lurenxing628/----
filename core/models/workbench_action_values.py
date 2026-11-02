"""Immutable values shared by collection previews and file responses."""

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_json import canonical_json

UPSERT_IMPORT_MODES = ("upsert",)


@dataclass(frozen=True)
class AtomicActionPreview:
    document: str
    source: object = field(default=None, repr=False, compare=False)
    _parsed: Dict[str, Any] = field(init=False, repr=False, compare=False)
    storage_failure_message: ClassVar[str] = "这批数据算不出完整预检结果，没有写入任何数据。请刷新后重新预检。"
    stale_message: ClassVar[str] = "预检结果、文件或相关数据已更新，没有写入数据。请重新预检并核对整批内容。"
    rejected_message: ClassVar[str] = "预检里有不通过的行，这一批没有写入任何数据。请改好后重新预检。"

    @classmethod
    def build(cls, operation, request, rows, notices=(), *, source=None):
        # Notices belong to the confirmed document, just like the selected rows.
        summary = {key: sum(row["result"] == key for row in rows)
                   for key in ("new", "update", "unchanged", "delete", "rejected")}
        body = {
            "version": 1,
            "operation": operation,
            "request": request,
            "commit_policy": "atomic",
            "rows": rows,
            "summary": summary,
            "notices": list(notices),
        }
        try:
            instance = cls(canonical_json(body), source)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("storage_failure", cls.storage_failure_message, 500) from exc
        object.__setattr__(instance, "_parsed", body)
        return instance

    def as_dict(self) -> Dict[str, Any]:
        return self._parsed

    def check_current(self, current: "AtomicActionPreview") -> Dict[str, Any]:
        """At confirmation the retained preview must equal, as a whole, the one rebuilt from current
        data inside the write transaction, and have no rejected rows."""
        if self.document != current.document:
            raise WorkbenchCommandRejected("stale_write", self.stale_message)
        body = current.as_dict()
        if body["summary"]["rejected"]:
            raise WorkbenchCommandRejected("constraint_conflict", self.rejected_message)
        return body


@dataclass(frozen=True)
class FileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int
