(function () {
  'use strict';

  const groups = {
    material: [['total', '物料主数据', 'primary'], ['active', '启用', 'ok'], ['low_stock', '低库存', 'warn'], ['inactive', '停用', 'neutral']],
    op_int: [['internal', '自制工种', 'primary'], ['linked_machines', '关联设备', 'neutral'], ['available_operators', '可用人员', 'ok'], ['without_machines', '未绑定设备', 'warn']],
    op_ext: [['external', '外协工种', 'primary'], ['available_suppliers', '可用供应商', 'ok'], ['merged', '合并周期策略', 'neutral'], ['separate', '分别周期策略', 'neutral']],
    machine: [['total', '设备总数', 'primary'], ['active', '可用', 'ok'], ['maintain', '检修', 'warn'], ['groups', '设备组', 'neutral']],
    operator: [['total', '人员总数', 'primary'], ['active', '在岗', 'ok'], ['leave', '请假', 'warn'], ['skills', '技能登记', 'neutral']],
    supplier: [['total', '供应商总数', 'primary'], ['active', '启用', 'ok'], ['pending_review', '待复核', 'warn'], ['inactive', '停用', 'neutral']]
  };
  function ResourceMetrics({
    node,
    data
  }) {
    const metrics = data && data.metrics,
      counts = metrics && metrics.counts || {};
    const issues = metrics && metrics.issues || [];
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "statline wb-metrics",
      style: {
        '--wb-columns': 4
      }
    }, (groups[node] || []).map(([key, label, tone]) => {
      const known = Number.isSafeInteger(counts[key]) && counts[key] >= 0;
      const unavailable = issues.find(issue => Array.isArray(issue.unavailable_fields) && issue.unavailable_fields.includes(key));
      const reason = unavailable && unavailable.message || metrics && metrics.basis && metrics.basis[key];
      return /*#__PURE__*/React.createElement("div", {
        key: key,
        className: "stat wb-metric",
        "data-tone": known ? tone : 'neutral',
        title: reason || undefined
      }, /*#__PURE__*/React.createElement("span", {
        className: "sl wb-metric-label"
      }, label), /*#__PURE__*/React.createElement("span", {
        className: "sv wb-metric-value",
        style: !known ? {
          fontSize: 16
        } : undefined
      }, known ? counts[key] : !data ? '待读取' : key === 'low_stock' ? '未设阈值' : '无法核实'));
    })), /*#__PURE__*/React.createElement(window.ResourceControls.Issues, {
      issues: issues
    }));
  }
  window.ResourceMetrics = ResourceMetrics;
})();
