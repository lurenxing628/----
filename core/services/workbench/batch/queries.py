"""Batch list/detail/choices from one real SQLite snapshot."""

from core.models.workbench_command import WorkbenchCommandRejected

from .facts import BatchFacts
from .projection import BatchProjection, batch_choices
from .resource_choices import BatchResourceFacts, operation_choices, operator_machine_links
from .scope import BatchFactScope
from .template_validation import template_status


def cell(entity, key):
    if key == "ready_status":
        return entity["display_ready_status"]
    if key == "part_no":
        return entity["relationships"][key]
    return entity[key] if key in ("business_code", "status") else entity["fields"][key]


def _header_cell(batch, fields, display_ready, key):
    if key == "ready_status":
        return display_ready
    if key == "part_no":
        return batch["part_no"]
    if key == "business_code":
        return batch["batch_id"]
    return fields[key]


def _matches_header(query, batch, fields, display_ready):
    if query["ready_status"] and query["ready_status"] != display_ready:
        return False
    if query["focus"] == "unready" and display_ready == "yes":
        return False
    return all(
        _header_cell(batch, fields, display_ready, key) in values
        for key, values in query["column_filters"].items()
        if key != "status"
    )


def _matches_operation_state(query, entity):
    if query["status"] and query["status"] != entity["status"]:
        return False
    if query["focus"] == "gaps" and entity["relationships"]["operation_count"] and not entity["relationships"]["gap_count"]:
        return False
    status_values = query["column_filters"].get("status")
    return status_values is None or entity["status"] in status_values


class WorkbenchBatchQueryService:
    def __init__(self, conn, logger=None):
        self.facts = BatchFacts(conn, logger)

    def matched(self, scope: BatchFactScope, query):
        facts = scope.load()
        projection = BatchProjection(facts)
        needle = query["query"].casefold()
        batch_ids = set(query["batch_ids"]) if query["batch_ids"] is not None else None
        rows = []
        for batch in facts["Batches"]:
            if batch_ids is not None and batch["batch_id"] not in batch_ids:
                continue
            part = projection.parts.get(batch["part_no"])
            label = part["part_name"] if part else ""
            if needle and not any(needle in value.casefold() for value in (batch["batch_id"], batch["part_no"], label)):
                continue
            header = projection.batch_header(batch)
            _, fields, display_ready, _ = header
            if not _matches_header(query, batch, fields, display_ready):
                continue
            entity = projection.summary(batch, header=header)
            if _matches_operation_state(query, entity):
                rows.append(entity)

        def sort_key(row):
            value = cell(row, query["sort"])
            return value is None, value

        rows.sort(key=lambda row: row["business_code"])
        rows.sort(key=sort_key, reverse=query["direction"] == "desc")
        return rows

    def page(self, scope: BatchFactScope, query):
        rows = self.matched(scope, query)
        start = (query["page"] - 1) * query["size"]
        return {
            "entities": rows[start : start + query["size"]],
            "page": {
                "number": query["page"],
                "size": query["size"],
                "total": len(rows),
                "pages": max(1, (len(rows) + query["size"] - 1) // query["size"]),
                "sort": [{"field": query["sort"], "direction": query["direction"]}],
            },
            "metrics": {
                "scope": "filtered",
                "total": len(rows),
                "completed": sum(row["all_operations_complete"] for row in rows),
            },
            "create_context": None,
        }

    def detail(self, scope: BatchFactScope, ref):
        """Expand complete operation details for the requested batch."""
        facts = scope.load()
        row = scope.batch(ref)
        projection = BatchProjection(facts)
        entity = projection.entity(row)
        entity["materials"] = projection.materials(row)
        entity["template"] = template_status(facts, row, projection.resources)
        return entity

    def summaries(self, scope: BatchFactScope, refs):
        """Selected-list consumers share the same summary as filtered lists."""
        facts = scope.load()
        rows = [scope.batch(ref) for ref in refs]
        projection = BatchProjection(facts)
        return [projection.summary(row) for row in rows]

    def choices_catalog(self):
        facts = self.facts.load_choices()
        return batch_choices(facts, operator_machine_links(facts))

    def operation_choices(self, scope: BatchFactScope, batch_ref, operation_ref):
        facts = scope.load()
        resources = BatchResourceFacts(facts)
        return operation_choices(
            scope, batch_ref, operation_ref, batch_choices(facts, resources.links), resources, facts
        )

    def selection(self, scope: BatchFactScope, query):
        rows = self.matched(scope, query)
        if len(rows) > 5000:
            raise WorkbenchCommandRejected("invalid_input", "当前范围超过 5000 批，请缩小范围后再选择。", 422)
        return {"refs": [row["ref"] for row in rows], "count": len(rows)}
