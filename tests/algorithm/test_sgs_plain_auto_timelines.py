"""A non-cacheable native run retains live reads and plain segment mutations."""

import subprocess
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.owned_timeline import OwnedTimeline, OwnedTypeEntries
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.slot_overlap_reuse import SlotReuseTimeline, overlap_reuse_for, sgs_overlap_reuse
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch import sgs
from core.algorithms.greedy.dispatch.sgs_reuse import can_skip_native_sgs_reuse
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime import default_snapshot_values
from tests._support.busy_block_case import BASE, native_calendar


def _case(namespace=False):
    ops = [BatchOperation(id=i, op_code="OP" + str(i), batch_id="B" + str(i), seq=1,
                          op_type_id="TURN", op_type_name="TURN", unit_hours=1.0) for i in range(1, 4)]
    if namespace:
        ops = [SimpleNamespace(**vars(op)) for op in ops]
    batches = {op.batch_id: Batch(batch_id=op.batch_id, part_no="P", quantity=1, due_date="2026-09-30") for op in ops}
    return ops, batches


def _run(ops, batches, *, force_owned=False, before_dispatch=None, seeds=None):
    pool = {"machines_by_op_type": {"TURN": ["M1"]}, "operators_by_machine": {"M1": ["O1"]},
            "machines_by_operator": {"O1": ["M1"]}, "pair_rank": {}}
    captured = []
    original = scheduler_module._prepare_run_state
    def prepare(*args, **kwargs):
        state = original(*args, **kwargs)
        captured.append(state)
        return state
    with ExitStack() as stack:
        calendar = stack.enter_context(native_calendar())
        stack.enter_context(patch.object(scheduler_module, "_prepare_run_state", prepare))
        factory = stack.enter_context(patch.object(scheduler_module, "create_native_sgs_reuse",
                                                   wraps=scheduler_module.create_native_sgs_reuse))
        if force_owned:
            stack.enter_context(patch.object(scheduler_module, "can_skip_native_sgs_reuse", return_value=False))
        if before_dispatch is not None:
            stack.enter_context(patch.object(scheduler_module.GreedyScheduler, "_log_start", before_dispatch))
        config = default_snapshot_values()
        config["auto_assign_enabled"] = "yes"
        scheduler = scheduler_module.GreedyScheduler(calendar, SimpleNamespace(**config))
        rows, summary, strategy, params = scheduler.schedule(
            ops, batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack", resource_pool=pool,
            readiness_gate_enabled=True, seed_results=seeds, strict_mode=True)
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return (rows, fields, strategy, params), captured[0], factory.call_count


@pytest.mark.parametrize("namespace", [False, True])
def test_native_automatic_runs_keep_payload_and_type_history_without_score_factory(namespace):
    ops, batches = _case(namespace)
    batches["B2"].ready_date = "2026-09-09"
    seed = ScheduleResult(op_id=99, op_code="SEED", batch_id="SEED", seq=1, machine_id="M1", operator_id="O1",
                          start_time=BASE, end_time=BASE + timedelta(hours=1), source="internal", op_type_name="MILL")
    expected, owned, old_factories = _run(ops, batches, force_owned=True, seeds=[seed])
    actual, plain, factories = _run(ops, batches, seeds=[seed])
    assert actual == expected
    assert actual[1]["scheduled_ops"] == 4 and actual[1]["failed_ops"] == 0
    assert old_factories == 1 and factories == 0
    assert type(owned.machine_timeline) is OwnedTimeline
    assert type(plain.machine_timeline) is SlotReuseTimeline and type(plain.operator_timeline) is dict
    assert all(type(values) is list for values in list(plain.machine_timeline.values()) + list(plain.operator_timeline.values()))
    assert type(plain.last_op_type_by_machine) is MachineTypeState
    assert all(type(values) is OwnedTypeEntries for values in plain.last_op_type_by_machine._entries.values())


@pytest.mark.parametrize("namespace", [False, True])
def test_fixed_resource_member_keeps_owned_storage_and_native_factory(namespace):
    ops, batches = _case(namespace)
    ops[1].machine_id, ops[1].operator_id = "M1", "O1"
    assert not can_skip_native_sgs_reuse(ops)
    payload, state, factories = _run(ops, batches)
    assert payload[1]["failed_ops"] == 0 and factories == 1
    assert type(state.machine_timeline) is OwnedTimeline and type(state.operator_timeline) is OwnedTimeline


def test_callback_can_change_automatic_resources_after_probe_and_every_candidate_is_rescored():
    ops, batches = _case()
    def change_resources(self, **kwargs):
        for op in ops:
            op.machine_id, op.operator_id = "M1", "O1"
    with patch.object(sgs, "_score_candidate", wraps=sgs._score_candidate) as scoring:
        payload, state, factories = _run(ops, batches, before_dispatch=change_resources)
    assert factories == 0 and scoring.call_count == 6
    assert type(state.machine_timeline) is SlotReuseTimeline
    assert payload[1]["failed_ops"] == 0
    assert [(row.machine_id, row.operator_id) for row in payload[0]] == [("M1", "O1")] * 3
    assert [row.start_time for row in payload[0]] == [BASE + timedelta(hours=i) for i in range(3)]


def test_plain_recorded_segments_keep_full_content_overlap_certificates():
    ops, batches = _case()
    _, state, _ = _run(ops, batches)
    machine, operator = state.machine_timeline["M1"], state.operator_timeline["O1"]
    with sgs_overlap_reuse(state.machine_timeline):
        reuse = overlap_reuse_for(state.machine_timeline)
        assert reuse is not None
        for kind, values in (("machine", machine), ("operator", operator)):
            first = reuse.index(kind, "R", values)
            list.__setitem__(values, 0, (BASE - timedelta(hours=1), BASE))
            changed = reuse.index(kind, "R", values)
            assert changed is not first
            assert reuse.index(kind, "R", values) is changed
            list.append(values, (BASE + timedelta(hours=8), BASE + timedelta(hours=9)))
            assert reuse.index(kind, "R", values) is not changed


class _Bomb:
    def __bool__(self):
        raise AssertionError("custom truth")

    def __eq__(self, other):
        raise AssertionError("custom equality")

    def __hash__(self):
        raise AssertionError("custom hash")


@pytest.mark.parametrize("field", ["source", "machine_id", "operator_id"])
def test_unknown_values_do_not_run_custom_methods(field):
    ops, _ = _case()
    vars(ops[0])[field] = _Bomb()
    assert not can_skip_native_sgs_reuse(ops)


def test_subclasses_and_custom_metaclasses_are_rejected_without_comparison():
    class Meta(type):
        def __eq__(self, other):
            raise AssertionError("metaclass equality")
        def __hash__(self):
            raise AssertionError("metaclass hash")
    class Custom(metaclass=Meta):
        def __getattribute__(self, name):
            raise AssertionError("custom getter")
    class Derived(SimpleNamespace):
        pass
    assert not can_skip_native_sgs_reuse([Custom()])
    assert not can_skip_native_sgs_reuse([Derived(machine_id=None, operator_id=None)])


def test_replaced_dict_and_non_string_keys_are_rejected_before_lookup():
    class CustomDict(dict):
        def keys(self):
            raise AssertionError("custom keys")
        def get(self, *args):
            raise AssertionError("custom get")
    ops, _ = _case()
    ops[0].__dict__ = CustomDict(vars(ops[0]))
    assert not can_skip_native_sgs_reuse(ops)
    class Key:
        def __hash__(self):
            return hash("source")
        def __eq__(self, other):
            raise AssertionError("colliding key equality")
    op = SimpleNamespace()
    cast(Any, vars(op))[Key()] = "internal"
    assert not can_skip_native_sgs_reuse([op])


@pytest.mark.parametrize("descriptor", ["source", "__getattribute__"])
def test_changed_class_hooks_do_not_preempt_prepare_stage_error(descriptor):
    ops, batches = _case()
    def fail(*args):
        raise AssertionError("new probe called a changed descriptor")
    hook = fail if descriptor == "__getattribute__" else property(fail)
    with patch.object(BatchOperation, descriptor, hook), patch.object(
            scheduler_module, "_prepare_run_state", side_effect=RuntimeError("prepare first")):
        # The direct probe cannot invoke a changed hook. Source is not consumed
        # by the existing ordering stage.
        assert not can_skip_native_sgs_reuse(ops)
        if descriptor != "__getattribute__":
            with native_calendar() as calendar, pytest.raises(RuntimeError, match="prepare first"):
                scheduler_module.GreedyScheduler(calendar, SimpleNamespace(**default_snapshot_values())).schedule(
                    ops, batches, start_dt=BASE, dispatch_mode="sgs", strict_mode=True)


def test_external_and_missing_resource_fields_are_safe_to_skip():
    assert can_skip_native_sgs_reuse([SimpleNamespace(source="external", machine_id="M1", operator_id="O1")])
    assert can_skip_native_sgs_reuse([SimpleNamespace()])
    assert not can_skip_native_sgs_reuse([SimpleNamespace(source="unknown")])


@pytest.mark.parametrize("before_import", [
    "native", "__init__", "__new__", "__post_init__", "__getattribute__", "__getattr__",
    "source", "machine_id", "operator_id",
])
def test_first_helper_import_never_constructs_dto_or_certifies_preexisting_access_hooks(before_import):
    # A fresh interpreter is essential: reloading an already imported helper
    # would miss constructor callbacks in the real initial import sequence.
    script = dedent("""
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from core.models.batch_operation import BatchOperation
        from core.models.batch import Batch
        from core.models.schedule_config_runtime import default_snapshot_values
        assert 'core.algorithms.greedy.dispatch.sgs_reuse' not in sys.modules
        op = BatchOperation(id=1, op_code='OP', batch_id='B')
        kind = sys.argv[1]
        calls = []
        def fail(*args, **kwargs):
            calls.append(kind)
            raise AssertionError('new probe invoked a pre-import callback: ' + kind)
        if kind in ('__init__', '__new__', '__getattr__'):
            setattr(BatchOperation, kind, fail)
        elif kind == '__post_init__':
            BatchOperation.__post_init__ = fail
            def changed_init(self, *args, **kwargs):
                self.__post_init__()
            BatchOperation.__init__ = changed_init
        elif kind == '__getattribute__':
            original = BatchOperation.__getattribute__
            def getter(self, name):
                if name == '__dict__':
                    return fail()
                return original(self, name)
            BatchOperation.__getattribute__ = getter
        elif kind in ('source', 'machine_id', 'operator_id'):
            setattr(BatchOperation, kind, property(fail))
        import core.algorithms.greedy.dispatch.sgs_reuse as helper
        assert calls == []
        safe = kind in ('native', '__init__', '__new__', '__post_init__')
        assert helper.can_skip_native_sgs_reuse([op]) is safe
        assert calls == []
        from core.algorithms.greedy import scheduler
        from tests._support.busy_block_case import BASE, native_calendar
        with native_calendar() as calendar, patch.object(
                scheduler, '_prepare_run_state', side_effect=RuntimeError('prepare first')):
            try:
                scheduler.GreedyScheduler(calendar, SimpleNamespace(**default_snapshot_values())).schedule(
                    [op], {'B': Batch(batch_id='B', part_no='P', quantity=1)}, start_dt=BASE,
                    dispatch_mode='sgs', strict_mode=True)
            except RuntimeError as exc:
                assert str(exc) == 'prepare first'
            else:
                raise AssertionError('expected the existing prepare-stage error')
        assert calls == []
    """)
    result = subprocess.run([sys.executable, "-c", script, before_import],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("model,hook", [(model, hook) for model in ("operation", "batch")
                                       for hook in ("getter", "descriptor")])
def test_preimport_model_hooks_cannot_enter_fixed_resource_score_cache(model, hook):
    script = dedent("""
        import cProfile
        import pstats
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from core.models.batch import Batch
        from core.models.batch_operation import BatchOperation
        from core.models.schedule_config_runtime import default_snapshot_values
        assert 'core.algorithms.greedy.dispatch.sgs_reuse' not in sys.modules
        ops = [BatchOperation(id=i, op_code='OP'+str(i), batch_id='B'+str(i), seq=1,
                              machine_id='M'+str(i), operator_id='O'+str(i), unit_hours=1.0,
                              op_type_name='TURN') for i in range(1, 4)]
        batches = {op.batch_id: Batch(batch_id=op.batch_id, part_no='P', quantity=1,
                                     due_date='2026-09-30') for op in ops}
        owner = BatchOperation if sys.argv[1] == 'operation' else Batch
        field = 'setup_hours' if sys.argv[1] == 'operation' else 'due_date'
        calls = []
        if sys.argv[2] == 'getter':
            original = owner.__getattribute__
            def getter(self, name):
                if name == field:
                    calls.append(name)
                return original(self, name)
            owner.__getattribute__ = getter
        else:
            def descriptor(self):
                calls.append(field)
                return object.__getattribute__(self, '__dict__')[field]
            setattr(owner, field, property(descriptor))
        from core.algorithms.greedy import scheduler
        from tests._support.busy_block_case import BASE, native_calendar
        def run(enabled):
            factory = scheduler.create_native_sgs_reuse if enabled else lambda *args: None
            calls.clear()
            with native_calendar() as calendar, patch.object(scheduler, 'create_native_sgs_reuse', factory):
                instance = scheduler.GreedyScheduler(calendar, SimpleNamespace(**default_snapshot_values()))
                profile = cProfile.Profile()
                profile.enable()
                rows, summary, *_ = instance.schedule(ops, batches, start_dt=BASE,
                    dispatch_mode='sgs', dispatch_rule='slack', strict_mode=True)
                profile.disable()
            scores = sum(value[1] for key, value in pstats.Stats(profile).stats.items()
                         if key[2] == '_score_candidate')
            payload = [(row.op_id, row.start_time, row.end_time) for row in rows]
            assert summary.failed_ops == 0
            return payload, list(calls), scores, instance._last_sgs_reuse_stats
        expected = run(False)
        actual = run(True)
        assert actual == expected
        assert actual[2] == 6 and actual[3] == {'hits': 0, 'misses': 0}
        assert actual[1], 'the custom accessor must remain observable'
    """)
    result = subprocess.run([sys.executable, "-c", script, model, hook],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
