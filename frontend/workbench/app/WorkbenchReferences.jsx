import React from './shared/runtime/react.js';
import { isFailure } from './shared/contract/kit.js';

const present = value => value !== null && value !== undefined && value !== '';
const text = value => typeof value === 'string' ? value : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);

function WorkbenchReference({ value, entries, label = '编号' }) {
  const rows = Object.entries(entries || {}).filter(([, item]) => present(item));
  if (present(value)) rows.unshift(['编号', value]);
  if (!rows.length) return null;
  return <details className="wb-ref"><summary>{label}</summary><dl>
    {rows.map(([name, item], index) => <div key={index}><dt>{name}</dt><dd><code>{text(item)}</code></dd></div>)}
  </dl></details>;
}

function technical(message) {
  const trimmed = message.trim();
  // File names are actionable business context; their dots/underscores are not rule codes.
  const codes = trimmed.replace(/\b[\w.-]+\.(?:csv|tsv|xls|xlsx|txt|log|json|zip|db|bak|pdf|md)\b/gi, '');
  return /[0-9a-f]{32,}/i.test(message) ||
    /\b[a-z][a-z0-9]*(?:[_.][a-z0-9]+)+\b/i.test(codes) ||
    /(?:HTTP\s*[:：]?\s*[1-5]\d\d|状态码\s*[:：]?\s*[1-5]\d\d|\b\w*(?:Error|Exception)\b)/i.test(message) ||
    /^[a-z][a-z0-9_.-]*$/i.test(codes) || /[\[{]\s*["']?[^\s\]}]+["']?\s*:/.test(message) ||
    trimmed.startsWith('[') && trimmed.endsWith(']') || trimmed.startsWith('{') && trimmed.endsWith('}');
}

// 界面错误文案只在这里判定：kit 统一错误对象（transport 转来的后端固定文案、前端自己写的中文）的 message 才是用户文案；
// 其余错误（TypeError、浏览器异常等）一律显示 fallback 中文通用句，原文只进折叠的“原始错误信息”。kit 文案里夹着编码时（technical）同样不上屏。
const GENERIC = '操作未完成，请核对后重试。';
const userCopy = error => isFailure(error) && !!error.message && !technical(error.message);
// 只能放一句话的地方（按钮禁用理由等）用 errorText，和 WorkbenchError 走同一条规则。
const errorText = (error, fallback = GENERIC) => userCopy(error) ? error.message : fallback;
// fields 是 kit 错误的字段行，调用方（ErrorBox）已滤掉页面上就地标红的项。
function WorkbenchError({ error, fallback = GENERIC, fields = [], hideMessage = false }) {
  if (!error) return null;
  const message = error.message;
  const entries = {}, messages = [];
  if (present(message) && !userCopy(error)) entries['原始错误信息'] = message;
  if (!hideMessage) messages.push(errorText(error, fallback));
  const labels = { code: '错误编号', status: '状态码', requestKey: '操作编号', requestRef: '结果编号' };
  Object.entries(labels).forEach(([key, label]) => { if (present(error[key])) entries[label] = error[key]; });
  if (error.name && error.name !== 'Error') entries['错误类型'] = error.name;
  fields.forEach((field, index) => {
    const detail = field.message;
    if (!detail) return;
    if (technical(detail)) { entries['填写项说明 ' + (index + 1)] = detail; if (!messages.length) messages.push(fallback); }
    else if (!messages.includes(detail)) messages.push(detail);
  });
  if (!messages.length && !Object.keys(entries).length) return null;
  return <div className="wb-error" role="alert">
    {messages.map((message, index) => <div key={index}>{message}</div>)}
    <WorkbenchReference entries={entries} />
  </div>;
}

export { WorkbenchReference, WorkbenchError, errorText };
export default { WorkbenchReference, WorkbenchError, errorText };
