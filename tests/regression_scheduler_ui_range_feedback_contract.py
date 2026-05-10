from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_batch_ops_table_has_stable_width_and_ellipsis_contract() -> None:
    html = _read("templates/scheduler/batch_detail.html")
    css = _read("static/css/ui_contract.css")

    assert "aps-batch-ops-table" in html
    assert 'data-col-key="op_code" data-default-w="180" data-min-w="150"' in html
    assert 'data-col-key="machine" data-default-w="260" data-min-w="220"' in html
    assert 'data-col-key="operator" data-default-w="260" data-min-w="220"' in html
    assert 'data-col-key="supplier" data-default-w="280" data-min-w="220"' in html
    assert "aps-cell-ellipsis aps-code-cell" in html
    assert ".aps-batch-ops-table" in css and "min-width: 1780px;" in css
    assert ".aps-batch-ops-table .js-machine-select" in css


def test_resource_dispatch_keeps_single_target_field_and_disabled_inactive_selects() -> None:
    html = _read("templates/scheduler/resource_dispatch.html")
    js = _read("static/js/resource_dispatch.js")
    css = _read("static/css/ui_contract.css")

    assert 'id="rdScopeTargetField"' in html
    assert 'id="rdOperatorField"' not in html
    assert 'id="rdMachineField"' not in html
    assert 'id="rdTeamField"' not in html
    for target in ("operator", "machine", "team"):
        assert f'data-scope-target="{target}"' in html
    assert "el.disabled = !active;" in js
    assert 'teamAxisField.classList.toggle("is-disabled", value !== "team")' in js
    assert ".aps-resource-team-axis-field.is-disabled" in css
    assert "待选择" in html


def test_scheduler_preset_switch_uses_page_script_without_public_auto_submit() -> None:
    for rel_path in ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"):
        html = _read(rel_path)
        assert 'data-scheduler-preset-auto-submit="1"' in html
        assert 'id="schedulerPresetSelect" name="preset_name" data-auto-submit="1"' not in html
        assert "js/scheduler_run.js" in html

    js = _read("static/js/scheduler_run.js")
    assert "切换排产方案会清空当前已选的 " in js
    assert "请先勾选至少一个待排批次。" in js
    assert 'document.addEventListener("click", function (event)' in js
    assert "stopImmediatePropagation" in js


def test_gantt_switches_keep_original_ids_and_compact_visual_contract() -> None:
    for rel_path in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        html = _read(rel_path)
        assert "aps-compact-switch" in html
        assert 'id="ganttOnlyOverdue"' in html
        assert 'id="ganttOnlyExternal"' in html
        assert 'id="ganttHighlightCC" checked' in html
        assert "js/gantt_contract.js" in html and html.index("js/gantt_contract.js") < html.index("js/gantt_render.js")

    css = _read("static/css/aps_gantt.css")
    assert "grid-template-columns: repeat(4, minmax(150px, 1fr)) auto;" in css
    assert ".aps-compact-switch input:checked + .aps-compact-switch-track" in css


def test_personnel_nav_and_primary_switch_contract() -> None:
    macro = _read("templates/components/ui_macros.html")
    personnel_detail = _read("templates/personnel/detail.html")
    personnel_calendar = _read("templates/personnel/calendar.html")
    equipment_detail = _read("templates/equipment/detail.html")
    css = _read("static/css/ui_contract.css")

    assert "macro personnel_nav(active='', size='sm', class='', operator_id=None, include_calendar=False)" in macro
    assert "个人工作日历" in macro and "全局工作日历" in macro
    assert "include_calendar=True" in personnel_detail
    assert "operator_calendar" in personnel_calendar
    assert "aps-table-switch" in personnel_detail
    assert "aps-table-switch" in equipment_detail
    assert ".aps-table-switch-track::after" in css


def test_targeted_form_feedback_script_is_page_scoped() -> None:
    batches_manage = _read("templates/scheduler/batches_manage.html")
    batch_detail = _read("templates/scheduler/batch_detail.html")
    personnel = _read("templates/personnel/list.html")
    equipment = _read("templates/equipment/list.html")
    js = _read("static/js/scheduler_form_feedback.js")

    assert 'id="batchCreateForm"' in batches_manage
    assert 'type="number"' in batches_manage
    assert 'min="1"' in batches_manage
    assert 'step="1"' in batches_manage
    for source in (batches_manage, batch_detail, personnel, equipment):
        assert "js/scheduler_form_feedback.js" in source
    assert "validateBatchCreate" in js
    assert "form.elements.ready_date" in js
    assert "齐套日期格式不正确，请选择日期。" in js
    assert "validateOperationForm" in js
    assert 'data-aps-batch-bulk-form="1"' in batches_manage
    assert 'aria-describedby="batchBulkActionHelp batchBulkActionError"' in batches_manage
    assert "aps-bulk-action-error" in batches_manage
    assert 'id="batchBulkActionError"' in batches_manage
    assert 'role="alert" aria-live="polite"' in batches_manage
    assert "blockEmptyBatchBulk" in js
    assert "batchBulkSubmitFormForTarget" in js
    assert "batchBulkFormForImplicitSubmitTarget" in js
    assert "deferClearBatchBulkErrorIfSelected" in js
    assert "window.setTimeout(function ()" in js
    assert 'document.addEventListener("keydown"' in js
    assert 'key !== "Enter" && key !== "NumpadEnter"' in js
    assert "请先勾选至少一个批次。" in js
    assert "stopImmediatePropagation" in js
    assert 'document.addEventListener("change"' in js
    assert 'document.addEventListener("change", function (event)' in js
    change_start = js.index('document.addEventListener("change", function (event)')
    submit_start = js.index('document.addEventListener("submit"', change_start)
    change_listener = js[change_start:submit_start]
    assert "}, true);" not in change_listener
    assert 'if (error.focus) error.focus();' in js
    assert "请选择设备" not in js
    assert "请选择人员" not in js
    assert '!isBlank(setupHours && setupHours.value)' in js
    assert '!isBlank(unitHours && unitHours.value)' in js
    assert "Number(setupHours.value) < 0" in js
    assert "Number(unitHours.value) < 0" in js
    assert "外协周期要填大于 0 的天数" in js
    assert 'data-aps-validate="operator-create"' in personnel
    assert 'data-aps-validate="machine-create"' in equipment
