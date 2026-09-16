"""The ATC k knob is a searchable dispatch-rule parameter with one canonical token grammar.

Finding 08 of the 2026-09-14 scheduler audit: ``DispatchRule`` offered three discrete rules and
ATC hard-coded ``k = 2.0``, so the SGS start/neighborhood search had no continuous knob. The
default stays 2.0; the optimizer searches a ladder of ``atc:k=<value>`` tokens, every consumer
reports the adopted token, and malformed tokens fail loudly instead of decoding as slack.
"""

from datetime import datetime, timedelta

import pytest

from core.algorithm_contracts.dispatch_rules import (
    ATC_K_LADDER,
    DEFAULT_ATC_K,
    DispatchInputs,
    DispatchRule,
    DispatchRuleSpec,
    as_dispatch_rule_spec,
    build_dispatch_key,
    dispatch_rule_search_pool,
    parse_dispatch_rule_token,
)
from core.algorithms import GreedyScheduler, SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_proof_oracle import (
    _ContinuousCalendar,
    _default_config,
    _operation_object,
    batch_objects,
)
from tests._support.optimizer_benchmark_grading import smtwt_overdue_case
from tests._support.optimizer_benchmark_loaders import SmtwtInstance

START = datetime(2026, 1, 5, 8, 0)


def _inputs(*, due, proc_hours, avg_proc_hours=12.0, atc_k=None, op_id=1):
    # START is 08:00; a 16 h job ends at the next midnight, exactly when a due date of START.date() expires.
    extra = {} if atc_k is None else {"atc_k": atc_k}
    return DispatchInputs(
        rule=DispatchRule.ATC, priority="normal", due_date=due, est_start=START, est_end=START + timedelta(hours=proc_hours),
        proc_hours=proc_hours, avg_proc_hours=avg_proc_hours, changeover_penalty=0, batch_order=0,
        batch_id="B", seq=1, op_id=op_id, **extra,
    )


@pytest.mark.parametrize("text, rule, k, token", [
    ("slack", DispatchRule.SLACK, DEFAULT_ATC_K, "slack"),
    (" CR ", DispatchRule.CR, DEFAULT_ATC_K, "cr"),
    ("atc", DispatchRule.ATC, DEFAULT_ATC_K, "atc"),
    ("atc:k=2", DispatchRule.ATC, 2.0, "atc"),
    ("ATC:k=4", DispatchRule.ATC, 4.0, "atc:k=4.0"),
    ("atc:k=0.5", DispatchRule.ATC, 0.5, "atc:k=0.5"),
])
def test_token_grammar_round_trips_through_one_canonical_form(text, rule, k, token):
    spec = parse_dispatch_rule_token(text)
    assert spec == DispatchRuleSpec(rule, k)
    assert spec.token == token
    assert parse_dispatch_rule_token(spec.token) == spec


@pytest.mark.parametrize("text", ["", None, "edd", "slack:k=2", "cr:k=1", "atc:k=0", "atc:k=-1", "atc:k=nan",
                                  "atc:k=inf", "atc:j=1", "atc:k", "atc:", "atc:k=abc"])
def test_malformed_tokens_are_rejected_instead_of_decoding_as_slack(text):
    with pytest.raises(ValueError):
        parse_dispatch_rule_token(text)


def test_spec_validates_k_and_only_atc_takes_it():
    assert DispatchRuleSpec(DispatchRule.ATC, 8).atc_k == 8.0
    with pytest.raises(ValueError):
        DispatchRuleSpec(DispatchRule.SLACK, 3.0)
    for bad in (0, -2.0, float("nan"), float("inf"), True, "4"):
        with pytest.raises(ValueError):
            DispatchRuleSpec(DispatchRule.ATC, bad)
    with pytest.raises(ValueError):
        DispatchRuleSpec("atc")  # type: ignore[arg-type]


def test_as_spec_accepts_the_three_explicit_forms_only():
    spec = DispatchRuleSpec(DispatchRule.ATC, 4.0)
    assert as_dispatch_rule_spec(spec) is spec
    assert as_dispatch_rule_spec(DispatchRule.CR) == DispatchRuleSpec(DispatchRule.CR)
    assert as_dispatch_rule_spec("atc:k=4.0") == spec
    with pytest.raises(TypeError):
        as_dispatch_rule_spec(4.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        as_dispatch_rule_spec("edd")


def test_default_k_keeps_the_historic_key_and_larger_k_looks_further_ahead():
    # tight: 16 h job, due today -> slack 0 h; loose: 8 h job, due tomorrow -> slack 32 h.
    tight = _inputs(due=START.date(), proc_hours=16.0, op_id=1)
    loose = _inputs(due=START.date() + timedelta(days=1), proc_hours=8.0, op_id=2)
    assert build_dispatch_key(tight) == build_dispatch_key(_inputs(due=START.date(), proc_hours=16.0, atc_k=2.0, op_id=1))
    # k = 2: the zero-slack job wins; k = 16: the shorter job with plenty of slack wins.
    assert build_dispatch_key(tight) < build_dispatch_key(loose)
    tight16 = _inputs(due=START.date(), proc_hours=16.0, atc_k=16.0, op_id=1)
    loose16 = _inputs(due=START.date() + timedelta(days=1), proc_hours=8.0, atc_k=16.0, op_id=2)
    assert build_dispatch_key(loose16) < build_dispatch_key(tight16)
    # Zero slack is independent of k; positive slack decays slower with larger k.
    assert build_dispatch_key(tight16)[0] == build_dispatch_key(tight)[0]
    assert build_dispatch_key(loose16)[0] < build_dispatch_key(loose)[0]


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_key_builder_refuses_invalid_k(bad):
    with pytest.raises(ValueError):
        build_dispatch_key(_inputs(due=START.date() + timedelta(days=1), proc_hours=8.0, atc_k=bad))


def test_search_pool_lists_registry_rules_then_the_ladder_nearest_default_first():
    pool = dispatch_rule_search_pool(("slack", "cr", "atc"))
    assert pool == ("slack", "cr", "atc", "atc:k=1.0", "atc:k=4.0", "atc:k=0.5", "atc:k=8.0", "atc:k=16.0")
    assert set(pool) == {"slack", "cr"} | {DispatchRuleSpec(DispatchRule.ATC, k).token for k in ATC_K_LADDER}
    assert dispatch_rule_search_pool(("slack", "CR", "slack")) == ("slack", "cr")
    assert dispatch_rule_search_pool(("atc:k=4.0", "atc")) == ("atc:k=4.0", "atc", "atc:k=1.0", "atc:k=0.5", "atc:k=8.0", "atc:k=16.0")
    with pytest.raises(ValueError):
        dispatch_rule_search_pool(("slack", ""))


def _decode(rule):
    # Three single-operation jobs: p = 2, 1, 1 days; due 2, 12, 12 days. With k = 2 the zero-slack
    # long job goes first; with k = 16 the short jobs win the machine and the long job is late.
    instance = SmtwtInstance(name="k-flip", processing_times=(2, 1, 1), weights=(1, 1, 1), due_dates=(2, 12, 12))
    case = smtwt_overdue_case(instance)
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, _strategy, used_params = scheduler.schedule(
        operations=[_operation_object(op) for op in case.operations], batches=batch_objects(case),
        strategy=SortStrategy.PRIORITY_FIRST, start_dt=case.start_dt, dispatch_mode="sgs", dispatch_rule=rule,
        seed_results=[], strict_mode=True,
    )
    assert summary.failed_ops == 0
    return [row.batch_id for row in sorted(results, key=lambda row: row.start_time)], used_params["dispatch_rule"]


def test_scheduler_decodes_ladder_tokens_and_reports_the_canonical_token():
    default_order, default_token = _decode("atc")
    explicit_order, explicit_token = _decode("ATC:k=2.0")
    far_order, far_token = _decode("atc:k=16")
    assert default_token == explicit_token == "atc"
    assert default_order == explicit_order
    assert far_token == "atc:k=16.0"
    assert far_order != default_order
    assert default_order[0] == "J001" and far_order[-1] == "J001"


def test_scheduler_rejects_malformed_rule_tokens_as_a_dispatch_rule_validation_error():
    with pytest.raises(ValidationError) as excinfo:
        _decode("atc:k=0")
    assert excinfo.value.field == "dispatch_rule"
