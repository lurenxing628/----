"""Selected legacy source consistency only; archived execution remains authoritative."""

from core.infrastructure.workbench_execution_ledger_schema import LEGACY_COLUMNS
from core.models.workbench_command import input_fingerprint

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks

EMPTY_SOURCE_HASH = input_fingerprint([])


def _typed_row(row):
    result = []
    for key in LEGACY_COLUMNS:
        value = row[key]
        encoded = value.hex() if type(value) in (bytes, float) else value
        result.append((type(value).__name__, encoded))
    return result


class WorkbenchExecutionSourceRepository(BaseRepository):
    def _source_rows(self, ids):
        result = {}
        # Expressions bypass date converters: compare original SQLite storage, not adapter types.
        columns = ",".join(f'CASE WHEN 1 THEN "{column}" END AS "{column}"' for column in LEGACY_COLUMNS)
        for chunk in chunks(ids):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"SELECT {columns} FROM OperationExecutionEvents WHERE id IN ({marks})", chunk)
            result.update((row["id"], row) for row in rows)
        return result

    def read(self, legacy_by_operation):
        ids = [row["id"] for rows in legacy_by_operation.values() for row in rows]
        source = self._source_rows(ids)
        hashes, changes = {}, {}
        for ref, rows in legacy_by_operation.items():
            state = []
            for archived in rows:
                current = source.get(archived["id"])
                typed = _typed_row(current) if current is not None else None
                state.append((archived["id"], typed))
                if typed != _typed_row(archived):
                    changes.setdefault(ref, []).append({"legacy_fact_ref": archived["legacy_fact_ref"],
                        "change": "missing" if current is None else "changed"})
            hashes[ref] = input_fingerprint(state)
        return {"hashes": hashes, "changes": changes, "hash": input_fingerprint(hashes)}
