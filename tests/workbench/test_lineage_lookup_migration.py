"""Real v27-to-current migration preserves trials while installing the v28 lookup."""

import hashlib
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    get_schema_version,
    set_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v28
from core.infrastructure.workbench_lineage_lookup_schema import LINEAGE_LOOKUP_INDEX, lineage_lookup_contract_issues
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.template_lineage import TemplateLineageWriter
from tests.workbench.dashboard_external_migration_support import V31_TABLES, assert_v31_receipt_maps_only
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v32_empty,
)
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.run_schema_migration_support import connect, snapshot, source_ddl
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only
from tests.workbench.trial_support import change, create, service

FIXTURE = Path(__file__).parent / "fixtures" / "schema-v27.sql"
FIXTURE_SHA = "dca9a9cd506c22096e4b4dd87e8524d31cf97c7f9dd2567564fecc5181a8e198"


def seeded_v27(path):
    from tests.workbench.frozen_business_seed_support import seed_frozen_business

    return seed_frozen_business(path, 27)


def test_fixed_v27_fixture_matches_original_and_fresh_v28_has_valid_index(tmp_path, schema_path):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA
    assert MIGRATIONS[28] is v28.run
    path = tmp_path / "fresh.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert lineage_lookup_contract_issues(conn) == []


def test_real_upgrade_keeps_all_typed_rows_trial_history_and_refs(tmp_path, schema_path):
    path, backups = tmp_path / "v27.db", tmp_path / "backups"
    with seeded_v27(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
        for table in ("WorkbenchTemplateLineageOrigins", "WorkbenchTemplateLineageEvents",
                      "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialChanges", "WorkbenchTrialScenarios"):
            assert before[table], table
        assert get_schema_version(conn) == 27
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        after = snapshot(conn)
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION and current_schema_contract_issues(conn) == []
        assert set(after) - set(before) == set(V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
        assert {key: after[key] for key in before if key != "SchemaVersion"} == {
            key: value for key, value in before.items() if key != "SchemaVersion"}
        old_names = {row[1] for row in ddl}
        assert [row for row in source_ddl(conn) if row[1] in old_names] == ddl
        assert lineage_lookup_contract_issues(conn) == []
        assert_v29_source_maps_only(conn)
        assert_v30_source_maps_only(conn)
        assert_v31_receipt_maps_only(conn)
        assert_v32_empty(conn)
    files = list(backups.glob(f"*before_migrate_v27_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(files) == 1
    with connect(files[0]) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == after
    assert len(list(backups.glob("*.db"))) == 1


def test_failed_probe_does_not_install_index_or_mutate_original_v27(tmp_path, schema_path, monkeypatch):
    path, backups = tmp_path / "failed.db", tmp_path / "backups"
    with seeded_v27(path) as conn:
        before, ddl = snapshot(conn), source_ddl(conn)
    install = v28.install_lineage_lookup

    def fail(conn):
        install(conn)
        raise RuntimeError("injected lookup migration failure")

    monkeypatch.setattr(v28, "install_lineage_lookup", fail)
    with pytest.raises(RuntimeError, match="injected lookup"):
        ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl


def test_current_database_missing_index_is_not_silently_repaired(tmp_path, schema_path):
    path = tmp_path / "damaged.db"
    ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        conn.execute("DROP INDEX " + LINEAGE_LOOKUP_INDEX)
        conn.commit()
        before, ddl = snapshot(conn), source_ddl(conn)
    with pytest.raises(MigrationContractError, match="lineage_lookup"):
        ensure_schema(str(path), schema_path=schema_path)
    with connect(path) as conn:
        assert snapshot(conn) == before and source_ddl(conn) == ddl
