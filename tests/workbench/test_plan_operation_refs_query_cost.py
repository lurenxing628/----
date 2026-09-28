"""Operation identity lookups stay bounded by requested keys, not cross products."""

from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.identity_metadata_support import seed_resources


def test_large_operation_ref_lookup_uses_bounded_primary_key_probes(schema_conn):
    conn = schema_conn
    seed_resources(conn)
    conn.executemany("INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_id, op_type_name, source) "
                     "VALUES (?, 'B1', ?, 'OT1', 'turning', 'internal')",
                     (("cost-" + str(index), index) for index in range(1, 10002)))
    conn.commit()
    expected = {int(row["source_key"]): row["ref"] for row in conn.execute(
        "SELECT source_key, ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
    requested = list(expected)
    # Count SQLite VM instructions instead of depending on host timing or a
    # particular EXPLAIN text. The former join order exceeded this by orders.
    steps = 0

    def progress():
        nonlocal steps
        steps += 1000
        return int(steps > 1000000)

    conn.set_progress_handler(progress, 1000)
    try:
        actual = WorkbenchPlanIdentityRepository(conn).get_operation_refs(requested + requested[:2])
    finally:
        conn.set_progress_handler(None, 0)
    assert actual == expected
    assert len(actual) == 10001
    assert steps < 1000000
