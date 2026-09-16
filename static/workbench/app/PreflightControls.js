(function () {
  'use strict';

  const {
    Button,
    ErrorBox
  } = window.ResourceControls;
  function Segment({
    label,
    value,
    choices,
    onChange,
    disabled
  }) {
    const id = React.useId();
    return /*#__PURE__*/React.createElement("div", {
      className: "pf-segment",
      role: "radiogroup",
      "aria-label": label
    }, choices.map(([key, text, unavailable]) => /*#__PURE__*/React.createElement("label", {
      key: String(key),
      className: value === key ? 'selected' : ''
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: id,
      checked: value === key,
      disabled: disabled || unavailable,
      onChange: () => onChange(key)
    }), /*#__PURE__*/React.createElement("span", null, text))));
  }
  function Rules({
    value,
    onChange,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-labelledby": "pf-rules-title"
    }, /*#__PURE__*/React.createElement("h3", {
      id: "pf-rules-title"
    }, "\u672C\u6B21\u6392\u4EA7\u89C4\u5219"), /*#__PURE__*/React.createElement("div", {
      className: "pf-rows"
    }, /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("strong", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u9F50\u5957\u68C0\u67E5",
      value: value.ready_check,
      choices: [[true, '开启'], [false, '关闭']],
      disabled: disabled,
      onChange: ready_check => onChange({
        ready_check
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("strong", null, "\u7F3A\u8D44\u6E90\u5DE5\u5E8F"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u7F3A\u8D44\u6E90\u5DE5\u5E8F",
      value: value.missing_resource_policy,
      choices: [["auto_assign", '自动分配'], ['exclude', '暂不排']],
      disabled: disabled,
      onChange: missing_resource_policy => onChange({
        missing_resource_policy
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("span", {
      className: "pf-fixed"
    }, "\u5DF2\u5F00\u5DE5\u5DE5\u5E8F\uFF1A\u4FDD\u7559\u8BB0\u5F55\uFF08\u4E0D\u53EF\u4FEE\u6539\uFF09")), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-note"
    }, "\u89C4\u5219\u4EC5\u7528\u4E8E\u672C\u6B21\u6392\u4EA7\u3002")));
  }
  function Metrics({
    counts
  }) {
    const items = [['selected_tasks', '范围内工序'], ['ready_tasks', '资料有效'], ['auto_assign_required', '自动分配待补'], ['skipped_tasks', '本次跳过'], ['blocked_tasks', '缺资料工序'], ['no_route_batches', '未生成工艺批次'], ['actual_fact_tasks', '已开工工序']];
    return /*#__PURE__*/React.createElement("dl", {
      className: "pf-metrics"
    }, items.map(([key, label]) => /*#__PURE__*/React.createElement("div", {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, counts ? counts[key] : '未检查'))));
  }
  function Reasons({
    data
  }) {
    const groups = new Map(),
      tasks = new Map(data.tasks.map(row => [row.operation_ref, row]));
    const batches = new Map(data.included_batches.concat(data.excluded_batches).map(row => [row.batch_ref, row.batch_id]));
    data.run_blocked_reasons.concat(data.warnings).forEach(item => {
      if (!groups.has(item.code)) groups.set(item.code, []);
      groups.get(item.code).push(item);
    });
    function summary(code, items) {
      const operations = new Set(items.map(item => item.operation_ref).filter(Boolean)).size;
      const messages = Array.from(new Set(items.map(item => item.message))).join('；');
      if (operations && code === 'operation_blocked') return operations + '道工序缺必填资料';
      if (operations && code === 'execution_review_required') return operations + '道工序已有执行记录待核对';
      if (code === 'route_not_generated') return new Set(items.map(item => item.batch_ref).filter(Boolean)).size + '批尚未生成工艺';
      return (operations ? operations + '道工序：' : '') + messages;
    }
    function objectLabel(item) {
      const task = tasks.get(item.operation_ref);
      if (task) return task.batch_id + ' · ' + task.sequence + ' ' + task.label + (task.piece_id ? ' · ' + task.piece_id : '');
      return item.batch_id || batches.get(item.batch_ref) || '批次与工序未读取';
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "pf-alert"
    }, /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, Array.from(groups, ([code, items]) => /*#__PURE__*/React.createElement("div", {
      key: code,
      "data-reason-group": code
    }, summary(code, items)))), /*#__PURE__*/React.createElement("details", {
      className: "pf-reasons"
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u56E0\u660E\u7EC6 \xB7 ", data.run_blocked_reasons.length + data.warnings.length, " \u9879"), /*#__PURE__*/React.createElement("div", {
      className: "pf-reason-list"
    }, Array.from(groups, ([code, items]) => /*#__PURE__*/React.createElement("div", {
      key: code
    }, items.map((item, index) => /*#__PURE__*/React.createElement("div", {
      className: "pf-reason-item",
      key: index,
      "data-reason-code": item.code,
      "data-operation-ref": item.operation_ref,
      "data-batch-ref": item.batch_ref
    }, objectLabel(item) && /*#__PURE__*/React.createElement("strong", null, objectLabel(item), "\uFF1A "), item.message, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '原因编号': item.code,
        '工序编号': item.operation_ref,
        '批次编号': item.batch_ref
      }
    }))))))));
  }
  function Styles() {
    return null;
  }
  window.PreflightControls = {
    Button,
    ErrorBox,
    Rules,
    Metrics,
    Reasons,
    Styles
  };
})();
