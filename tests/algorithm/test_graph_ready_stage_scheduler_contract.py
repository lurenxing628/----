"""Stage selection contracts with exact task clocks; no fabricated scheduling output."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_stage_scheduler import SearchStage, StageScheduler


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Stage(SearchStage):
    def __init__(self, name, *, clock, log, durations, events=None, ready=None, unavailable_reason="no_work"):
        self.name, self.clock, self.log = name, clock, log
        self.durations = list(durations)
        self.events = list(events) if events is not None else [0] * len(self.durations)
        self.ready = ready or (lambda: True)
        self.reason = unavailable_reason
        self.calls = 0
        self.finished = False

    def available(self):
        return self.calls < len(self.durations) and self.ready()

    def unavailable_reason(self):
        return None if self.available() else self.reason

    def run_task(self):
        self.log.append(self.name)
        self.clock.now += self.durations[self.calls]
        event_count = self.events[self.calls]
        self.calls += 1
        return event_count

    def finish(self):
        self.finished = True


def _stages(clock, log, *, durations, events=None):
    names = ("profiles", "elite_repair", "iterated_greedy")
    return [Stage(name, clock=clock, log=log, durations=durations[index],
                  events=None if events is None else events[index]) for index, name in enumerate(names)]


def test_zero_clock_gives_each_available_stage_a_first_task_then_keeps_fair_ties():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([0.0] * 3, [0.0] * 3, [0.0] * 3))
    scheduler = StageScheduler(stages, clock=clock, deadline=1.0)
    scheduler.run()
    assert log == ["profiles", "elite_repair", "iterated_greedy"] * 3
    report = scheduler.summary()
    assert set(report["stage_time_ms"].values()) == {0}
    assert set(report["stage_charged_time_ms"].values()) == {3}
    assert all(item == {"status": "task_started", "reason": None} for item in report["stage_startup"].values())
    assert report["rotation_stop_reason"] == "stages_exhausted"
    assert all(stage.finished for stage in stages)


def test_stage_that_becomes_available_later_gets_its_start_before_more_tried_tasks():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([0.01] * 4, [0.01] * 2, [0.01] * 2))
    stages[1].ready = lambda: stages[0].calls >= 2
    scheduler = StageScheduler(stages, clock=clock, deadline=1.0)
    scheduler.run()
    assert log[:4] == ["profiles", "iterated_greedy", "profiles", "elite_repair"]


def test_deadline_prevents_pending_startups_and_reports_them_without_promising_preemption():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([1.1], [0.01], [0.01]))
    scheduler = StageScheduler(stages, clock=clock, deadline=1.0)
    scheduler.run()
    assert log == ["profiles"]
    report = scheduler.summary()
    assert report["stage_startup"]["profiles"]["status"] == "task_started"
    assert report["stage_startup"]["elite_repair"] == report["stage_startup"]["iterated_greedy"] == {
        "status": "skipped", "reason": "time_budget"}
    assert report["stage_time_ms"]["profiles"] == 1100
    assert report["rotation_stop_reason"] == "time_budget"


def test_disabled_stage_reports_its_actual_reason_when_no_startup_is_possible():
    clock, log = Clock(), []
    stage = Stage("disabled", clock=clock, log=log, durations=[0.01], ready=lambda: False, unavailable_reason="disabled")
    scheduler = StageScheduler([stage], clock=clock, deadline=0.0)
    scheduler.run()
    assert scheduler.summary()["stage_startup"]["disabled"] == {"status": "skipped", "reason": "disabled"}
    assert log == []


def test_availability_work_crossing_deadline_does_not_start_a_task():
    clock, log = Clock(), []

    def ready():
        clock.now = 1.0
        return True

    stage = Stage("profiles", clock=clock, log=log, durations=[0.01], ready=ready)
    scheduler = StageScheduler([stage], clock=clock, deadline=1.0)
    scheduler.run()
    assert log == []
    assert scheduler.summary()["stage_startup"]["profiles"] == {"status": "skipped", "reason": "time_budget"}


def test_time_fairness_uses_duration_instead_of_equal_candidate_counts():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([0.01] * 100, [0.02] * 100, [0.03] * 100))
    scheduler = StageScheduler(stages, clock=clock, deadline=0.6)
    scheduler.run()
    assert max(scheduler.seconds.values()) - min(scheduler.seconds.values()) <= 0.03 + 1e-12
    assert stages[0].calls > stages[1].calls > stages[2].calls


def test_recent_strict_events_change_selection_but_bonus_cannot_starve_quiet_stages():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([0.01] * 1000,) * 3,
                     events=([0] * 1000, [0] * 1000, [1] * 1000))
    scheduler = StageScheduler(stages, clock=clock, deadline=1.2)
    scheduler.run()
    assert log[:4] == ["profiles", "elite_repair", "iterated_greedy", "iterated_greedy"]
    assert stages[2].calls > stages[0].calls >= 30
    assert stages[1].calls >= 30
    report = scheduler.summary()
    assert report["stage_strict_improvements"]["iterated_greedy"] == stages[2].calls
    assert report["stage_recent_improvements_per_second"]["iterated_greedy"] == pytest.approx(100.0)
    # One indivisible task can put the preferred stage beyond the bounded weighted share.
    assert scheduler.seconds["iterated_greedy"] <= min(scheduler.seconds.values()) * 1.25 + 0.01 + 1e-12


def test_improvement_feedback_expires_when_the_recent_tasks_stop_improving():
    clock, log = Clock(), []
    stage = Stage("profiles", clock=clock, log=log, durations=[0.01] * 10, events=[2, 1] + [0] * 8)
    scheduler = StageScheduler([stage], clock=clock, deadline=1.0)
    scheduler.run()
    report = scheduler.summary()
    assert report["stage_strict_improvements"]["profiles"] == 3
    assert report["stage_recent_improvements_per_second"]["profiles"] == 0.0


def test_zero_duration_improvements_are_counted_but_do_not_invent_a_gain_rate():
    clock, log = Clock(), []
    stages = _stages(clock, log, durations=([0.0] * 4,) * 3, events=([0] * 4, [0] * 4, [2] * 4))
    scheduler = StageScheduler(stages, clock=clock, deadline=1.0)
    scheduler.run()
    assert log == ["profiles", "elite_repair", "iterated_greedy"] * 4
    report = scheduler.summary()
    assert report["stage_strict_improvements"]["iterated_greedy"] == 8
    assert set(report["stage_recent_improvements_per_second"].values()) == {0.0}
    assert set(report["stage_time_ms"].values()) == {0}


@pytest.mark.parametrize("events", [-1, 0.5, True, None])
def test_invalid_improvement_event_counts_fail_loud(events):
    clock, log = Clock(), []
    stage = Stage("profiles", clock=clock, log=log, durations=[0.01], events=[events])
    scheduler = StageScheduler([stage], clock=clock, deadline=1.0)
    with pytest.raises(ValueError, match="strict improvement event count"):
        scheduler.run()
    assert stage.finished


def test_ig_startup_waits_for_real_readiness_only_until_its_first_task():
    from core.services.scheduler.run.optimizer_graph_ready_stages import IteratedGreedyStage

    ready = [False]
    run = SimpleNamespace(available=lambda: True, started_at=None, limits=SimpleNamespace(enabled=True),
                          state=SimpleNamespace(best={"score": (1,)}), search=None, deadline=1.0,
                          clock=lambda: 0.0, stopped=False)
    stage = IteratedGreedyStage(run, startup_ready=lambda: ready[0])
    assert not stage.available()
    assert stage.unavailable_reason() == "waiting_for_repair_parent"
    # Readiness can be satisfied immediately; there is no hard-coded count of profile attempts.
    ready[0] = True
    assert stage.available()
    run.started_at = 0.0
    ready[0] = False
    assert stage.available()


def test_profiles_all_rejected_still_allow_ig_to_decode_a_legal_baseline():
    from core.infrastructure.errors import ValidationError
    from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
    from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case

    now, starts = [0.0], []

    def schedule(scheduler, **kwargs):
        origin = kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"]
        starts.append((now[0], origin))
        if origin != "graph_ready_v2_iterated_greedy":
            now[0] += 1.0
            raise ValidationError("controlled profile rejection", field="schedule")
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += 1.0
        return result

    result = run_production_repair_case(max_candidates=3, clock=lambda: now[0], schedule_fn=schedule,
                                        strict_mode=False, time_budget_seconds=4.0, iterated_greedy={"max_decodes": 1})
    assert len(starts) == 4 and starts[-1] == (3.0, "graph_ready_v2_iterated_greedy")
    assert all(origin != "graph_ready_v2_iterated_greedy" for _time, origin in starts[:3])
    assert result["repair"]["repair_evaluated_candidates"] == 0
    assert result["iterated_greedy"]["decodes"] == 1
    assert result["iterated_greedy"]["parent_origin"] == "baseline"
    assert result["best"]["summary"].failed_ops == 0
    assert tuple(result["best"]["score"]) <= tuple(result["baseline"]["score"])
