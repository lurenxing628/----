"""Add the exact lookup used by frozen v27 birth triggers, without replaying facts."""

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.infrastructure.workbench_template_lineage_schema import template_lineage_contract_issues

from .schema_structure import SchemaStructure

LINEAGE_LOOKUP_INDEX = "idx_wb_lineage_operation_id_text"


def lineage_lookup_objects():
    """DDL hook for the main-owned current schema; v27 objects stay unchanged."""
    return {LINEAGE_LOOKUP_INDEX:
            "CREATE INDEX idx_wb_lineage_operation_id_text ON BatchOperations(CAST(id AS TEXT))"}


def lineage_lookup_contract_issues(structure):
    """Validate only this additive index; do not replace the v27 contract hook."""
    rows = [obj for name, obj in structure.objects.items() if name.lower() == LINEAGE_LOOKUP_INDEX.lower()]
    if not rows:
        return ["missing_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    expected = lineage_lookup_objects()[LINEAGE_LOOKUP_INDEX]
    if (len(rows) != 1 or rows[0][0] != "index" or rows[0][1] != "BatchOperations" or
            canonical_sql(rows[0][2]) != canonical_sql(expected)):
        return ["invalid_lineage_lookup:" + LINEAGE_LOOKUP_INDEX]
    return []


def install_lineage_lookup(conn):
    """Caller owns BEGIN/COMMIT/ROLLBACK; install only the exactly missing index."""
    if not conn.in_transaction:
        raise RuntimeError("install_lineage_lookup requires the caller's migration transaction.")
    structure = SchemaStructure(conn)
    issues = template_lineage_contract_issues(conn, structure=structure)
    lookup_issues = lineage_lookup_contract_issues(structure)
    issues += [issue for issue in lookup_issues if not issue.startswith("missing_lineage_lookup:")]
    if issues:
        raise RuntimeError("Cannot install lineage lookup: " + "; ".join(issues))
    if lookup_issues:
        conn.execute(lineage_lookup_objects()[LINEAGE_LOOKUP_INDEX])
