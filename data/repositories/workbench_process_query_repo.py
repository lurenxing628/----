"""Batch-read original templates and references, never allocating identity on GET."""

from .base_repo import BaseRepository

_PART_SCOPE = """WITH target_part AS (
    SELECT entity_key AS part_no FROM WorkbenchEntityRefs
    WHERE ref=? AND kind='part' AND active=1
), related_groups AS (
    SELECT group_id FROM ExternalGroups WHERE part_no IN (SELECT part_no FROM target_part)
    UNION
    SELECT ext_group_id FROM PartOperations
    WHERE part_no IN (SELECT part_no FROM target_part) AND ext_group_id IS NOT NULL
) """


class WorkbenchProcessQueryRepository(BaseRepository):
    def __init__(self, conn, logger=None, *, part_ref=None):
        super().__init__(conn, logger=logger)
        self.part_ref = part_ref

    def parts(self):
        if self.part_ref is not None:
            return self.fetchall("""SELECT p.*, r.ref, r.revision,
                (SELECT COUNT(*) FROM Batches b WHERE b.part_no=p.part_no) AS batch_count
                FROM Parts p LEFT JOIN WorkbenchEntityRefs r
                  ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
                WHERE r.ref=? ORDER BY p.part_no""", (self.part_ref,))
        return self.fetchall("""SELECT p.*, r.ref, r.revision, COALESCE(b.amount,0) AS batch_count
            FROM Parts p LEFT JOIN WorkbenchEntityRefs r
              ON r.kind='part' AND r.entity_key=p.part_no AND r.active=1
            LEFT JOIN (SELECT part_no,COUNT(*) AS amount FROM Batches GROUP BY part_no) b
              ON b.part_no=p.part_no ORDER BY p.part_no""")

    def operations(self):
        scoped = self.part_ref is not None
        identity_fields = ", r.alternate_key AS ref_alternate_key" if scoped else ""
        where = """WHERE o.part_no IN (SELECT part_no FROM target_part)
            OR o.ext_group_id IN (SELECT group_id FROM related_groups) """ if scoped else ""
        return self.fetchall((_PART_SCOPE if scoped else "") + "SELECT o.*, r.ref, r.revision" + identity_fields + """,
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
            """ + where + "ORDER BY o.part_no,o.seq,o.id", (self.part_ref,) if scoped else ())

    def groups(self):
        scoped = self.part_ref is not None
        identity_fields = ", r.alternate_key AS ref_alternate_key" if scoped else ""
        where = "WHERE eg.group_id IN (SELECT group_id FROM related_groups) " if scoped else ""
        return self.fetchall((_PART_SCOPE if scoped else "") + "SELECT eg.*, r.ref, r.revision" + identity_fields + """, s.supplier_id AS supplier_exists,
            s.name AS supplier_label, sr.ref AS supplier_ref FROM ExternalGroups eg
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.entity_key=eg.group_id AND r.active=1
            LEFT JOIN Suppliers s ON s.supplier_id=eg.supplier_id
            LEFT JOIN WorkbenchEntityRefs sr ON sr.kind='supplier' AND sr.entity_key=s.supplier_id AND sr.active=1
            """ + where + "ORDER BY eg.part_no,eg.start_seq,eg.group_id", (self.part_ref,) if scoped else ())

    def references(self):
        catalogs = ("OpTypes", "Suppliers", "WorkbenchSupplierProfiles", "WorkbenchSupplierOpTypes", "WorkbenchOpTypePolicies")
        references = {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in catalogs}
        for table in ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations"):
            where = " WHERE part_ref=?" if self.part_ref is not None else ""
            references[table] = self.fetchall('SELECT * FROM "' + table + '"' + where + " ORDER BY rowid",
                                              (self.part_ref,) if self.part_ref is not None else ())
        return references

    def identities(self):
        if self.part_ref is not None:
            return self.fetchall("""SELECT ref,kind,entity_key,alternate_key,revision,active
                FROM WorkbenchEntityRefs WHERE kind IN ('op_type','supplier') OR ref=?
                ORDER BY ref""", (self.part_ref,))
        return self.fetchall("""SELECT ref,kind,entity_key,alternate_key,revision,active FROM WorkbenchEntityRefs
            WHERE kind IN ('part','template_operation','template_external_group','op_type','supplier') ORDER BY ref""")
