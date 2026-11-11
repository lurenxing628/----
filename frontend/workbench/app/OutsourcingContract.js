import APSWorkbenchTransport from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';

const T = APSWorkbenchTransport, BASE = '/api/workbench/v1/outsourcing', COMMANDS = '/api/workbench/v1/commands/';
const states = { in_transit: '在途', returned: '已回厂', awaiting_confirmation: '待确认' };
const fields = ['sent', 'planned', 'returned', 'confirmedState'];
const labels = { sent: '实际发出', planned: '计划回厂', returned: '实际回厂', confirmedState: '确认状态' };
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
const text = v => typeof v === 'string' && v.length > 0;

function check(ok, message = '外协读到的数据不完整，请刷新后重试。') { if (!ok) throw new Error(message); }

function time(v) {
  if (typeof v !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(v)) return false;
  const n = v.match(/\d+/g).map(Number), date = new Date(0);
  date.setUTCFullYear(n[0], n[1] - 1, n[2]); date.setUTCHours(n[3], n[4], n[5], 0);
  return n[0] > 0 && date.toISOString().slice(0, 19) === v;
}

function stamp(v) { const s = typeof v === 'string' && v.length === 16 ? v + ':00' : v; check(time(s), '请按 2026-09-13 08:30 这样填写日期和时间。'); return s; }

// 回厂事实与外协目标：校验只在读取、预检、回执、本机记录和表单这些边界各做一次；已校验的值用 factValues / targetValues 直接取字段。
const factValues = v => Object.fromEntries(fields.map(k => [k, v[k]]));

function facts(v) {
  check(object(v) && fields.every(k => Object.prototype.hasOwnProperty.call(v, k)) && time(v.sent) && time(v.planned)
    && (v.returned === null || time(v.returned)) && Object.prototype.hasOwnProperty.call(states, v.confirmedState));
  check(v.planned >= v.sent && (v.returned === null || v.returned >= v.sent), '计划回厂和实际回厂不能早于实际发出。');
  check((v.confirmedState === 'returned') === (v.returned !== null), '已回厂状态和实际回厂时间要一起填。还没回厂就点「清除实际回厂」。');
  return true;
}

// 登记用的目标只认类型、批次、供应商和排好序的工序编号。
const targetValues = t => ({ kind: t.kind, batch_ref: t.batch_ref, supplier_ref: t.supplier_ref, operation_refs: t.operation_refs.slice().sort() });

function target(t) {
  check(object(t) && ['single', 'merged'].includes(t.kind) && ref(t.batch_ref) && ref(t.supplier_ref) && Array.isArray(t.operation_refs)
    && t.operation_refs.length >= 1 && t.operation_refs.length <= 200 && t.operation_refs.every(ref) && new Set(t.operation_refs).size === t.operation_refs.length
    && (t.kind === 'single') === (t.operation_refs.length === 1), '单工序要选 1 道，合并发出至少选 2 道，而且不能重复。');
  return targetValues(t);
}

function query(kind, value) {
  const allowed = ['page', 'size', 'snapshot_ref'].concat(kind === 'receipts' ? ['status'] : []);
  if (kind === 'targets') allowed.push('query');
  const q = { page: 1, size: 10, ...value };
  check(object(value) && Object.keys(q).every(k => allowed.includes(k)) && Number.isSafeInteger(q.page) && q.page >= 1 && q.page <= 1000000
    && Number.isSafeInteger(q.size) && q.size >= 1 && q.size <= 100
    && (q.status === undefined || ['all', 'awaiting', 'overdue', 'returned'].includes(q.status)) && (q.snapshot_ref === undefined || text(q.snapshot_ref))
    && (q.query === undefined || typeof q.query === 'string' && q.query.length <= 200 && !q.query.includes('\0'))
    && (q.page === 1 || text(q.snapshot_ref)), '外协的筛选或翻页条件无效，当前范围没有变化。请重新选择。'); return q;
}

// 信封已由 transport 校验；外协列表翻页钉在这次读取的数据版本上，所以列表读取的数据版本不能为空。
function envelope(v, q) {
  check(text(v.meta.snapshot_ref));
  if (q.snapshot_ref) check(q.snapshot_ref === v.meta.snapshot_ref, '数据已更新，请刷新后重试。刚才的选择已保留。'); return v.data;
}

function page(p, q) {
  check(object(p) && p.number === q.page && p.size === q.size, '读到的页码和数量与当前范围不一致，请刷新后重试。');
}

function catalog(v, kind, q, selected) {
  const d = envelope(v, q);
  if (kind === 'targets' || kind === 'receipts') {
    page(d.page, q);
  } else {
    check(object(d.item) && d.item.outsourcing_ref === selected, '详情或历史和所选登记对不上，页面没有切换。请刷新后重试。');
    if (kind === 'history') {
      check(object(d.history));
      page(d.history.page, q);
    }
  }
  return v;
}

function previewResult(v, input) {
  const d = v.data;
  // 新登记的 input 只有 target、没有 outsourcing_ref，后端回显 null。
  check(equal(d.input, input) && d.outsourcing_ref === (input.outsourcing_ref ?? null) && d.can_confirm === true
    && (!input.target || equal(targetValues(d.target), input.target)));
  return v;
}

function receipt(v, intent) {
  const d = v && v.data;
  check(v && v.ok === true && v.result === 'committed' && object(d)
    && (!intent.input.outsourcing_ref || d.outsourcing_ref === intent.input.outsourcing_ref)
    && equal(factValues(d), intent.after) && equal(targetValues(d.target), targetValues(intent.target))
    && d.declared_operator === intent.input.declared_operator && d.reason === intent.input.reason,
    '保存结果和这条外协登记对不上，结果还不确定。请点「查询结果」，不要重复提交。');
  return v;
}

// 外协读取、预检、提交和回执查询都按 30 秒等待；提交失败的结果编号指向通用命令回执。
async function read(kind, args, selected, signal) {
  const q = query(kind, args); check(['targets', 'receipts', 'detail', 'history'].includes(kind));
  if (['detail', 'history'].includes(kind)) check(ref(selected));
  const path = ['targets', 'receipts'].includes(kind) ? '/' + kind : '/receipts/' + selected + (kind === 'history' ? '/history' : '');
  return catalog(await T.read(BASE + path, q, { signal, timeout: 30000 }), kind, q, selected);
}

async function preview(input) { return previewResult(await T.preview(BASE + '/receipts/preview', { input }, { timeout: 30000 }), input); }

async function command(intent, token) {
  return receipt(await T.command(BASE + '/receipts', { input: intent.input, request_key: intent.request_key, write_token: token },
    { timeout: 30000, expect: COMMANDS + intent.request_key }), intent);
}

async function lookup(intent) {
  const v = await T.lookup(COMMANDS + intent.request_key, {}, { timeout: 30000 });
  check(object(v) && ['recorded', 'not_observed'].includes(v.state));
  if (v.state === 'not_observed') return null;
  return receipt(v.receipt, intent);
}

const OutsourcingContract = { states, fields, labels, object, ref, text, time, check, equal, stamp, facts, factValues, target, targetValues, receipt, read, preview, command, lookup };

export { OutsourcingContract, states, fields, labels, object, ref, text, time, check, equal, stamp, facts, factValues, target, targetValues, receipt, read, preview, command, lookup };
export default OutsourcingContract;
