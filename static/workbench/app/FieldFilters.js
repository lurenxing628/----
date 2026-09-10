(function () {
  'use strict';

  const {
    Button
  } = window.FieldControls;
  function FieldFilters({
    scope,
    onChange,
    disabled,
    summary
  }) {
    const [draft, setDraft] = React.useState(scope);
    const counts = summary && summary.state_counts;
    React.useEffect(() => setDraft(scope), [scope]);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("form", {
      className: "field-filters",
      onSubmit: event => {
        event.preventDefault();
        if (!disabled) onChange(draft);
      }
    }, /*#__PURE__*/React.createElement("label", null, "\u641C\u7D22\u6279\u6B21\u6216\u5DE5\u5E8F", /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u6279\u6B21\u6216\u5DE5\u5E8F",
      value: draft.query || '',
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        query: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u8BA1\u5212\u5B8C\u5DE5\u8D77\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u8D77\u65E5",
      value: draft.plan_finish_date_from || '',
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        plan_finish_date_from: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u8BA1\u5212\u5B8C\u5DE5\u6B62\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u6B62\u65E5",
      value: draft.plan_finish_date_to || '',
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        plan_finish_date_to: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      "aria-label": "\u67E5\u8BE2\u73B0\u573A\u8BB0\u5F55",
      disabled: disabled
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u73B0\u573A\u7B5B\u9009",
      disabled: disabled,
      onClick: () => onChange({
        plan_ref: scope.plan_ref
      })
    }), /*#__PURE__*/React.createElement("div", {
      className: "field-states",
      role: "group",
      "aria-label": "\u62A5\u5DE5\u72B6\u6001"
    }, [['all', '全部'], ...Object.entries(window.FieldContract.states)].map(([state, label]) => /*#__PURE__*/React.createElement("button", {
      key: state,
      type: "button",
      "aria-label": label,
      disabled: disabled,
      "aria-pressed": (scope.state || 'all') === state,
      onClick: () => onChange({
        ...scope,
        state
      })
    }, label, counts && /*#__PURE__*/React.createElement("span", {
      "data-field-state-count": state
    }, " ", state === 'all' ? summary.state_scope_tasks : counts[state]))))), (scope.range_start || scope.batch_ids || scope.resource_ref) && /*#__PURE__*/React.createElement("div", {
      className: "field-filters field-note"
    }, scope.range_start && /*#__PURE__*/React.createElement("span", null, "\u8BA1\u5212\u91CD\u53E0\u8303\u56F4\uFF1A", window.FieldContract.date(scope.range_start), " \u81F3 ", window.FieldContract.date(scope.range_end)), scope.batch_ids && /*#__PURE__*/React.createElement("span", null, "\u6307\u5B9A\u6279\u6B21\uFF1A", scope.batch_ids.length, " \u4E2A"), scope.resource_ref && /*#__PURE__*/React.createElement("span", null, "\u5DF2\u9650\u5B9A", scope.resource_type === 'machine' ? '设备' : '人员', "\u5173\u8054\u5DE5\u5E8F")), summary && /*#__PURE__*/React.createElement("div", {
      className: "field-metrics"
    }, [['unreported', '待报工'], ['started', '已登记开工'], ['partial', '部分完成'], ['complete', '已完工']].map(([key, label]) => /*#__PURE__*/React.createElement("span", {
      key: key
    }, label, /*#__PURE__*/React.createElement("b", null, counts ? counts[key] : '未读取'))), /*#__PURE__*/React.createElement("span", null, "\u7D2F\u8BA1\u5B9E\u62A5\u5DE5\u65F6", /*#__PURE__*/React.createElement("b", null, summary.effective_processing_hours === null || summary.effective_processing_hours === undefined ? '未知' : Math.round(summary.effective_processing_hours * 1000) / 1000 + ' h'), summary.unknown_hour_reports > 0 && /*#__PURE__*/React.createElement("small", null, "\u5DF2\u77E5\u5C0F\u8BA1 ", summary.known_effective_processing_hours, " h \xB7 ", summary.unknown_hour_reports, " \u6761\u5F85\u8865"))));
  }
  window.FieldFilters = FieldFilters;
})();
