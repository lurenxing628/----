(function () {
  'use strict';

  const {
      Button,
      Issues
    } = window.ResourceControls,
    M = window.DashboardTimelineModel;
  const value = v => v === null || v === undefined ? '未知' : typeof v === 'number' ? M.number(v) : String(v);
  const risk = row => row.risk === 'overdue' ? '晚交 ' + value(row.delay_hours) + ' h' : row.risk === 'on_time' ? '预计准时' : '交付未知';
  function Batch({
    row,
    selected,
    onSelect
  }) {
    return /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "search",
      "data-analysis-select-batch": row.batch_ref,
      "aria-pressed": selected === row.batch_ref,
      onClick: () => onSelect(row.batch_ref)
    }, row.batch_id);
  }
  function Delivery({
    data,
    selected,
    onSelect,
    onCompare
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.DashboardTimeline, {
      data: data,
      selectedBatch: selected,
      onSelect: onSelect
    }), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5F71\u54CD\u6279\u6B21"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5F71\u54CD\u6279\u6B21"), /*#__PURE__*/React.createElement(Button, {
      icon: "git-compare-arrows",
      onClick: onCompare
    }, "\u5BF9\u6BD4\u8C03\u6574\u65B9\u6848")), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u96F6\u4EF6"), /*#__PURE__*/React.createElement("th", null, "\u4EA4\u671F"), /*#__PURE__*/React.createElement("th", null, "\u8BA1\u5212\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("th", null, "\u4EA4\u4ED8\u5224\u65AD"), /*#__PURE__*/React.createElement("th", null, "\u4F18\u5148\u7EA7"))), /*#__PURE__*/React.createElement("tbody", null, data.deliveries.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref,
      "data-analysis-delivery": row.batch_ref,
      "data-selected": selected === row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Batch, {
      row: row,
      selected: selected,
      onSelect: onSelect
    }), /*#__PURE__*/React.createElement("small", null, value(row.part_label))), /*#__PURE__*/React.createElement("td", null, value(row.due_date)), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.planned_finish)), /*#__PURE__*/React.createElement("td", null, risk(row)), /*#__PURE__*/React.createElement("td", null, {
      normal: '普通',
      urgent: '急件',
      critical: '特急'
    }[row.priority] || '未知')))))), !data.deliveries.length && /*#__PURE__*/React.createElement("p", {
      className: "dy-empty"
    }, "\u5F53\u524D\u6B63\u5F0F\u8BA1\u5212\u6CA1\u6709\u6279\u6B21\u4EA4\u4ED8\u8BB0\u5F55\u3002")));
  }
  function Downtime({
    data,
    selected,
    onSelect
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.DashboardTimeline, {
      data: data,
      mode: "downtime",
      selectedBatch: selected,
      onSelect: onSelect
    }), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u76F4\u63A5\u91CD\u53E0\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("h3", null, "\u76F4\u63A5\u91CD\u53E0\u7684\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", null, "\u539F\u8BA1\u5212\u5F00\u59CB"), /*#__PURE__*/React.createElement("th", null, "\u539F\u8BA1\u5212\u7ED3\u675F"), /*#__PURE__*/React.createElement("th", null, "\u91CD\u53E0\u5C0F\u65F6"))), /*#__PURE__*/React.createElement("tbody", null, data.overlaps.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.task_ref,
      "data-overlap-task": row.task_ref,
      "data-selected": selected === row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Batch, {
      row: row,
      selected: selected,
      onSelect: onSelect
    }), /*#__PURE__*/React.createElement("small", null, row.process_label)), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.source.planned_start)), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.source.planned_end)), /*#__PURE__*/React.createElement("td", null, value(row.source.overlap_hours), " h")))))), !data.overlaps.length && /*#__PURE__*/React.createElement("p", {
      className: "dy-empty"
    }, "\u5F53\u524D\u8BFB\u53D6\u8303\u56F4\u672A\u786E\u8BA4\u76F4\u63A5\u91CD\u53E0\uFF0C\u6765\u6E90\u5F02\u5E38\u4ECD\u5355\u72EC\u5217\u793A\u3002")), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u505C\u673A\u767B\u8BB0\u4F9D\u636E"
    }, /*#__PURE__*/React.createElement("h3", null, "\u767B\u8BB0\u4F9D\u636E"), data.downtimes.map(row => /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts",
      key: row.downtime_ref
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u8BBE\u5907"), /*#__PURE__*/React.createElement("dd", null, value((data.resources.find(r => r.resource_ref === row.machine_ref) || {}).label))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, value(row.reason))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5F00\u59CB / \u7ED3\u675F"), /*#__PURE__*/React.createElement("dd", null, M.timeLabel(row.start), " / ", M.timeLabel(row.end))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u767B\u8BB0\u65F6\u95F4\uFF08\u539F\u5B58\u503C\uFF09"), /*#__PURE__*/React.createElement("dd", null, M.timeLabel(row.recorded_at)))))));
  }
  function Material({
    data
  }) {
    const p = data.pending;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5F85\u6392\u6279\u6B21\u4E0E\u9F50\u5957\u65E5\u671F"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5F85\u6392\u6279\u6B21\u4E0E\u9F50\u5957\u65E5\u671F"), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u5F85\u6392 ", value(p.count), " \u6279 \xB7 \u5DF2\u8BFB\u53D6 ", p.known_count, " \u6279"), /*#__PURE__*/React.createElement(Issues, {
      issues: p.issues
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u96F6\u4EF6"), /*#__PURE__*/React.createElement("th", null, "\u6570\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u4EA4\u671F"), /*#__PURE__*/React.createElement("th", null, "\u9F50\u5957\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u9F50\u5957\u65E5\u671F"))), /*#__PURE__*/React.createElement("tbody", null, p.items.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref,
      "data-pending-batch": row.batch_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, row.batch_id), /*#__PURE__*/React.createElement("small", null, value(row.part_label))), /*#__PURE__*/React.createElement("td", null, value(row.quantity)), /*#__PURE__*/React.createElement("td", null, value(row.due_date)), /*#__PURE__*/React.createElement("td", null, {
      yes: '已齐套',
      no: '未齐套',
      partial: '部分齐套'
    }[row.ready_status] || '未知'), /*#__PURE__*/React.createElement("td", null, value(row.ready_date))))))), !p.items.length && /*#__PURE__*/React.createElement("p", {
      className: "dy-empty"
    }, p.count === 0 ? '当前没有待排批次。' : '待排批次来源未能完整读取。'), /*#__PURE__*/React.createElement("h3", null, "\u672C\u6B21\u6392\u4EA7\u7EA6\u675F"), /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5F53\u524D\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u672C\u673A\u5F85\u6392\u6279\u6B21\u6C60")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6392\u4EA7\u8F93\u5165"), /*#__PURE__*/React.createElement("dd", null, "\u5F53\u524D\u672A\u9009\u5B9A")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement("dd", null, "\u672A\u9009\u5B9A\u6392\u4EA7\u8F93\u5165")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7F3A\u8D44\u6E90 / \u5DF2\u5F00\u5DE5\u7B56\u7565"), /*#__PURE__*/React.createElement("dd", null, "\u672A\u9009\u5B9A\u6392\u4EA7\u8F93\u5165"))));
  }
  function Actual({
    data,
    navigate
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5DE5\u5E8F\u6267\u884C\u504F\u5DEE"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u5E8F\u6267\u884C\u4E8B\u5B9E\u4E0E\u5B9A\u989D\u5BF9\u7167"), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-analysis-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", null, "\u5B9A\u989D\u52A0\u5DE5\u5C0F\u65F6"), /*#__PURE__*/React.createElement("th", null, "\u6709\u6548\u52A0\u5DE5\u5C0F\u65F6"), /*#__PURE__*/React.createElement("th", null, "\u8D85\u8017\u5224\u65AD"), /*#__PURE__*/React.createElement("th", null, "\u73B0\u573A\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, data.execution.map(row => {
      const source = row.source,
        hours = source.hours || {},
        context = {
          plan_ref: source.plan_ref,
          task_ref: source.task_ref,
          operation_ref: source.operation_ref
        };
      return /*#__PURE__*/React.createElement("tr", {
        key: source.task_ref
      }, /*#__PURE__*/React.createElement("td", null, row.subject), /*#__PURE__*/React.createElement("td", null, value(hours.quota_processing_hours), " h"), /*#__PURE__*/React.createElement("td", null, value(hours.effective_processing_hours), " h"), /*#__PURE__*/React.createElement("td", null, hours.overrun === true ? '已确认超耗' : hours.overrun === false ? '未超耗' : '无法评估'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
        icon: "square-pen",
        onClick: () => navigate({
          view: 'field',
          context,
          enabled: true
        })
      }, "\u73B0\u573A\u62A5\u5DE5"), /*#__PURE__*/React.createElement(Button, {
        icon: "chart-gantt",
        onClick: () => navigate({
          view: 'fieldgantt',
          context,
          enabled: true
        })
      }, "\u73B0\u573A\u5B9E\u9645")));
    })))));
  }
  window.DashboardAnalysisPanels = {
    Delivery,
    Downtime,
    Material,
    Actual,
    value
  };
})();
