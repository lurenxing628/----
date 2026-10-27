"""Real-schema, in-memory fixtures for the private plan catalog; no app startup."""

START = "2026-09-09 08:00:00"
END = "2026-09-09 09:00:00"


def seed_operation(conn):
    conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('CAT-P', 'Catalog part')")
    conn.execute("INSERT INTO Batches(batch_id, part_no, quantity) VALUES ('CAT-B', 'CAT-P', 1)")
    return conn.execute(
        "INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name) VALUES ('CAT-OP', 'CAT-B', 1, 'Catalog op')"
    ).lastrowid


def history(conn, version, status="success", summary="{}", *, op_id=None, time=START):
    conn.execute(
        "INSERT INTO ScheduleHistory(version, strategy, result_status, result_summary, schedule_time) "
        "VALUES (?, 'catalog', ?, ?, ?)", (version, status, summary, time),
    )
    if op_id is not None:
        conn.execute(
            "INSERT INTO Schedule(version, op_id, start_time, end_time) VALUES (?, ?, ?, ?)",
            (version, op_id, START, END),
        )
