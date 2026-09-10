"""Original stage-save assertions against explicit next-release CO storage."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import install
from tests.workbench import test_process_stage_commands as legacy
from tests.workbench.process_commands_support import stage_database


@pytest.mark.parametrize("check", [
    legacy.test_zero_hours_need_explicit_unit_review_but_setup_zero_is_normal,
    legacy.test_hours_keep_per_operation_and_merged_totals_independent,
    legacy.test_separate_group_hidden_total_never_reset_by_hours,
    legacy.test_merged_group_with_only_total_days_accepts_null_member_cycle,
    legacy.test_10000_existing_operations_can_confirm_source_and_hours_without_truncation,
])
def test_existing_stage_save_contract_with_explicit_co_ddl(schema_conn, check):
    with TransactionManager(schema_conn).transaction():
        install(schema_conn)
    conn = stage_database.__wrapped__(schema_conn)
    check(conn)
