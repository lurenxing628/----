"""Batch list/detail/choices from one real SQLite snapshot."""

from core.models.workbench_batch_query import batch_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_facts import BatchFacts
from core.services.workbench.batch_projection import BatchProjection


def cell(entity, key):
    if key == "part_no":
        return entity["relationships"][key]
    return entity[key] if key in ("business_code", "status") else entity["fields"][key]


def matches_entity(query, batch, entity):
    if query["status"] and query["status"] != entity["status"] or query["ready_status"] and query["ready_status"] != batch["ready_status"]:
        return False
    if query["focus"] == "unready" and batch["ready_status"] == "yes":
        return False
    if query["focus"] == "gaps" and entity["operations"] and not entity["relationships"]["gap_count"]:
        return False
    return all(cell(entity, key) in values for key, values in query["column_filters"].items())


class WorkbenchBatchQueryService(BatchFacts):
    def matched(self, scope):
        query = batch_scope(scope)
        facts = self.load()
        projection = BatchProjection(facts)
        needle = query["query"].casefold()
        rows = []
        for batch in facts["Batches"]:
            part = projection.parts.get(batch["part_no"])
            label = part["part_name"] if part else ""
            if needle and not any(needle in str(value or "").casefold() for value in (batch["batch_id"], batch["part_no"], label)):
                continue
            if query["batch_ids"] is not None and batch["batch_id"] not in query["batch_ids"]:
                continue
            entity = projection.entity(batch)
            if matches_entity(query, batch, entity):
                rows.append(entity)
        rows.sort(key=lambda row: row["business_code"])
        rows.sort(key=lambda row: (cell(row, query["sort"]) is None, cell(row, query["sort"]) or 0), reverse=query["direction"] == "desc")
        return rows

    def page(self, scope):
        rows = self.matched(scope)
        start = (scope["page"] - 1) * scope["size"]
        return {"entities": rows[start:start + scope["size"]], "page": {"number": scope["page"], "size": scope["size"],
                    "total": len(rows), "pages": max(1, (len(rows) + scope["size"] - 1) // scope["size"]),
                    "sort": [{"field": scope["sort"], "direction": scope["direction"]}]},
                "metrics": {"scope": "filtered", "total": len(rows), "completed": sum(row["all_operations_complete"] for row in rows)},
                "create_context": None}

    def detail(self, ref):
        row = self.batch(ref)
        projection = BatchProjection(self.load())
        entity = projection.entity(row)
        entity["materials"] = projection.materials(row)
        entity["template"] = self.load()["workflow"][row["part_no"]]["workflow"]
        return entity

    def choices(self):
        projection = BatchProjection(self.load())
        parts = [{"ref": projection.ref("part", row["part_no"]), "business_code": row["part_no"], "label": row["part_name"]}
                 for row in self.load()["Parts"]]
        return {"parts": parts, **{name: [projection.resource(kind, key) for key in projection.catalogs[kind]]
                                  for name, kind in (("machines", "machine"), ("operators", "operator"), ("suppliers", "supplier"))},
                "authorizations": [{"machine_ref": projection.ref("machine", mid), "operator_ref": projection.ref("operator", oid)}
                                   for oid, mid in sorted(projection.links)]}

    def selection(self, scope):
        rows = self.matched(scope)
        if len(rows) > 5000:
            raise WorkbenchCommandRejected("invalid_input", "当前范围超过 5000 批，请缩小范围后再选择。", 422)
        return {"refs": [row["ref"] for row in rows], "count": len(rows)}
