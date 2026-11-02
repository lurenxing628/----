"""Server-owned source file facts; database-dependent proposals are rebuilt separately."""

import json
import uuid
from dataclasses import dataclass

from core.shared.strict_json import canonical_json


@dataclass(frozen=True)
class PreparedImportSource:
    request_document: str
    _rows: list
    _notices: list

    @classmethod
    def build(cls, request, rows, notices):
        """Take ownership of the decoder's private rows and notices."""
        document = canonical_json({**request, "actual_source_ref": uuid.uuid4().hex})
        return cls(document, rows, notices)

    def request(self):
        """The canonical request this source was prepared for."""
        return json.loads(self.request_document)

    def parsed(self):
        # Each proposal owns its mutable row diagnostics; the retained file facts never change.
        return self._rows, self._notices
