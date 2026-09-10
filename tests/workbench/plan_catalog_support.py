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


def candidate(conn, version, role, *, op_id=None, source="candidate_rows", status="completed", saved="yes"):
    candidate_id = conn.execute(
        "INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, detail_saved) "
        "VALUES (?, ?, ?, 'baseline', ?, ?)", (version, role, role + " label", status, saved),
    ).lastrowid
    selection(conn, version, role, candidate_id, source)
    if op_id is not None:
        conn.execute(
            "INSERT INTO ScheduleCandidateRows(version, candidate_id, op_id, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?)", (version, candidate_id, op_id, START, END),
        )
    return candidate_id


def selection(conn, version, role, candidate_id, source="schedule"):
    conn.execute(
        "INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table) VALUES (?, ?, ?, ?)",
        (version, role, candidate_id, source),
    )


def scenario(conn, key, version, *, op_id=None, status="active", published_version=None,
             role="adopted", source="schedule", candidate_id=None, candidate_key=None):
    conn.execute(
        "INSERT INTO ScheduleAdjustmentScenario(scenario_id, source_draft_id, base_version, base_plan_role, "
        "base_source_table, base_candidate_id, base_candidate_key, scenario_name, status, validation_status, "
        "row_count, published_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid', ?, ?)",
        (key, "draft-" + key, version, role, source, candidate_id, candidate_key, key + " name", status,
         1 if op_id is not None else 0, published_version),
    )
    if op_id is not None:
        conn.execute(
            "INSERT INTO ScheduleAdjustmentScenarioRow(scenario_id, source_table, op_id, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?)", (key, source, op_id, START, END),
        )
