import React from './shared/runtime/react.js';

const noFeedback = summary => !!summary && summary.production_reports === 0;

function actualValue(value, empty, missing = '未知') {
  if (value === null || value === undefined) return empty ? <span className="rw-no-feedback-value" aria-label="暂无现场数据">—</span> : missing;
  return String(value);
}

function NoFeedback({ summary }) {
  return noFeedback(summary) ? <p className="rw-no-feedback" role="status">当前范围暂无报工记录。</p> : null;
}

const ReportEvidence = { NoFeedback, noFeedback, actualValue };

export { ReportEvidence, NoFeedback, noFeedback, actualValue };
export default ReportEvidence;
