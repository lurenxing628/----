"""仓储不裁决后上提到服务层的拒绝码：每个上提的 raise 点都仍以原码、原状态、原文案裁决。

覆盖复审指出的六个零测试引用的码：template_lineage_unavailable / template_lineage_not_new /
template_lineage_mismatch / calibration_source_unavailable / dashboard_external_unavailable / trial_schema_unavailable。
仓储用桩替代，只提供事实；裁决全部发生在策略模块里。
"""

import sqlite3
from types import SimpleNamespace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler import template_lineage, template_lineage_query
from core.services.workbench.calibration import adoption_policy
from core.services.workbench.calibration import facts as calibration_facts
from core.services.workbench.dashboard import policy as dashboard_policy
from core.services.workbench.facts import trial_policy

REF = "a" * 48
OTHER = "b" * 48


def _expect(code, status, fn):
    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        fn()
    assert (exc_info.value.code, exc_info.value.status) == (code, status)
    return str(exc_info.value)


def _writer(monkeypatch, **facts):
    conn = sqlite3.connect(":memory:")
    conn.execute("BEGIN")
    writer = template_lineage.TemplateLineageWriter(conn)
    defaults = dict(schema_state=lambda: "loaded", identity_schema_broken=lambda: False,
                    has_execution_facts=lambda ref: False, has_legacy_execution_events=lambda op_id: False,
                    template=lambda template_id: None, instance=lambda op_id: None,
                    insert_instance=lambda payload: None)
    defaults.update(facts)
    monkeypatch.setattr(writer, "repo", SimpleNamespace(**defaults))
    return writer


def _template(part_ref=REF):
    return {"template_operation_ref": "c" * 48, "part_ref": part_ref, "seq": 1}


def _instance(part_ref=REF, op_id=7):
    return {"id": op_id, "operation_ref": REF, "batch_ref": OTHER, "part_ref": part_ref, "seq": 1, "piece_id": None, "source": "internal"}


# ---- template_lineage_unavailable ----

@pytest.mark.parametrize("state,expected", [("loaded", True), ("missing", False)])
def test_lineage_available_reports_installed_state_without_ruling(state, expected):
    assert template_lineage_query.lineage_available(SimpleNamespace(schema_state=lambda: state)) is expected


def test_partial_lineage_storage_is_unavailable_not_repaired():
    message = _expect("template_lineage_unavailable", 409,
                      lambda: template_lineage_query.lineage_available(SimpleNamespace(schema_state=lambda: "invalid")))
    assert "没有自动补表" in message


def test_broken_identity_storage_blocks_copies(monkeypatch):
    writer = _writer(monkeypatch, identity_schema_broken=lambda: True)
    assert "没有用不可靠的版本继续" in _expect("template_lineage_unavailable", 409, writer.require_ready)
    missing = _writer(monkeypatch, schema_state=lambda: "missing")
    assert "还没安装" in _expect("template_lineage_schema_missing", 409, missing.require_ready)


@pytest.mark.parametrize("row", [None, {"template_operation_ref": None, "part_ref": REF}, {"template_operation_ref": REF, "part_ref": None}])
def test_template_without_permanent_identity_is_unavailable(monkeypatch, row):
    writer = _writer(monkeypatch, template=lambda template_id: row)
    assert "不会按图号或工序号猜着匹配" in _expect("template_lineage_unavailable", 409, lambda: writer.template(1))


@pytest.mark.parametrize("row", [None, dict(_instance(), batch_ref=None), dict(_instance(), part_ref=None)])
def test_instance_without_permanent_refs_is_unavailable(monkeypatch, row):
    writer = _writer(monkeypatch, instance=lambda op_id: row)
    assert "模板来源没有自动补上" in _expect("template_lineage_unavailable", 409, lambda: writer.instance(7))


# ---- template_lineage_not_new ----

def test_executed_instances_cannot_receive_or_rebind_an_origin(monkeypatch):
    writer = _writer(monkeypatch, has_execution_facts=lambda ref: True)
    assert "已开工的工序" in _expect("template_lineage_not_new", 409, lambda: writer._require_unexecuted(_instance()))
    legacy = _writer(monkeypatch, has_legacy_execution_events=lambda op_id: True)
    assert "历史报工记录" in _expect("template_lineage_not_new", 409, lambda: legacy._require_unexecuted(_instance()))


@pytest.mark.parametrize("events", [[], [{"event_type": "updated"}], [{"event_type": "created"}, {"event_type": "updated"}]])
def test_origin_is_only_recorded_for_a_freshly_created_unchanged_instance(monkeypatch, events):
    writer = _writer(monkeypatch)
    monkeypatch.setattr(template_lineage, "read_events", lambda repo, refs: {REF: events})
    assert "原有的工序不能往前补" in _expect("template_lineage_not_new", 409,
                                       lambda: writer.record_origin(_instance(), _template(), "{}"))


# ---- template_lineage_mismatch ----

def test_copying_a_template_into_another_parts_batch_is_a_mismatch(monkeypatch):
    writer = _writer(monkeypatch, template=lambda template_id: _template(REF),
                     insert_instance=lambda payload: _instance(part_ref=OTHER))
    assert "没有按图号猜着匹配" in _expect("template_lineage_mismatch", 409, lambda: writer.copy_template("B1", 1))


def test_copying_an_instance_whose_origin_belongs_to_another_part_is_a_mismatch(monkeypatch):
    origin = {"template_snapshot": "{}"}
    facts = {"origins": {REF: origin}, "events": {REF: [{"event_id": 1}]}, "problems": {REF: []}}
    monkeypatch.setattr(template_lineage, "TemplateLineageQuery", lambda conn, repo=None: SimpleNamespace(read=lambda refs: facts))
    monkeypatch.setattr(template_lineage, "validate_origin", lambda origin, events: (_template(OTHER), None))
    writer = _writer(monkeypatch, instance=lambda op_id: _instance(REF), insert_instance=lambda payload: _instance(REF, op_id=8))
    assert "不是原来源模板的零件" in _expect("template_lineage_mismatch", 409, lambda: writer.copy_instance("B1", 7))


# ---- calibration_source_unavailable ----

def test_calibration_schema_is_required_before_any_read():
    assert "没有补表或补身份" in _expect("calibration_source_unavailable", 409,
                                       lambda: calibration_facts.require_calibration_schema(SimpleNamespace(schema_installed=lambda: False)))


@pytest.mark.parametrize("row", [dict(operation_ref=None, part_ref=REF, revision=1), dict(operation_ref=REF, part_ref=None, revision=1),
                                 dict(operation_ref=REF, part_ref=REF, revision="1"), dict(operation_ref=REF, part_ref=REF, revision=0)])
def test_template_rows_missing_identity_are_unavailable(row):
    repo = SimpleNamespace(part_exists=lambda ref: True, template_rows=lambda part_ref, limit: [row])
    query = SimpleNamespace(part_ref=None, source=None, query="")
    assert "模板或所属零件的永久身份缺失" in _expect("calibration_source_unavailable", 409,
                                             lambda: calibration_facts.read_templates(repo, query))


def test_candidate_instances_missing_identity_are_unavailable():
    repo = SimpleNamespace(candidate_instance_rows=lambda parts, limit: [{"operation_ref": REF}, {"operation_ref": None}])
    assert "执行实例永久身份缺失" in _expect("calibration_source_unavailable", 409,
                                       lambda: calibration_facts.read_candidate_instances(repo, ["P1"]))


def test_adoption_template_without_part_identity_is_unavailable():
    repo = SimpleNamespace(template=lambda ref: {"part_ref": None})
    assert "未按图号补配" in _expect("calibration_source_unavailable", 409, lambda: adoption_policy.require_template(repo, REF))
    missing = SimpleNamespace(template=lambda ref: None)
    _expect("entity_not_found", 404, lambda: adoption_policy.require_template(missing, REF))


# ---- dashboard_external_unavailable / trial_schema_unavailable ----

def test_external_dashboard_schema_and_trial_schema_are_required_with_503():
    assert "未补表" in _expect("dashboard_external_unavailable", 503,
                              lambda: dashboard_policy.require_external_schema(SimpleNamespace(schema_installed=lambda: False)))
    assert "试调记录结构不完整" in _expect("trial_schema_unavailable", 503,
                                    lambda: trial_policy.require_trial_schema(SimpleNamespace(schema_issues=lambda: ["missing"])))
    trial_policy.require_trial_schema(SimpleNamespace(schema_issues=lambda: []))
    dashboard_policy.require_external_schema(SimpleNamespace(schema_installed=lambda: True))
