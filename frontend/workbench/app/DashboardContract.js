import APSWorkbenchTransport from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import DashboardAnalysisAPI from './DashboardAnalysisAPI.js';

const T = APSWorkbenchTransport, BASE = '/api/workbench/v1/dashboard', RECEIPTS = '/api/workbench/v1/commands/';
const READ_TIMEOUT_MS = 60000;
// 同一页面的列表读取共用一条读取通道：新的筛选会让后端放弃这条通道上还没读完的旧请求。
const LANE = 'dashboard-list:' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
const categories = { all: '全部风险', delivery: '交期风险', actual: '执行偏差', external: '外协回厂', downtime: '停机影响', material: '齐套缺口', candidate: '候选方案待确认' };
const statuses = { new: '待分析', following: '跟进中', awaiting_verification: '待验证', closed: '已关闭' };
const states = { loaded: '已读取', no_data: '无数据', no_official_plan: '无正式计划', unavailable: '暂无数据', not_applicable: '未指定交期' };
const fields = ['owner', 'deadline', 'action', 'remark', 'completed_at', 'completion_evidence', 'evidence_reference_text', 'evidence_ref'];
const labels = { status: '处置状态', owner: '责任人', deadline: '责任期限', action: '处置行动', remark: '原因说明', completed_at: '完成时间', completion_evidence: '具体完成结果', evidence_reference_text: '凭据说明', evidence_ref: '已核验附件编号' };
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
const text = v => typeof v === 'string' && v.length > 0;
const count = v => Number.isSafeInteger(v) && v >= 0;

function check(ok, message = '值班台读到的数据不完整，请刷新后重试。') { if (!ok) throw new Error(message); }

function scope(value) {
  const q = { category: 'all', status: 'all', query: '', sort: 'subject', direction: 'asc', page: 1, size: 20, source: 'production', ...value };
  check(object(value) && Object.keys(q).every(k => ['category', 'status', 'query', 'sort', 'direction', 'page', 'size', 'source', 'snapshot_ref'].includes(k))
    && Object.prototype.hasOwnProperty.call(categories, q.category) && ['all', 'open', ...Object.keys(statuses)].includes(q.status)
    && typeof q.query === 'string' && q.query.length <= 200 && !q.query.includes('\0') && ['subject', 'category', 'status', 'deadline'].includes(q.sort)
    && ['asc', 'desc'].includes(q.direction) && count(q.page) && q.page >= 1 && q.page <= 100000 && count(q.size) && q.size >= 1 && q.size <= 100
    && q.source === 'production' && (q.snapshot_ref === undefined || text(q.snapshot_ref)), '值班台筛选条件无效，当前筛选没有变化。请重新选择筛选条件。');
  q.query = q.query.trim(); return q;
}

// 处置状态的唯一校验点（本机记录读取时核对）；baseHandling 只从处置里取基础字段。
function handling(h) { check(object(h) && Object.prototype.hasOwnProperty.call(statuses, h.status) && fields.every(k => h[k] === null || typeof h[k] === 'string')); return h; }
const baseHandling = h => Object.fromEntries(['status', ...fields].map(k => [k, h[k]]));

// 信封已由 transport 校验；值班台翻页和详情都钉在这次读取的数据版本上，所以数据版本不能为空。
function envelope(v, s) {
  check(text(v.meta.snapshot_ref));
  if (s) {
    check(!s.snapshot_ref || s.snapshot_ref === v.meta.snapshot_ref, '数据已更新，请刷新后重试。刚才的选择已保留。');
    const expected = { kind: 'dashboard', ...s }; delete expected.page; delete expected.snapshot_ref;
    check(equal(v.data.scope, expected) && v.data.as_of === v.meta.as_of, '读到的数据和当前筛选不一致，请刷新后重试。');
  }
  return v.data;
}

function pagination(p, q) { check(object(p) && p.number === q.page && p.size === q.size); }

function catalog(v, query) {
  const q = scope(query), d = envelope(v, q);
  pagination(d.page, q);
  return v;
}

function detailResult(v, q, selected, historyPage) {
  const s = scope(q), d = envelope(v, s);
  check(object(d.item) && d.item.item_ref === selected, '详情内容和所选条目不一致，页面没有切换。请刷新后重试。');
  if (historyPage !== undefined) {
    check(object(d.history));
    pagination(d.history.page, { page: historyPage, size: s.size });
  }
  return v;
}

function expected(intent) {
  const h = { ...intent.before };
  if (intent.action === 'reopen') { h.status = 'following'; h.remark = intent.input.reason; ['completed_at', 'completion_evidence', 'evidence_reference_text', 'evidence_ref'].forEach(k => { h[k] = null; }); }
  else { h.status = intent.input.target_status; fields.forEach(k => { if (Object.prototype.hasOwnProperty.call(intent.input, k)) h[k] = intent.input[k]; }); }
  return h;
}

function receipt(v, intent) {
  const d = v && v.data; check(v && v.ok === true && ['committed', 'unchanged'].includes(v.result) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
    && object(d) && d.item_ref === intent.item_ref
    && equal(d.handling, expected(intent)) && equal(d.source, intent.source) && equal(d.risk, intent.risk)
    && (v.result === 'committed' ? ref(d.history_ref) : d.history_ref === null), '保存结果和这条处置对不上，结果还不确定。请点「查询结果」，不要重复提交。'); return v;
}

// 值班台读取（含回执查询）按 60 秒等待，超时说清楚是值班台读取；写入按 30 秒等待。
async function wait(load) {
  try { return await load(); }
  catch (error) { if (error.code === 'timeout') error.message = '值班台读取超时（超过 60 秒），请重试或缩小筛选范围。'; throw error; }
}

function read(path, query, signal, lane) { return wait(() => T.read(path, query, { signal, timeout: READ_TIMEOUT_MS, lane })); }

async function list(q, signal) {
  const value = catalog(await read(BASE, q, signal, LANE), q);
  try {
    if (value.data.analysis_error !== null) check(text(value.data.analysis_error) && value.data.analysis === null);
    else DashboardAnalysisAPI.validate({ ...value, data: value.data.analysis }, value.data.plan && value.data.plan.plan_ref, { section: 'overview', page: 1, size: 20 });
  } catch (error) {
    value.data.analysis = null;
    value.data.analysis_error = '影响分析读取失败：' + error.message;
  }
  return value;
}

async function detail(selected, q, historyPage, signal) {
  check(ref(selected)); const args = { ...q }; if (historyPage !== undefined) args.history_page = historyPage;
  return detailResult(await read(BASE + '/items/' + selected + (historyPage === undefined ? '' : '/history'), args, signal), q, selected, historyPage);
}

async function command(intent, token) {
  return receipt(await T.command(BASE + '/items/' + intent.item_ref + '/' + intent.action, { request_key: intent.request_key, write_token: token, input: intent.input },
    { timeout: 30000, expect: RECEIPTS + intent.request_key }), intent);
}

async function lookup(intent) {
  const v = await wait(() => T.lookup(RECEIPTS + intent.request_key, {}, { timeout: READ_TIMEOUT_MS }));
  check(object(v) && ['recorded', 'not_observed'].includes(v.state));
  if (v.state === 'not_observed') return null;
  return receipt(v.receipt, intent);
}

const DashboardContract = {
  categories, statuses, states, fields, labels, object, ref, text, equal, check, scope, handling, baseHandling, catalog, expected, receipt,
  read, list, detail, command, lookup
};

export {
  DashboardContract, categories, statuses, states, fields, labels, object, ref, text, equal, check, scope, handling, baseHandling, catalog, expected, receipt,
  read, list, detail, command, lookup
};
export default DashboardContract;
