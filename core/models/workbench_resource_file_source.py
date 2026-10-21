"""Server-owned source file facts; database-dependent proposals are rebuilt separately."""

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass

from core.errors import ValidationError
from core.models.content import same
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json


@dataclass(frozen=True)
class PreparedImportSource:
    operation: str
    request_document: str
    content: bytes
    source_ref: str
    _rows: list
    _notices: list

    @classmethod
    def build(cls, operation, request, rows, notices, *, content):
        """Take ownership of the decoder's private rows and notices."""
        source_ref = uuid.uuid4().hex
        document = canonical_json({**request, "actual_source_ref": source_ref})
        return cls(operation, document, bytes(content), source_ref, rows, notices)

    @classmethod
    def confirmation(cls, preview, content):
        if isinstance(content, cls):
            return content
        if (not isinstance(preview, AtomicActionPreview) or not isinstance(preview.source, cls)
                or type(content) is not bytes or preview.source.content != content):
            raise WorkbenchCommandRejected("stale_write", "原文件内容已变化，请重新预检。")
        return preview.source

    def request_for(self, operation, file_format, mode, scope=None):
        request = json.loads(self.request_document)
        if (self.operation != operation or request["format"] != file_format or request["mode"] != mode
                or scope is not None and not same(request["scope"], scope)):
            raise ValidationError("原文件的格式、方式或范围已变化，请重新预检。", field="file")
        return request

    def parsed(self):
        # Each proposal owns its mutable row diagnostics; the retained file facts never change.
        return deepcopy(self._rows), deepcopy(self._notices)
