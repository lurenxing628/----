(function () {
  'use strict';

  const title = '趋势、偏差与资源分析';
  function ResourceHours({
    data,
    onDrill,
    view,
    onChange
  }) {
    const {
        Button
      } = window.ResourceControls,
      {
        kind,
        page
      } = view,
      {
        hoursText
      } = window.ReportTable;
    const rows = data.resources[kind === 'machine' ? 'machines' : 'people'],
      pages = Math.max(1, Math.ceil(rows.length / 6));
    const current = Math.min(page, pages),
      maximum = Math.max(1, ...rows.map(row => row.known_effective_processing_hours || 0));
    const visible = rows.slice((current - 1) * 6, current * 6);
    const open = row => onDrill('records', {
      resource_type: kind,
      resource_ref: row.resource_ref || 'unassigned'
    });
    return /*#__PURE__*/React.createElement("section", {
      className: "er-section er-resource-hours",
      "aria-label": "\u5B9E\u9645\u8D44\u6E90\u5DE5\u65F6"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-section-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5B9E\u9645\u8D44\u6E90\u5DE5\u65F6"), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": "\u8D44\u6E90\u5DE5\u65F6\u7C7B\u578B"
    }, [['machine', '设备'], ['operator', '人员']].map(([key, label]) => /*#__PURE__*/React.createElement(Button, {
      key: key,
      "aria-pressed": kind === key,
      className: 'seg-btn' + (kind === key ? ' on' : ''),
      onClick: () => onChange({
        kind: key,
        page: 1
      })
    }, label)))), /*#__PURE__*/React.createElement("div", {
      className: "er-resource-list"
    }, visible.map(row => /*#__PURE__*/React.createElement("div", {
      className: "er-resource-row",
      key: row.resource_ref || 'unassigned',
      "data-resource-ref": row.resource_ref || 'unassigned'
    }, /*#__PURE__*/React.createElement(Button, {
      className: "lnk er-resource-name",
      disabled: !onDrill,
      onClick: () => open(row)
    }, row.resource_label), /*#__PURE__*/React.createElement(Button, {
      className: "er-resource-bar",
      "aria-label": '查看 ' + row.resource_label + ' 关联记录',
      disabled: !onDrill,
      onClick: () => open(row),
      title: '已知工时 ' + hoursText(row.known_effective_processing_hours) + '；未知 ' + row.unknown_hour_events + ' 条'
    }, row.known_effective_processing_hours !== null && /*#__PURE__*/React.createElement("i", {
      "aria-hidden": "true",
      style: {
        width: row.known_effective_processing_hours / maximum * 100 + '%'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "er-resource-value"
    }, row.effective_processing_hours === null ? '总工时未知' : '总工时 ' + hoursText(row.effective_processing_hours), " \xB7 \u5DF2\u77E5 ", hoursText(row.known_effective_processing_hours), " \xB7 \u5F85\u8865 ", row.unknown_hour_events, " \u6761"))), !rows.length && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u8D44\u6E90\u5DE5\u65F6\u8BB0\u5F55"
    })), /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: current,
      pages: pages,
      total: rows.length,
      size: 6,
      unit: "\u7EC4",
      label: "\u8D44\u6E90\u5DE5\u65F6",
      onPage: number => onChange({
        kind,
        page: number
      })
    }), /*#__PURE__*/React.createElement("p", {
      className: "er-method"
    }, "\u70B9\u51FB\u8D44\u6E90\u67E5\u770B\u62A5\u5DE5\u660E\u7EC6\u3002"), /*#__PURE__*/React.createElement(window.ReportTable.Table, {
      data: {
        topic: kind === 'machine' ? 'machines' : 'people',
        rows: visible,
        columns: window.ReviewChartViews.resourceColumns()
      }
    }));
  }
  // expanded：执行复盘页把图表当主体，直接展开，不再折叠；报表中心仍是可折叠的辅助区。
  function Charts({
    data,
    open,
    onChange,
    onDrill,
    resourceView,
    onResourceView,
    expanded = false
  }) {
    const {
        DistributionChart,
        TrendChart
      } = window.ReviewChartViews,
      {
        hoursText
      } = window.ReportTable,
      legacy = window.WorkbenchTerms.legacy_field_records;
    const points = data.charts.trend.map(row => ({
      time: new Date(row.date + 'T00:00:00').getTime(),
      label: row.date,
      planned: row.planned,
      actual: row.actual,
      unclosed: row.actual == null ? null : Math.max(0, row.planned - row.actual)
    }));
    const items = (rows, tone) => rows.map(row => ({
      ...row,
      id: row.label,
      tone
    }));
    const body = /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "er-overview-grid"
    }, /*#__PURE__*/React.createElement("section", {
      className: "er-section er-trend"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8BA1\u5212\u4E0E\u5B9E\u9645\u7D2F\u8BA1\u5B8C\u5DE5"), /*#__PURE__*/React.createElement(TrendChart, {
      points: points,
      label: "\u8303\u56F4\u5185\u5DE5\u5E8F\u7D2F\u8BA1\u5B8C\u5DE5"
    })), /*#__PURE__*/React.createElement("section", {
      className: "er-section er-insights"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8BB0\u5F55\u8981\u70B9"), /*#__PURE__*/React.createElement("p", null, "\u5DF2\u786E\u8BA4\u665A\u5B8C\u6210 ", data.summary.finish_late, " \u9053\uFF1B\u5230\u671F\u672A\u786E\u8BA4 ", data.summary.unclosed_due, " \u9053\u3002"), /*#__PURE__*/React.createElement("p", null, legacy, " ", data.summary.events, " \u6761\uFF1B\u9010\u6B21\u62A5\u5DE5 ", data.summary.production_reports, " \u6761\uFF1B\u5168\u90E8\u8BB0\u5F55 ", data.summary.records, " \u6761\u3002"), !window.ReportEvidence.noFeedback(data.summary) && /*#__PURE__*/React.createElement("p", null, "\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6 ", hoursText(data.summary.effective_processing_hours), "\uFF1B\u5DF2\u77E5\u5C0F\u8BA1 ", hoursText(data.summary.known_effective_processing_hours), "\uFF1B\u5DE5\u65F6\u672A\u77E5 ", data.summary.unknown_hour_events, " \u6761\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rw-actions"
    }, [['finish_late', '晚完成明细'], ['unclosed', '未确认明细'], [data.scope.focus, '工序明细']].map(([focus, label]) => /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      key: label,
      icon: "arrow-right",
      disabled: !onDrill,
      onClick: () => onDrill('delivery', {
        focus
      })
    }, label))))), /*#__PURE__*/React.createElement("div", {
      className: "er-distribution-grid"
    }, /*#__PURE__*/React.createElement(DistributionChart, {
      items: items(data.charts.finish, 'info'),
      label: "\u5DF2\u786E\u8BA4\u6574\u9053\u5B8C\u5DE5\u504F\u5DEE"
    }), /*#__PURE__*/React.createElement(DistributionChart, {
      items: items(data.charts.aging, 'warning'),
      label: "\u5230\u671F\u672A\u786E\u8BA4\u5DF2\u8FC7\u65F6\u957F"
    })), /*#__PURE__*/React.createElement("p", {
      className: "er-method"
    }, "\u6309\u5F53\u524D\u5B8C\u5DE5\u8BB0\u5F55\u6C47\u603B\u6BCF\u65E5\u7D2F\u8BA1\u5B8C\u5DE5\u6570\uFF1B\u5F85\u786E\u8BA4\u65F6\u957F\u4ECE\u8BA1\u5212\u5B8C\u5DE5\u65F6\u95F4\u8D77\u8BA1\u7B97\u3002"), /*#__PURE__*/React.createElement(ResourceHours, {
      data: data,
      onDrill: onDrill,
      view: resourceView,
      onChange: onResourceView
    }));
    if (expanded) return /*#__PURE__*/React.createElement("section", {
      className: "er-chart-disclosure er-chart-expanded",
      "data-expanded": "true",
      "aria-label": title
    }, /*#__PURE__*/React.createElement("h3", {
      className: "er-chart-title"
    }, title), body);
    return /*#__PURE__*/React.createElement("details", {
      className: "er-chart-disclosure",
      open: open,
      onToggle: event => onChange(event.currentTarget.open)
    }, /*#__PURE__*/React.createElement("summary", null, title), body);
  }
  window.ReviewCharts = Charts;
})();
