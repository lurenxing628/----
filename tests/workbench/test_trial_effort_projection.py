"""Real trial slots save requirements independently of unchanged geometry."""

from copy import deepcopy

from core.models.workbench_trial_codec import load
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.trial_origin import delivery_origin, operation_contexts
from core.services.workbench.facts.trial_policy import load_draft, load_scenario
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from core.services.workbench.trial.effort import operation_types
from core.services.workbench.trial.preparation import apply_preparation, preparation_projection, trial_changeovers
from core.services.workbench.trial.projection import unplanned_operations
from core.services.workbench.trial.service import WorkbenchTrialService
from tests.workbench.test_legacy_resource_projection import shipped
from tests.workbench.trial_support import candidate, change, create, service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def test_new_trial_slot_persists_the_same_requirement_used_for_calendar_math(trial_case):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=2,unit_hours=0.5 WHERE id=?", (case.op_id,))
    case.conn.commit()
    draft = create(case)
    assert draft["operation_effort"] is None
    adjusted = change(case, draft, start="2026-09-09T12:00:00")["data"]
    task, = adjusted["tasks"]
    assert task["end"] == "2026-09-09T15:30:00"
    effort, = adjusted["operation_effort"]["items"]
    assert effort["operation_ref"] == task["operation_ref"]
    assert effort["setup_standard_hours"] == 2 and effort["processing_standard_hours"] == 1.5
    assert effort["required_standard_hours"] == 3.5
    assert effort["target_quantity"] == effort["execution_target_quantity"] == effort["remaining_quantity"] == 3
    assert effort["quantity_basis"] == effort["execution_quantity_basis"] == "batch"
    assert effort["setup_state"] == "pending"
    projected = task["operation_effort"]
    assert projected["before"]["setup_standard_hours"] is None
    assert projected["before"]["standard"]["standard_total_hours"] == 3.5
    assert projected["after"]["setup_standard_hours"] == 2
    assert adjusted["comparison"]["preparation_common"]["after"]["scheduled_setup_hours"]["value"] == 2
    assert adjusted["comparison"]["changeover_common"]["before"]["count"] is None
    assert adjusted["comparison"]["changeover_common"]["after"]["count"] == 0
    shipped(adjusted, r"""
const w = h.runtime, data = w.TrialContract.workspace(sourceData);
const tree = h.render(w.TrialResults.Preparation, {data, name: w.TrialGantt.resourceNames(data), onSelect() {}}), text = h.text(tree);
assert(text.includes('准备标准工时') && text.includes('合计'));
const requirementDetail = h.walk(tree).find(node => node.type === 'details' && h.text(node) === '工时详情');
assert(requirementDetail && h.text({...requirementDetail, props:{...requirementDetail.props, open:true}}).includes('当前试调需求'));
const retained = h.walk(tree).find(node => node.type === 'details' && h.text(node) === '保留安排与报工工序');
assert(retained && h.text({...retained, props:{...retained.props, open:true}}).includes('保留原安排'));
assert(text.includes('工种切换次数') && h.text({...requirementDetail, props:{...requirementDetail.props, open:true}}).includes('需求未保存'));
const requirement = w.TrialExport.preparation(data), switches = w.TrialExport.changeovers(data), legacy = w.TrialExport.csv(data);
assert(requirement.text.includes('归档单件标准（小时）') && requirement.text.includes('本次执行目标量'));
assert(switches.text.includes('前工序编号') && switches.text.includes('汇总'));
assert(legacy.text.includes('工种切换次数（次）') && !legacy.text.includes('换型次数'));
const damaged = structuredClone(data);
delete damaged.tasks[0].operation_effort.after.required_standard_hours;
assert.throws(() => w.TrialContract.workspace(damaged));
return {shipped_contract:true, preparation_panel:true, csv_exports:true};
""")
    stored = load(case.conn.execute("SELECT current_json FROM WorkbenchTrialRows WHERE task_ref=?", (task["task_ref"],)).fetchone()[0])
    assert stored["operation_effort"] == effort
    saved = service(case.conn).save(draft["draft_ref"], {"name": "Saved preparation"},
                                   adjusted["write_context"]["write_token"], "trial-effort-save-01")["data"]
    reread, _, rows = load_saved_scenario(case.conn, saved["scenario_ref"])
    assert reread["operation_effort"] == saved["operation_effort"] == adjusted["operation_effort"]
    assert rows[0]["current"]["operation_effort"] == effort


def test_runtime_metadata_does_not_make_a_trial_geometry_change(trial_case):
    case = trial_case
    draft = create(case)
    same = change(case, draft, start="2026-09-09T08:00:00", machine="M1", operator="O1")["data"]
    assert not same["tasks"][0]["changed"] and same["operation_effort"] is None
    updated = change(case, same, key="trial-effort-change-02")["data"]
    reset = change(case, updated, start="2026-09-09T08:00:00", machine="M1", operator="O1", key="trial-effort-change-03")["data"]
    assert not reset["tasks"][0]["changed"]
    assert reset["comparison"]["changed_operations"] == 0
    assert reset["operation_effort"]["items"][0]["required_standard_hours"] == 3
    before = case.conn.execute("SELECT count(*) FROM WorkbenchTrialChanges").fetchone()[0]
    no_change = change(case, reset, start="2026-09-09T08:00:00", machine="M1", operator="O1", key="trial-effort-change-04")["data"]
    assert no_change["operation_effort"] == reset["operation_effort"]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchTrialChanges").fetchone()[0] == before


def test_trial_retained_requirement_keeps_original_target_separate_from_creation_execution(trial_case, monkeypatch):
    case = trial_case
    case.conn.execute("UPDATE Batches SET quantity=10 WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=2,unit_hours=0.5 WHERE id=?", (case.op_id,))
    case.conn.commit()
    base = candidate(case)
    case.conn.execute("UPDATE Batches SET quantity=20 WHERE batch_id='B1'")
    case.conn.commit()
    draft = create(case, base)
    task, = draft["tasks"]
    before, after = task["operation_effort"]["before"], task["operation_effort"]["after"]
    assert before["target_quantity"] == 10 and before["execution_target_quantity"] == 20
    assert after["target_quantity"] == 10 and after["required_standard_hours"] == 7
    assert after["execution_target_quantity"] == after["remaining_quantity"] == 20
    assert after["requirement_role"] == after["allocation_state"] == "retained"
    assert after["standard"]["target_quantity"] == 10
    summary = draft["comparison"]["preparation_common"]
    assert summary["after"]["scheduled_setup_hours"]["value"] == 0
    assert summary["role_totals"]["after"]["retained"]["setup_standard_hours"]["value"] == 2
    assert summary["deltas"]["scheduled_setup_hours"]["state"] == "different_coverage"
    assert summary["deltas"]["scheduled_setup_hours"]["direction"] == "neutral"
    item, = draft["operation_effort"]["items"]
    assert item["target_quantity"] == 10 and item["execution_target_quantity"] == 20
    assert item["required_standard_hours"] == 7
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    outside = deepcopy(head["admission"])
    outside["source"]["capture"]["input"]["batch_refs"] = []
    assert delivery_origin(outside, rows)[0] == {}
    contexts = operation_contexts(rows, outside)
    context = contexts[task["operation_ref"]]
    original = rows[0]["original"]
    assert context["operation"] is original["operation"] and context["execution"] is original["execution"]
    assert context["batch"] is original["batch"] and context["batch_ref"] == original["batch_ref"]
    assert context["row"] is rows[0] and context["arranged"] is True
    pairs, retained = preparation_projection(rows, outside, draft["operation_effort"], contexts=contexts)
    assert set(pairs) == {row["operation_ref"] for row in rows}
    assert pairs[task["operation_ref"]]["after"]["required_standard_hours"] == 7
    assert retained["role_totals"]["after"]["retained"]["setup_standard_hours"]["value"] == 2
    unplanned = unplanned_operations(contexts)
    assert unplanned == []
    apply_preparation(deepcopy(draft["tasks"]), unplanned, pairs)
    shipped(draft, r"""
const w = h.runtime, data = w.TrialContract.workspace(sourceData);
const tree = h.render(w.TrialResults.Preparation, {data, name: w.TrialGantt.resourceNames(data), onSelect() {}}), text = h.text(tree);
assert(text.includes('保留原安排'));
const sources = h.walk(tree).filter(node => node.type === 'details' && h.text(node) === '需求依据与数量');
assert.equal(sources.length, 2);
const facts = new Map(h.walk(sources[1]).find(node => node.type === 'dl').children.filter(row => row !== null).map(row => [h.text(row.children[0]), h.text(row.children[1])]));
assert.equal(facts.get('排产目标量'), '10 · 批次目标数量');
assert.equal(facts.get('报工目标量'), '20 · 批次目标数量');
const csv = w.TrialExport.preparation(data).text.trim().split('\r\n').map(row => row.split(','));
const head = csv[0].map(cell => cell.replace(/^\uFEFF/, '').replace(/^"|"$/g, ''));
const current = csv[2];
assert.equal(current[head.indexOf('原需求目标量')], '10');
assert.equal(current[head.indexOf('本次执行目标量')], '20');
assert.equal(current[head.indexOf('所需标准工时（小时）')], '7');
return {shipped_contract:true, retained_quantity:true, csv_quantity:true};
""")
    # The real AJ completion must determine the role even when this source row
    # has no completed_actuals anchor. The requirement itself remains 10/7h.
    case.plan(1, [case.op_id], end="2026-09-09T15:00:00")
    case.command("create", case.task(1, case.op_id), case.values(20,
        actual_end="2026-09-09T15:00:00", effective_processing_hours=7))
    with monkeypatch.context() as patch:
        patch.setattr("core.services.workbench.trial.base.attach_execution_anchors", lambda *_: [])
        completed = create(case, base, key="trial-completed-effort-create")
    head, rows = load_draft(service(case.conn).repo, completed["draft_ref"])
    assert head["admission"]["execution"][rows[0]["operation_ref"]]["execution_state"] == "complete"
    assert "execution_anchor" not in rows[0]["original"]
    saved = service(case.conn).save(completed["draft_ref"], {"name": "Completed retained requirement"},
        completed["write_context"]["write_token"], "trial-completed-effort-save")["data"]
    saved_item, = saved["operation_effort"]["items"]
    assert saved_item["requirement_role"] == "completed" and saved_item["setup_state"] == "already_completed"
    assert saved_item["target_quantity"] == 10 and saved_item["required_standard_hours"] == 7
    assert saved_item["execution_target_quantity"] == 20 and saved_item["remaining_quantity"] == 0


def test_saved_legacy_trial_does_not_restore_runtime_from_newer_draft_metadata(trial_case, monkeypatch):
    case = trial_case
    draft = create(case)
    adjusted = change(case, draft)["data"]
    original_projection = WorkbenchTrialService._projection

    def legacy_projection(*args, **kwargs):
        result = original_projection(*args, **kwargs)
        result.pop("operation_effort")
        result["comparison"].pop("preparation_common")
        for task in result["tasks"]:
            task.pop("operation_effort")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchTrialService, "_projection", legacy_projection)
        saved = service(case.conn).save(draft["draft_ref"], {"name": "Historical requirements"},
            adjusted["write_context"]["write_token"], "trial-legacy-effort-save-01")["data"]
    before = case.conn.total_changes
    reread = service(case.conn).scenario(saved["scenario_ref"])
    assert "operation_effort" not in reread
    effort = reread["tasks"][0]["operation_effort"]["after"]
    assert effort["setup_standard_hours"] is effort["processing_standard_hours"] is effort["required_standard_hours"] is None
    assert effort["standard"]["standard_total_hours"] == 3
    assert reread["comparison"]["preparation_common"]["after"]["scheduled_setup_hours"]["value"] is None
    assert load_scenario(service(case.conn).repo, saved["scenario_ref"]) == saved
    assert case.conn.total_changes == before


def test_trial_switches_follow_actual_type_identity_and_saved_complete_arrangements(trial_case):
    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Drilling')")
    for machine in ("M1", "M2"):
        case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES (?,'T2')", (machine,))
    case.operation(seq=2, op_type_id="T2", op_type_name="Turning")
    case.conn.commit()
    draft = create(case, candidate(case))
    common = draft["comparison"]["changeover_common"]
    assert common["before"]["count"] == common["after"]["count"] == draft["comparison"]["changeovers"] == 1
    event, = common["after"]["events"]
    assert event["previous_type"] == "Turning" and event["next_type"] == "Drilling"
    assert event["previous_type_ref"] != event["next_type_ref"]
    assert event["previous_operation_ref"] == draft["tasks"][0]["operation_ref"]
    assert event["next_operation_ref"] == draft["tasks"][1]["operation_ref"]
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    facts = GenerationFacts(head["admission"]["source"]["capture"])
    second = rows[1]
    missing = operation_types(rows, facts.entity_refs, facts.tables["OpTypes"],
                              [{"op_id": second["original"]["operation"]["id"]}])
    assert missing[second["operation_ref"]] == {"ref": case.ref("op_type", "T2"), "label": "Drilling"}
    unknown = operation_types(rows, facts.entity_refs, facts.tables["OpTypes"],
                              [{"op_id": second["original"]["operation"]["id"], "op_type_id": None}])
    assert unknown[second["operation_ref"]] == {"ref": None, "label": None}
    unknown_source = dict(head["admission"], source=dict(head["admission"]["source"], operation_types=unknown))
    assert trial_changeovers(rows, unknown_source)["before"]["count"] is None
    updated = change(case, draft, task=1, start="2026-09-09T12:00:00")["data"]
    assert updated["comparison"]["changeovers"] == 0
    assert updated["comparison"]["changeover_common"]["before"]["count"] == 1
