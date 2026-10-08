(function () {
  'use strict';

  const C = window.APSResourceContract;
  const {
    Button,
    Icon,
    MetricValue
  } = window.ResourceControls;
  const labels = {
    known: '已确认',
    recorded: '已登记',
    zero: '0 条记录',
    unknown: '未知',
    not_configured: '未填写',
    unavailable: '暂无数据'
  };
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  const number = value => Number.isFinite(value) && value >= 0;
  const amount = value => window.WorkbenchFormat.number(value, {
    digits: 1
  });
  const integer = value => window.WorkbenchFormat.number(value, {
    digits: 0
  });
  const hoursOrNone = value => value == null ? '暂无数据' : window.WorkbenchFormat.hours(value);
  const countLabels = {
    active: '启用',
    inactive: '停用',
    maintain: '停机',
    leave: '请假',
    pending_review: '待复核',
    unknown: '未知'
  };
  const chipOrder = ['process', 'material', 'op_int', 'machine', 'operator', 'op_ext', 'supplier'];
  // 首次展开；手动选择在同一页会话内跨节点保留，不因窗口尺寸改变而重置。
  const COLLAPSED_CHOICE_KEY = 'aps_resource_rail_collapsed';
  function readCollapsedChoice() {
    try {
      const value = sessionStorage.getItem(COLLAPSED_CHOICE_KEY);
      return {
        collapsed: value === 'true' ? true : value === 'false' ? false : null,
        error: ''
      };
    } catch (_) {
      return {
        collapsed: null,
        error: '无法读取产能链显示设置，当前已展开，仍可手动收起。'
      };
    }
  }
  function processText(item, total, loading) {
    const unavailable = {
      lead: '工艺阶段暂无数据',
      pending: '',
      lines: []
    };
    if (loading || !item || item.status === 'unavailable') return unavailable;
    const counts = item.counts;
    const fields = ['total', 'route', 'source', 'hours', 'ready', 'legacy', 'managed', 'legacy_route_present', 'route_confirmed', 'source_confirmed', 'hours_confirmed'];
    if (!counts || !fields.every(key => Number.isSafeInteger(counts[key]) && counts[key] >= 0) || counts.total !== total || counts.route + counts.source + counts.hours + counts.ready !== total || counts.legacy + counts.managed !== total || counts.legacy_route_present > Math.min(counts.legacy, counts.source) || counts.legacy - counts.legacy_route_present > counts.route || counts.route_confirmed !== counts.source + counts.hours + counts.ready - counts.legacy_route_present || counts.source_confirmed !== counts.hours + counts.ready || counts.hours_confirmed !== counts.ready || item.status !== (total === 0 ? 'zero' : counts.ready === total ? 'ready' : 'pending')) return unavailable;
    if (total === 0) return {
      lead: '暂无零件',
      pending: '',
      lines: []
    };
    return {
      lead: '已确认 ' + counts.ready + ' / ' + total + ' 项',
      pending: [['route', '待路线'], ['source', '待归属'], ['hours', '待工时']].filter(([key]) => counts[key] > 0).map(([key, label]) => label + ' ' + counts[key]).join(' · '),
      lines: ['待路线 ' + counts.route + ' / 待归属 ' + counts.source + ' / 待工时 ' + counts.hours, '已确认：路线 ' + counts.route_confirmed + ' / 归属 ' + counts.source_confirmed + ' / 工时 ' + counts.hours_confirmed, ...(counts.legacy ? [counts.legacy + ' 项暂无确认记录，其中 ' + counts.legacy_route_present + ' 项已有路线资料'] : [])]
    };
  }
  function itemLines(item, key) {
    if (!item) return [];
    if (item.status === 'unavailable') return ['关联数量暂无数据'];
    const states = Object.keys(countLabels).filter(key => number(item.counts[key]) && item.counts[key] > 0).map(key => countLabels[key] + ' ' + integer(item.counts[key]));
    const facts = key === 'op_int' ? [['without_machines', '未关联设备'], ['available_operators', '匹配人员']] : key === 'op_ext' ? [['merge_mode_unset', '周期规则未设'], ['available_suppliers', '匹配供应商']] : [];
    facts.forEach(([field, label]) => states.push(label + ' ' + (number(item.counts[field]) ? integer(item.counts[field]) : '未知')));
    return states;
  }
  const itemText = (item, key) => itemLines(item, key).join(' / ');
  function dayText(day) {
    const origin = day.explicit ? '单独设置' : '按默认（未单独设置）';
    if (!day.effective) return day.date + ' · ' + origin + ' · 暂无数据：' + day.issues.map(issue => issue.message).join('；');
    const value = day.effective;
    return day.date + ' · ' + origin + '\n' + window.WorkbenchFormat.dateTime(value.window_start, {
      seconds: true
    }) + ' 至 ' + window.WorkbenchFormat.dateTime(value.window_end, {
      seconds: true
    }) + (value.crosses_midnight ? '（跨夜，归班次起始日）' : '') + '\n班次 ' + window.WorkbenchFormat.hours(value.hours) + ' × 效率 ' + amount(value.efficiency * 100) + '%；有效 ' + window.WorkbenchFormat.hours(value.effective_hours) + '\n普通件 ' + (value.allow_normal ? '允许' : '不允许') + ' / 急件及特急件 ' + (value.allow_urgent ? '允许' : '不允许') + (value.rest_reason === 'priorities_disabled' ? '；普通件和急件都不许可，但班次工时不是 0' : '') + (day.issues.length ? '\n' + day.issues.map(issue => issue.message).join('；') : '');
  }
  function CalendarSummary({
    value,
    error,
    loading,
    node,
    disabled,
    onNode
  }) {
    const stats = value && value.stats,
      standard = value && value.standard_hours;
    const standardText = standard ? standard.status === 'known' ? window.WorkbenchFormat.hours(standard.value) : labels[standard.status] : '暂无数据';
    const days = value ? value.days : weekdays.map((label, index) => ({
      weekday: index,
      date: label,
      status: 'unavailable',
      issues: []
    }));
    const source = stats ? stats.configured_days === 0 ? '本周全部按默认规则' : '单独设置 ' + integer(stats.configured_days) + ' 天 · 按默认 ' + integer(stats.default_days) + ' 天' : '来源暂无数据';
    const differentPriorities = stats && (stats.normal_effective_hours !== stats.effective_hours || stats.urgent_effective_hours !== stats.effective_hours);
    return /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: 'hb-block hero hb-cal-block' + (node === 'calendar' ? ' on' : ''),
      "aria-label": "\u5DE5\u4F5C\u65E5\u5386 \xB7 \u5168\u5C40",
      style: {
        font: 'inherit',
        color: 'inherit',
        textAlign: 'left'
      },
      disabled: disabled,
      "aria-pressed": node === 'calendar',
      onClick: () => onNode('calendar')
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-summary"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-heading"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bhead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bdot cal"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-bname"
    }, "\u5DE5\u4F5C\u65E5\u5386"), /*#__PURE__*/React.createElement("span", {
      className: "hb-bmeas"
    }, "\u81EA\u5236 \xB7 \u5168\u5C40")), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-range"
    }, /*#__PURE__*/React.createElement(MetricValue, {
      pending: loading
    }, value ? value.week_start + ' 至 ' + value.week_end : '日期暂无数据'))), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stats"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat",
      "data-calendar-week-hours": true
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-label"
    }, "\u672C\u5468\u6709\u6548"), ' ', /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-value"
    }, /*#__PURE__*/React.createElement(MetricValue, {
      pending: loading
    }, stats ? hoursOrNone(stats.effective_hours) : '暂无数据'))), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-label"
    }, "\u5DE5\u4F5C\u65E5"), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-value"
    }, /*#__PURE__*/React.createElement(MetricValue, {
      pending: loading
    }, stats ? stats.work_days == null ? '未知' : integer(stats.work_days) + ' 天' : '暂无数据'))), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-label"
    }, "\u4F11\u606F / \u7981\u6392"), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-stat-value"
    }, /*#__PURE__*/React.createElement(MetricValue, {
      pending: loading
    }, stats ? stats.rest_days == null ? '未知' : integer(stats.rest_days) + ' 天' : '暂无数据')))), differentPriorities && /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-facts"
    }, "\u666E\u901A\u4EF6 ", hoursOrNone(stats.normal_effective_hours), " \xB7 \u6025\u4EF6 ", hoursOrNone(stats.urgent_effective_hours))), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-week"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-unit"
    }, "\u6BCF\u65E5\u6709\u6548\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-strip"
    }, days.map(day => {
      const effective = day.effective,
        rest = effective && effective.is_rest;
      return /*#__PURE__*/React.createElement("span", {
        className: 'hb-seg' + (rest ? ' rest' : '') + (!loading && !effective ? ' unavailable' : ''),
        key: day.date,
        "data-calendar-date": day.date,
        "data-calendar-source": day.source,
        "data-calendar-status": day.status,
        title: value ? dayText(day) : loading ? '正在读取工作日历' : error || '工作日历暂无数据'
      }, /*#__PURE__*/React.createElement("span", {
        className: "hb-sl"
      }, weekdays[day.weekday]), /*#__PURE__*/React.createElement("span", {
        className: "rail-day-value"
      }, /*#__PURE__*/React.createElement(MetricValue, {
        pending: loading
      }, effective ? rest ? effective.rest_reason === 'priorities_disabled' ? '禁排' : '休息' : amount(effective.effective_hours) : '未知')));
    })), /*#__PURE__*/React.createElement("span", {
      className: "rail-calendar-source"
    }, /*#__PURE__*/React.createElement(MetricValue, {
      pending: loading
    }, source, " \xB7 \u6807\u51C6 ", standardText, " / \u65E5"))));
  }
  function ResourceRail({
    node,
    counts,
    onNode,
    onNavigate,
    disabled
  }) {
    const summary = counts.summary || {},
      value = summary.data || {},
      readiness = value.readiness;
    const items = readiness && readiness.items || {};
    const process = processText(items.process, counts.process && counts.process.total, summary.loading);
    const [choice, setChoice] = React.useState(readCollapsedChoice);
    const compact = choice.collapsed === true;
    function toggle() {
      const next = !compact;
      let error = '';
      try {
        sessionStorage.setItem(COLLAPSED_CHOICE_KEY, String(next));
      } catch (_) {
        error = '无法保存产能链显示设置，当前显示已切换；重新打开时可能恢复原设置。';
      }
      setChoice({
        collapsed: next,
        error
      });
    }
    const countText = key => {
      const item = counts[key];
      return item && number(item.total) ? integer(item.total) + ' ' + C.nodes[key].unit : summary.loading ? '未读取' : '暂无数据';
    };
    const notices = [...new Set([summary.error && C.message(summary.error), value.readiness_error, value.calendar_error, ...chipOrder.flatMap(key => (items[key] && items[key].issues || []).map(issue => C.nodes[key].label + '：' + issue.message)), ...(value.calendar ? [...(value.calendar.stats.issues || []).map(issue => '工作日历：' + issue.message), ...value.calendar.days.flatMap(day => day.issues.map(issue => day.date + '：' + issue.message)), ...value.calendar.holiday_default_efficiency.issues.map(issue => '假期默认效率：' + issue.message)] : [])].filter(Boolean))];
    const tile = (key, tone) => {
      const item = items[key],
        text = countText(key),
        count = counts[key];
      const lines = itemLines(item, key),
        issues = item && item.issues || [];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: 'hb-tile ' + tone + (node === key ? ' on' : ''),
        key: key,
        disabled: disabled,
        "data-rail-node": key,
        title: [C.nodes[key].label, ...lines, ...issues.map(issue => issue.message), count && count.error].filter(Boolean).join('；'),
        "aria-pressed": node === key,
        onClick: () => onNode(key)
      }, /*#__PURE__*/React.createElement("span", {
        className: 'hb-tico ' + tone
      }, /*#__PURE__*/React.createElement(Icon, {
        name: C.nodes[key].icon
      })), /*#__PURE__*/React.createElement("span", {
        className: "hb-tbody"
      }, /*#__PURE__*/React.createElement("span", {
        className: "rail-tile-title"
      }, /*#__PURE__*/React.createElement("span", {
        className: "hb-tname"
      }, C.nodes[key].label), /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta"
      }, /*#__PURE__*/React.createElement(MetricValue, {
        pending: summary.loading
      }, text))), key === 'process' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta rail-process-progress"
      }, /*#__PURE__*/React.createElement(MetricValue, {
        pending: summary.loading
      }, process.lead)), process.pending && /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta rail-pending"
      }, process.pending)) : lines.length > 0 && /*#__PURE__*/React.createElement("span", {
        className: "rail-tile-facts"
      }, lines.map(line => /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta",
        key: line
      }, /*#__PURE__*/React.createElement(MetricValue, {
        pending: summary.loading
      }, line))))));
    };
    const lane = (label, tone, keys) => /*#__PURE__*/React.createElement("div", {
      className: 'hb-lane ' + (tone === 'int' ? 'intl' : 'extl')
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-lane-head"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-lane-dot"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-lane-name"
    }, label), /*#__PURE__*/React.createElement("span", {
      className: "hb-lane-meas"
    }, tone === 'int' ? '按工时排产' : '按自然日周期')), /*#__PURE__*/React.createElement("div", {
      className: 'hb-lane-row rail-resource-links' + (keys.length === 2 ? ' rail-resource-pair' : ''),
      "data-resource-source": keys[0],
      "data-resource-targets": keys.slice(1).join(' ')
    }, /*#__PURE__*/React.createElement("div", {
      className: "rail-branch-source"
    }, tile(keys[0], tone)), /*#__PURE__*/React.createElement("span", {
      className: 'rail-branch-link' + (keys.length > 2 ? ' fork' : ''),
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right"
    })), /*#__PURE__*/React.createElement("div", {
      className: "rail-branch-targets"
    }, keys.slice(1).map(key => tile(key, tone)))));
    const chip = (key, label, icon) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: key,
      className: node === key ? 'on' : '',
      "data-rail-node": key,
      "aria-pressed": node === key,
      disabled: disabled,
      title: C.nodes[key] ? [C.nodes[key].label, itemText(items[key], key)].filter(Boolean).join('；') : label,
      onClick: () => onNode(key)
    }, /*#__PURE__*/React.createElement(Icon, {
      name: icon
    }), /*#__PURE__*/React.createElement("span", null, label), key !== 'calendar' && /*#__PURE__*/React.createElement("b", null, /*#__PURE__*/React.createElement(MetricValue, {
      pending: summary.loading
    }, countText(key))));
    return /*#__PURE__*/React.createElement("section", {
      className: 'rail' + (compact ? ' rail-collapsed' : ''),
      "data-collapsed": compact ? 'true' : 'false',
      "aria-label": "\u4EA7\u80FD\u94FE",
      "aria-busy": !!summary.loading
    }, /*#__PURE__*/React.createElement("div", {
      className: "rail-bar"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-cap"
    }, "\u4EA7\u80FD\u94FE"), summary.loading && /*#__PURE__*/React.createElement("span", {
      className: "rail-read-state",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u2026"), /*#__PURE__*/React.createElement(Button, {
      className: "btn link rail-toggle",
      icon: compact ? 'chevron-down' : 'chevron-up',
      "aria-expanded": !compact,
      onClick: toggle
    }, compact ? '展开产能链' : '收起产能链')), choice.error && /*#__PURE__*/React.createElement("p", {
      className: "muted",
      role: "alert"
    }, choice.error), notices.length > 0 && /*#__PURE__*/React.createElement("ul", {
      className: "rail-notices",
      role: "alert"
    }, notices.map(text => /*#__PURE__*/React.createElement("li", {
      key: text
    }, text))), compact && /*#__PURE__*/React.createElement("div", {
      className: "seg rail-compact",
      role: "group",
      "aria-label": "\u4EA7\u80FD\u94FE\u5FEB\u6377\u5207\u6362"
    }, chipOrder.map(key => chip(key, C.nodes[key].label, C.nodes[key].icon)), chip('calendar', '工作日历', 'calendar-days')), !compact && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "flow"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-hub",
      style: {
        width: '100%'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-block hero rail-input"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-bhead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bdot io"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-bname"
    }, "\u5DE5\u827A\u4E0E\u7269\u6599")), /*#__PURE__*/React.createElement("div", {
      className: "hb-bbody"
    }, tile('process', 'io'), tile('material', 'io'))), /*#__PURE__*/React.createElement("div", {
      className: "hb-flowarr",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right"
    })), /*#__PURE__*/React.createElement("div", {
      className: "hb-block hero hb-ops"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-bhead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bdot fk"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-bname"
    }, "\u52A0\u5DE5\u8D44\u6E90")), /*#__PURE__*/React.createElement("div", {
      className: "hb-bbody"
    }, lane('自制链', 'int', ['op_int', 'machine', 'operator']), lane('外协链', 'ext', ['op_ext', 'supplier']))), /*#__PURE__*/React.createElement("div", {
      className: "hb-flowarr",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right"
    })), /*#__PURE__*/React.createElement(CalendarSummary, {
      value: value.calendar,
      loading: summary.loading,
      error: summary.error ? C.message(summary.error) : value.calendar_error,
      node: node,
      disabled: disabled,
      onNode: onNode
    }))), /*#__PURE__*/React.createElement("div", {
      className: "rail-foot"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-r-top"
    }, (process.lines.length > 0 || value.calendar) && /*#__PURE__*/React.createElement("details", {
      className: "rail-details"
    }, /*#__PURE__*/React.createElement("summary", null, "\u786E\u8BA4\u8BB0\u5F55\u4E0E\u65E5\u5386\u89C4\u5219"), /*#__PURE__*/React.createElement("div", {
      className: "rail-detail-content"
    }, process.lines.length > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, "\u5DE5\u827A\u786E\u8BA4\u8BB0\u5F55"), process.lines.map(line => /*#__PURE__*/React.createElement("p", {
      key: line
    }, line))), value.calendar && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, "\u5DE5\u4F5C\u65E5\u5386\u89C4\u5219"), /*#__PURE__*/React.createElement("p", null, value.calendar.basis), /*#__PURE__*/React.createElement("p", null, "\u5DE5\u5382\u65E5\u671F ", value.calendar.factory_today, " \xB7 \u6309\u73ED\u6B21\u8D77\u59CB\u65E5\u7EDF\u8BA1"), /*#__PURE__*/React.createElement("p", null, "\u5047\u671F\u5F55\u5165\u9ED8\u8BA4\u6548\u7387\uFF1A", value.calendar.holiday_default_efficiency.status === 'known' ? amount(value.calendar.holiday_default_efficiency.value * 100) + '%' : labels[value.calendar.holiday_default_efficiency.status], "\u3002", value.calendar.holiday_default_efficiency.basis)))), /*#__PURE__*/React.createElement("span", {
      className: "hb-r-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      className: "hb-r-next",
      icon: "arrow-right",
      disabled: disabled,
      reason: typeof onNavigate !== 'function' ? '批次管理尚未开通。' : '',
      onClick: () => onNavigate('batches')
    }, "\u4E0B\u4E00\u6B65 \xB7 \u6279\u6B21\u7BA1\u7406")))));
  }
  window.ResourceRail = ResourceRail;
})();
