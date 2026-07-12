"""Compatibility imports for migration helpers now owned by the infrastructure parent."""

from core.infrastructure.migration_common import (
    MigrationOutcome,
    add_column_if_missing,
    column_exists,
    fallback_log,
    merge_outcomes,
    table_exists,
)

__all__ = [
    "MigrationOutcome",
    "add_column_if_missing",
    "column_exists",
    "fallback_log",
    "merge_outcomes",
    "table_exists",
]
