"""Archived result identity, semantic comparisons and native complete history files."""

import csv
import io
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from openpyxl import load_workbook

from tests.workbench.decision_history_support import (
    BASE,
    api,
    clone_run,
    compare_conditions,
    copy_case,
    exported_history_references,
    four_source_case,
    read,
)
from tests.workbench.plan_catalog_support import update_schedule_rows
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.run_candidate_support import compute_two_objectives, retained
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


@pytest.fixture(scope="module")
def history_template(tmp_path_factory):
    with four_source_case(tmp_path_factory.mktemp("decision-history-template")) as case:
        yield case


@pytest.fixture
def history_case(history_template, tmp_path):
    case: Any = copy_case(history_template, tmp_path)
    with case.app.app_context():
        yield case
    case.conn.close()


def test_history_event_keeps_all_metrics_but_enriches_only_its_candidate(candidate_case, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.history.metric_gate import COVERAGE_FIELDS
    from core.services.workbench.history.reading import HistoryReader
    from core.services.workbench.run.decision import decision_overview
    from core.services.workbench.run.decision_resource_engine import DecisionResources
    from core.services.workbench.run.decision_source import DecisionSource

    case = candidate_case
    run_ref, candidates = compute_two_objectives(case)
    candidate_ref = candidates[-1]
    start, end = "2026-09-09T00:00:00", "2026-09-10T00:00:00"
    with TransactionManager(case.conn).transaction():
        source = DecisionSource(CandidateStore(case.conn), run_ref, selected_candidate_ref=candidate_ref,
            range_start=start, range_end=end, resource_view="full_candidate")
        expected = decision_overview(source)
        selected = next(row for row in expected["candidates"] if row["candidate_ref"] == candidate_ref)
        calls, original = [], DecisionResources.metrics

        def metrics(engine, key):
            calls.append(key)
            return original(engine, key)

        from core.models.workbench_decision_history import normalize_history_query
        from core.services.workbench.history.metrics import project_history_metrics
        from core.services.workbench.history_entries.catalog import read_history_snapshot_context

        monkeypatch.setattr(DecisionResources, "metrics", metrics)
        reader = HistoryReader(case.conn)
        actual = reader.decision(run_ref, start, end, candidate_ref=candidate_ref)
        assert "evaluations" not in actual["candidates"][0]
        assert actual["resource_cohort"] == expected["resource_cohort"]
        actual_public = {
            key: {field: val for field, val in item.items() if field not in COVERAGE_FIELDS}
            for key, item in actual["candidates"][0]["metrics"].items()
        }
        assert actual_public == selected["metrics"]
        assert any(field in item for item in actual["candidates"][0]["metrics"].values() for field in COVERAGE_FIELDS)
        assert actual["candidates"][0]["coverage"] == selected["coverage"]
        assert calls == [candidate_ref]
        subset = reader.decision(run_ref, start, end, candidate_ref=candidate_ref, metric_keys=["makespan_hours"])
        assert "evaluations" not in subset["candidates"][0]
        assert set(subset["candidates"][0]["metrics"]) == {"makespan_hours"}
        _, _, anchors = read_history_snapshot_context(case.conn, normalize_history_query(), ["run:" + run_ref])
        descriptor = anchors["run:" + run_ref]
        all_keys = [row["key"] for row in expected["metric_definitions"]]
        projected = project_history_metrics(
            reader, descriptor, {"metric_keys": all_keys, "range_start": start, "range_end": end}
        )
        assert {key: item["member_unit"] for key, item in projected["metrics"].items()} == {
            key: item["member_unit"] for key, item in selected["metrics"].items()
        }


def test_capture_admits_the_stored_run_input_and_rejects_a_tampered_one(history_case):
    import json

    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.shared.refs import new_ref
    from core.shared.strict_json import canonical_json

    case = history_case
    stored = dict(case.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (case.history_refs["run_ref"],)).fetchone())
    accepted = json.loads(stored["normalized_input_json"])
    assert CandidateStore(case.conn).capture(stored["run_ref"])["input"] == accepted
    # 排产记录存下的输入按受理时同一套规则读入：缺必需项、多出项、值不合规都是存档损坏，读取失败，不当作“未记录”。
    tampered = {
        "missing": {key: value for key, value in accepted.items() if key != "material_strategy"},
        "extra": {**accepted, "polluted": True},
        "invalid": {**accepted, "completed_policy": "discard_actuals"},
    }
    for name, value in tampered.items():
        row = dict(stored, run_ref=new_ref(), request_key=new_ref(), input_ref="tampered-" + name,
                   normalized_input_json=canonical_json(value))
        case.conn.execute("INSERT INTO WorkbenchRunJobs(" + ",".join(row) + ") VALUES (" + ",".join("?" for _ in row) + ")",
                          tuple(row.values()))
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            CandidateStore(case.conn).capture(row["run_ref"])
        assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500), name
    case.conn.rollback()


def test_saved_trial_frozen_members_are_the_arrangements_its_hold_window_kept(trial_case, monkeypatch):
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.models.workbench_trial_codec import dump, load_object
    from core.models.workbench_trial_scenario_archive import scenario_snapshot
    from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
    from core.services.workbench.facts.trial_scenario_archive import load_verified_scenario
    from core.services.workbench.history_entries.conditions import production_conditions
    from core.services.workbench.history_entries.conditions_source import ConditionSource
    from core.services.workbench.history_entries.packets import TrialPacket
    from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
    from tests.workbench.plan_catalog_support import insert_schedule_rows
    from tests.workbench.trial_support import create, official
    from tests.workbench.trial_support import service as trial_service

    case = trial_case
    # 来源计划按交付设置带两天不重排时段，两道原安排都落在时段里，试调原样保留它们。
    point = case.operation(seq=2, setup_hours=0, unit_hours=0)
    case.config(freeze_window_enabled="yes", freeze_window_days=2)
    intent = official(case)
    insert_schedule_rows(case.conn, 1, [{"op_id": point, "machine_id": "M1", "operator_id": "O1",
                                         "start_time": "2026-09-09T11:00:00", "end_time": "2026-09-09T11:00:00"}])
    case.conn.commit()
    draft = trial_service(case.conn).get(create(case, intent)["draft_ref"])
    frozen = {task["operation_ref"] for task in draft["tasks"]
              if [reason["code"] for reason in task["edit_context"]["blocked_reasons"]] == ["task_frozen"]}
    assert len(frozen) == 2
    saved = trial_service(case.conn).save(draft["draft_ref"], {"name": "保留时段"}, draft["write_context"]["write_token"],
                                          "trial-save-frozen-0001")["data"]
    # 保存后每行都只读，冻结成员另记在保存记录里，不靠行的编辑状态推断。
    assert all(task["edit_context"]["blocked_reasons"][0]["code"] == "scenario_readonly" for task in saved["tasks"])
    case.conn.execute("BEGIN")
    with candidate_read_snapshot(case.conn):
        scenario = load_verified_scenario(case.conn, saved["scenario_ref"])
        repo = WorkbenchTrialRepository(case.conn)
        archive = load_object(repo.scenario_header(saved["scenario_ref"])["snapshot_json"])
        columns = {row["row_ref"]: row for row in repo.iter_scenario_rows(saved["scenario_ref"])}
        stored = {ref: load_object(row["payload_json"]) for ref, row in columns.items()}
    case.conn.rollback()
    packet = TrialPacket(saved["scenario_ref"], "scenario:" + saved["scenario_ref"], scenario.saved, scenario.head,
                         scenario.rows, scenario.origin)
    projection = production_conditions(ConditionSource(packet))[0]
    assert {entity for category, entity, field in projection.rows if category == "freeze" and field == "frozen_member"} == frozen
    known, path, origin, _reason = projection.families["frozen_members"]
    assert known is True and projection.source.source(path, origin)["path"] == "saved.frozen_operation_refs"
    # 冻结清单的形状（不重复的工序引用）在存档读取边界准入。
    assert sorted(archive["snapshot"]["frozen_operation_refs"]) == sorted(frozen)
    tampered = dict(archive, snapshot=dict(archive["snapshot"], frozen_operation_refs=sorted(frozen)[:1] * 2))
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        scenario_snapshot(tampered, stored, columns)
    assert rejected.value.code == "trial_snapshot_invalid"
    # 它是不是本方案的工序，在任务绑回来源草稿行之后按真实身份核对：清单不是真实工序的子集就拒收。
    # 存档列由触发器锁定，这里在仓储读出处换成损坏的存储文本。
    real_header = WorkbenchTrialRepository.scenario_header

    def forged_header(repo_self, ref):
        value = real_header(repo_self, ref)
        forged = load_object(value["snapshot_json"])
        forged["snapshot"]["frozen_operation_refs"] = ["f" * 48]
        return dict(value, snapshot_json=dump(forged))

    monkeypatch.setattr(WorkbenchTrialRepository, "scenario_header", forged_header)
    case.conn.execute("BEGIN")
    with candidate_read_snapshot(case.conn), pytest.raises(WorkbenchCommandRejected) as rejected:
        load_verified_scenario(case.conn, saved["scenario_ref"])
    case.conn.rollback()
    assert (rejected.value.code, rejected.value.status) == ("trial_snapshot_invalid", 409)


def test_three_saved_sources_preserve_events_and_result_identity_on_two_timelines(history_case):
    from core.models.workbench_run_receipt import FailedReceipt
    from core.services.workbench.facts.decision_read_models import decode_model
    from core.services.workbench.run.terminal import record_terminal_without_results
    from core.shared.refs import new_ref
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    case, refs = history_case, history_case.history_refs
    queued = case.accept(key="history-queued-run-0001")["run_ref"]
    failed = case.accept(key="history-failed-run-0001")["run_ref"]
    repo = WorkbenchRunRepository(case.conn)
    repo.claim(failed, new_ref(), "2026-09-10T12:00:01")
    case.conn.commit()
    client, statements = api(case)
    with retained(case.conn):
        running_view = read(client, timeline="run", state="running")["data"]
        assert running_view["totals"] == {"run": 3, "official": 3, "filtered": 1}
        assert len(running_view["entries"]) == 1
        assert running_view["entries"][0]["identity"]["run_ref"] == failed
        assert running_view["entries"][0]["state"] == "running"
        assert running_view["entries"][0]["times"]["started_at"] == "2026-09-10T12:00:01"
    failure = FailedReceipt("failed", {"code": "fixture_saved_failure", "message": "Saved worker failure"}, None)
    admission = decode_model(repo.admission_read_model(failed, ("decision",)), ("decision",))["decision"]
    record_terminal_without_results(case.conn, repo.head(failed), admission, failure, "2026-09-10T12:00:02")
    case.conn.commit()
    statements.clear()
    with retained(case.conn):
        runs = read(
            client,
            timeline="run",
            state="complete",
            metric_keys=[
                "overdue_count",
                "total_tardiness_hours",
                "makespan_hours",
                "elapsed_seconds",
                "changed_operation_count",
                "machine_change_count",
            ],
        )["data"]
        official = read(client, timeline="official", order="asc")["data"]
        assert runs["totals"] == {"run": 3, "official": 3, "filtered": 1}
        assert official["totals"] == {"run": 3, "official": 3, "filtered": 3}
        assert len(runs["entries"]) == 1 and runs["entries"][0]["identity"]["run_ref"] == refs["run_ref"]
        assert runs["entries"][0]["identity"]["candidate_ref"] == refs["candidate_ref"]
        assert runs["entries"][0]["metrics"]["changed_operation_count"]["value"] == 0
        assert runs["entries"][0]["metrics"]["machine_change_count"]["value"] == 0
        by_ref = {row["entry_ref"]: row for row in official["entries"]}
        for prefix in ("candidate", "second_candidate"):
            event = by_ref["adoption:" + refs[prefix + "_receipt_ref"]]
            assert event["source_kind"] == "candidate_adoption"
            assert event["identity"]["run_ref"] == refs["run_ref"]
            assert event["identity"]["candidate_ref"] == refs["candidate_ref"]
            assert event["identity"]["plan_ref"] == refs[prefix + "_plan_ref"]
            assert event["identity"]["plan_version"] == refs[prefix + "_version"]
        trial = by_ref["adoption:" + refs["trial_receipt_ref"]]
        assert trial["source_kind"] == "trial_adoption"
        assert trial["identity"]["scenario_ref"] == refs["scenario_ref"]
        assert trial["identity"]["draft_ref"] == refs["draft_ref"]
        assert trial["identity"]["run_ref"] is None and trial["identity"]["candidate_ref"] is None
        assert trial["identity"]["plan_ref"] == refs["trial_plan_ref"]
        trial_gantt = next(row for row in trial["navigation"] if row["view"] == "gantt")
        assert trial_gantt["enabled"] and trial_gantt["context"] == {"plan_ref": refs["trial_plan_ref"]}
        unfinished = read(client, timeline="run", state="queued", selected_entry_ref="run:" + queued)["data"]["selection"]["entry"]
        assert unfinished["identity"]["run_ref"] == queued and unfinished["source"]["state"] == "unavailable"
        run_link = next(row for row in unfinished["navigation"] if row["view"] == "run")
        assert run_link["enabled"] and run_link["context"] == {"run_ref": queued}
        for state, ref in (("queued", queued), ("failed", failed)):
            entry = read(client, timeline="run", state=state, selected_entry_ref="run:" + ref,
                metric_keys=["expected_operation_count", "scheduled_operation_count", "machine_available_hours"])["data"]["selection"]["entry"]
            expected = entry["metrics"]["expected_operation_count"]
            assert expected["value"] == entry["scope"]["operation_count"] == 1
            assert expected["state"] == "complete" and expected["unknown_count"] == 0
            assert expected["member_unit"] == "operation"
            assert not {"covered_batch_refs", "covered_operation_refs", "covered_resource_refs"}.intersection(expected)
            assert "batch_refs" not in entry["scope"] and "operation_refs" not in entry["scope"]
            assert entry["scope"]["batch_quantity"]["member_unit"] == "batch"
            assert "covered_batch_refs" not in entry["scope"]["batch_quantity"]
            assert entry["reading_context"]["resource_window"]["cohort"] == {"machine_count": None, "operator_count": None}
            assert entry["metrics"]["scheduled_operation_count"]["value"] is None
            assert entry["metrics"]["scheduled_operation_count"]["member_unit"] == "record"
            assert entry["metrics"]["machine_available_hours"]["value"] is None
            assert entry["metrics"]["machine_available_hours"]["member_unit"] == "record"
        assert set(by_ref) == {"adoption:" + refs[key] for key in ("candidate_receipt_ref", "second_candidate_receipt_ref", "trial_receipt_ref")}
        for row in runs["entries"] + official["entries"]:
            assert set(row["times"]) == {"accepted_at", "started_at", "finished_at", "adopted_at", "committed_at_utc", "schedule_time"}
        assert client.get(BASE, query_string={"timeline": "invalid"}).status_code == 422
    assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")) for sql in statements)


def test_saved_production_conditions_and_metric_gates_keep_algorithm_experiments_separate(history_case, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.models.workbench_decision_history import normalize_history_query
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
    from core.services.workbench.history.metric_gate import gate_history_metric
    from core.services.workbench.history.projection import missing_packet
    from core.services.workbench.history.reading import HistoryReader
    from core.services.workbench.history_entries import conditions as condition_module
    from core.services.workbench.history_entries.catalog import read_history_snapshot_context
    from core.services.workbench.history_entries.conditions import (
        _compare,
        _materials,
        _Projection,
        analyze_prepared_history_conditions,
        extract_entry_condition_digests,
        materialize_history_conditions,
    )
    from core.services.workbench.history_entries.conditions_source import ConditionSource
    from core.services.workbench.history_entries.metric_window import history_window
    from core.services.workbench.history_entries.packets import UnavailablePacket

    case, refs = history_case, history_case.history_refs
    experiment, _ = clone_run(case, "2026-09-11T12:00:00", change_artifact=lambda value: value.update(time_budget_seconds=30))
    changed, _ = clone_run(case, "2026-09-12T12:00:00", change_input=lambda value: value.update(ready_check=False))
    for day in range(13, 25):
        clone_run(case, "2026-09-" + str(day) + "T12:00:00")
    client, _ = api(case)
    query = {"comparison": "same_conditions", "reference_run_ref": refs["run_ref"],
             "selected_entry_ref": "run:" + experiment, "metric_keys": ["overdue_count", "makespan_hours"]}
    with retained(case.conn):
        reference_only = read(client, comparison="same_conditions", reference_run_ref=refs["run_ref"],
                              metric_keys=query["metric_keys"])["data"]
        assert reference_only["selection"]["entry"] is None
        assert reference_only["selection"]["reference"]["identity"]["run_ref"] == refs["run_ref"]
        assert reference_only["entries"] and reference_only["comparison"]["conditions"]["state"] == "unknown"
        assert all(row["state"] == "unavailable" and row["value"] is None
                   for row in reference_only["comparison"]["metric_deltas"].values())
        counts = {key: Counter() for key in ("source", "production", "experiments")}
        calendar_calls = Counter()
        source_init, production, experiments = ConditionSource.__init__, condition_module.production_conditions, condition_module._experiments
        calendar = condition_module._calendar

        def count_source(self, packet):
            counts["source"][(packet.kind, packet.ref, packet.entry_ref)] += 1
            return source_init(self, packet)

        def count_production(source):
            counts["production"][(source.kind, source.ref)] += 1
            return production(source)

        def count_calendar(projection, resources, known, window):
            source = projection.source
            calendar_calls[(source.kind, source.ref, window["start"], window["end"])] += 1
            return calendar(projection, resources, known, window)

        def count_experiments(source, packet):
            counts["experiments"][(source.kind, source.ref)] += 1
            return experiments(source, packet)

        with monkeypatch.context() as checks:
            checks.setattr(ConditionSource, "__init__", count_source)
            checks.setattr(condition_module, "production_conditions", count_production)
            checks.setattr(condition_module, "_calendar", count_calendar)
            checks.setattr(condition_module, "_experiments", count_experiments)
            equal_payload = read(client, **query)
            equal = equal_payload["data"]
            assert len(equal["trend"]["points"]) == 15
            points_by_ref = {pt["entry_ref"]: pt for pt in equal["trend"]["points"]}
            assert points_by_ref["run:" + changed]["condition_state"] == "different"
            assert all(
                pt["condition_state"] == "equal"
                for ref_key, pt in points_by_ref.items()
                if ref_key != "run:" + changed
            )
            # Default 7d window uses precomputed digests in O(1); only the 2 selected pair entries load ConditionSource.
            assert sum(counts["source"].values()) == sum(counts["production"].values()) == sum(counts["experiments"].values()) == 2
            assert sum(calendar_calls.values()) == 2
            assert set(counts["source"]) == {
                ("run", refs["run_ref"], "run:" + refs["run_ref"]),
                ("run", experiment, "run:" + experiment),
            }
            next_request = read(client, **query)["data"]
            assert next_request == equal
            assert sum(counts["source"].values()) == sum(counts["production"].values()) == sum(counts["experiments"].values()) == 4
            for values in counts.values():
                values.clear()
            calendar_calls.clear()
            custom_window = read(client, **dict(query, resource_window_days=14))["data"]
            custom_points = {pt["entry_ref"]: pt for pt in custom_window["trend"]["points"]}
            assert custom_points["run:" + changed]["condition_state"] == "different"
            # Static digest inequality short-circuits custom-window ConditionSource/calendar loading for `changed`.
            assert ("run", changed, "run:" + changed) not in counts["source"]
            assert sum(counts["source"].values()) == 14
            for values in counts.values():
                values.clear()
            calendar_calls.clear()
            cfg_csv = client.get(
                BASE + "/export",
                query_string=dict(
                    query,
                    metric_keys=",".join(query["metric_keys"]),
                    snapshot_ref=equal_payload["meta"]["snapshot_ref"],
                    format="csv",
                    section="configurations",
                ),
            )
            assert cfg_csv.status_code == 200, cfg_csv.get_data(as_text=True)
            assert sum(counts["production"].values()) == 0 and sum(calendar_calls.values()) == 0
            assert sum(counts["source"].values()) == sum(counts["experiments"].values()) == 2
            cfg_rows = list(csv.reader(io.StringIO(cfg_csv.data.decode("utf-8-sig"))))
            cfg_header, cfg_body = cfg_rows[0], cfg_rows[1:]
            assert len(cfg_body) == len(equal["comparison"]["configurations"]["rows"])
            field_idx, state_idx = cfg_header.index("字段"), cfg_header.index("对照状态")
            assert [(row[field_idx], row[state_idx]) for row in cfg_body] == [
                (row["field"], row["state"]) for row in equal["comparison"]["configurations"]["rows"]
            ]
        assert equal["comparison"]["conditions"]["state"] == "equal"
        assert equal["comparison"]["configurations"]["state"] == "different"
        # 算法实验设置：原保存的排产配置、本次优化策略和预算、实际所选方案的参数与策略参数。
        settings_rows = equal["comparison"]["configurations"]["rows"]
        assert {row["entity"]["key"] for row in settings_rows} == {"archived_settings", "run_options", "chosen", "used_params"}
        assert {row["field"] for row in settings_rows if row["entity"]["key"] == "run_options"} == {
            "primary_objective", "target_objectives", "time_budget_seconds"}
        assert {row["field"] for row in settings_rows if row["entity"]["key"] == "chosen"} == {
            "algo_mode", "objective_name", "time_budget_seconds", "sort_strategy", "dispatch_mode"}
        assert equal["comparison"]["objective"]["state"] == "equal"
        assert equal["selection"]["reference"]["identity"]["run_ref"] == refs["run_ref"]
        delta = equal["comparison"]["metric_deltas"]["overdue_count"]
        assert delta["state"] == "comparable" and delta["value"] == 0 and delta["direction"] == "equal"
        different = read(client, **dict(query, selected_entry_ref="run:" + changed))["data"]
        assert different["comparison"]["conditions"]["state"] == "different"
        assert different["comparison"]["conditions"]["summary"]["different"] > 0
        states = [row["state"] for row in different["comparison"]["conditions"]["rows"]]
        assert states[0] == "different"
        assert states == sorted(states, key={"different": 0, "unknown": 1, "equal": 2}.__getitem__)
        assert different["comparison"]["conclusion"]["state"] == "different_conditions"
        from core.services.workbench.history.queries import read_history_all

        assert equal["selection"]["reference"]["metrics"]["makespan_hours"]["member_unit"] == "record"
        assert "covered_operation_refs" not in equal["selection"]["reference"]["metrics"]["makespan_hours"]
        assert equal["selection"]["reference"]["metrics"]["overdue_count"]["member_unit"] == "batch"
        assert "covered_batch_refs" not in equal["selection"]["reference"]["metrics"]["overdue_count"]
        internal_equal, _, _ = read_history_all(case.conn, query)
        before = internal_equal["selection"]["reference"]["metrics"]["makespan_hours"]
        after = internal_equal["selection"]["entry"]["metrics"]["makespan_hours"]
        definition = next(row for row in equal["metric_definitions"] if row["key"] == "makespan_hours")
        for field, value, state in (("metric_version", "another-saved-version", "different_version"),
                                   ("unit", "another-saved-unit", "different_version"),
                                   ("scope", "another-saved-scope", "different_coverage"),
                                   ("covered_operation_refs", ["e" * 48], "different_coverage")):
            altered = deepcopy(after)
            altered[field] = value
            gated = gate_history_metric(definition, before, altered, production_state="equal", objective_state="equal")
            assert gated["state"] == state and gated["value"] is None
        assert len(before["covered_operation_refs"]) == len(after["covered_operation_refs"]) == 1
        objective = gate_history_metric(definition, before, after, production_state="equal", objective_state="different")
        assert objective["state"] == "different_objective" and objective["value"] is None
        with TransactionManager(case.conn).transaction(), candidate_read_snapshot(case.conn):
            _, _, anchors = read_history_snapshot_context(
                case.conn, normalize_history_query(), ["run:" + refs["run_ref"]]
            )
            packet = HistoryReader(case.conn).read(anchors["run:" + refs["run_ref"]])
        window = {"start": "2026-09-09T08:00:00", "end": "2026-09-09T16:00:00"}
        for values in counts.values():
            values.clear()
        calendar_calls.clear()
        with monkeypatch.context() as checks, TransactionManager(case.conn).transaction():
            checks.setattr(ConditionSource, "__init__", count_source)
            checks.setattr(condition_module, "production_conditions", count_production)
            checks.setattr(condition_module, "_calendar", count_calendar)
            checks.setattr(condition_module, "_experiments", count_experiments)
            reader = HistoryReader(case.conn)
            source = reader.condition_source(packet)
            assert not counts["production"] and not calendar_calls
            side = reader.condition_side(packet, window)
            alias = replace(packet, entry_ref="adoption:same-source")
            assert reader.condition_source(alias) is source
            assert reader.condition_side(alias, dict(window, cohort={"machine_refs": []})) is side
            saved_rows, saved_families = deepcopy(side["conditions"].rows), deepcopy(side["conditions"].families)
            before_side, after_side, cond_analysis, _, _ = analyze_prepared_history_conditions(side, side)
            materialize_history_conditions(before_side, after_side, cond_analysis)
            assert side["conditions"].rows == saved_rows and side["conditions"].families == saved_families
            other_window = dict(window, end="2026-09-10T16:00:00")
            other_side = reader.condition_side(packet, other_window)
            assert other_side is not side and other_side["configurations"] is side["configurations"]
            assert sum(counts["source"].values()) == sum(counts["experiments"].values()) == sum(counts["production"].values()) == 1
            assert sum(calendar_calls.values()) == 2 and set(calendar_calls.values()) == {1}
            assert side["conditions"].rows == saved_rows and side["conditions"].families == saved_families
            assert any(key[0] == "calendar_downtime" and "2026-09-10" in key[1] for key in other_side["conditions"].rows)
            assert not any(key[0] == "calendar_downtime" and "2026-09-10" in key[1] for key in side["conditions"].rows)
            without_result = replace(packet, candidate=None, raw_tasks=None, entry_ref="run:without-result")
            assert reader.condition_source(without_result) is not source
            issue = {"code": "audit_missing", "message": "Saved adoption audit gap"}
            issues = []
            for suffix in ("1", "2"):
                unavailable = UnavailablePacket(packet.kind, packet.ref, "adoption:audit_missing_" + suffix, issue)
                isolated = reader.condition_source(unavailable)
                assert isolated is not source and not isolated.available and isolated.issue == issue
                issues.append(isolated)
            assert issues[0] is not issues[1]
            assert reader.condition_source(missing_packet()) is not reader.condition_source(
                missing_packet("selection_required", "请选择实际历史条目。"))
        for source, expected_state in (("internal", "unknown"), ("external", "equal")):
            hours = deepcopy(packet)
            operation = next(iter(hours.facts.tables["BatchOperations"].values()))
            if source == "external":
                # 改成外协时触发器记下外协背景，存档随所选工序带上它。
                ext_cols = hours.capture["facts"]["columns"]["BatchExternalContexts"]
                batch_row = hours.facts.tables["Batches"][operation["batch_id"]]
                ext_row = dict.fromkeys(ext_cols)
                ext_row.update(
                    operation_id=operation["id"],
                    part_no=batch_row["part_no"],
                    sequence=operation["seq"],
                    origin="creation",
                    captured_at="2026-09-09T08:00:00",
                )
                hours.capture["facts"]["tables"]["BatchExternalContexts"] = [
                    [ext_row[col] for col in ext_cols]
                ]
                hours = replace(hours, facts=GenerationFacts(hours.capture))
                operation = hours.facts.tables["BatchOperations"][operation["id"]]
            operation.update(source=source, setup_hours=None, unit_hours=None, ext_days=2)
            compared = compare_conditions(hours, hours, window)
            rows = [row for row in compared["conditions"]["rows"] if row["category"] == "requirements"
                    and row["field"] in ("setup_hours", "unit_hours")]
            assert len(rows) == 2 and all(row["state"] == expected_state for row in rows)
            # 历史目录落库的摘要：静态条件任何一项未知就不给摘要，趋势比较改走完整条件对照。
            _, static_digest, calendar_digest = extract_entry_condition_digests(
                hours, history_window(hours, normalize_history_query())
            )
            if source == "internal":
                assert static_digest is None
            else:
                # 外协按保存的周期安排，没有厂内标准工时：两项已知为空，摘要照常给出。
                assert static_digest is not None and calendar_digest is not None
                assert all(row["before"]["state"] == "known" and row["before"]["value"] is None for row in rows)
        saved_selection = packet.receipt.selection
        primary = saved_selection["primary_objective"]
        saved_objective = compare_conditions(packet, packet, window)["objective"]["before"]
        assert saved_objective["source"]["path"] == "receipt.selection"
        assert saved_objective["value"] == {"name": primary, "field_order": saved_selection["objective_field_order"][primary]}
        # 物料齐套规则提交时可省，规范后的排产输入总带上，存下的排产记录也就总有这一项。
        assert packet.capture["input"]["material_strategy"] == "strict"
        metadata_capture = deepcopy(packet.capture)
        metadata_capture.pop("run_ref", None)
        facts = metadata_capture["facts"]
        for name in ("Batches", "BatchOperations", "SchemaVersion", "ScheduleConfig"):
            columns = facts["columns"][name]
            for row in facts["tables"][name]:
                for field in ("created_at", "updated_at"):
                    if field in columns:
                        row[columns.index(field)] = "2026-09-12T23:59:59"
                if name == "SchemaVersion":
                    row[columns.index("version")] += 1
                if name == "ScheduleConfig" and row[columns.index("config_key")] == "graph_critical_weight":
                    row[columns.index("config_value")] = "700"
        metadata = replace(packet, capture=metadata_capture, facts=GenerationFacts(metadata_capture),
                           ref="7" * 48, entry_ref="run:" + "7" * 48)
        compared = compare_conditions(packet, metadata, window)
        assert compared["conditions"]["state"] == "equal"
        assert compared["configurations"]["state"] == "different"
        mapping = {packet.capture["input"]["batch_refs"][0]: "e" * 48,
                   packet.raw_tasks[0]["operation_ref"]: "f" * 48}

        def replace_members(value: Any) -> Any:
            if isinstance(value, dict):
                return {mapping.get(key, key): replace_members(item) for key, item in value.items()}
            if isinstance(value, list):
                return [replace_members(item) for item in value]
            return mapping.get(value, value) if isinstance(value, str) else value

        members_capture = replace_members(deepcopy(packet.capture))
        members_capture.pop("run_ref", None)
        members = replace(packet, capture=members_capture, facts=GenerationFacts(members_capture),
                          candidate=replace_members(deepcopy(packet.candidate)),
                          raw_tasks=replace_members(deepcopy(packet.raw_tasks)))
        compared = compare_conditions(packet, members, window)
        assert compared["conditions"]["state"] == "different"
        scope = [row for row in compared["conditions"]["rows"] if row["category"] == "scope"]
        for field in ("batch_member", "operation_member"):
            previous = {row["entity"]["key"] for row in scope if row["field"] == field and row["before"]["value"] is True}
            current = {row["entity"]["key"] for row in scope if row["field"] == field and row["after"]["value"] is True}
            assert len(previous) == len(current) == 1 and previous != current
        arrival_tables = {"BatchMaterials": [{"id": 1, "batch_id": "B0", "material_id": "M0",
            "required_qty": 1, "available_qty": 1, "ready_status": "yes"}],
            "BatchMaterialReviews": [], "BatchMaterialStages": [], "Suppliers": [],
            "BatchMaterialArrivals": [{"requirement_id": 1, "arrival_date": "2026-09-10", "quantity": quantity}
                                     for quantity in (0.1, 0.2, 0.3)]}
        stub: Any = SimpleNamespace(table=lambda name: arrival_tables.get(name), original_table=lambda name: [],
            entity_refs={("material", "M0"): "a" * 48},
            source=lambda path, origin="environment": {"kind": "run", "ref": refs["run_ref"], "path": path})
        original, reversed_rows = _Projection(stub), _Projection(stub)
        _materials(original, {"c" * 48: {"batch_id": "B0"}}, {})
        arrival_tables["BatchMaterialArrivals"].reverse()
        _materials(reversed_rows, {"c" * 48: {"batch_id": "B0"}}, {})
        arrivals = _compare(original, reversed_rows, (("materials_outsource", "物料与外协"),))
        quantity = next(row for row in arrivals["rows"] if row["field"] == "quantity")
        assert quantity["before"]["value"] == quantity["after"]["value"] == 0.6
        assert arrivals["state"] == "equal"

        machine_ref = next(ref for (kind, _key), ref in packet.facts.entity_refs.items() if kind == "machine")
        operator_ref = next(ref for (kind, _key), ref in packet.facts.entity_refs.items() if kind == "operator")

        def packet_with_reports(report_specs, suffix):
            capture = deepcopy(packet.capture)
            specs = [(0, item) if not isinstance(item, tuple) else item for item in report_specs]
            completed_total = sum(int(qty) for qty, _hours in specs)
            target_qty = capture["execution"][0]["target_quantity"]
            capture["execution"][0].update(
                execution_state="partial",
                known_completed_quantity=completed_total,
                remaining_quantity=target_qty - completed_total,
                reports=[
                    {
                        "actual_start": "2026-09-09T08:00:00",
                        "actual_end": "2026-09-09T12:00:00",
                        "actual_machine_ref": machine_ref,
                        "actual_operator_ref": operator_ref,
                        "completed_quantity": qty,
                        "effective_processing_hours": hours,
                    }
                    for qty, hours in specs
                ],
            )
            return replace(packet, capture=capture, facts=GenerationFacts(capture),
                           ref=suffix * 48, entry_ref="run:" + suffix * 48)

        reordered = compare_conditions(packet_with_reports([1.0, 2.0], "8"), packet_with_reports([2.0, 1.0], "9"), window)
        assert reordered["conditions"]["state"] == "equal"
        hour_rows = [row for row in reordered["conditions"]["rows"] if row["field"] == "effective_processing_hours"]
        assert [(row["state"], row["before"]["value"], row["before"]["source"]["path"], row["after"]["source"]["path"])
                for row in hour_rows] == [
            ("equal", 1.0, "capture.execution[0].reports[0].effective_processing_hours",
             "capture.execution[0].reports[1].effective_processing_hours"),
            ("equal", 2.0, "capture.execution[0].reports[1].effective_processing_hours",
             "capture.execution[0].reports[0].effective_processing_hours"),
        ]

        numeric_equiv = compare_conditions(
            packet_with_reports([(1, 1.0), (1, 2.0)], "4"),
            packet_with_reports([(1.0, 2.0), (1, 1.0)], "5"),
            window,
        )
        assert numeric_equiv["conditions"]["state"] == "equal"
        numeric_equiv_flipped = compare_conditions(
            packet_with_reports([(1, 1.0), (1, 2.0)], "4"),
            packet_with_reports([(1, 2.0), (1.0, 1.0)], "6"),
            window,
        )
        assert numeric_equiv_flipped["conditions"]["state"] == "equal"

        changed_hours = compare_conditions(packet_with_reports([1.0, 2.0], "8"), packet_with_reports([1.0, 3.0], "a"), window)
        assert changed_hours["conditions"]["state"] == "different"
        diff_rows = [row for row in changed_hours["conditions"]["rows"] if row["state"] == "different"]
        assert len(diff_rows) == 1 and diff_rows[0]["field"] == "effective_processing_hours"
        assert diff_rows[0]["before"]["value"] == 2.0 and diff_rows[0]["after"]["value"] == 3.0
        assert diff_rows[0]["before"]["source"]["path"] == "capture.execution[0].reports[1].effective_processing_hours"
        assert diff_rows[0]["after"]["source"]["path"] == "capture.execution[0].reports[1].effective_processing_hours"

        changed_multiplicity = compare_conditions(packet_with_reports([1.0, 1.0], "b"), packet_with_reports([1.0], "c"), window)
        assert changed_multiplicity["conditions"]["state"] == "different"
        extra_rows = [row for row in changed_multiplicity["conditions"]["rows"] if row["state"] == "different"]
        assert len(extra_rows) == 6
        assert all(row["before"]["present"] is True and row["after"]["present"] is False for row in extra_rows)
        assert all(row["before"]["source"]["path"] == f"capture.execution[0].reports[1].{row['field']}" for row in extra_rows)


def test_shared_resource_window_uses_saved_capacity_and_keeps_missing_capacity_unknown(history_case):
    from core.services.workbench.facts.production_capture import table_rows
    from core.services.workbench.facts.trial_origin import TrialOrigin
    from core.services.workbench.facts.trial_scenario_archive import load_verified_scenario
    from core.services.workbench.history.metrics import _metric, _path, _trial, metric_definitions
    from core.services.workbench.history_entries.conditions_source import ConditionSource
    from core.services.workbench.history_entries.packets import TrialPacket
    from core.services.workbench.trial.constraints import build_archived_trial_intervals
    from core.services.workbench.trial.projection import comparison as trial_comparison
    from core.services.workbench.trial.projection import scenario_tasks
    from tests.workbench.trial_support import change, create
    from tests.workbench.trial_support import service as trial_service

    case, refs = history_case, history_case.history_refs
    period_index = [row[1] for row in case.conn.execute("PRAGMA table_info(WorkbenchCalendarDefaults)")].index("periods_json")

    def half_shift(facts):
        row = facts["tables"]["WorkbenchCalendarDefaults"][0]
        if isinstance(row, dict):
            row["periods_json"] = '[{"start":"08:00","end":"12:00","day_offset":0}]'
        else:
            row[period_index] = '[{"start":"08:00","end":"12:00","day_offset":0}]'

    changed, _ = clone_run(case, "2026-09-11T12:00:00", change_facts=half_shift)
    client, _ = api(case)
    query = {"reference_run_ref": refs["run_ref"], "selected_entry_ref": "run:" + changed,
             "comparison": "same_conditions", "range_start": "2026-09-09T08:00:00", "range_end": "2026-09-09T16:00:00",
             "metric_keys": ["machine_available_hours", "machine_occupied_hours", "machine_utilization_ratio",
                             "operator_available_hours", "operator_occupied_hours", "operator_utilization_ratio", "makespan_hours"]}
    with retained(case.conn):
        data = read(client, **query)["data"]
        before, after = data["selection"]["reference"], data["selection"]["entry"]
        assert data["resource_window"]["mode"] == "absolute" and data["resource_window"]["boundary"] == "half_open"
        for entry in (before, after):
            window = entry["reading_context"]["resource_window"]
            assert window["start"] == query["range_start"] and window["end"] == query["range_end"]
            assert window["time_basis"] == "factory_local"
        assert before["reading_context"]["resource_window"]["cohort"] == after["reading_context"]["resource_window"]["cohort"]
        assert set(before["reading_context"]["resource_window"]["cohort"]) == {"machine_count", "operator_count"}
        for kind in ("machine", "operator"):
            count = before["reading_context"]["resource_window"]["cohort"][kind + "_count"]
            assert count > 0
            for entry, hours in ((before, 8), (after, 4)):
                metrics = entry["metrics"]
                assert metrics[kind + "_available_hours"]["member_unit"] == kind
                assert "covered_resource_refs" not in metrics[kind + "_available_hours"]
                assert metrics[kind + "_available_hours"]["value"] == count * hours
                assert metrics[kind + "_occupied_hours"]["value"] == 3
                ratio = metrics[kind + "_utilization_ratio"]
                assert ratio["numerator_hours"] == 3 and ratio["denominator_hours"] == count * hours
                assert ratio["value"] == pytest.approx(3 / (count * hours))
        assert data["comparison"]["conditions"]["state"] == "different"
        assert any(point["range_changed"] for point in data["trend"]["points"])
        assert all(
            set(point["resource_window"]["cohort"]) == {"machine_count", "operator_count"}
            and "batch_refs" not in point["scope"] and "operation_refs" not in point["scope"]
            for point in data["trend"]["points"]
        )
        trial = read(client, **dict(query, timeline="official", selected_entry_ref="adoption:" + refs["trial_receipt_ref"]))["data"]["selection"]["entry"]
        assert trial["metrics"]["makespan_hours"]["value"] == 3
        assert trial["metrics"]["makespan_hours"]["member_unit"] == "record"
        for kind in ("machine", "operator"):
            count = trial["reading_context"]["resource_window"]["cohort"][kind + "_count"]
            ratio = trial["metrics"][kind + "_utilization_ratio"]
            assert ratio["member_unit"] == kind and "covered_resource_refs" not in ratio
            assert ratio["numerator_hours"] == 3 and ratio["denominator_hours"] == count * 4
            assert ratio["value"] == pytest.approx(3 / (count * 4))
            assert ratio["source"]["path"].startswith("head.admission.facts")

    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Drilling')")
    for machine in ("M1", "M2"):
        case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,'T2')", (machine,))
    case.conn.execute("UPDATE BatchOperations SET unit_hours=? WHERE id=?", (1 / 3, case.op_id))
    second = case.operation(seq=2, op_type_id="T2", op_type_name="Drilling", unit_hours=1 / 3)
    case.plan(5, [case.op_id, second], end="2026-09-09T09:00:00")
    update_schedule_rows(
        case.conn, 5, where="op_id = ?", params=(second,), start_time="2026-09-09T09:00:00", end_time="2026-09-09T10:00:00"
    )
    case.conn.commit()
    draft = create(case, {"base": {"plan_ref": case.plan_ref(5)}}, key="history-windowed-switch-create")
    draft = change(case, draft, task=0, start="2026-09-09T08:00:00", key="history-windowed-switch-first")["data"]
    draft = change(case, draft, task=1, start="2026-09-09T09:00:00", key="history-windowed-switch-second")["data"]
    published = trial_service(case.conn).save(draft["draft_ref"], {"name": "Saved windowed switches"},
        draft["write_context"]["write_token"], "history-windowed-switch-save")["data"]
    scenario = load_verified_scenario(case.conn, published["scenario_ref"])
    saved = scenario.saved
    packet = TrialPacket(saved["scenario_ref"], "scenario:" + saved["scenario_ref"], saved, scenario.head, scenario.rows,
                         scenario.origin)
    # 正式计划来源的试调只记下齐套规则和起止日：没记下的缺资源规则、执行规则按未知，不报存档损坏。
    planning = {row["field"]: row for row in compare_conditions(packet, packet, {"start": "2026-09-09T08:00:00", "end": "2026-09-09T10:00:00"})["conditions"]["rows"]
                if row["category"] == "scope" and row["entity"]["key"] == "planning"}
    assert {field for field, row in planning.items() if row["state"] == "unknown"} == {"missing_resource_policy", "completed_policy"}
    assert all(planning[field]["before"]["reason"]["code"] == "not_recorded" for field in ("missing_resource_policy", "completed_policy"))
    assert planning["material_strategy"]["before"]["value"] == "strict"
    reader = SimpleNamespace(condition_source=ConditionSource)
    for start, end, expected in (("2026-09-09T08:00:00", "2026-09-09T10:00:00", 1),
                                 ("2026-09-10T00:00:00", "2026-09-11T00:00:00", 0)):
        metrics, _, _ = _trial(packet, {"start": start, "end": end, "cohort": {}}, reader=reader)
        count = metrics["type_changeover_count"]
        assert count["value"] == expected and count["state"] == "complete"
        assert count["scope"] == "fixed_changeover_window" and count["member_unit"] == "operation"

    from core.services.workbench.history import metrics as history_metrics
    from core.services.workbench.trial import preparation as trial_preparation

    changeover_sides = Counter()
    original_changeover = trial_preparation.changeover_projection

    def count_changeover_side(*args, **kwargs):
        changeover_sides["calls"] += 1
        return original_changeover(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            history_metrics,
            "project_completion_summary",
            lambda *_: pytest.fail("Unrequested completion count metrics must not run completion summary"),
        )
        patch.setattr(trial_preparation, "changeover_projection", count_changeover_side)
        scoped_metrics, _, _ = _trial(
            packet,
            {"start": "2026-09-09T08:00:00", "end": "2026-09-09T10:00:00", "cohort": {}},
            reader=reader,
            metric_keys=["type_changeover_count", "makespan_hours"],
        )
        assert scoped_metrics["type_changeover_count"]["value"] == 1
        assert changeover_sides["calls"] == 1

    # Pure adapter probes reuse verified permanent rows; no saved record or receipt is rewritten.
    partial = deepcopy(packet)
    partial.saved["tasks"].pop()
    missing_ref = partial.rows.pop()["operation_ref"]
    missing_task = published["tasks"][-1]
    partial.saved["unplanned_operations"] = [{key: missing_task[key]
        for key in ("operation_ref", "batch_ref", "sequence", "piece_id", "predecessor_refs")}]
    partial.saved["unplanned_operations"][0]["status"] = "skipped"
    # The official plan source's stored document; its typed source reads the same dict.
    source = partial.origin.source.document
    definitions = {row["key"]: row for row in metric_definitions()}
    for deferred_ids, deferred_count, ordinary_count, expected_count in (([second], 1, 0, 1), ([], 0, 1, 2)):
        source.update(deferred_operation_ids=deferred_ids, deferred_operation_issues=[])
        partial = replace(partial, origin=TrialOrigin.saved(partial.head["admission"], partial.rows, partial.origin.source))
        if ordinary_count:
            partial.saved["unplanned_operations"] = []
            ledger = partial.saved["operation_effort"]
            ledger["items"] = [row for row in ledger["items"] if row["operation_ref"] != missing_ref]
        intervals = build_archived_trial_intervals(partial.rows, execution=partial.head["admission"]["execution"])
        partial.saved["comparison"] = trial_comparison(
            scenario_tasks(partial.saved, partial.rows, trial_intervals=intervals),
            partial.saved["validation"],
            partial.rows,
            partial.origin,
            trial_intervals=intervals,
        )
        metrics, _, _ = _trial(partial, {"start": "2026-09-09T08:00:00", "end": "2026-09-09T10:00:00", "cohort": {}},
                               reader=reader)
        assert metrics["deferred_operation_count"]["value"] == deferred_count
        assert metrics["unplanned_operation_count"]["value"] == ordinary_count
        assert metrics["expected_operation_count"]["value"] == expected_count
        assert missing_ref in metrics["deferred_operation_count"]["covered_operation_refs"]
        conditions = ConditionSource(partial)
        assert conditions.operations[missing_ref]["id"] == second
        index = next(index for index, row in enumerate(table_rows(partial.head["admission"]["facts"], "BatchOperations"))
                     if row["id"] == second)
        assert conditions.source("operations." + missing_ref, origin="original")["path"] == (
            f"head.admission.facts.tables.BatchOperations[{index}]")
        for key in ("expected_operation_count", "deferred_operation_count", "unplanned_operation_count"):
            item = _metric(metrics[key], definitions[key], partial, _path(partial, definitions[key]))
            assert item["source"]["path"] == "head.admission" and item["member_unit"] == "operation"
        scheduled = _metric(metrics["scheduled_operation_count"], definitions["scheduled_operation_count"], partial,
                            _path(partial, definitions["scheduled_operation_count"]))
        assert scheduled["source"]["path"] == "saved.tasks"
        if ordinary_count:
            demand = metrics["unplanned_setup_hours"]
            assert demand["value"] is None and demand["state"] == "unavailable"
            assert demand["unknown_count"] == demand["total_count"] == 1


def test_filtered_twenty_and_fifty_pages_export_all_native_rows_and_reject_stale_snapshot(history_case):
    case = history_case
    expected = []
    for index in range(51):
        at = (datetime(2026, 9, 13, 8) + timedelta(minutes=index)).isoformat()
        expected.append("run:" + clone_run(case, at)[0])
    outside = "run:" + clone_run(case, "2026-09-14T08:00:00")[0]
    client, _ = api(case)
    query = {"timeline": "run", "date_from": "2026-09-13", "date_to": "2026-09-13", "state": "complete", "order": "asc",
             "metric_keys": ["overdue_count", "makespan_hours", "machine_utilization_ratio"]}
    with retained(case.conn):
        initial = read(client, **query)
        assert initial["data"]["page"]["total"] == 51
        query["snapshot_ref"] = initial["meta"]["snapshot_ref"]
        entries = {}
        for size, lengths in ((20, [20, 20, 11]), (50, [50, 1])):
            rows = []
            for page, length in enumerate(lengths, 1):
                result = read(client, **dict(query, page=page, size=size))["data"]
                assert len(result["entries"]) == length and result["page"]["total"] == 51
                rows.extend(row["entry_ref"] for row in result["entries"])
                for row in result["entries"]:
                    if row["entry_ref"] in entries:
                        assert row["label"] == entries[row["entry_ref"]]["label"]
                entries.update((row["entry_ref"], row) for row in result["entries"])
            assert rows == expected and outside not in rows and len(set(rows)) == 51
        assert entries[expected[0]]["label"] == "第2次运行"
        assert entries[expected[-1]]["label"] == "第52次运行"
        from core.services.workbench.history import queries as history_queries
        from core.services.workbench.history_entries import conditions as condition_module

        export_query = dict(query, metric_keys=",".join(query["metric_keys"]), page=2, size=20)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                history_queries,
                "condition_pair",
                lambda *_, **__: pytest.fail("CSV entries export must not compute condition comparison"),
            )
            patch.setattr(
                history_queries,
                "configuration_pair",
                lambda *_, **__: pytest.fail("CSV entries export must not compute configuration comparison"),
            )
            csv_response = client.get(BASE + "/export", query_string=dict(export_query, format="csv", section="entries"))
        assert csv_response.status_code == 200, csv_response.get_data(as_text=True)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                history_queries,
                "project_entry",
                lambda *_, **__: pytest.fail("CSV condition/configuration export must not project entry metrics"),
            )
            sec_res = client.get(BASE + "/export", query_string=dict(export_query, format="csv", section="conditions"))
            assert sec_res.status_code == 200, sec_res.get_data(as_text=True)
            patch.setattr(
                condition_module,
                "production_conditions",
                lambda *_, **__: pytest.fail("CSV configurations export must not project production conditions"),
            )
            patch.setattr(
                condition_module,
                "_calendar",
                lambda *_, **__: pytest.fail("CSV configurations export must not project calendar conditions"),
            )
            cfg_res = client.get(BASE + "/export", query_string=dict(export_query, format="csv", section="configurations"))
            assert cfg_res.status_code == 200, cfg_res.get_data(as_text=True)
        csv_rows = list(csv.reader(io.StringIO(csv_response.data.decode("utf-8-sig"))))
        header, exported = csv_rows[0], csv_rows[1:]
        assert len(header) == len(set(header)) and len(exported) > 51 * 3
        assert int(csv_response.headers["X-Workbench-Row-Count"]) == len(exported)
        assert csv_response.headers["X-Workbench-Export-Version"] == "2"
        csv_references = exported_history_references(header, exported)
        xlsx_response = client.get(BASE + "/export", query_string=dict(export_query, format="xlsx", section="all"))
        assert xlsx_response.status_code == 200, xlsx_response.get_data(as_text=True)
        workbook = load_workbook(io.BytesIO(xlsx_response.data), read_only=True, data_only=True)
        try:
            native = list(workbook["历史条目"].iter_rows(max_col=len(header), values_only=True))
            assert tuple(header) == native[0] and len(native) == 1 + len(exported)
            assert len(set(native[0])) == len(native[0])
            assert xlsx_response.headers["X-Workbench-Export-Version"] == "2"
            native_references = exported_history_references(header, native[1:])
            assert native_references == csv_references
            primary_count = len(native) - 1 + sum(sum(1 for _row in workbook[title].values) - 1
                                                for title in ("生产条件", "算法配置"))
            assert int(xlsx_response.headers["X-Workbench-Row-Count"]) == primary_count
            for value in (0,):
                assert any(type(cell) in (int, float) and cell == value for row in native[1:] for cell in row)
            assert any(type(cell) is float and cell > 0 for row in native[1:] for cell in row)
            assert any(cell is None for row in native[1:] for cell in row)
            entry_index, key_index = header.index("历史条目编号"), header.index("指标键")
            record_index = header.index("记录类型")
            csv_by_key = {(row[entry_index], row[key_index]): row for row in exported if row[record_index] == "指标值"}
            native_by_key = {(row[entry_index], row[key_index]): row for row in native[1:] if row[record_index] == "指标值"}
            assert set(csv_by_key) == set(native_by_key) == {(ref, key) for ref in expected for key in query["metric_keys"]}
            full_entries = {
                row["entry_ref"]: row
                for row in history_queries.read_history_all(case.conn, query, section="entries")[0]["entries"]
            }
            expected_units = {
                "overdue_count": "batch",
                "makespan_hours": "record",
                "machine_utilization_ratio": "machine",
            }
            for ref, entry in entries.items():
                full_entry = full_entries[ref]
                quantity = entry["scope"]["batch_quantity"]
                full_quantity = full_entry["scope"]["batch_quantity"]
                assert "batch_refs" not in entry["scope"] and "operation_refs" not in entry["scope"]
                assert "covered_batch_refs" not in quantity and quantity["member_unit"] == "batch"
                assert set(entry["reading_context"]["resource_window"]["cohort"]) == {"machine_count", "operator_count"}
                for path, value in (("scope.batch_quantity.covered_batch_refs", full_quantity["covered_batch_refs"]),
                                    ("scope.batch_refs", full_entry["scope"]["batch_refs"]),
                                    ("scope.operation_refs", full_entry["scope"]["operation_refs"]),
                                    ("reading_context.resource_window.cohort.machine_refs", full_entry["reading_context"]["resource_window"]["cohort"]["machine_refs"]),
                                    ("reading_context.resource_window.cohort.operator_refs", full_entry["reading_context"]["resource_window"]["cohort"]["operator_refs"])):
                    assert csv_references[ref, None, path] == value
                for key in query["metric_keys"]:
                    source_metric = entry["metrics"][key]
                    full_metric = full_entry["metrics"][key]
                    assert source_metric["member_unit"] == expected_units[key]
                    assert not {"covered_batch_refs", "covered_operation_refs", "covered_resource_refs"}.intersection(source_metric)
                    csv_row, native_row = csv_by_key[ref, key], native_by_key[ref, key]
                    for label, value in (("条目名称", entry["label"]), ("运行编号", entry["identity"]["run_ref"]), ("候选编号", entry["identity"]["candidate_ref"]),
                                         ("指标版本", source_metric["metric_version"]), ("指标范围", source_metric["scope"]),
                                         ("指标来源编号", source_metric["source"]["ref"]),
                                         ("批次总量单位", quantity["unit"]), ("批次总量覆盖状态", quantity["state"]),
                                         ("批次总量指标范围", quantity["scope"]), ("批次总量指标版本", quantity["metric_version"]),
                                         ("批次总量来源类型", quantity["source"]["kind"]), ("批次总量来源编号", quantity["source"]["ref"]),
                                         ("批次总量来源字段", quantity["source"]["path"])):
                        assert csv_row[header.index(label)] == native_row[header.index(label)] == value
                    for label, field in (("批次总量", "value"), ("批次总量已知小计", "known_subtotal"),
                                         ("批次总量已知批次数", "known_count"), ("批次总量未知批次数", "unknown_count"),
                                         ("批次总量总批次数", "total_count")):
                        number = native_row[header.index(label)]
                        assert type(number) in (int, float) and number == quantity[field]
                        assert float(csv_row[header.index(label)]) == quantity[field]
                    assert native_row[header.index("导出格式版本")] == 2
                    assert csv_row[header.index("导出格式版本")] == "2"
                    for field in ("covered_batch_refs", "covered_operation_refs", "covered_resource_refs"):
                        assert csv_references[ref, key, field] == full_metric[field]
                    for label in ("批次总量缺项编码", "批次总量缺项说明"):
                        assert native_row[header.index(label)] is None and csv_row[header.index(label)] == ""
                    value = source_metric["value"]
                    displayed = value * 100 if value is not None and source_metric["unit"] == "%" else value
                    number = native_row[header.index("数值")]
                    if displayed is None:
                        assert number is None and csv_row[header.index("数值")] == ""
                    else:
                        assert type(number) in (int, float) and number == pytest.approx(displayed)
                        assert float(csv_row[header.index("数值")]) == pytest.approx(displayed)
        finally:
            workbook.close()
    clone_run(case, "2026-09-13T09:00:00")
    from core.services.workbench.history.reading import HistoryReader

    with pytest.MonkeyPatch.context() as stale_patch:
        stale_patch.setattr(
            HistoryReader,
            "read",
            lambda *_, **__: pytest.fail("Stale history snapshot must reject before restoring full archives"),
        )
        stale_patch.setattr(
            HistoryReader,
            "metric_packet",
            lambda *_, **__: pytest.fail("Stale history snapshot must reject before projecting entry metrics"),
        )
        stale_list = client.get(BASE, query_string=dict(export_query))
        assert stale_list.status_code == 409 and stale_list.get_json()["error"]["code"] == "snapshot_stale"
        stale = client.get(BASE + "/export", query_string=dict(export_query, format="csv", section="entries"))
        assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"

    from core.models.workbench_decision_history import normalize_history_query
    from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
    from core.services.workbench.history.projection import configuration_pair
    from core.services.workbench.history_entries.catalog import read_history_snapshot_context

    with candidate_read_snapshot(case.conn):
        reader = HistoryReader(case.conn)
        _, _, anchors = read_history_snapshot_context(case.conn, normalize_history_query(), expected[:2])
        selected_desc, reference_desc = anchors[expected[0]], anchors[expected[1]]
        selected_packet = reader.read(selected_desc)
        reference_packet = reader.read(reference_desc)
        projected_pair = configuration_pair(reader, reference_desc, selected_desc)
        # 配置对照两侧各取自己那次运行保存的业务选择：目标清单与主目标的评分字段顺序。
        [targets] = [row for row in projected_pair["configurations"]["rows"] if row["field"] == "target_objectives"]
        for side, packet in (("before", reference_packet), ("after", selected_packet)):
            selection = packet.receipt.selection
            primary = selection["primary_objective"]
            assert targets[side]["value"] == selection["target_objectives"]
            assert projected_pair["objective"][side]["value"] == {
                "name": primary, "field_order": selection["objective_field_order"][primary]}
