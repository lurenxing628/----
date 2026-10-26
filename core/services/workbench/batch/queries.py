"""Batch list/detail/choices from one real SQLite snapshot."""

from core.models.workbench_batch_query import batch_scope
from core.models.workbench_command import WorkbenchCommandRejected

from .facts import BatchFacts
from .projection import BatchProjection, batch_choices
from .resource_choices import BatchResourceFacts, operation_choices, operator_machine_links
from .template_validation import template_status


def cell(entity, key):
    if key == "ready_status":
        return entity["display_ready_status"]
    if key == "part_no":
        return entity["relationships"][key]
    return entity[key] if key in ("business_code", "status") else entity["fields"][key]


def matches_entity(query, entity):
    if query["status"] and query["status"] != entity["status"] or query["ready_status"] and query["ready_status"] != cell(entity, "ready_status"):
        return False
    if query["focus"] == "unready" and cell(entity, "ready_status") == "yes":
        return False
    if query["focus"] == "gaps" and entity["relationships"]["operation_count"] and not entity["relationships"]["gap_count"]:
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
            if needle and not any(needle in value.casefold() for value in (batch["batch_id"], batch["part_no"], label)):
                continue
            if query["batch_ids"] is not None and batch["batch_id"] not in query["batch_ids"]:
                continue
            entity = projection.summary(batch)
            if matches_entity(query, entity):
                rows.append(entity)

        def sort_key(row):
            value = cell(row, query["sort"])
            return value is None, value

        rows.sort(key=lambda row: row["business_code"])
        rows.sort(key=sort_key, reverse=query["direction"] == "desc")
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
        """Expand complete operation details for the requested batch."""
        row = self.batch(ref)
        facts = self.load()
        projection = BatchProjection(facts)
        entity = projection.entity(row)
        entity["materials"] = projection.materials(row)
        entity["template"] = template_status(facts, row, projection.resources)
        return entity

    def summaries(self, refs):
        """Selected-list consumers share the same summary as filtered lists."""
        facts = self.load()
        rows = [self.batch(ref) for ref in refs]
        projection = BatchProjection(facts)
        return [projection.summary(row) for row in rows]

    def choices(self, batch_ref=None, operation_ref=None):
        if batch_ref is None and operation_ref is None:
            facts = self.load_choices()
            return batch_choices(facts, operator_machine_links(facts))
        facts = self.load()
        resources = BatchResourceFacts(facts)
        return operation_choices(self, batch_ref, operation_ref, batch_choices(facts, resources.links), resources, facts)

    def selection(self, scope):
        rows = self.matched(scope)
        if len(rows) > 5000:
            raise WorkbenchCommandRejected("invalid_input", "当前范围超过 5000 批，请缩小范围后再选择。", 422)
        return {"refs": [row["ref"] for row in rows], "count": len(rows)}
