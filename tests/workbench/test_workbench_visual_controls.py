"""Regression coverage for visible SVGs and compact workbench composition."""

from tests._support.workbench_browser_contract import browser_contract


def test_shared_icons_and_batch_search_have_visible_shapes(app_client):
    result = browser_contract("""
const names = ['files', 'list-checks', 'lock', 'git-compare-arrows', 'eye', 'rotate-ccw', 'square-pen'];
const area = await render(React.createElement('div', {}, names.map(name =>
  React.createElement(window.ResourceControls.Icon, {name, key:name}))));
const icons = Array.from(area.querySelectorAll('svg'));
expect(icons.length === names.length, 'All requested icons must render');
icons.forEach((icon, index) => {
  const box = icon.getBBox();
  expect(box.width > 0 && box.height > 0, names[index] + ' rendered an empty SVG');
});
const search = document.querySelector('.batch-workspace label.search');
expect(search && search.querySelector('svg path'), 'Batch search must render its leading icon');
const input = search.querySelector('input'), a = input.getBoundingClientRect(), b = search.querySelector('svg').getBoundingClientRect();
expect(b.left >= a.left && b.right <= a.left + parseFloat(getComputedStyle(input).paddingLeft),
  'Search icon must stay inside the input padding');
expect(b.top >= a.top && b.bottom <= a.bottom, 'Search icon must align vertically inside input');
return {icons: icons.length};
""", app=app_client.application, path="/workbench?view=batches")
    assert result == {"icons": 7}


def test_critical_chain_keeps_nodes_and_relationships_in_one_scroll_row(app_client):
    result = browser_contract("""
const nodes = Array.from({length:6}, (_,index) => ({task_ref:String(index), batch_id:'BATCH-2026-' + index,
  sequence:index + 1, process_label:'精加工', start:'2026-09-08T08:00:00', end:'2026-09-08T10:00:00'}));
const chain = {state:'available', mode:'full', makespan_end:'2026-09-08T10:00:00', nodes,
  task_refs:nodes.map(n => n.task_ref), edges:nodes.slice(1).map(() =>
    ({edge_type:'operator',reason:'资源前驱（人员）',gap_minutes:0}))};
const area = await render(React.createElement('div', {className:'fg-live',style:{width:'900px'}},
  React.createElement(window.ActualGanttControls.Chain, {chain, model:{items:nodes.map(task => ({task}))}, onLocate:()=>{}})));
const flow = area.querySelector('.fg-chain-flow'), buttons = Array.from(area.querySelectorAll('[data-chain-node]'));
const tops = buttons.map(button => button.getBoundingClientRect().top);
expect(buttons.length === 6 && Math.max(...tops) - Math.min(...tops) < 1, 'Chain nodes must not wrap');
expect(flow.scrollWidth > flow.clientWidth && getComputedStyle(flow).overflowX === 'auto', 'Long chain must scroll within its own row');
buttons.forEach(button => {
  const icon = button.querySelector('svg').getBoundingClientRect(), label = button.querySelector('.fg-chain-node-label').getBoundingClientRect();
  expect(icon.right <= label.left && icon.top < label.bottom && icon.bottom > label.top,
    'Locate icon must sit beside node text');
});
expect(area.querySelectorAll('[data-chain-edge-reason]').length === 5, 'Keep every relationship');
expect(getComputedStyle(area.querySelector('.fg-chain-edge-label svg')).strokeDasharray !== 'none',
  'Resource dependencies use a dashed connector');
expect(area.textContent.includes('近似'), 'Preserve the analysis qualification');
return {nodes:buttons.length, edges:5};
""", app=app_client.application, path="/workbench/trial")
    assert result == {"nodes": 6, "edges": 5}


def test_dashboard_gap_table_is_collapsed_and_keeps_all_rows_in_a_five_row_view(app_client):
    result = browser_contract("""
const message = '关联资料缺失，请联系维护人员。';
const gaps = Array.from({length:10}, (_,index) => ({source_ref:'source-' + index, code:'identity_missing',
  subject:'合并显示文本', message, operation:{code:'OP（2026）_' + index, name:'表处理（外协）'}}));
const area = await render(React.createElement('div', {className:'dashboard-live',style:{width:'900px'}},
  React.createElement(window.DashboardPanels.Gaps, {categories:{external:{issues:[],unknown_count:10,evaluation_gaps:gaps}},selected:'external'})));
const details = area.querySelector('details');
expect(!details.open && details.getBoundingClientRect().height < 80, 'Keep details collapsed to a single summary row initially');
details.open = true; await new Promise(resolve => requestAnimationFrame(resolve));
const scroll = area.querySelector('.dy-gap-table-scroll'), table = scroll.querySelector('table');
const rows = Array.from(table.tBodies[0].rows), header = table.tHead.getBoundingClientRect().height;
expect(rows.length === 10 && table.tHead.rows[0].cells.length === 2, 'Keep all operations in the two-column table');
expect(rows[0].cells[0].textContent === 'OP（2026）_0' && rows[0].cells[1].textContent === '表处理（外协）', 'Read original code and name separately');
expect(area.querySelectorAll('.dy-gap-reason').length === 1, 'Explain the shared cause once');
expect(scroll.clientHeight <= header + rows[0].getBoundingClientRect().height * 5 + 1, 'Visible area is at most five rows plus header');
expect(scroll.scrollHeight > scroll.clientHeight && getComputedStyle(scroll).overflowY === 'auto', 'Remaining rows scroll inside the table');
scroll.scrollTop = scroll.scrollHeight; await new Promise(resolve => requestAnimationFrame(resolve));
const end = rows[9].getBoundingClientRect(), frame = scroll.getBoundingClientRect();
expect(end.bottom <= frame.bottom + 1 && end.top >= frame.top, 'The last operation is reachable');
return {rows:rows.length, columns:2};
""", app=app_client.application, path="/workbench?view=dashboard")
    assert result == {"rows": 10, "columns": 2}
