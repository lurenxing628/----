"""Server-owned source file facts; database-dependent proposals are rebuilt separately."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedImportSource:
    _request: dict
    _rows: list
    _notices: list

    @classmethod
    def build(cls, request, rows, notices):
        """Take ownership of the decoder's private rows and notices."""
        return cls({**request, "actual_source_ref": uuid.uuid4().hex}, rows, notices)

    def request(self):
        """The request this source was prepared for; each proposal gets its own copy to extend."""
        return dict(self._request)

    def parsed(self):
        # Each proposal owns its mutable row diagnostics; the retained file facts never change.
        return self._rows, self._notices
