"""Lookup index used by birth triggers on BatchOperations."""

from core.infrastructure.workbench_metadata_schema import canonical_sql

LINEAGE_LOOKUP_INDEX = "idx_wb_lineage_operation_id_text"


def lineage_lookup_objects():
    """DDL hook for the main-owned current schema."""
    return {LINEAGE_LOOKUP_INDEX:
            "CREATE INDEX idx_wb_lineage_operation_id_text ON BatchOperations(CAST(id AS TEXT))"}


def lineage_lookup_contract_issues(structure):
    """Validate only this additive index."""
    rows = [obj for name, obj in structure.objects.items() if name.lower() == LINEAGE_LOOKUP_INDEX.lower()]
    if not rows:
        return ["missing_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    expected = lineage_lookup_objects()[LINEAGE_LOOKUP_INDEX]
    if (len(rows) != 1 or rows[0][0] != "index" or rows[0][1] != "BatchOperations" or
            canonical_sql(rows[0][2]) != canonical_sql(expected)):
        return ["invalid_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    return []
