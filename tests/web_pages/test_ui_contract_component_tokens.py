"""Current React controls, semantic tokens and retained order-independent POST parsers.

Retired Jinja macros are not restored: presentation now reads the served React
components, while disabled values and missing/zero distinctions remain locked.
"""

from __future__ import annotations

import json

from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract
from web.viewmodels.ui_presenters import UiSummaryItem

COMPONENT_INPUTS = (
    "static/workbench/app/resource-contract.js",
    "static/workbench/app/ResourceControls.js",
    "static/workbench/app/ResourceMetrics.js",
    "static/workbench/app/SystemMaintenanceAPI.js",
    "static/workbench/app/SystemMaintenanceControls.js",
    "static/workbench/app/SystemMaintenanceConfig.js",
)


def _read(name):
    """Read a declared production input in this private source."""
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _components(body, data=None):
    """Load existing built components and bundled icons, never rebuild them."""
    manifest = json.loads(_read("static/workbench/asset-manifest.json"))
    foundation = [name for name in manifest["scripts"] if name.startswith("workbench/assets/foundation-")]
    assert len(foundation) == 1
    return browser_contract(body, scripts=("static/" + foundation[0],) + COMPONENT_INPUTS, data=data)


def test_ui_contract_declares_semantic_tokens_and_components() -> None:
    tokens = _read("static/workbench/prototype/tokens/colors.css")
    css = _read("static/workbench/prototype/ui_kits/workbench/workbench-ui.css")
    for token in ("--ui-surface", "--ui-surface-muted", "--ui-text-strong", "--ui-text-subtle",
                  "--ui-focus-ring", "--ui-neutral-bg", "--ui-info-bg", "--ui-success-bg",
                  "--ui-warning-bg", "--ui-danger-bg", "--ui-table-head-bg"):
        assert token in tokens
    for selector in (".wb-metrics", ".wb-metric", ".wb-action", ".wb-control", ".wb-table-shell"):
        assert selector in css
    assert "--wb-metric-color:var(--ui-text)" in css
    for tone in ("success", "warning", "danger"):
        assert tone in css
    assert ":disabled" in css and ":focus-visible" in css
    assert "overflow-x:auto" in css
    assert _read("frontend/workbench/prototype/tokens/colors.css") == tokens


def test_maintained_css_layer_is_ordered_local_and_matches_current_sources() -> None:
    manifest = json.loads(_read("static/workbench/asset-manifest.json"))
    styles = manifest["styles"]
    maintained = [name for name in styles if name.startswith("workbench/app/styles/")]
    foundation = ["workbench/app/styles/" + name for name in (
        "00-tokens.css", "10-shell.css", "20-controls.css", "30-workspaces.css")]
    assert maintained and maintained[0] == foundation[0]
    positions = [maintained.index(name) for name in foundation]
    assert positions == sorted(positions)
    assert styles[-len(maintained):] == maintained
    assert all(name.startswith("workbench/prototype/") for name in styles[:-len(maintained)])
    for name in maintained:
        source = "frontend/" + name
        assert _read("static/" + name) == _read(source), source


def test_ui_macros_expose_shared_contract_components() -> None:
    result = _components("""
const UI = window.APSWorkbenchUI, C = window.ResourceControls;
const names = ['TransferButton','ControlButton','DataMeter','MetricStrip','Metric','DataTable'];
expect(names.every(name => typeof UI[name] === 'function'));
expect(['ErrorBox','Issues','Button','Modal','Choice'].every(name => typeof C[name] === 'function'));
const node = await render(React.createElement(UI.MetricStrip, null,
  React.createElement(UI.Metric, {label:'严格摘要', value:'明确值', helper:'说明文字'})));
expect(node.querySelector('.wb-metric-value').textContent === '明确值');
expect(node.querySelector('.wb-metric-helper').textContent === '说明文字');
return names;
""")
    assert len(result) == 6
    assert not (REPO_ROOT / "templates/components/ui_macros.html").exists()


def test_notice_macro_defaults_to_static_message_and_allows_explicit_live_role() -> None:
    _components("""
const UI = window.APSWorkbenchUI, C = window.ResourceControls;
let node = await render(React.createElement(UI.Metric, {label:'普通提示', value:'当前值', helper:'这是静态页面提示。'}));
expect(node.textContent.includes('这是静态页面提示。'));
expect(!node.querySelector('[role],[aria-live]'), 'Static annotation became a live announcement');
node = await render(React.createElement(UI.Metric, {label:'强提醒', value:'需要立刻知道。', role:'alert', 'aria-live':'assertive'}));
expect(node.querySelector('[role=alert][aria-live=assertive]'));
node = await render(React.createElement(C.Issues, {issues: [{message:'已读取的资料有缺项。'}]}));
expect(node.querySelector('[role=status]').textContent === '已读取的资料有缺项。');
node = await render(React.createElement(C.ErrorBox, {error:new Error('需要核对原请求。')}));
expect(node.querySelector('[role=alert]').textContent.includes('需要核对原请求。'));
return true;
""")


def test_toggle_object_keeps_disabled_checked_hidden_value_safe() -> None:
    result = _components("""
const A = window.SystemMaintenanceAPI, values = Object.fromEntries(A.fields.map(field => [field.key, field.switch ? 'yes' : 7]));
const stored = A.config({values, stored_values:Object.fromEntries(A.fields.map(field => [field.key,String(values[field.key])])),
  dirty_fields:[], defaulted_fields:[], dirty_reasons:{}, write_context:{write_token:'original-config-token'}});
const calls = [], api = {read: async kind => {expect(kind === 'config'); return {data:stored};}};
const command = {locked:true, execute:(...args) => calls.push(args)};
const props = {api, revision:1, command, theme:'light', pageSize:10, compact:false, onPageSize:()=>{}, onCompact:()=>{}, onSetTheme:()=>{}};
let node = await render(React.createElement(window.SystemMaintenanceConfig, props));
const checkbox = node.querySelector('#sm-maintenance-auto_backup_enabled');
expect(checkbox && checkbox.checked && checkbox.disabled, 'Disabled checked value changed');
node.querySelector('.sm-config-form').dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
expect(calls.length === 0, 'Disabled form submitted');
node = await render(React.createElement(window.SystemMaintenanceConfig, {...props, command:{...command,locked:false}}));
expect(node.querySelector('#sm-maintenance-auto_backup_enabled').checked);
node.querySelector('.sm-config-form').dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
expect(calls.length === 1 && calls[0][0] === 'config' && calls[0][1] === 'original-config-token');
expect(JSON.stringify(calls[0][2]) === JSON.stringify(values), 'JSON submission lost an unchanged checkbox');
expect(stored.values.auto_backup_enabled === 'yes');
return calls[0][2];
""")
    assert result["auto_backup_enabled"] == "yes"
    assert result["auto_backup_cleanup_enabled"] == result["auto_log_cleanup_enabled"] == "yes"
    assert len(result) == 8


def test_business_templates_do_not_call_low_level_toggle_row_macro_directly() -> None:
    for path in (REPO_ROOT / "templates").rglob("*.html"):
        source = path.read_text(encoding="utf-8")
        assert "ui.toggle_row(" not in source, str(path.relative_to(REPO_ROOT))
        assert "ui._toggle_row_internal(" not in source, str(path.relative_to(REPO_ROOT))


def test_summary_item_legacy_macro_still_shows_dash_for_old_pages() -> None:
    _components("""
const C = window.APSResourceContract, UI = window.APSWorkbenchUI;
const values = [null, ''].map(value => C.fieldValue('supplier','default_days',value));
expect(values.every(value => value === '未填写'), 'Missing data became zero or a success value');
const node = await render(React.createElement(UI.MetricStrip, null,
  ...values.map((value,index) => React.createElement(UI.Metric,{key:index,label:'旧摘要',value}))));
expect(Array.from(node.querySelectorAll('.wb-metric-value')).every(item => item.textContent === '未填写'));
expect(C.fieldValue('supplier','default_days',0) === '0');
return values;
""")


def test_summary_grid_uses_presenter_items_without_legacy_fallback() -> None:
    items = (UiSummaryItem("严格摘要", "明确值", "说明文字", tone="success"),
             UiSummaryItem("折叠摘要", "未记录", "这是一段说明。", tone="warning", details_summary="查看说明"))
    values = _components("""
const UI = window.APSWorkbenchUI;
const node = await render(React.createElement(UI.MetricStrip, null, ...data.map((item,index) =>
  React.createElement(UI.Metric, {key:index,label:item.label,value:item.value,tone:item.tone,
    helper:item.details_summary ? React.createElement('details', null,
      React.createElement('summary',null,item.details_summary), item.desc) : item.desc}))));
const values = Array.from(node.querySelectorAll('.wb-metric-value')).map(item => item.textContent);
expect(JSON.stringify(values) === JSON.stringify(data.map(item => item.value)));
expect(node.textContent.includes('严格摘要') && node.textContent.includes('折叠摘要'));
expect(node.querySelector('summary').textContent === '查看说明');
expect(!node.querySelector('details').open);
return values;
""", data=[item.__dict__ for item in items])
    assert values == ["明确值", "未记录"]


def test_presenterized_pages_do_not_bypass_summary_item_values() -> None:
    values = _components("""
const data = {metrics:{counts:{total:0,active:null,low_stock:null,inactive:2},issues:[],basis:{}}};
const node = await render(React.createElement(window.ResourceMetrics,{node:'material',data}));
const values = Array.from(node.querySelectorAll('.wb-metric-value')).map(item => item.textContent);
expect(JSON.stringify(values) === JSON.stringify(['0','暂无数据','未设阈值','2']));
return values;
""")
    assert values == ["0", "暂无数据", "未设阈值", "2"]
    for path in ("frontend/workbench/app/BatchDetail.jsx", "frontend/workbench/app/SystemLive.jsx",
                 "frontend/workbench/app/SystemMaintenanceConfig.jsx"):
        source = _read(path)
        assert "ui.summary_item(" not in source and "ui.summary_grid(" not in source


def test_business_toggle_routes_use_order_independent_form_parsers() -> None:
    route_contracts = {
        "web/routes/system_backup.py": (
            'form_yes_no_value(request.form, "auto_backup_enabled")',
            'form_yes_no_value(request.form, "auto_backup_cleanup_enabled")',
        ),
        "web/routes/system_logs.py": (
            'form_yes_no_value(request.form, "auto_log_cleanup_enabled")',
        ),
        "web/routes/domains/scheduler/scheduler_config.py": (
            "_SCHEDULER_CONFIG_TOGGLE_FIELDS",
            'form_yes_no_value(form, key)',
        ),
        "web/routes/system_plugins.py": (
            'form_yes_no_value(request.form, "enabled", default="no")',
        ),
        "web/routes/process_parts.py": (
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_run.py": (
            'form_optional_toggle_bool(request.form, "enforce_ready")',
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_batches.py": (
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/domains/scheduler/scheduler_week_plan.py": (
            'form_optional_toggle_bool(request.form, "enforce_ready")',
            'form_toggle_bool(request.form, "strict_mode")',
        ),
        "web/routes/process_excel_routes.py": (
            'form_toggle_bool(request.form, "strict_mode")',
            '"excelImportStrictMode"',
        ),
        "web/routes/domains/scheduler/scheduler_excel_batches.py": (
            'form_toggle_bool(request.form, "strict_mode")',
            'form_toggle_bool(request.form, "auto_generate_ops", default=False)',
            '"batchImportStrictMode"',
            '"batchImportAutoOps"',
        ),
    }
    for rel_path, markers in route_contracts.items():
        source = _read(rel_path)
        for marker in markers:
            assert marker in source, f"{rel_path} 缺少 {marker}"

    excel_utils_source = _read("web/routes/excel_utils.py")
    assert "strict_mode_enabled" not in excel_utils_source
