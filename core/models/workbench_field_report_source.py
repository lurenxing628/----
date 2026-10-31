"""Server-owned original report file identity and its one-time decoded rows."""

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PreparedFieldReportSource:
    content: bytes
    source_ref: str
    _rows: tuple

    @classmethod
    def build(cls, content, rows):
        original = bytes(content)
        stored = tuple(
            {
                "row": r["row"],
                "values": dict(r["values"]),
                "errors": tuple(dict(e) for e in r.get("errors", ())),
            }
            for r in rows
        )
        return cls(original, uuid4().hex, stored)

    def parsed(self):
        # Business matching owns its mutable diagnostics; retained source rows stay untouched.
        return [{"row": r["row"], "values": r["values"], "errors": list(r["errors"])} for r in self._rows]
