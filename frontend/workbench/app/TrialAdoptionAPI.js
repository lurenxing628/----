import T from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import RunAdoptionAPI from './RunAdoptionAPI.js';
import { object, text, nonempty, ref48, token32, checker } from './shared/contract/kit.js';

const BASE = '/api/workbench/v1/trial/scenarios/';
const key = v => text(v) && /^trial-adoption-[a-f0-9]{48}$/.test(v), positive = v => Number.isSafeInteger(v) && v > 0;
const INVALID = '读到的采用数据不完整或对不上，这次没有确认采用。请刷新重试。';
// 采用回执与回执查询都在命令发出之后：核对不过时结果未知，本机待确认记录不能清。
const check = checker(INVALID), checkResult = checker(INVALID, { committed: 'unknown' });
function shape(v, required, optional = []) {
  return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
}
// 采用范围有两种来源：试调详情（source）不带数据上下文，可采用的预检（overview）恒带数据上下文。
// 投影只取这些字段、不校验；overview 在本机存储读取边界先校验再投影。
const scopeFields = v => ({ scenario_ref: v.scenario_ref, draft_ref: v.draft_ref, baseline: v.baseline, task_count: v.task_count, scope_complete: true });
const overviewFields = v => ({ ...scopeFields(v), data_context_ref: v.data_context_ref });
const validScope = v => object(v) && ref48(v.scenario_ref) && ref48(v.draft_ref) && v.scenario_ref !== v.draft_ref && positive(v.task_count) && v.scope_complete === true
  && shape(v.baseline, ['plan_ref', 'version']) && (v.baseline.plan_ref === null ? v.baseline.version === null : ref48(v.baseline.plan_ref) && positive(v.baseline.version));
function overview(v) { check(validScope(v) && RunAdoptionAPI.contextRef(v.data_context_ref)); return overviewFields(v); }
function sameScope(a, b) {
  return a.scenario_ref === b.scenario_ref && a.draft_ref === b.draft_ref && a.task_count === b.task_count
    && a.scope_complete === b.scope_complete && a.baseline.plan_ref === b.baseline.plan_ref && a.baseline.version === b.baseline.version;
}
function source(scenarioRef, data) {
  check(ref48(scenarioRef) && object(data) && data.scenario_ref === scenarioRef && data.status === 'saved' && data.tasks_complete === true,
    '请先完整读取所选的试调方案；不能采用其他记录或不完整的内容。');
  return scopeFields(data);
}
function previewResult(v, original) {
  const d = v.data;
  check(d.scenario_ref === original.scenario_ref);
  if (d.validation.can_adopt === true) {
    check(sameScope(d, original) && nonempty(d.data_context_ref) && token32(d.write_context.write_token));
  }
  return d;
}
// intent 已由调用方校验：adopt/lookup 传入已存的采用记录，valid() 核完其余字段才调用这里。
function receipt(v, intent) {
  const d = v && v.data, p = d && d.official_plan, s = intent.preview;
  checkResult(object(v) && v.ok === true && v.result === 'committed'
    && object(d) && d.scenario_ref === s.scenario_ref && d.draft_ref === s.draft_ref && d.row_count === s.task_count
    && object(p) && ref48(p.plan_ref) && p.source_scenario_ref === s.scenario_ref && p.source_draft_ref === s.draft_ref && p.baseline_ref === s.baseline.plan_ref);
  return v;
}
function lookupResult(v, intent) {
  checkResult(object(v) && ['recorded', 'not_observed'].includes(v.state));
  if (v.state === 'not_observed') {
    checkResult(['unresolved', 'context_replaced'].includes(v.resolution));
    return { state: 'not_observed', receipt: null, may_be_in_flight: v.may_be_in_flight, resolution: v.resolution, data_context_ref: v.data_context_ref };
  }
  return receipt(v.receipt, intent);
}
// original 由 source() 从完整读取的试调方案构造；预检、采用和回执查询都按 30 秒等待。
async function preview(original, signal) {
  return previewResult(await T.preview(BASE + original.scenario_ref + '/adopt-preview', {}, { signal, timeout: 30000 }), original);
}
// intent 是 begin() 刚写入的待确认记录，writeToken 已由 previewResult 核过；回执查询的 intent 来自已校验的本机记录。
async function adopt(intent, writeToken) {
  const target = BASE + intent.scenario_ref + '/adoption-commands/' + intent.request_key;
  return receipt(await T.command(BASE + intent.scenario_ref + '/adopt', { write_token: writeToken, request_key: intent.request_key, input: intent.input },
    { timeout: 30000, expect: target }), intent);
}
async function lookup(intent, signal) {
  return lookupResult(await T.lookup(BASE + intent.scenario_ref + '/adoption-commands/' + intent.request_key,
    { data_context_ref: intent.preview.data_context_ref }, { signal, timeout: 30000 }), intent);
}
const TrialAdoptionAPI = { preview, adopt, lookup, source, overview, overviewFields, sameScope, receipt, check, shape, key, equal };
export { TrialAdoptionAPI, preview, adopt, lookup, source, overview, overviewFields, sameScope, receipt, check, shape, key, equal };
export default TrialAdoptionAPI;
