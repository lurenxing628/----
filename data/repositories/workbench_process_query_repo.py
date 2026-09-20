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

    # ---- 单个零件模板（工艺动作快照） ----
    def part_by_no(self, part_no):
        return self.fetchone("SELECT * FROM Parts WHERE part_no=?", (part_no,))

    def template_operations_with_refs(self, part_no):
        """零件的全部工序（含停用）连有效模板工序编号，按 seq 排序。"""
        return self.fetchall("""SELECT o.*,r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            WHERE o.part_no=? ORDER BY o.seq""", (part_no,))

    def template_groups_with_refs(self, part_no):
        """零件的外协组连有效模板外协组编号，按起始序、组号排序。"""
        return self.fetchall("""SELECT g.*,r.ref FROM ExternalGroups g LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_external_group' AND r.entity_key=g.group_id AND r.active=1
            WHERE g.part_no=? ORDER BY g.start_seq,g.group_id""", (part_no,))

    def foreign_group_use_exists(self, part_no):
        """本零件的外协组是否还被别的零件工序引用。"""
        return self.fetchone("""SELECT 1 FROM PartOperations o JOIN ExternalGroups g ON g.group_id=o.ext_group_id
            WHERE g.part_no=? AND o.part_no<>? LIMIT 1""", (part_no, part_no)) is not None

    # ---- 路线预览 / 归属确认的参考资料 ----
    def op_type_reference_rows(self):
        return self.fetchall("SELECT op_type_id, name, category FROM OpTypes")

    def supplier_reference_rows(self):
        return self.fetchall("SELECT supplier_id, name FROM Suppliers")

    def op_type_categories(self):
        return self.fetchall("SELECT op_type_id,category FROM OpTypes")

    def supplier_status_rows(self):
        """供应商状态连停用原因（WorkbenchSupplierProfiles.inactive_reason）。"""
        return self.fetchall("""SELECT s.supplier_id,s.status,p.inactive_reason
        FROM Suppliers s LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id""")
