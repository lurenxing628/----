"""Read and copy the exact external context captured for one operation."""

import json

from .base_repo import BaseRepository

COPY_COLUMNS = ("operation_id", "part_no", "sequence", "template_operation_id", "template_status", "group_id",
                "group_part_no", "start_sequence", "end_sequence", "merge_mode", "total_days", "supplier_id",
                "group_ref", "template_operation_ref", "origin", "captured_at")


class BatchExternalContextRepository(BaseRepository):
    def for_operations(self, operation_ids):
        return self.fetchall(
            "SELECT * FROM BatchExternalContexts WHERE operation_id IN (SELECT value FROM json_each(?)) ORDER BY operation_id",
            (json.dumps(list(operation_ids)),),
        )

    def mark_template_copy(self, operation_id):
        return self.execute("UPDATE BatchExternalContexts SET origin='template_copy' WHERE operation_id=?", (operation_id,)).rowcount

    def copy_captured(self, source, destination_id):
        self.execute("DELETE FROM BatchExternalContexts WHERE operation_id=?", (destination_id,))
        values = dict(source, operation_id=destination_id,
                      origin="instance_copy")
        self.execute("INSERT INTO BatchExternalContexts (" + ",".join(COPY_COLUMNS) + ") VALUES (" +
                     ",".join("?" for _ in COPY_COLUMNS) + ")", tuple(values[key] for key in COPY_COLUMNS))
