"""Read and copy the exact external context captured for one operation."""

from .base_repo import BaseRepository

COPY_COLUMNS = ("operation_id", "part_no", "sequence", "template_operation_id", "template_status", "group_id",
                "group_part_no", "start_sequence", "end_sequence", "merge_mode", "total_days", "supplier_id",
                "group_ref", "template_operation_ref", "origin", "captured_at")


class BatchExternalContextRepository(BaseRepository):
    def available(self):
        return self.fetchone("SELECT 1 FROM sqlite_master WHERE type='table' AND name='BatchExternalContexts'") is not None

    def get(self, operation_id):
        return self.fetchone("SELECT * FROM BatchExternalContexts WHERE operation_id=?", (operation_id,))

    def for_operations(self, operation_ids):
        ids = sorted(set(operation_ids))
        if not ids:
            return []
        if not self.available():
            version = self.fetchone("SELECT version FROM SchemaVersion WHERE id=1")
            if version is not None and version["version"] < 33:
                return []
            raise RuntimeError("Current database is missing BatchExternalContexts.")
        rows = []
        for start in range(0, len(ids), 400):
            group = ids[start:start + 400]
            rows.extend(self.fetchall("SELECT * FROM BatchExternalContexts WHERE operation_id IN ("
                                      + ",".join("?" for _ in group) + ") ORDER BY operation_id", group))
        return rows

    def group_members(self, batch_id, group_ref, piece_id):
        return self.fetchall("""SELECT c.*,o.seq AS current_sequence,o.source AS current_source,
            o.supplier_id AS current_supplier_id FROM BatchExternalContexts c
            JOIN BatchOperations o ON o.id=c.operation_id
            WHERE o.batch_id=? AND c.group_ref=? AND o.piece_id IS ? ORDER BY o.seq,o.id""",
            (batch_id, group_ref, piece_id))

    def mark_template_copy(self, operation_id):
        return self.execute("UPDATE BatchExternalContexts SET origin='template_copy' WHERE operation_id=?", (operation_id,)).rowcount

    def copy_captured(self, source, destination_id):
        self.execute("DELETE FROM BatchExternalContexts WHERE operation_id=?", (destination_id,))
        values = dict(source, operation_id=destination_id,
                      origin=source["origin"] if source["origin"] == "migration_v33" else "instance_copy")
        self.execute("INSERT INTO BatchExternalContexts (" + ",".join(COPY_COLUMNS) + ") VALUES (" +
                     ",".join("?" for _ in COPY_COLUMNS) + ")", tuple(values[key] for key in COPY_COLUMNS))
