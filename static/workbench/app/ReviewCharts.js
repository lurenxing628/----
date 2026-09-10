(function () {
  'use strict';

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
      } = view;
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
    }, /*#__PURE__*/React.createElement("style", null, `
        .er-resource-hours .er-resource-row { display:grid; grid-template-columns:minmax(120px,1fr) minmax(100px,2fr) minmax(160px,1fr); align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid var(--ui-border); }
        .er-resource-hours .er-resource-name { white-space:normal; overflow-wrap:anywhere; text-align:left; }
        .er-resource-hours .er-resource-bar { width:100%; height:26px; position:relative; background:var(--ui-surface-muted); border:0; padding:0; border-radius:0; }
        .er-resource-hours .er-resource-bar i { position:absolute; top:0; bottom:0; left:0; background:var(--ui-info-text); }
        .er-resource-hours .er-resource-value { font-size:12px; overflow-wrap:anywhere; }
        @media(max-width:700px) { .er-resource-hours .er-resource-row { grid-template-columns:minmax(100px,1fr) minmax(90px,1fr); }.er-resource-hours .er-resource-value { grid-column:1/-1; } }
      `), /*#__PURE__*/React.createElement("div", {
      className: "rw-section-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5B9E\u9645\u8D44\u6E90\u5DE5\u65F6"), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "tablist",
      "aria-label": "\u8D44\u6E90\u5DE5\u65F6\u7C7B\u578B"
    }, [['machine', '设备'], ['operator', '人员']].map(([key, label]) => /*#__PURE__*/React.createElement(Button, {
      key: key,
      role: "tab",
      "aria-selected": kind === key,
      className: 'seg-btn' + (kind === key ? ' on' : ''),
      onClick: () => onChange({
        kind: key,
        page: 1
      })
    }, label)))), /*#__PURE__*/React.createElement("div", {
      role: "tabpanel",
      "aria-label": kind === 'machine' ? '实际设备工时' : '实际人员工时'
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
      title: '已知工时 ' + window.ReportTable.text(row.known_effective_processing_hours) + ' h；未知 ' + row.unknown_hour_events + ' 条'
    }, row.known_effective_processing_hours !== null && /*#__PURE__*/React.createElement("i", {
      "aria-hidden": "true",
      style: {
        width: row.known_effective_processing_hours / maximum * 100 + '%'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "er-resource-value"
    }, row.effective_processing_hours === null ? '总工时未知' : row.effective_processing_hours + ' h', " \xB7 \u5DF2\u77E5 ", window.ReportTable.text(row.known_effective_processing_hours), " h \xB7 \u5F85\u8865 ", row.unknown_hour_events, " \u6761"))), !rows.length && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u8D44\u6E90\u5DE5\u65F6\u8BB0\u5F55\u3002")), /*#__PURE__*/React.createElement("div", {
      className: "rw-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", rows.length, " \u7EC4 \xB7 ", current, " / ", pages), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u8D44\u6E90\u5DE5\u65F6\u4E0A\u4E00\u9875",
      disabled: current <= 1,
      onClick: () => onChange({
        kind,
        page: current - 1
      })
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u8D44\u6E90\u5DE5\u65F6\u4E0B\u4E00\u9875",
      disabled: current >= pages,
      onClick: () => onChange({
        kind,
        page: current + 1
      })
    })), /*#__PURE__*/React.createElement("p", {
      className: "er-method"
    }, "\u5B9E\u9645\u52A0\u5DE5\u5DE5\u65F6\uFF0C\u4E0D\u4EE3\u8868\u5229\u7528\u7387\uFF1B\u4E0B\u94BB\u4FDD\u7559\u5173\u8054\u5DE5\u5E8F\u7684\u5168\u90E8\u8BB0\u5F55\u3002"), /*#__PURE__*/React.createElement(window.ReportTable.Table, {
      data: {
        topic: kind === 'machine' ? 'machines' : 'people',
        rows: visible,
        columns: window.ReviewChartViews.resourceColumns
      }
    }));
  }
  function Charts({
    data,
    open,
    onChange,
    onDrill,
    resourceView,
    onResourceView
  }) {
    const {
      DistributionChart,
      TrendChart
    } = window.ReviewChartViews;
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
    return /*#__PURE__*/React.createElement("details", {
      className: "er-chart-disclosure",
      open: open,
      onToggle: event => onChange(event.currentTarget.open)
    }, /*#__PURE__*/React.createElement("summary", null, "\u8D8B\u52BF\u3001\u504F\u5DEE\u4E0E\u8D44\u6E90\u5206\u6790"), /*#__PURE__*/React.createElement("div", {
      className: "er-overview-grid"
    }, /*#__PURE__*/React.createElement("section", {
      className: "er-section er-trend"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8BA1\u5212\u4E0E\u5B9E\u9645\u7D2F\u8BA1\u5B8C\u5DE5"), /*#__PURE__*/React.createElement(TrendChart, {
      points: points,
      label: "\u8303\u56F4\u5185\u5DE5\u5E8F\u7D2F\u8BA1\u5B8C\u5DE5"
    })), /*#__PURE__*/React.createElement("section", {
      className: "er-section er-insights"
    }, /*#__PURE__*/React.createElement("h3", null, "\u4E8B\u5B9E\u91CD\u70B9"), /*#__PURE__*/React.createElement("p", null, "\u5DF2\u786E\u8BA4\u665A\u5B8C ", data.summary.finish_late, " \u9053\uFF1B\u5230\u671F\u672A\u786E\u8BA4 ", data.summary.unclosed_due, " \u9053\u3002"), /*#__PURE__*/React.createElement("p", null, "\u65E7\u73B0\u573A\u4E8B\u4EF6 ", data.summary.events, " \u6761\uFF1B\u9010\u6B21\u62A5\u5DE5 ", data.summary.production_reports, " \u6761\uFF1B\u5168\u90E8\u8BB0\u5F55 ", data.summary.records, " \u6761\u3002"), /*#__PURE__*/React.createElement("p", null, "\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6 ", window.ReportTable.text(data.summary.effective_processing_hours), " \u5C0F\u65F6\uFF1B\u5DF2\u77E5\u5C0F\u8BA1 ", window.ReportTable.text(data.summary.known_effective_processing_hours), " \u5C0F\u65F6\uFF1B\u5DE5\u65F6\u672A\u77E5 ", data.summary.unknown_hour_events, " \u6761\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rw-actions"
    }, [['finish_late', '晚完明细'], ['unclosed', '未确认明细'], [data.scope.focus, '工序明细']].map(([focus, label]) => /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
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
    }, "\u5B9E\u9645\u66F2\u7EBF\u6309\u5DF2\u8BB0\u5F55\u7684\u6574\u9053\u5B8C\u5DE5\u4E8B\u5B9E\u56DE\u7B97\uFF0C\u4E0D\u662F\u5386\u53F2\u65F6\u70B9\u5FEB\u7167\uFF1B\u5230\u671F\u672A\u786E\u8BA4\u5DF2\u8FC7\u65F6\u957F\u4E0D\u662F\u5B9E\u9645\u665A\u5B8C\u504F\u5DEE\u3002"), /*#__PURE__*/React.createElement(ResourceHours, {
      data: data,
      onDrill: onDrill,
      view: resourceView,
      onChange: onResourceView
    }));
  }
  window.ReviewCharts = Charts;
})();
