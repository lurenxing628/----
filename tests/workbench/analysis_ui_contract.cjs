'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(x => x !== null && x !== false && x !== undefined) });
const react = { createElement: h, Fragment: 'fragment', createContext: () => ({}) };
const window = { ResourceControls: { Button: 'button', Issues: 'issues' }, WorkbenchFormat: { dateTime: v => v == null ? '未知' : v.replace('T', ' '), date: v => v == null ? '未知' : v.slice(0, 10), number: v => v == null ? '未知' : String(v), hours: v => v == null ? '未知' : String(v) + ' h' }, WorkbenchReference: 'reference', WorkbenchDetailPanel: 'detail-panel', WorkbenchListControls: { Pager: 'pager', EmptyState: 'empty-state' } };
// 值班台来源依据的按项词表取自全站词表，这里加载真实的 WorkbenchTerms。
vm.runInNewContext(fs.readFileSync(path.join(app, 'WorkbenchTerms.js'), 'utf8'), { window });
const controlMocks = window.ResourceControls;
const names = ['ResourceControls.jsx', 'DashboardContract.js', 'DashboardEvidence.jsx', 'DashboardPanels.jsx', 'MasterOverviewContract.js', 'MasterOverviewTable.jsx', 'MasterOverviewDetail.jsx', 'MasterOverviewWorkspace.jsx'];
const source = names.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: source });
for (const file of built.outputs) {
  vm.runInNewContext(file.code, { React: react, window });
  if (file.path.endsWith('ResourceControls.jsx')) window.ResourceControls = { ...controlMocks, MetricValue: window.ResourceControls.MetricValue };
}
function expand(node) { if (!node || typeof node !== 'object') return node; if (typeof node.type === 'function') return expand(node.type({ ...node.props, children: node.children })); return { ...node, children: node.children.map(expand) }; }
function text(node) { if (node == null) return ''; if (typeof node !== 'object') return String(node); return node.children.map(text).join(' '); }
function nodes(node) { return !node || typeof node !== 'object' ? [] : [node, ...node.children.flatMap(nodes)]; }
const noop = () => {}, skeletons = tree => nodes(tree).filter(node => node.props.className === 'wb-metric-placeholder');
const values = tree => nodes(tree).filter(node => node.type === 'strong').map(text);
const dashboard = props => expand(h(window.DashboardPanels.Overview, { onCategory: noop, onAnalysis: noop, ...props }));
const firstDashboard = dashboard({ loading: true });
assert.deepEqual(values(firstDashboard), Array(7).fill(''), '首读数值区只展示占位，不先写未读取、未知或0');
assert.equal(skeletons(firstDashboard).length, 12, '七个值位及五个动态备注位均为静态骨架');
assert(skeletons(firstDashboard).every(node => node.props['aria-hidden'] === 'true'));
const dashboardData = { categories: Object.fromEntries(['delivery', 'actual', 'external', 'downtime', 'material'].map(key => [key, {
  state: 'loaded', risk_count: 0, closed_count: 0, known_risk_count: 0, awaiting_return_count: 0, overdue_count: 0, awaiting_confirmation_count: 0
}])) };
const analysisPending = dashboard({ data: dashboardData, analysisLoading: true });
assert.deepEqual(values(analysisPending), ['0', '', '0', '0', '0', '0', ''], '主请求完成后只保留分析请求的两个骨架');
assert.equal(skeletons(analysisPending).length, 2);
const firstFailure = dashboard({ error: new Error('read failed') });
assert.deepEqual(values(firstFailure), Array(7).fill('读取失败'));
assert.equal(skeletons(firstFailure).length, 0, '主请求失败也终止等待主请求的分析卡片骨架');
const analysisFailure = dashboard({ data: dashboardData, analysisError: new Error('analysis failed') });
assert.deepEqual(values(analysisFailure), ['0', '读取失败', '0', '0', '0', '0', '读取失败']);
const dashboardUnknown = dashboard({ data: { categories: { ...dashboardData.categories, external: { ...dashboardData.categories.external, risk_count: null } } },
  analysis: { pressure: { count: 0 }, pending: { count: 0 } } });
assert.deepEqual(values(dashboardUnknown), ['0', '0', '0', '未知', '0', '0', '0'], '读取成功后的真实0与业务未知保留');
const masterScope = window.APSMasterOverviewContract.scope({}), master = window.MasterOverviewWorkspace;
const statistics = props => expand(h(master.Statistics, { scope: masterScope, domainsId: 'counts', onDomain: noop, ...props }));
const firstMaster = statistics({ pending: true });
assert.deepEqual(values(firstMaster), Array(12).fill(''));
assert.equal(skeletons(firstMaster).length, 20, '资料总览四个总数、八个类别及其备注全部采用同一占位规则');
const firstTabs = expand(h(master.ListTabs, { scope: masterScope, pending: true, onChange: noop }));
assert.equal(skeletons(firstTabs).length, 2); assert(!text(firstTabs).includes('未读取'));
const masterFailure = statistics({ error: new Error('read failed') });
assert.deepEqual(values(masterFailure), Array(12).fill('读取失败')); assert.equal(skeletons(masterFailure).length, 0);
const overview = { complete: true, stats: { entities: 0, issues: 0, affected: 0, relations: 0 },
  domains: window.APSMasterOverviewContract.domains.map(([id]) => ({ id, loaded: true, count: 0, attention: 0, unknown: 0 })) };
const masterRefreshing = statistics({ overview, pending: true });
assert.deepEqual(values(masterRefreshing), Array(12).fill('0')); assert.equal(skeletons(masterRefreshing).length, 0, '刷新保留现有全局summary');
assert(nodes(masterRefreshing).filter(node => node.props['aria-busy'] === true).length === 2);
const masterPartial = statistics({ overview: { ...overview, complete: false, stats: { ...overview.stats, relations: null },
  domains: overview.domains.map((domain, index) => index ? domain : { ...domain, loaded: false, count: null }) } });
assert.equal(values(masterPartial)[3], '未知'); assert.equal(values(masterPartial)[4], '未读取');
assert(text(masterPartial).includes('已读取资料')); assert.equal(skeletons(masterPartial).length, 0, '返回后的实际来源缺口不是loading');
const sample = { kind: 'delivery', plan_ref: 'a'.repeat(48), request_key: 'c'.repeat(48), code: 'qualification.empty',
  evaluation: { delay_days: 0, planned_finish: null }, requirements: [{ label: '原料', business_code: 'M-001', required_quantity: 0, available_quantity: null }] };
const tree = expand(h(window.DashboardEvidence.Structure, { value: sample }));
assert.match(text(tree), /0/); assert.match(text(tree), /未知/); assert.match(text(tree), /原料/);
assert(!text(tree).includes('a'.repeat(48)), '完整引用不能进入普通可见字段');
assert(!text(tree).includes('c'.repeat(48)) && !text(tree).includes('qualification.empty'), '请求键与规则码只能进编号折叠区');
assert.match(text(tree), /M-001/); assert.match(text(tree), /交期风险/); assert(!text(tree).includes('delivery'), '来源类型显示中文类别，不显示内部取值');
const references = nodes(tree).filter(row => row.type === 'reference');
assert(references.some(row => Object.values(row.props.entries || {}).includes('a'.repeat(48))), '完整引用必须保留在编号折叠区');
assert(references.some(row => Object.values(row.props.entries || {}).includes('c'.repeat(48))), '请求键必须保留在编号折叠区');
assert(!references.some(row => Object.values(row.props.entries || {}).includes('M-001')), '业务编号不是技术引用，不得折叠');
assert(!nodes(tree).some(row => row.type === 'pre'), '来源字段必须结构化呈现');
const page = { number: 3, pages: 8, total: 15, size: 2 }, onPage = () => {}, onSize = () => {};
const pager = window.DashboardPanels.Pager({ page, onPage, onSize });
assert.equal(pager.props.page, page, '恢复范围的页码与总数原样传入');
assert.deepEqual(Array.from(pager.props.sizes), [2, 10, 20, 50, 100], '服务端允许的历史size不可丢失');
assert.equal(pager.props.onSize, onSize);
const detailPage = window.MasterOverviewTable.Pager({ page: { number: 1, pages: 1, total: 0, size: 10 }, detail: true, onPage });
assert.deepEqual(Array.from(detailPage.props.sizes), [10]);
const masterPager = window.MasterOverviewTable.Pager({ page: { number: 1, pages: 1, total: 0, size: 20 }, onPage, onSize });
assert.deepEqual(Array.from(masterPager.props.sizes), [20, 50, 100]);
const onClose = () => {};
const item = { item_ref: 'b'.repeat(48), subject: '批次 B1', category: 'delivery', risk: { active: true, message: '预计晚交' }, handling: { status: 'new' }, source: {}, navigation: [] };
const detail = window.DashboardPanels.Detail({ item, onClose });
assert.equal(detail.type, 'detail-panel'); assert.equal(detail.props.detailKey, item.item_ref); assert.equal(detail.props.onClose, onClose);
assert.equal(window.MasterOverviewDetail({ selected: null }), null, '关闭后不遗留空详情列');
const missing = { issues: [{ code: 'no_official_plan', message: '当前没有正式计划' }], state: 'no_official_plan', evaluation_gaps: [], risk_count: null, known_risk_count: 0 };
const gaps = expand(window.DashboardPanels.Gaps({ categories: { delivery: missing, actual: missing, downtime: missing }, selected: 'all' }));
assert.equal(nodes(gaps).filter(node => node.type === 'issues').length, 1);
assert.equal(nodes(gaps).find(node => node.type === 'issues').props.issues.length, 1, '相同原因只出现一次');
assert.match(text(gaps), /交期风险/); assert.match(text(gaps), /执行偏差/); assert.match(text(gaps), /停机影响/);
let prevented = false, switched = false;
const tabs = window.MasterOverviewTable.Tabs({ values: [['issues', '待维护项'], ['entities', '实体清单']], value: 'issues', onChange: () => { switched = true; }, label: '清单类型' });
tabs.children[0].props.onKeyDown({ key: 'ArrowLeft', altKey: true, preventDefault: () => { prevented = true; } });
assert.equal(prevented, false); assert.equal(switched, false, '浏览器返回快捷键不得被页签吞掉');
// 同一个取值在不同项里按各自的词表显示：齐套的 partial 是“部分齐套”，执行状态的 complete 是“已完工”，记录完整性的 complete 是“完整”；
// 物料数量按批次详情的口径显示全部小数，0.004 不能读成 0.00。这一段用真实的 WorkbenchFormat。
const real = { ResourceControls: window.ResourceControls, DashboardContract: window.DashboardContract, WorkbenchReference: 'reference' };
for (const name of ['WorkbenchFormat.js', 'WorkbenchTerms.js']) vm.runInNewContext(fs.readFileSync(path.join(app, name), 'utf8'), { window: real });
vm.runInNewContext(built.outputs.find(file => file.path.endsWith('DashboardEvidence.jsx')).code, { React: react, window: real });
const show = real.DashboardEvidence.display;
assert.equal(show('partial', 'ready_status'), '部分齐套');
assert.equal(show('partial', 'execution_state'), '部分完成');
assert.equal(show('complete', 'execution_state'), '已完工');
assert.equal(show('complete', 'data_quality'), '完整');
assert.equal(show('legacy_incomplete', 'data_quality'), '历史资料不完整');
assert.equal(show('on_time', 'risk'), '预计按期');
assert.equal(show(0.004, 'required_quantity'), '0.004');
assert.equal(show(2.0005, 'available_quantity'), '2.0005');
assert.equal(show(1.5, 'overlap_hours'), '1.50');
const materials = text(expand(h(real.DashboardEvidence.Structure, { value: { requirements: [{ label: '原料', required_quantity: 0.004, ready_status: 'partial' }] } })));
assert.match(materials, /0\.004/); assert.match(materials, /部分齐套/); assert(!materials.includes('部分完成'), materials);
const note = text(expand(h(real.DashboardEvidence.Evidence, { source: { kind: 'execution_deviation', execution_state: 'complete', data_quality: 'complete' } })));
assert.match(note, /执行状态：\s*已完工\s*·\s*记录完整性\s*：\s*完整/, note);
// 值班台候选对比和影响批次：不足 0.01 的非零差值、超期时长写“不到 0.01”，不显示成 0；按期与计划详情同一叫法。
real.DashboardTimelineModel = { number: (v, options) => real.WorkbenchFormat.number(v, options) };
real.ResourceControls = { ...window.ResourceControls, Modal: 'modal' };
const panels = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: ['DashboardAnalysisPanels.jsx', 'DashboardCandidatePanels.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) });
for (const file of panels.outputs) vm.runInNewContext(file.code, { React: react, window: real });
const P = real.DashboardCandidatePanels, A = real.DashboardAnalysisPanels;
assert.deepEqual([0.004, -0.001, 0.0003].map(v => P.signed(v)), ['+不到 0.01', '-不到 0.01', '+不到 0.01']);
assert.deepEqual([0, 2, -0.5, null].map(v => P.signed(v)), ['0', '+2', '-0.50', '未知']);
assert.equal(P.signed(0.00004, 100), '+不到 0.01');
assert.equal(P.number(0.004), '不到 0.01');
for (const R of [P.risk, A.risk]) {
  assert.equal(R({ risk: 'overdue', delay_hours: 0.004 }), '超期不到 0.01 小时');
  assert.equal(R({ risk: 'overdue', delay_hours: 1.5 }), '超期 1.50 小时');
  assert.equal(R({ risk: 'on_time', delay_hours: 0 }), '预计按期');
  assert.equal(R({ risk: 'unknown', delay_hours: null }), '暂无数据');
}
assert.equal(A.value(0.004), '不到 0.01');
console.log('analysis UI source evidence contracts passed');
