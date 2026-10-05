"""Server-owned source file facts; database-dependent proposals are rebuilt separately."""

import json
from copy import deepcopy
from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_command import canonical_json


@dataclass(frozen=True)
class PreparedImportSource:
    operation: str
    request_document: str
    _rows: tuple
    _notices: tuple

    @classmethod
    def build(cls, operation, request, rows, notices):
        return cls(operation, canonical_json(request), tuple(deepcopy(rows)), tuple(deepcopy(notices)))

    def request_for(self, operation, file_format, mode, scope=None):
        request = json.loads(self.request_document)
        if (self.operation != operation or request["format"] != file_format or request["mode"] != mode
                or scope is not None and request["scope"] != scope):
            raise ValidationError("原文件的格式、方式或范围已变化，请重新预检。", field="file")
        return request

    def parsed(self):
        # Each proposal owns its mutable row diagnostics; the retained file facts never change.
        return list(deepcopy(self._rows)), list(deepcopy(self._notices))
