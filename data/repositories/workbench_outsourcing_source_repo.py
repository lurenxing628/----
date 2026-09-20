"""Exact instance reads; raw SQL expressions bypass host DATE converters.

Judgement (missing identities, drift, membership rules, row caps) belongs to
core.services.workbench.outsourcing_source; this module only returns what is stored.
"""

# Fixed legacy source tables per identity kind; never derived from caller input.
SOURCE_TABLES = {"batch": ("Batches", "batch_id"), "supplier": ("Suppliers", "supplier_id"),
                 "part": ("Parts", "part_no"), "operation": ("BatchOperations", "id")}


class WorkbenchOutsourcingSourceRepository:
    def __init__(self, conn):
        self.conn = conn

    def source_row(self, kind, value):
        """Stored row of the legacy source table for kind, every column verbatim; None when absent."""
        if kind not in SOURCE_TABLES:
            raise ValueError("Unknown outsourcing source kind: " + repr(kind))
        table, column = SOURCE_TABLES[kind]
        columns = [row[1] for row in self.conn.execute('PRAGMA table_info("' + table + '")')]
        selected = ",".join('CASE WHEN 1 THEN "' + key + '" END AS "' + key + '"' for key in columns)
        row = self.conn.execute('SELECT ' + selected + ' FROM "' + table + '" WHERE "' + column + '"=?', (value,)).fetchone()
        return dict(row) if row is not None else None

    def entity_identity(self, ref, kind):
        """Active entity identity row for ref of kind; None when absent or retired."""
        row = self.conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE ref=? AND kind=? AND active=1", (ref, kind)).fetchone()
        return dict(row) if row is not None else None

    def active_ref(self, kind, key):
        """Active identity ref of the entity with business key; None when absent."""
        row = self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()
        return row[0] if row is not None else None

    def operation_identity(self, ref):
        """Active operation identity row; None when absent or retired."""
        row = self.conn.execute("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref=? AND kind='operation' AND active=1", (ref,)).fetchone()
        return dict(row) if row is not None else None

    def operation_origin(self, ref):
        """Recorded birth batch of the operation; None when no origin was recorded."""
        row = self.conn.execute("SELECT * FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=?", (ref,)).fetchone()
        return dict(row) if row is not None else None

    def source_confirmation(self, operation_ref):
        """First-registration source confirmation of the operation; None when never confirmed."""
        row = self.conn.execute(
            "SELECT * FROM WorkbenchOutsourcingSourceConfirmations WHERE operation_ref=?", (operation_ref,)).fetchone()
        return dict(row) if row is not None else None

    def confirmation_matches_receipt(self, operation_ref, batch_ref, fact_ref):
        """Whether fact_ref is the sequence-1 fact of a receipt that holds operation_ref for batch_ref."""
        return self.conn.execute("""SELECT 1 FROM WorkbenchOutsourcingMembers m
            JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref
            JOIN WorkbenchOutsourcingFacts f ON f.outsourcing_ref=r.outsourcing_ref
            WHERE m.operation_ref=? AND r.batch_ref=? AND f.fact_ref=? AND f.sequence=1""",
            (operation_ref, batch_ref, fact_ref)).fetchone() is not None

    def has_membership(self, operation_ref):
        """Whether the operation is a member of any receipt."""
        return self.conn.execute("SELECT 1 FROM WorkbenchOutsourcingMembers WHERE operation_ref=?", (operation_ref,)).fetchone() is not None

    def plan_identity_revision(self):
        return self.conn.execute("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1").fetchone()[0]

    def external_operation_rows(self, batch_id, limit):
        """Up to limit + 1 external operations (optionally of one batch) with identity, membership and receipt refs."""
        params, where = (), ""
        if batch_id is not None:
            where, params = " AND o.batch_id=?", (batch_id,)
        rows = self.conn.execute("""SELECT r.ref AS operation_ref, o.op_code, o.op_type_name, b.ref AS batch_ref,
            s.ref AS supplier_ref, m.outsourcing_ref,
            h.batch_ref AS receipt_batch_ref, h.supplier_ref AS receipt_supplier_ref FROM BatchOperations o
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
            LEFT JOIN WorkbenchEntityRefs s ON s.kind='supplier' AND s.active=1 AND s.entity_key=o.supplier_id
            LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
            LEFT JOIN WorkbenchOutsourcingReceipts h ON h.outsourcing_ref=m.outsourcing_ref
            WHERE o.source='external'""" + where + " ORDER BY r.ref LIMIT ?", params + (limit + 1,)).fetchall()
        return [dict(row) for row in rows]
