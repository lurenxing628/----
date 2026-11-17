"""Shared decision-workspace fixtures: operation refs, a spare machine/operator pair, edited representative runs."""

from dataclasses import replace
from datetime import datetime

from core.services.workbench.run import compute as compute_module
from tests.workbench.run_candidate_support import compute, install_representatives


def operation_ref(case, op_id):
    return case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
        (str(op_id),),
    ).fetchone()[0]


def add_pair(case, machine="M2", operator="O2", label=r"备用'甲\N"):
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES (?,?)", (machine, label))
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,'T1')", (machine,))
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, label))
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))


def representative_archive(case, monkeypatch, settings=None, *, count=1, edits=None):
    """Save a real current run with ``count`` representatives, then give chosen ones explicit arrangements."""
    real_outcomes = compute_module._candidate_outcomes

    def outcomes_with_edits(conn, schedule_input, comparison, *, calendar, validation_context):
        outcomes = real_outcomes(
            conn,
            schedule_input,
            comparison,
            calendar=calendar,
            validation_context=validation_context,
        )
        for index, edit in (edits or {}).items():
            key = comparison.candidates[index].candidate_key
            outcome = outcomes[key]
            payload = outcome.validated_payload
            rows = []
            for row in payload.schedule_rows:
                item = {"op_id": row.op_id, "machine_id": row.machine_id, "operator_id": row.operator_id,
                        "start_time": row.start_time.isoformat(), "end_time": row.end_time.isoformat()}
                edit(item)
                rows.append(replace(
                    row,
                    machine_id=item["machine_id"],
                    operator_id=item["operator_id"],
                    start_time=datetime.fromisoformat(item["start_time"]),
                    end_time=datetime.fromisoformat(item["end_time"]),
                ))
            updated_payload = replace(payload, schedule_rows=list(rows))
            outcomes[key] = replace(
                outcome,
                validated_payload=updated_payload,
                resolved_intervals={row.op_id: (row.start_time, row.end_time) for row in rows},
            )
        return outcomes

    with monkeypatch.context() as archived:
        install_representatives(archived, count)
        if edits:
            archived.setattr(compute_module, "_candidate_outcomes", outcomes_with_edits)
        return compute(case, settings)
