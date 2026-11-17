"""Exact identity lookups and append-only copy origins in the caller transaction; no rulings here."""

import json

from core.models.workbench_template_lineage import COPY_COLUMNS
from core.shared.refs import new_ref

from .base_repo import BaseRepository

INSTANCE_SELECT = """SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity"""
INSTANCE_FROM = """ FROM BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id
    LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
    LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
    LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no"""


class WorkbenchTemplateLineageRepository(BaseRepository):
    def insert_instance(self, payload):
        cursor = self.execute(
            "INSERT INTO BatchOperations ("
            + ",".join(COPY_COLUMNS)
            + ") VALUES ("
            + ",".join("?" for _ in COPY_COLUMNS)
            + ")",
            tuple(payload[key] for key in COPY_COLUMNS),
        )
        return self.fetchone(INSTANCE_SELECT + INSTANCE_FROM + " WHERE o.id=?", (cursor.lastrowid,))

    def origin_rows(self, refs):
        if not refs:
            return []
        return self.fetchall(
            """SELECT o.lineage_ref, o.operation_ref, o.template_operation_ref,
                      o.template_revision, o.source_eligible, o.instance_modified,
                      r.active AS operation_active
               FROM WorkbenchTemplateLineageOrigins o
               JOIN WorkbenchPlanSourceRefs r ON r.ref = o.operation_ref
               WHERE o.operation_ref IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(refs)),),
        )

    def append_origin(self, operation_ref, template_operation_ref, template_revision, *, source_eligible):
        row = {
            "lineage_ref": new_ref(),
            "operation_ref": operation_ref,
            "template_operation_ref": template_operation_ref,
            "template_revision": template_revision,
            "source_eligible": int(bool(source_eligible)),
            "instance_modified": 0,
        }
        self.conn.execute(
            "INSERT INTO WorkbenchTemplateLineageOrigins ("
            + ",".join(row)
            + ") VALUES ("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        return row
