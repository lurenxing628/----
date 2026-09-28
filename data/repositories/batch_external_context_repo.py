"""Read and copy the exact external context captured for one operation."""

from .base_repo import BaseRepository


class BatchExternalContextRepository(BaseRepository):
    def available(self):
        return self.fetchone("SELECT 1 FROM sqlite_master WHERE type='table' AND name='BatchExternalContexts'") is not None

    def get(self, operation_id):
        return self.fetchone("SELECT * FROM BatchExternalContexts WHERE operation_id=?", (operation_id,))

    def for_operations(self, operation_ids):
        if not self.available():
            return self.rows_for_readonly_preflight()
        ids, rows = sorted(set(operation_ids)), []
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

    def rows_for_readonly_preflight(self):
        if not self.available():
            version = self.fetchone("SELECT version FROM SchemaVersion WHERE id=1")
            if version is not None and version["version"] < 33:
                return []
            raise RuntimeError("Current database is missing BatchExternalContexts.")
        return self.fetchall("SELECT * FROM BatchExternalContexts ORDER BY operation_id")

    def mark_template_copy(self, operation_id):
        self.execute("UPDATE BatchExternalContexts SET origin='template_copy' WHERE operation_id=?", (operation_id,))

    def copy(self, source_id, destination_id):
        self.execute("DELETE FROM BatchExternalContexts WHERE operation_id=?", (destination_id,))
        self.execute("""INSERT INTO BatchExternalContexts
            SELECT ?,part_no,sequence,template_operation_id,template_status,group_id,group_part_no,
                start_sequence,end_sequence,merge_mode,total_days,supplier_id,group_ref,template_operation_ref,
                CASE WHEN origin='migration_v33' THEN origin ELSE 'instance_copy' END,captured_at
            FROM BatchExternalContexts WHERE operation_id=?""", (destination_id, source_id))
