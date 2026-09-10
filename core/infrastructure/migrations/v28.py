"""Index the frozen v27 operation birth lookup; registration belongs to main."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.workbench_lineage_lookup_schema import install_lineage_lookup


def run(conn, logger=None) -> MigrationOutcome:
    """Use the caller's transaction without changing schema version or old rows."""
    install_lineage_lookup(conn)
    return MigrationOutcome.APPLIED
