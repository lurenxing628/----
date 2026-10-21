"""Exact instance reads; raw SQL expressions bypass host DATE converters.

Judgement (missing identities, drift, membership rules, row caps) belongs to
core.services.workbench.outsourcing.source; this module only returns what is stored.
"""

from core.infrastructure.connection_guards import schema_contract_memo

# Fixed legacy source tables per identity kind; never derived from caller input.
SOURCE_TABLES = {"batch": ("Batches", "batch_id"), "supplier": ("Suppliers", "supplier_id"),
                 "part": ("Parts", "part_no"), "operation": ("BatchOperations", "id")}


def _key(kind, value):
    """Keep requested SQLite values distinct until the database compares them."""
    return kind, type(value), value


def _chunks(values, size=300):
    values = list(dict.fromkeys(values))
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _requests(values):
    """One bound value per requested key; the ordinal returns its original Python value."""
    return ",".join("(" + str(index) + ",?)" for index in range(len(values)))


class WorkbenchOutsourcingSourceFacts:
    """Exact, caller-owned source facts captured within one outsourcing transaction."""
    def __init__(self):
        self._entities = {}
        self._source_rows = {}
        self._active_refs = {}
        self._operations = {}
        self._origins = {}
        self._confirmations = {}
        self._memberships = set()
        self._receipt_matches = set()
        self._routes = {}
        self._revision = None

    def source_row(self, kind, value):
        if kind not in SOURCE_TABLES:
            raise ValueError("Unknown outsourcing source kind: " + repr(kind))
        return self._source_rows.get(_key(kind, value))

    def entity_identity(self, ref, kind):
        return self._entities.get((ref, kind))

    def active_ref(self, kind, key):
        return self._active_refs.get(_key(kind, key))

    def operation_identity(self, ref):
        return self._operations.get(ref)

    def operation_origin(self, ref):
        return self._origins.get(ref)

    def source_confirmation(self, operation_ref):
        return self._confirmations.get(operation_ref)

    def confirmation_matches_receipt(self, operation_ref, batch_ref, fact_ref):
        return (operation_ref, batch_ref, fact_ref) in self._receipt_matches

    def has_membership(self, operation_ref):
        return operation_ref in self._memberships

    def plan_identity_revision(self):
        return self._revision

    def route_rows(self, batch_id, piece_id):
        return self._routes.get((batch_id, piece_id), [])

    def _entity(self, identity):
        self._entities[(identity["ref"], identity["kind"])] = identity
        self._active_refs[_key(identity["kind"], identity["entity_key"])] = identity["ref"]


class WorkbenchOutsourcingSourceRepository:
    def __init__(self, conn):
        self.conn = conn

    def source_row(self, kind, value):
        """Stored row of the legacy source table for kind, every column verbatim; None when absent."""
        if kind not in SOURCE_TABLES:
            raise ValueError("Unknown outsourcing source kind: " + repr(kind))
        table, column = SOURCE_TABLES[kind]
        columns = [row[1] for row in schema_contract_memo(self.conn).structure.table_info(table)]
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

    def _capture_entities(self, facts, refs):
        refs = [ref for ref, kind in refs if (ref, kind) not in facts._entities]
        for chunk in _chunks(refs):
            rows = self.conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE active=1 "
                "AND kind IN ('batch','supplier') AND ref IN (" + ",".join("?" for _ in chunk) + ")", chunk)
            for row in rows:
                facts._entity(dict(row))

    def _capture_active_refs(self, facts, kind, values):
        keys = [key for key in dict.fromkeys(_key(kind, value) for value in values) if key not in facts._active_refs]
        # Preserve TEXT affinity for entity_key, including non-text legacy relations.
        for chunk in _chunks(keys, size=400):
            values = [key[2] for key in chunk]
            rows = self.conn.execute("WITH requested(request_index,request_key) AS (VALUES " + _requests(values) + ") "
                "SELECT requested.request_index,r.* FROM requested JOIN WorkbenchEntityRefs r "
                "ON r.entity_key=requested.request_key WHERE r.kind=? AND r.active=1", values + [kind])
            for key in chunk:
                facts._active_refs[key] = None
            for row in rows:
                identity = dict(row)
                index = identity.pop("request_index")
                facts._entity(identity)
                facts._active_refs[chunk[index]] = identity["ref"]

    def _capture_source_rows(self, facts, kind, values):
        requested = {_key(kind, value): value for value in values}
        keys = [key for key in requested if key not in facts._source_rows]
        if not keys:
            return
        table, column = SOURCE_TABLES[kind]
        columns = [row[1] for row in schema_contract_memo(self.conn).structure.table_info(table)]
        selected = ",".join('CASE WHEN 1 THEN source."' + key.replace('"', '""') + '" END' for key in columns)
        for chunk in _chunks(keys, size=400):
            values = [key[2] for key in chunk]
            rows = self.conn.execute("WITH requested(request_index,request_key) AS (VALUES " + _requests(values) + ") "
                "SELECT requested.request_index," + selected + ' FROM requested JOIN "' + table + '" source '
                'ON source."' + column + '"=requested.request_key', values)
            for key in chunk:
                facts._source_rows[key] = None
            for row in rows:
                facts._source_rows[chunk[row[0]]] = dict(zip(columns, row[1:]))

    def capture(self, targets, *, entities=(), include_routes=False):
        """Read every dependency once for these targets in the caller's current transaction.

        entities contains already-read {identity, row} pairs, such as the selected
        batch used to limit the target query. No lookup on the result reads SQLite.
        """
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing source capture requires a caller-owned snapshot")
        facts = WorkbenchOutsourcingSourceFacts()
        targets = list(targets)
        for entity in entities:
            identity = entity["identity"]
            facts._entity(identity)
            facts._source_rows[_key(identity["kind"], identity["entity_key"])] = entity["row"]
        entity_refs = [(target[kind + "_ref"], kind) for target in targets for kind in ("batch", "supplier")]
        operation_refs = list(dict.fromkeys(ref for target in targets for ref in target["operation_refs"]))
        self._capture_entities(facts, entity_refs)
        for chunk in _chunks(operation_refs):
            marks = ",".join("?" for _ in chunk)
            for row in self.conn.execute("SELECT * FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 "
                                         "AND ref IN (" + marks + ")", chunk):
                facts._operations[row["ref"]] = dict(row)
        for kind in ("batch", "supplier"):
            self._capture_source_rows(facts, kind,
                [identity["entity_key"] for (ref, entity_kind), identity in facts._entities.items() if entity_kind == kind])
        self._capture_source_rows(facts, "operation", [identity["source_key"] for identity in facts._operations.values()])
        operation_rows = [row for (kind, value_type, value), row in facts._source_rows.items() if kind == "operation" and row is not None]
        self._capture_active_refs(facts, "batch", [row["batch_id"] for row in operation_rows])
        batch_rows = [row for (kind, value_type, value), row in facts._source_rows.items() if kind == "batch" and row is not None]
        self._capture_active_refs(facts, "part", [row["part_no"] for row in batch_rows])
        self._capture_source_rows(facts, "part",
            [identity["entity_key"] for (ref, kind), identity in facts._entities.items() if kind == "part"])
        for chunk in _chunks(operation_refs):
            marks = ",".join("?" for _ in chunk)
            for row in self.conn.execute("SELECT * FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref IN (" + marks + ")", chunk):
                facts._origins[row["operation_ref"]] = dict(row)
            for row in self.conn.execute("SELECT * FROM WorkbenchOutsourcingSourceConfirmations WHERE operation_ref IN (" + marks + ")", chunk):
                facts._confirmations[row["operation_ref"]] = dict(row)
            for row in self.conn.execute("""SELECT m.operation_ref,r.batch_ref,f.fact_ref FROM WorkbenchOutsourcingMembers m
                LEFT JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref
                LEFT JOIN WorkbenchOutsourcingFacts f ON f.outsourcing_ref=r.outsourcing_ref AND f.sequence=1
                WHERE m.operation_ref IN (""" + marks + ")", chunk):
                facts._memberships.add(row["operation_ref"])
                if row["batch_ref"] is not None and row["fact_ref"] is not None:
                    facts._receipt_matches.add((row["operation_ref"], row["batch_ref"], row["fact_ref"]))
        if include_routes:
            for target in targets:
                if len(target["operation_refs"]) < 2:
                    continue
                identity = facts.operation_identity(target["operation_refs"][0])
                row = facts.source_row("operation", identity["source_key"]) if identity is not None else None
                if row is not None:
                    key = row["batch_id"], row["piece_id"]
                    if key not in facts._routes:
                        facts._routes[key] = self.route_rows(*key)
        facts._revision = self.plan_identity_revision()
        return facts

    def route_rows(self, batch_id, piece_id):
        """Actual operation order for one piece, including shared batch operations."""
        return [dict(row) for row in self.conn.execute(
            "SELECT id,op_code,seq,piece_id,source,supplier_id FROM BatchOperations "
            "WHERE batch_id=? AND (piece_id IS ? OR piece_id IS NULL) ORDER BY seq,id", (batch_id, piece_id))]

    def external_operation_rows(self, batch_id, limit, query="", *, unregistered_only=False):
        """Up to limit + 1 external operations (optionally of one batch) with identity, membership and receipt refs."""
        params, where = (), ""
        if batch_id is not None:
            where, params = " AND o.batch_id=?", (batch_id,)
        if unregistered_only:
            where += " AND m.outsourcing_ref IS NULL"
        rows = self.conn.execute("""SELECT r.ref AS operation_ref, o.op_code, o.op_type_name, o.seq, o.piece_id, b.ref AS batch_ref,
            s.ref AS supplier_ref, m.outsourcing_ref,
            h.batch_ref AS receipt_batch_ref, h.supplier_ref AS receipt_supplier_ref FROM BatchOperations o
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
            LEFT JOIN WorkbenchEntityRefs s ON s.kind='supplier' AND s.active=1 AND s.entity_key=o.supplier_id
            LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
            LEFT JOIN WorkbenchOutsourcingReceipts h ON h.outsourcing_ref=m.outsourcing_ref
            LEFT JOIN Batches batch ON batch.batch_id=o.batch_id
            LEFT JOIN Parts part ON part.part_no=batch.part_no
            LEFT JOIN Suppliers supplier ON supplier.supplier_id=o.supplier_id
            WHERE o.source='external'""" + where + """ AND (?='' OR
                instr(lower(COALESCE(o.op_code,'')),lower(?))>0 OR
                instr(lower(COALESCE(o.op_type_name,'')),lower(?))>0 OR
                instr(lower(COALESCE(o.batch_id,'')),lower(?))>0 OR
                instr(lower(COALESCE(batch.part_no,'')),lower(?))>0 OR
                instr(lower(COALESCE(part.part_name,'')),lower(?))>0 OR
                instr(lower(COALESCE(o.supplier_id,'')),lower(?))>0 OR
                instr(lower(COALESCE(supplier.name,'')),lower(?))>0 OR
                instr(lower(COALESCE(o.piece_id,'')),lower(?))>0)
            ORDER BY o.batch_id COLLATE NOCASE,o.piece_id COLLATE NOCASE,o.seq,o.id LIMIT ?""",
            params + (query,) * 9 + (limit + 1,)).fetchall()
        return [dict(row) for row in rows]
