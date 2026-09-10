"""Batch-read original templates and references, never allocating identity on GET."""

from .base_repo import BaseRepository


class WorkbenchProcessQueryRepository(BaseRepository):
    def parts(self):
        return self.fetchall("""SELECT p.*, r.ref, r.revision, COALESCE(b.amount,0) AS batch_count
            FROM Parts p LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
            LEFT JOIN (SELECT part_no,COUNT(*) AS amount FROM Batches GROUP BY part_no) b
              ON b.part_no=p.part_no ORDER BY p.part_no""")

    def operations(self):
        return self.fetchall("""SELECT o.*, r.ref, r.revision,
            ot.op_type_id AS op_type_exists, ot.name AS op_type_label, ot.category AS op_type_category,
            tr.ref AS op_type_ref, s.supplier_id AS supplier_exists, s.name AS supplier_label,
            sr.ref AS supplier_ref, eg.group_id AS group_exists, eg.part_no AS group_part_no,
            gr.ref AS external_group_ref
            FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            LEFT JOIN OpTypes ot ON ot.op_type_id=o.op_type_id
            LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='op_type' AND tr.entity_key=ot.op_type_id AND tr.active=1
            LEFT JOIN Suppliers s ON s.supplier_id=o.supplier_id
            LEFT JOIN WorkbenchEntityRefs sr ON sr.kind='supplier' AND sr.entity_key=s.supplier_id AND sr.active=1
            LEFT JOIN ExternalGroups eg ON eg.group_id=o.ext_group_id
            LEFT JOIN WorkbenchEntityRefs gr ON gr.kind='template_external_group' AND gr.entity_key=eg.group_id AND gr.active=1
            ORDER BY o.part_no,o.seq,o.id""")

    def groups(self):
        return self.fetchall("""SELECT eg.*, r.ref, r.revision, s.supplier_id AS supplier_exists,
            s.name AS supplier_label, sr.ref AS supplier_ref FROM ExternalGroups eg
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.entity_key=eg.group_id AND r.active=1
            LEFT JOIN Suppliers s ON s.supplier_id=eg.supplier_id
            LEFT JOIN WorkbenchEntityRefs sr ON sr.kind='supplier' AND sr.entity_key=s.supplier_id AND sr.active=1
            ORDER BY eg.part_no,eg.start_seq,eg.group_id""")

    def references(self):
        tables = ("OpTypes", "Suppliers", "WorkbenchSupplierProfiles", "WorkbenchSupplierOpTypes", "WorkbenchOpTypePolicies")
        return {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in tables}

    def identities(self):
        return self.fetchall("""SELECT ref,kind,entity_key,alternate_key,revision,active FROM WorkbenchEntityRefs
            WHERE kind IN ('part','template_operation','template_external_group','op_type','supplier') ORDER BY ref""")
