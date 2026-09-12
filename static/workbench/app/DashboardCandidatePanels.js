(function () {
  'use strict';

  const {
    Button,
    Modal
  } = window.ResourceControls;
  const number = v => window.WorkbenchFormat.number(v, {
    digits: Number.isInteger(v) ? 0 : 2
  });
  const signed = (v, scale = 1) => v === null ? '未知' : v === 0 ? '0' : (v > 0 ? '+' : '') + number(v * scale);
  const risk = row => row.risk === 'overdue' ? '晚交 ' + number(row.delay_hours) + ' h' : row.risk === 'on_time' ? '预计准时' : '交付未知';
  function Peak({
    value
  }) {
    return value.peak_utilization !== null ? /*#__PURE__*/React.createElement(React.Fragment, null, window.WorkbenchFormat.percent(value.peak_utilization)) : value.state === 'available' ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u96F6\u53EF\u7528\u5BB9\u91CF") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u5BB9\u91CF\u672A\u77E5");
  }
  function Metrics({
    data
  }) {
    const old = data.summary.before,
      selected = data.summary.after;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u6574\u4F53\u6536\u76CA\u4E0E\u4EE3\u4EF7"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6574\u4F53\u6536\u76CA\u4E0E\u4EE3\u4EF7"), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u5019\u9009\u65B9\u6848\u6536\u76CA\u4E0E\u4EE3\u4EF7\u5BF9\u7167"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6307\u6807"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D7\u7406\u65F6\u6B63\u5F0F\u57FA\u7EBF"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6240\u9009\u5019\u9009\u65B9\u6848"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D8\u5316"))), /*#__PURE__*/React.createElement("tbody", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, window.WorkbenchTerms.overdue_count), /*#__PURE__*/React.createElement("td", null, number(old.overdue_count)), /*#__PURE__*/React.createElement("td", null, number(selected.overdue_count)), /*#__PURE__*/React.createElement("td", null, signed(old.overdue_count === null || selected.overdue_count === null ? null : selected.overdue_count - old.overdue_count))), /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, window.WorkbenchTerms.total_tardiness_hours, " h"), /*#__PURE__*/React.createElement("td", null, number(old.total_tardiness_hours)), /*#__PURE__*/React.createElement("td", null, number(selected.total_tardiness_hours)), /*#__PURE__*/React.createElement("td", null, signed(old.total_tardiness_hours === null || selected.total_tardiness_hours === null ? null : selected.total_tardiness_hours - old.total_tardiness_hours))), /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, "\u540C\u65F6\u95F4\u7A97\u6362\u578B\u6B21\u6570"), /*#__PURE__*/React.createElement("td", {
      title: old.changeovers.reason || ''
    }, number(old.changeovers.value)), /*#__PURE__*/React.createElement("td", {
      title: selected.changeovers.reason || ''
    }, number(selected.changeovers.value)), /*#__PURE__*/React.createElement("td", null, signed(data.summary.changeover_delta))), data.resources.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.resource_ref,
      "data-comparison-resource": row.resource_ref
    }, /*#__PURE__*/React.createElement("td", null, row.label || '名称未记录', " \xB7 \u65E5\u5CF0\u503C"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Peak, {
      value: row.before
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Peak, {
      value: row.after
    })), /*#__PURE__*/React.createElement("td", null, signed(row.delta, 100), " \u4E2A\u767E\u5206\u70B9")))))), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, /*#__PURE__*/React.createElement("span", null, "\u4EA4\u4ED8\u672A\u77E5\uFF1A\u57FA\u7EBF ", old.unknown_count, " \u6279 / \u5019\u9009 ", selected.unknown_count, " \u6279"), /*#__PURE__*/React.createElement("span", null, "\u8D44\u6E90\u65E5\u5CF0\u503C\uFF1A\u540C\u8303\u56F4\u81EA\u7136\u65E5\u5185\u53EF\u7528\u65F6\u6BB5\u5360\u7528\u7387")), !data.resource_scope_complete && /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning"
    }, data.resource_scope_unknown_rows, " \u6761\u5B89\u6392\u7684\u8D44\u6E90\u6765\u6E90\u4E0D\u5B8C\u6574\uFF0C\u672A\u5C06\u7F3A\u53E3\u89C6\u4E3A\u96F6\u8D1F\u8377\u3002"));
  }
  function Batches({
    data,
    selected,
    onSelect
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u9010\u6279\u4EA4\u671F\u53D8\u5316"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9010\u6279\u4EA4\u671F\u53D8\u5316"), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u9010\u6279\u4EA4\u671F\u53D8\u5316"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6279\u6B21 / \u96F6\u4EF6"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4EA4\u671F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u57FA\u7EBF\u8BA1\u5212\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5019\u9009\u8BA1\u5212\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u57FA\u7EBF / \u5019\u9009"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u62D6\u671F\u53D8\u5316 h"))), /*#__PURE__*/React.createElement("tbody", null, data.batches.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref,
      "data-comparison-batch": row.batch_ref,
      "data-selected": selected === row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "mini",
      icon: "search",
      "aria-pressed": selected === row.batch_ref,
      onClick: () => onSelect(row.batch_ref)
    }, row.batch_id), /*#__PURE__*/React.createElement("small", null, row.part_label || '名称未记录')), /*#__PURE__*/React.createElement("td", null, row.after.due_date || '未知'), /*#__PURE__*/React.createElement("td", null, row.before.planned_finish ? window.WorkbenchFormat.dateTime(row.before.planned_finish) : '未确认完整排程'), /*#__PURE__*/React.createElement("td", null, row.after.planned_finish ? window.WorkbenchFormat.dateTime(row.after.planned_finish) : '未确认完整排程'), /*#__PURE__*/React.createElement("td", null, risk(row.before), " / ", risk(row.after)), /*#__PURE__*/React.createElement("td", null, signed(row.delay_delta_hours))))))));
  }
  function Summary({
    data,
    onClose
  }) {
    return /*#__PURE__*/React.createElement(Modal, {
      title: "\u5019\u9009\u65B9\u6848\u6458\u8981",
      icon: "chart-gantt",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        icon: "arrow-left",
        onClick: onClose
      }, "\u8FD4\u56DE\u6BD4\u8F83")
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form dy-candidate-summary"
    }, /*#__PURE__*/React.createElement("h3", null, data.candidate.label || '候选名称未记录'), /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u53D7\u7406\u65F6\u6B63\u5F0F\u57FA\u7EBF"), /*#__PURE__*/React.createElement("dd", null, data.baseline.baseline_ref ? '已核实受理时基线' : '受理时没有正式基线')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, window.WorkbenchTerms.overdue_count), /*#__PURE__*/React.createElement("dd", null, number(data.summary.after.overdue_count))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, window.WorkbenchTerms.total_tardiness_hours), /*#__PURE__*/React.createElement("dd", null, number(data.summary.after.total_tardiness_hours), " h")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u540C\u7A97\u6362\u578B\u6B21\u6570"), /*#__PURE__*/React.createElement("dd", null, number(data.summary.after.changeovers.value))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6362\u8BBE\u5907\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, number(data.machine_changes.count), " \xB7 \u5DF2\u786E\u8BA4 ", data.machine_changes.known_count, " \xB7 \u672A\u77E5 ", data.machine_changes.unknown_count))), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '候选编号': data.candidate.candidate_ref,
        '受理时基线编号': data.baseline.baseline_ref
      }
    }), /*#__PURE__*/React.createElement("details", {
      className: "wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6362\u8BBE\u5907\u5DE5\u5E8F\u7F16\u53F7"), data.machine_changes.operation_refs.map(ref => /*#__PURE__*/React.createElement("p", {
      key: ref
    }, ref)), !data.machine_changes.operation_refs.length && /*#__PURE__*/React.createElement("p", null, "\u6CA1\u6709\u5DF2\u786E\u8BA4\u6362\u8BBE\u5907\u7684\u5DE5\u5E8F\u3002"))));
  }
  window.DashboardCandidatePanels = {
    Metrics,
    Batches,
    Summary,
    number
  };
})();
