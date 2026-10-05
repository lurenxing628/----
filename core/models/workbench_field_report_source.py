"""Server-owned original report file identity and its one-time decoded rows."""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class PreparedFieldReportSource:
    content: bytes
    file_digest: str
    _rows: tuple

    @classmethod
    def build(cls, content, rows):
        original = bytes(content)
        return cls(original, sha256(original).hexdigest(), tuple(deepcopy(rows)))

    def parsed(self):
        # Business matching owns its mutable diagnostics; retained source rows stay untouched.
        return list(deepcopy(self._rows))
