"""Opt-in pytest plugin: install frozen lineage DDL in batch regression fixtures."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_template_lineage_schema import install


@pytest.fixture(autouse=True)
def install_lineage_for_batch_regression(schema_conn):
    with TransactionManager(schema_conn).transaction():
        install(schema_conn)
