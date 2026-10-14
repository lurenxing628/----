"""Checkpoint content comparisons preserve resumed decoding and calendar rollback checks."""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest, decode_output_contents
from core.algorithms.greedy.dispatch.sgs_checkpoint_tail import DecodeTailReuse
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.errors import ValidationError
from core.services.scheduler.calendar.checkpoint_certificate import calendar_checkpoint_snapshot
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.run.optimizer.graph import iterated_greedy as ig_module
from core.services.scheduler.run.optimizer.graph.iterated_greedy_checkpoints import CheckpointStore
from core.services.scheduler.run.optimizer.graph_ready_profiles import default_weight_profiles
from data.repositories.calendar_checkpoint_repo import CalendarCheckpointRepository
from tests._support.busy_block_case import at, native_calendar
from tests.algorithm.test_execution_calendar_certified_overlay import _saturated_case


def test_checkpoint_resumes_same_inputs_and_rejects_changed_type_or_prefix():
    case = _saturated_case(batch_count=2, ops_per_batch=2)
    seed = ScheduleResult(99, "SEED", "FROZEN", 1, "M1", "O1", at(-1), at(),
                          op_type_name="SAME LABEL", op_type_id="T0")
    case["seed_results"] = [seed]
    with native_calendar() as calendar:
        scheduler = GreedyScheduler(calendar_service=calendar, config_service={"auto_assign_enabled": "no"})
        captured = []
        full = scheduler.schedule(**case, decode_checkpoints=DecodeCheckpointRequest([1, 2, 4], captured.append))
        checkpoint = captured[0]
        assert len(captured) == 3 and isinstance(checkpoint.signature, tuple)
        resumed = scheduler.schedule(**case, decode_resume=checkpoint)
        assert full[0] == resumed[0]
        contents = decode_output_contents(*full[:2])
        assert isinstance(contents, tuple) and contents == decode_output_contents(*resumed[:2])

        tail = DecodeTailReuse(captured)
        tail_result = scheduler.schedule(
            **case, decode_resume=checkpoint,
            decode_checkpoints=DecodeCheckpointRequest([1, 2, 4], lambda item: None, tail_reuse=tail),
        )
        assert tail_result[0] == full[0]
        assert tail.reused_picks == 2

        changed = dict(case, seed_results=[replace(seed, op_type_id="T1")])
        with pytest.raises(ValidationError) as caught:
            scheduler.schedule(**changed, decode_resume=checkpoint)
        assert caught.value.details["reason"] == "decode_checkpoint_signature_mismatch"
        changed_rows = [replace(row, op_type_id="OTHER") if row.op_id == 99 else row for row in full[0]]
        assert decode_output_contents(changed_rows, full[1]) != contents
        changed_rows = [replace(row, seq=True) if row.op_id == 99 else row for row in full[0]]
        assert decode_output_contents(changed_rows, full[1]) != contents
        summary = deepcopy(full[1])
        summary.failure_details = [{"op_id": 99, "reasons": ["original"]}]
        frozen = decode_output_contents(full[0], summary)
        saved_summary = deepcopy(summary)
        summary.failure_details[0]["reasons"].append("changed")
        assert frozen == decode_output_contents(full[0], saved_summary)
        assert frozen != decode_output_contents(full[0], summary)

        changed = deepcopy(case)
        first = checkpoint.prefix_op_ids[0]
        changed["graph_ready_context"]["graph_priority_key_by_op_id"][first] = (999.0, 999.0)
        with pytest.raises(ValidationError) as caught:
            scheduler.schedule(**changed, decode_resume=checkpoint)
        assert caught.value.details["reason"] == "decode_checkpoint_prefix_mismatch"


def test_ig_pending_contents_bound_memory_expire_scores_and_verify_full_decode(monkeypatch):
    search = object.__new__(ig_module._IteratedGreedySearch)
    profile = default_weight_profiles(max_weight_profiles=1)[0][0]
    search.profile = ig_module.ig_decode_profile(profile)
    search.parent = SimpleNamespace(batch_order=("B1",), order=(1,), inherited=())
    search.scores, search.pending_outputs, search.decoded_entries = {}, OrderedDict(), OrderedDict()
    search.pending_output_rows, search.scored_decodes = 0, 0
    search.checkpoints = CheckpointStore(1)
    monkeypatch.setattr(search.checkpoints, "best_for", lambda *args, **kwargs: SimpleNamespace(position=1))
    search.solution_pool = SimpleNamespace(size=3)
    search.clock, search.t_begin, search.decode_seconds = lambda: 0.0, 0.0, []
    search.report = {"duplicate_decision_pruned": 0, "reference_capture_decodes": 0,
                     "validation_decodes": 0, "context_switches": 0}
    search.incumbent = SimpleNamespace(best={"score": (0.0,)}, observe_trial=lambda candidate: None, report_state=None)
    search.attempts, search.strict_mode = [], True
    accepted, evaluations = [], []
    search._consider_for_incumbent = accepted.append
    monkeypatch.setattr(ig_module, "append_graph_attempt", lambda **kwargs: None)
    template = {"results": [], "summary": ScheduleSummary(True, 0, 0, 0, [], [], 0.0), "score": (10.0,)}

    def evaluate(**kwargs):
        evaluations.append((kwargs["repair_decision"].operation_order, "decode_resume" in kwargs))
        return {"results": list(template["results"]), "summary": deepcopy(template["summary"]), "score": template["score"]}

    search.evaluate = evaluate
    reference = SimpleNamespace(checkpoints=[], order=(1,))
    for index in range(33):
        assert search._score_trial((index + 1,), reference) == ((10.0,), True)
    assert len(search.pending_outputs) == 32 and search.pending_output_rows == 0
    assert (1,) not in search.scores and (1,) not in search.pending_outputs
    assert search._score_trial((1,), reference) == ((10.0,), True)
    assert evaluations.count(((1,), True)) == 2

    rows = [ScheduleResult(index, "OP", "B1", index, "M1", "O1", at(), at(1), op_type_id="T1")
            for index in range(1, 20001)]
    template.update(results=rows, summary=ScheduleSummary(True, 20000, 20000, 0, [], [], 0.0))
    first, second = tuple(range(1, 20001)), (2, 1) + tuple(range(3, 20001))
    search._score_trial(first, reference)
    search._score_trial(second, reference)
    assert len(search.pending_outputs) == 1 and search.pending_output_rows == 20000
    assert first not in search.scores and first not in search.pending_outputs
    entry = search._decode_entry(second)
    assert entry is not None and entry.score == (10.0,)
    assert search.pending_output_rows == 0 and not search.pending_outputs
    assert search.scores[second] == ((10.0,), True) and search.checkpoints.equivalence_checks == 1
    assert len(accepted) == 1 and evaluations[-1] == (second, False)

    for index, changed in enumerate(("output", "score", "score_type"), 30000):
        template.update(results=[rows[0]], summary=ScheduleSummary(True, 1, 1, 0, [], [], 0.0),
                        score=(1.0,) if changed == "score_type" else (10.0,))
        order = (index,)
        search._score_trial(order, reference)
        if changed == "output":
            template["results"] = [replace(rows[0], op_type_id="T2")]
        elif changed == "score":
            template["score"] = (11.0,)
        else:
            template["score"] = (True,)
        with pytest.raises(ValidationError) as caught:
            search._decode_entry(order)
        assert caught.value.details["reason"] == "decode_checkpoint_equivalence_violation"
        assert order not in search.pending_outputs and order not in search.scores
        assert search.pending_output_rows == 0 and len(accepted) == 1

    template.update(score=(10.0,))
    search._score_trial((40000,), reference)
    search._set_parent(SimpleNamespace(batch_order=("B2",), order=(1,), inherited=()), profile)
    assert not search.pending_outputs and search.pending_output_rows == 0
    assert not search.scores and not search.decoded_entries and search.report["context_switches"] == 1


def test_calendar_content_cache_does_not_reuse_rolled_back_transaction(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO WorkCalendar (date,shift_hours,efficiency) VALUES ('2026-09-08',8,1)")
    conn.commit()
    calendar = CalendarService(conn)
    original_reader = CalendarCheckpointRepository.calendar_signature_rows
    with patch.object(CalendarCheckpointRepository, "calendar_signature_rows", autospec=True,
                      side_effect=original_reader) as reader:
        original = calendar_checkpoint_snapshot(calendar)
        assert original[0] == "calendar-business-v1" and isinstance(original[1], tuple)
        assert calendar_checkpoint_snapshot(calendar) is original
        assert reader.call_count == 1

        conn.execute("BEGIN")
        conn.execute("UPDATE WorkCalendar SET efficiency=0.5 WHERE date='2026-09-08'")
        changed = calendar_checkpoint_snapshot(calendar)
        before_rollback = conn.total_changes
        assert changed != original and "_decode_checkpoint_calendar_cache" not in vars(calendar)
        conn.rollback()
        conn.execute("BEGIN")
        assert conn.total_changes == before_rollback
        assert calendar_checkpoint_snapshot(calendar) == original
        assert reader.call_count == 3
        conn.rollback()

        conn.execute("PRAGMA query_only=ON")
        readonly = calendar_checkpoint_snapshot(calendar)
        assert readonly == original and calendar_checkpoint_snapshot(calendar) is readonly
        assert reader.call_count == 4
