import React from '../runtime/react.js';

const readableColors = {
  'var(--ui-primary)': 'var(--ui-info-text)',
  'var(--ui-danger)': 'var(--ui-danger-text)',
  'var(--ui-warning)': 'var(--ui-warning-text)',
  'var(--ui-success)': 'var(--ui-success-text)',
  'var(--ui-muted)': 'var(--ui-info-muted)'
};

function MetricStrip({ children, columns, className = '', style = {}, ...props }) {
  const count = columns || React.Children.count(children) || 1;
  return (
    <div {...props} className={'wb-metrics' + (className ? ' ' + className : '')} style={{ '--wb-columns': count, ...style }}>
      {children}
    </div>
  );
}

function Metric({ label, value, unit, helper, badge, tone = 'neutral', valueColor, className = '', valueClassName = '', style = {}, ...props }) {
  const color = valueColor ? { '--wb-metric-color': readableColors[valueColor] || valueColor } : {};
  return (
    <div {...props} className={'wb-metric' + (className ? ' ' + className : '')} data-tone={tone} style={{ ...color, ...style }}>
      <div className="wb-metric-heading">
        <span className="wb-metric-label">{label}</span>
        {badge || null}
      </div>
      <div className="wb-metric-line">
        <span className={'wb-metric-value' + (valueClassName ? ' ' + valueClassName : '')}>{value}</span>
        {unit ? <span className="wb-metric-unit">{unit}</span> : null}
      </div>
      {helper ? <div className="wb-metric-helper">{helper}</div> : null}
    </div>
  );
}

export { MetricStrip, Metric };
export default { MetricStrip, Metric };
