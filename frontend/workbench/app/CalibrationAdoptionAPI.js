import T from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import C from './CalibrationAPI.js';
import { object, ref48, failure, checker } from './shared/contract/kit.js';

const BASE = '/api/workbench/v1/calibration/';
const key = v => typeof v === 'string' && /^calibration-[a-f0-9]{48}$/.test(v);

const INVALID = '读到的采用结果不完整或来源不一致，没有确认采用。';
// 采用回执与回执查询都在命令发出之后：核对不过时结果未知，本机待确认记录不能清。
const check = checker(INVALID), checkResult = checker(INVALID, { committed: 'unknown' });

// 采用表单的唯一校验点：原因和经办人两项必填，校验后去掉首尾空白；字数等值域由后端校验，422 带字段路径。
// 两项必填的本地错误与后端同一套路径（reason / declared_operator），标在对应输入框上。
function input(draft) {
  [['reason', '请填写采用原因。'], ['declared_operator', '请填写经办人。']].forEach(([path, message]) => {
    if (!(typeof draft[path] === 'string' && draft[path].trim())) throw failure(message, { fields: [{ path, message }] });
  });
  return { reason: draft.reason.trim(), declared_operator: draft.declared_operator.trim() };
}

// 确认采用的负载由已校验的填写内容加上用户确认构成。
const confirmation = filled => ({ ...filled, confirm: true });

// 采用绑定的纯投影：本机记录读取边界按 CalibrationAPI.validBinding 校验，预检结果按 original 严格相等核对。
const binding = row => Object.fromEntries(C.bindingFields.map(k => [k, row[k]]));

// filled 是 input() 规整过的填写内容，original 是所选模板行的采用绑定。
function previewResult(value, original, filled) {
  const d = value.data;
  check(d.template_operation_ref === original.template_operation_ref && equal(d.input, filled));
  check(object(d.suggestion) && equal(binding(d.suggestion), original), '模板、原定额或完工记录已变化，请点「刷新所选模板」后重新预检。');
  return d;
}

// intent 是本存储读到或刚登记的采用记录，baseline 与 input 都已校验过。
function receipt(value, intent) {
  const d = value && value.data, s = intent.baseline;
  checkResult(value && value.ok === true && value.result === 'committed'
    && typeof value.receipt_ref === 'string' && /^[a-f0-9]{32}$/.test(value.receipt_ref)
    && object(d) && ref48(d.adoption_ref) && d.template_operation_ref === s.template_operation_ref
    && d.request_key === intent.request_key && d.reason === intent.input.reason && d.declared_operator === intent.input.declared_operator && d.confirmed === true);
  return value;
}

// 预检、采用和回执查询都按 30 秒等待；回执还没记下时 lookup 返回 null。
// row 是建议行，filled 是 input() 规整过的填写内容。
async function preview(row, filled, signal) {
  const original = binding(row);
  return previewResult(await T.preview(BASE + original.template_operation_ref + '/adopt-preview', { input: filled }, { signal, timeout: 30000 }), original, filled);
}

// intent 是本存储登记的采用记录（input 已带确认），writeToken 已由 previewResult 核过。
async function adopt(intent, writeToken) {
  return receipt(await T.command(BASE + intent.baseline.template_operation_ref + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: intent.input },
    { timeout: 30000, expect: BASE + intent.baseline.template_operation_ref + '/adopt/receipts/' + intent.request_key }), intent);
}

async function lookup(intent, signal) {
  const value = await T.lookup(BASE + intent.baseline.template_operation_ref + '/adopt/receipts/' + intent.request_key, {}, { signal, timeout: 30000 });
  checkResult(object(value) && ['recorded', 'not_observed'].includes(value.state));
  if (value.state === 'not_observed') return null;
  return receipt(value.receipt, intent);
}

const CalibrationAdoptionAPI = { preview, adopt, lookup, receipt, binding, input, confirmation, check, key, equal };

export { CalibrationAdoptionAPI, preview, adopt, lookup, receipt, binding, input, confirmation, check, key, equal };
export default CalibrationAdoptionAPI;
