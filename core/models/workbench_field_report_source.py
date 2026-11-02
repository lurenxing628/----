"""Server-owned report file identity and its one-time decoded rows."""

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PreparedFieldReportSource:
    source_ref: str
    _rows: tuple

    @classmethod
    def build(cls, rows):
        """Take ownership of the rows the decoder has just built for this file."""
        return cls(uuid4().hex, tuple(rows))

    def parsed(self):
        # Business matching owns its mutable diagnostics; retained source rows stay untouched.
        return [{"row": r["row"], "values": r["values"], "errors": list(r["errors"])} for r in self._rows]
