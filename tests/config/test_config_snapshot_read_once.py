"""One read per field, with the existing explicit-error priority preserved."""

from collections import Counter

import pytest

from core.errors import ValidationError
from core.models.schedule_config_runtime_coercion import (
    ensure_schedule_config_snapshot as runtime_snapshot,
)
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.config.config_snapshot import (
    build_schedule_config_snapshot,
    ensure_schedule_config_snapshot,
)


class _Values:
    def __init__(self, values):
        self.values, self.reads = values, Counter()

    def get(self, key, default=None):
        self.reads[key] += 1
        assert self.reads[key] == 1, "a snapshot must not observe two values for the same field"
        return self.values.get(key, default)


@pytest.mark.parametrize("ensure", [ensure_schedule_config_snapshot, runtime_snapshot])
def test_runtime_strict_snapshot_reads_each_field_once(ensure):
    config = _Values(default_snapshot_values())
    assert ensure(config, strict_mode=True).to_dict() == config.values
    assert set(config.reads) == set(config.values)


@pytest.mark.parametrize("ensure", [ensure_schedule_config_snapshot, runtime_snapshot])
def test_explicit_invalid_field_still_precedes_unrelated_missing_field(ensure):
    config = _Values({"dispatch_mode": "invalid"})
    with pytest.raises(ValidationError) as error:
        ensure(config, strict_mode=True)
    assert error.value.field == "dispatch_mode"


def test_repo_strict_snapshot_reads_each_field_once():
    values = default_snapshot_values()
    repo = _Values({key: {"config_value": value} for key, value in values.items()})
    assert build_schedule_config_snapshot(repo, strict_mode=True).to_dict() == values
    assert set(repo.reads) == set(values)


def test_page_save_reuses_rows_for_normalized_and_raw_state(schema_conn):
    service = ConfigService(schema_conn)
    service.ensure_defaults()
    values = service.get_snapshot(strict_mode=True).to_dict()
    statements = []
    schema_conn.set_trace_callback(statements.append)
    try:
        outcome = service.save_page_config(values)
    finally:
        schema_conn.set_trace_callback(None)
    assert outcome.snapshot.to_dict() == values
    for key, value in values.items():
        assert outcome.raw_persisted_values[key] == str(value)
    reads = [sql.upper() for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert sum("FROM SCHEDULECONFIG ORDER BY" in sql for sql in reads) == 2
    assert not any(f"WHERE CONFIG_KEY = '{key.upper()}'" in sql for key in values for sql in reads)
