"""Exact instance reads; raw SQL expressions bypass host DATE converters."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing import MAX_ROWS, bounded, label, raw_facts, reject


def _target_text(value):
    return value if type(value) is str and value.strip() and "\x00" not in value else None


class WorkbenchOutsourcingSourceRepository:
    def __init__(self, conn):
        self.conn = conn

    def _row(self, table, column, value):
        columns = [row[1] for row in self.conn.execute('PRAGMA table_info("' + table + '")')]
        selected = ",".join('CASE WHEN 1 THEN "' + key + '" END AS "' + key + '"' for key in columns)
        row = self.conn.execute('SELECT ' + selected + ' FROM "' + table + '" WHERE "' + column + '"=?', (value,)).fetchone()
        return dict(row) if row is not None else None

    def entity(self, ref, kind):
        row = self.conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE ref=? AND kind=? AND active=1", (ref, kind)).fetchone()
        if row is None:
            reject("原批次、零件或供应商已移除，未改指同编号的新对象。", "entity_not_found", 404)
        table, column = {"batch": ("Batches", "batch_id"), "supplier": ("Suppliers", "supplier_id"),
                         "part": ("Parts", "part_no")}[kind]
        source = self._row(table, column, row["entity_key"])
        if source is None:
            reject("永久引用的原始对象不存在，未重建或补配。", "identity_missing", 409)
        return {"identity": dict(row), "row": source}

    def _active_ref(self, kind, key):
        row = self.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()
        if row is None:
            reject("来源缺少永久引用，不能按当前编号补配。", "identity_missing", 409)
        return row[0]

    def operation(self, ref):
        identity = self.conn.execute("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref=? AND kind='operation' AND active=1", (ref,)).fetchone()
        if identity is None:
            reject("原工序实例已移除，旧引用不会改指同编号新工序。", "entity_not_found", 404)
        row = self._row("BatchOperations", "id", identity["source_key"])
        origin = self.conn.execute("SELECT * FROM WorkbenchOutsourcingOperationOrigins WHERE operation_ref=?", (ref,)).fetchone()
        if row is None or origin is None or origin["batch_ref"] is None:
            raise WorkbenchCommandRejected("identity_missing", "工序原始批次映射缺失，未猜测或补建。", 409)
        batch_ref = self._active_ref("batch", row["batch_id"])
        if origin["batch_ref"] != batch_ref:
            reject("工序所属批次实例已变化，不能将旧工序关联到同号新批次。", "identity_drift", 409)
        return {"identity": dict(identity), "origin": dict(origin), "row": row}

    def load(self, target):
        batch = self.entity(target["batch_ref"], "batch")
        supplier = self.entity(target["supplier_ref"], "supplier")
        part = self.entity(self._active_ref("part", batch["row"]["part_no"]), "part")
        operations = [self.operation(ref) for ref in target["operation_refs"]]
        for op in operations:
            row = op["row"]
            if row["source"] != "external" or op["origin"]["batch_ref"] != target["batch_ref"]:
                reject("登记成员必须是所选批次的真实外协工序。", "constraint_conflict", 409)
            if row["supplier_id"] != supplier["row"]["supplier_id"]:
                reject("登记供应商与工序承接供应商不一致；请先核实，未自动换供应商。", "constraint_conflict", 409)
        if len({op["row"]["piece_id"] for op in operations}) != 1:
            reject("合并发出成员必须属于同一批次分件；未跨分件自动合并。", "constraint_conflict", 409)
        identity = {"batch_ref": target["batch_ref"], "part_ref": part["identity"]["ref"],
                    "supplier_ref": target["supplier_ref"], "members": [
                        {"operation_ref": op["identity"]["ref"], **{key: op["row"][key] for key in
                         ("op_code", "batch_id", "piece_id", "seq", "op_type_id", "op_type_name", "source", "supplier_id")}}
                        for op in operations]}
        public = {**target, "grouping_basis": "explicit_receipt_membership",
                  "batch": {"ref": target["batch_ref"], "business_code": label(batch["row"]["batch_id"]),
                            "label": label(batch["row"]["part_name"])},
                  "supplier": {"ref": target["supplier_ref"], "business_code": label(supplier["row"]["supplier_id"]),
                               "label": label(supplier["row"]["name"])},
                  "operations": [{"operation_ref": op["identity"]["ref"], "business_code": label(op["row"]["op_code"]),
                                  "sequence": label(op["row"]["seq"]), "piece": label(op["row"]["piece_id"]),
                                  "label": label(op["row"]["op_type_name"])} for op in operations]}
        clock = self.conn.execute("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1").fetchone()[0]
        return {"public": bounded(public), "identity": raw_facts(identity),
                "facts": bounded(raw_facts({"batch": batch, "part": part, "supplier": supplier,
                                           "operations": operations, "source_clock": clock}))}

    def _target_entity_labels(self, row, kind):
        ref = row[kind + "_ref"]
        # A registered member must not display a same-number replacement as its original object.
        if row["outsourcing_ref"] is not None and row["receipt_" + kind + "_ref"] != ref:
            return None
        try:
            source = self.entity(ref, kind)["row"]
        except WorkbenchCommandRejected as exc:
            if exc.code not in ("entity_not_found", "identity_missing"):
                raise
            return None
        code, name = ("batch_id", "part_name") if kind == "batch" else ("supplier_id", "name")
        return {"ref": ref, "business_code": _target_text(source[code]), "label": _target_text(source[name])}

    def targets(self, batch_ref=None):
        """Add nullable batch/supplier {ref, business_code, label}; unknown text stays null."""
        params = ()
        where = ""
        if batch_ref is not None:
            batch = self.entity(batch_ref, "batch")
            where, params = " AND o.batch_id=?", (batch["row"]["batch_id"],)
        rows = self.conn.execute("""SELECT r.ref AS operation_ref, o.op_code, o.op_type_name, b.ref AS batch_ref,
            s.ref AS supplier_ref, m.outsourcing_ref,
            h.batch_ref AS receipt_batch_ref, h.supplier_ref AS receipt_supplier_ref FROM BatchOperations o
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
            LEFT JOIN WorkbenchEntityRefs s ON s.kind='supplier' AND s.active=1 AND s.entity_key=o.supplier_id
            LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
            LEFT JOIN WorkbenchOutsourcingReceipts h ON h.outsourcing_ref=m.outsourcing_ref
            WHERE o.source='external'""" + where + " ORDER BY r.ref LIMIT ?", params + (MAX_ROWS + 1,)).fetchall()
        if len(rows) > MAX_ROWS:
            reject("外协工序超过10000项，请限定批次。", "query_too_large", 413)
        result = []
        for row in rows:
            item = {"operation_ref": row["operation_ref"], "business_code": label(row["op_code"]),
                    "label": label(row["op_type_name"]), "batch_ref": row["batch_ref"], "supplier_ref": row["supplier_ref"],
                    "outsourcing_ref": row["outsourcing_ref"], "can_register": False, "issues": [],
                    "batch": None, "supplier": None}
            if any(row[key] is None for key in ("operation_ref", "batch_ref", "supplier_ref")):
                item["issues"] = [{"code": "identity_missing", "message": "成员或承接关系缺少永久引用，不能登记。"}]
            else:
                # Known per-row identity gaps stay visible; storage failures propagate.
                try:
                    self.operation(row["operation_ref"])
                    item["can_register"] = row["outsourcing_ref"] is None
                    item["batch"] = self._target_entity_labels(row, "batch")
                    item["supplier"] = self._target_entity_labels(row, "supplier")
                except WorkbenchCommandRejected as exc:
                    item["issues"] = [{"code": exc.code, "message": str(exc)}]
            result.append(item)
        return bounded(result)
