"""Immutable values shared by collection previews and file responses."""

import json
from dataclasses import dataclass, field
from typing import ClassVar

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json


@dataclass(frozen=True)
class AtomicActionPreview:
    document: str
    source: object = field(default=None, repr=False, compare=False)
    storage_failure_message: ClassVar[str] = "这批数据算不出完整预检结果，没有写入任何数据。请刷新后重新预检。"

    @classmethod
    def build(cls, operation, request, rows, notices=(), *, source=None):
        # Notices belong to the confirmed document, just like the selected rows.
        summary = {key: sum(row["result"] == key for row in rows)
                   for key in ("new", "update", "unchanged", "delete", "rejected")}
        try:
            return cls(canonical_json({"version": 1, "operation": operation, "request": request,
                                       "commit_policy": "atomic", "rows": rows, "summary": summary,
                                       "notices": list(notices)}), source)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("storage_failure", cls.storage_failure_message, 500) from exc

    def as_dict(self):
        return json.loads(self.document)

    def intent(self):
        body = self.as_dict()
        return {"preview_document": self.document, "operation": body["operation"], "request": body["request"]}


@dataclass(frozen=True)
class FileDownload:
    filename: str
    mime_type: str
    content: bytes
    row_count: int
