"""Exact instance reads; raw SQL expressions bypass host DATE converters.

Judgement (missing identities, drift, membership rules, row caps) belongs to
core.services.workbench.outsourcing.source; this module only returns what is stored.
"""

import json

from core.models.workbench_outsourcing import MEMBER_KEYS, OPERATION_REVISION_KEYS

# Fixed legacy source table, key column and the stored columns the source rules read, per identity
# kind; never derived from caller input. Operation rows carry exactly the receipt evidence columns.
SOURCE_TABLES = {
    "batch": ("Batches", "batch_id", ("batch_id", "part_no", "part_name")),
    "supplier": ("Suppliers", "supplier_id", ("supplier_id", "name")),
    "part": ("Parts", "part_no", ("part_no", "part_name")),
    "operation": ("BatchOperations", "id", MEMBER_KEYS + OPERATION_REVISION_KEYS),
}

_EXTERNAL_OP_ORDER = "o.batch_id COLLATE NOCASE, o.piece_id COLLATE NOCASE, o.seq, o.id"

_TARGET_IDENTITY_SELECT = (
    "SELECT r.ref AS operation_ref, o.op_code, o.op_type_name, o.seq, o.piece_id, "
    "b.ref AS batch_ref, s.ref AS supplier_ref, m.outsourcing_ref, "
    "h.batch_ref AS receipt_batch_ref, h.supplier_ref AS receipt_supplier_ref "
    "FROM BatchOperations o "
    "LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT) "
    "LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id "
    "LEFT JOIN WorkbenchEntityRefs s ON s.kind='supplier' AND s.active=1 AND s.entity_key=o.supplier_id "
    "LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref "
    "LEFT JOIN WorkbenchOutsourcingReceipts h ON h.outsourcing_ref=m.outsourcing_ref "
)

_TARGET_SEARCH_JOINS = (
    "LEFT JOIN Batches batch ON batch.batch_id=o.batch_id "
    "LEFT JOIN Parts part ON part.part_no=batch.part_no "
    "LEFT JOIN Suppliers supplier ON supplier.supplier_id=o.supplier_id "
)

_TARGET_SEARCH_PREDICATE = (
    "AND ("
    "instr(lower(COALESCE(o.op_code,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(o.op_type_name,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(o.batch_id,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(batch.part_no,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(part.part_name,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(o.supplier_id,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(supplier.name,'')),lower(?))>0 OR "
    "instr(lower(COALESCE(o.piece_id,'')),lower(?))>0)"
)


def _key(kind, value):
    """Keep requested SQLite values distinct until the database compares them."""
    return kind, type(value), value


def _chunks(values, size=400):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _requests(values):
    """One bound value per requested key; the ordinal returns its original Python value."""
    return ",".join("(" + str(index) + ",?)" for index in range(len(values)))


class WorkbenchOutsourcingSourceFacts:
    """Exact, caller-owned source facts captured within one outsourcing transaction."""

    def __init__(self, revision: int):
        self._entities = {}
        self._source_rows = {}
        self._active_refs = {}
        self._operations = {}
        self._memberships = {}
        self._routes = {}
        self._revision = revision

    def source_row(self, kind, value):
        return self._source_rows.get(_key(kind, value))

    def entity_identity(self, ref, kind):
        return self._entities.get((ref, kind))

    def active_ref(self, kind, key):
        return self._active_refs.get(_key(kind, key))

    def operation_identity(self, ref):
        return self._operations.get(ref)

    def membership(self, operation_ref):
        return self._memberships.get(operation_ref)

    def memberships(self, operation_refs):
        """Stored member rows of these operations, ordered by operation ref."""
        return [
            self._memberships[ref]
            for ref in sorted(set(operation_refs))
            if ref in self._memberships
        ]

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
        """Stored row of the legacy source table for kind, its read columns verbatim; None when absent."""
        table, column, columns = SOURCE_TABLES[kind]
        selected = ",".join('+"' + key + '" AS "' + key + '"' for key in columns)
        row = self.conn.execute(
            "SELECT " + selected + ' FROM "' + table + '" WHERE "' + column + '"=?',
            (value,),
        ).fetchone()
        return dict(row) if row is not None else None

    def entity_identity(self, ref, kind):
        """Active entity identity row for ref of kind; None when absent or retired."""
        row = self.conn.execute(
            "SELECT * FROM WorkbenchEntityRefs WHERE ref=? AND kind=? AND active=1",
            (ref, kind),
        ).fetchone()
        return dict(row) if row is not None else None

    def plan_identity_revision(self):
        return self.conn.execute(
            "SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1"
        ).fetchone()[0]

    def _capture_entities(self, facts, refs):
        missing = [ref for ref, kind in refs if (ref, kind) not in facts._entities]
        if not missing:
            return
        rows = self.conn.execute(
            "SELECT * FROM WorkbenchEntityRefs WHERE active=1 "
            "AND kind IN ('batch','supplier') AND ref IN (SELECT value FROM json_each(?))",
            (json.dumps(missing),),
        )
        for row in rows:
            facts._entity(dict(row))

    def _capture_active_refs(self, facts, kind, values):
        keys = [
            key
            for key in dict.fromkeys(_key(kind, value) for value in values)
            if key not in facts._active_refs
        ]
        # Preserve TEXT affinity for entity_key, including non-text legacy relations.
        for chunk in _chunks(keys):
            raw_values = [key[2] for key in chunk]
            rows = self.conn.execute(
                "WITH requested(request_index,request_key) AS (VALUES "
                + _requests(raw_values)
                + ") "
                "SELECT requested.request_index,r.* FROM requested JOIN WorkbenchEntityRefs r "
                "ON r.entity_key=requested.request_key WHERE r.kind=? AND r.active=1",
                [*raw_values, kind],
            )
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
        table, column, columns = SOURCE_TABLES[kind]
        selected = ",".join('+source."' + key + '"' for key in columns)
        for chunk in _chunks(keys):
            raw_values = [key[2] for key in chunk]
            rows = self.conn.execute(
                "WITH requested(request_index,request_key) AS (VALUES "
                + _requests(raw_values)
                + ") "
                "SELECT requested.request_index,"
                + selected
                + ' FROM requested JOIN "'
                + table
                + '" source '
                'ON source."' + column + '"=requested.request_key',
                raw_values,
            )
            for key in chunk:
                facts._source_rows[key] = None
            for row in rows:
                facts._source_rows[chunk[row[0]]] = dict(zip(columns, row[1:]))

    def capture(self, targets, *, entities=(), include_routes=False, revision: int):
        """Read every dependency once for these targets in the caller's current transaction.

        entities contains already-read {identity, row} pairs, such as the selected
        batch used to limit the target query. No lookup on the result reads SQLite.
        """
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing source capture requires a caller-owned snapshot")
        facts = WorkbenchOutsourcingSourceFacts(revision)
        targets = list(targets)
        for entity in entities:
            identity = entity["identity"]
            facts._entity(identity)
            facts._source_rows[_key(identity["kind"], identity["entity_key"])] = entity["row"]
        entity_refs = [
            (target[kind + "_ref"], kind)
            for target in targets
            for kind in ("batch", "supplier")
        ]
        op_refs_json = json.dumps([ref for target in targets for ref in target["operation_refs"]])
        self._capture_entities(facts, entity_refs)
        for row in self.conn.execute(
            "SELECT * FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1 "
            "AND ref IN (SELECT value FROM json_each(?))",
            (op_refs_json,),
        ):
            facts._operations[row["ref"]] = dict(row)
        for kind in ("batch", "supplier"):
            self._capture_source_rows(
                facts,
                kind,
                [
                    identity["entity_key"]
                    for (_ref, entity_kind), identity in facts._entities.items()
                    if entity_kind == kind
                ],
            )
        self._capture_source_rows(
            facts,
            "operation",
            [identity["source_key"] for identity in facts._operations.values()],
        )
        operation_rows = [
            row
            for (kind, _value_type, _value), row in facts._source_rows.items()
            if kind == "operation" and row is not None
        ]
        self._capture_active_refs(facts, "batch", [row["batch_id"] for row in operation_rows])
        batch_rows = [
            row
            for (kind, _value_type, _value), row in facts._source_rows.items()
            if kind == "batch" and row is not None
        ]
        self._capture_active_refs(facts, "part", [row["part_no"] for row in batch_rows])
        self._capture_source_rows(
            facts,
            "part",
            [
                identity["entity_key"]
                for (_ref, kind), identity in facts._entities.items()
                if kind == "part"
            ],
        )
        for row in self.conn.execute(
            "SELECT m.operation_ref, m.outsourcing_ref, r.batch_ref "
            "FROM WorkbenchOutsourcingMembers m "
            "JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref "
            "WHERE m.operation_ref IN (SELECT value FROM json_each(?))",
            (op_refs_json,),
        ):
            facts._memberships[row["operation_ref"]] = {
                "operation_ref": row["operation_ref"],
                "outsourcing_ref": row["outsourcing_ref"],
                "batch_ref": row["batch_ref"],
            }
        if include_routes:
            for target in targets:
                if len(target["operation_refs"]) < 2:
                    continue
                identity = facts.operation_identity(target["operation_refs"][0])
                row = (
                    facts.source_row("operation", identity["source_key"])
                    if identity is not None
                    else None
                )
                if row is not None:
                    key = row["batch_id"], row["piece_id"]
                    if key not in facts._routes:
                        facts._routes[key] = self.route_rows(*key)
        return facts

    def route_rows(self, batch_id, piece_id):
        """Actual operation order for one piece, including shared batch operations."""
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT id,op_code,seq,piece_id,source,supplier_id FROM BatchOperations "
                "WHERE batch_id=? AND (? IS NULL OR piece_id IS ? OR piece_id IS NULL) ORDER BY seq,id",
                (batch_id, piece_id, piece_id),
            )
        ]

    def target_page(self, batch_id, query: str, *, number: int, size: int):
        """Paginated external operation rows: slice o.id via idx_wb_outsourcing_external_ops, then LEFT JOIN."""
        batch_where = (
            " AND o.batch_id=? COLLATE NOCASE AND o.batch_id=?"
            if batch_id is not None
            else ""
        )
        params: tuple = (batch_id, batch_id) if batch_id is not None else ()
        if query:
            from_where = (
                "FROM BatchOperations o "
                + _TARGET_SEARCH_JOINS
                + "WHERE o.source='external'"
                + batch_where
                + " "
                + _TARGET_SEARCH_PREDICATE
            )
            filter_params = params + (query,) * 8
        else:
            from_where = "FROM BatchOperations o WHERE o.source='external'" + batch_where
            filter_params = params
        total = self.conn.execute("SELECT COUNT(*) " + from_where, filter_params).fetchone()[0]
        offset = (number - 1) * size
        if total == 0 or offset >= total:
            return [], total
        page_ids = [
            row[0]
            for row in self.conn.execute(
                "SELECT o.id "
                + from_where
                + " ORDER BY "
                + _EXTERNAL_OP_ORDER
                + " LIMIT ? OFFSET ?",
                filter_params + (size, offset),
            )
        ]
        rows = self.conn.execute(
            _TARGET_IDENTITY_SELECT
            + "WHERE o.id IN (SELECT value FROM json_each(?)) ORDER BY "
            + _EXTERNAL_OP_ORDER,
            (json.dumps(page_ids),),
        ).fetchall()
        return [dict(row) for row in rows], total

    def unregistered_operation_rows(self, limit: int):
        """Up to limit + 1 unregistered external operations ordered by idx_wb_outsourcing_external_ops."""
        rows = self.conn.execute(
            "SELECT r.ref AS operation_ref, o.op_code, o.op_type_name, o.seq, o.piece_id, "
            "b.ref AS batch_ref, s.ref AS supplier_ref, m.outsourcing_ref, "
            "NULL AS receipt_batch_ref, NULL AS receipt_supplier_ref "
            "FROM BatchOperations o "
            "LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT) "
            "LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref "
            "LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id "
            "LEFT JOIN WorkbenchEntityRefs s ON s.kind='supplier' AND s.active=1 AND s.entity_key=o.supplier_id "
            "WHERE o.source='external' AND m.outsourcing_ref IS NULL "
            "ORDER BY " + _EXTERNAL_OP_ORDER + " LIMIT ?",
            (limit + 1,),
        ).fetchall()
        return [dict(row) for row in rows]
