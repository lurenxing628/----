(function () {
  'use strict';

  const C = window.APSResourceContract;
  const {
    Button,
    Icon
  } = window.ResourceControls;
  const labels = {
    known: '已核实',
    recorded: '已登记',
    zero: '0 条记录',
    unknown: '未知',
    not_configured: '未配置',
    unavailable: '无法核实'
  };
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  const number = value => Number.isFinite(value) && value >= 0;
  const amount = value => number(value) ? String(Number(value.toFixed(3))) : '未知';
  const countLabels = {
    active: '启用',
    inactive: '停用',
    maintain: '检修',
    leave: '请假',
    pending_review: '待复核',
    unknown: '未知'
  };
  function processText(item, total, loading) {
    const unavailable = {
      lead: loading ? '工艺阶段待读取' : '工艺阶段无法核实',
      lines: []
    };
    if (loading || !item || item.status === 'unavailable') return unavailable;
    const counts = item.counts;
    const fields = ['total', 'route', 'source', 'hours', 'ready', 'legacy', 'managed', 'legacy_route_present', 'route_confirmed', 'source_confirmed', 'hours_confirmed'];
    if (!counts || !fields.every(key => Number.isSafeInteger(counts[key]) && counts[key] >= 0) || counts.total !== total || counts.route + counts.source + counts.hours + counts.ready !== total || counts.legacy + counts.managed !== total || counts.legacy_route_present > Math.min(counts.legacy, counts.source) || counts.legacy - counts.legacy_route_present > counts.route || counts.route_confirmed !== counts.source + counts.hours + counts.ready - counts.legacy_route_present || counts.source_confirmed !== counts.hours + counts.ready || counts.hours_confirmed !== counts.ready || item.status !== (total === 0 ? 'zero' : counts.ready === total ? 'ready' : 'pending')) return unavailable;
    if (total === 0) return {
      lead: '暂无零件',
      lines: []
    };
    return {
      lead: '工艺已确认 ' + counts.ready + ' / ' + total + ' 项',
      lines: ['待路线 ' + counts.route + ' / 待归属 ' + counts.source + ' / 待工时 ' + counts.hours, '已确认：路线 ' + counts.route_confirmed + ' / 归属 ' + counts.source_confirmed + ' / 工时 ' + counts.hours_confirmed, ...(counts.legacy ? ['存量 ' + counts.legacy + ' 项未确认；含路线资料 ' + counts.legacy_route_present + ' 项'] : [])]
    };
  }
  function itemText(item, key) {
    if (!item) return '';
    const states = Object.keys(countLabels).filter(key => number(item.counts[key]) && item.counts[key] > 0).map(key => countLabels[key] + ' ' + item.counts[key]);
    const facts = key === 'op_int' ? [['without_machines', '未绑设备'], ['available_operators', '匹配人员']] : key === 'op_ext' ? [['merge_mode_unset', '策略未设'], ['available_suppliers', '匹配供应商']] : [];
    facts.forEach(([field, label]) => {
      if (number(item.counts[field])) states.push(label + ' ' + item.counts[field]);
    });
    return states.join(' / ');
  }
  function dayText(day) {
    const origin = day.explicit ? '显式配置' : '服务默认（未配置）';
    if (!day.effective) return day.date + ' · ' + origin + ' · 无法核实：' + day.issues.map(issue => issue.message).join('；');
    const value = day.effective;
    return day.date + ' · ' + origin + '\n' + value.window_start + ' 至 ' + value.window_end + (value.crosses_midnight ? '（跨夜，归班次起始日）' : '') + '\n班次 ' + amount(value.hours) + ' h × 效率 ' + amount(value.efficiency * 100) + '%；有效 ' + amount(value.effective_hours) + ' h\n普通件 ' + (value.allow_normal ? '允许' : '不允许') + ' / 急件及特急件 ' + (value.allow_urgent ? '允许' : '不允许') + (value.rest_reason === 'priorities_disabled' ? '；两类均不许可，非0班次工时' : '') + (day.issues.length ? '\n' + day.issues.map(issue => issue.message).join('；') : '');
  }
  function CalendarSummary({
    value,
    error,
    loading,
    node,
    disabled,
    onNode
  }) {
    const pending = loading ? '待读取' : '无法核实';
    const stats = value && value.stats,
      standard = value && value.standard_hours;
    const standardText = standard ? standard.status === 'known' ? amount(standard.value) + ' h' : labels[standard.status] : pending;
    const days = value ? value.days : weekdays.map((label, index) => ({
      weekday: index,
      date: label,
      status: 'unavailable',
      issues: []
    }));
    const rest = stats && stats.rest_days != null ? stats.rest_days + ' 天' : pending;
    const holiday = value && value.holiday_default_efficiency;
    const caption = value ? value.week_start + ' 至 ' + value.week_end : '本周排班 · ' + pending;
    return /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: 'hb-block hero hb-cal-block' + (node === 'calendar' ? ' on' : ''),
      style: {
        font: 'inherit',
        color: 'inherit',
        textAlign: 'left'
      },
      disabled: disabled,
      "aria-pressed": node === 'calendar',
      onClick: () => onNode('calendar')
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bhead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bdot cal"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-bname"
    }, "\u5DE5\u4F5C\u65E5\u5386"), /*#__PURE__*/React.createElement("span", {
      className: "hb-bmeas"
    }, "\u5168\u5C40")), /*#__PURE__*/React.createElement("span", {
      className: "hb-bbody"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-top"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "calendar-days"
    })), /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-lead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-cl1"
    }, "\u5DE5\u65F6 / \u8C03\u4F11 / \u52A0\u73ED"), /*#__PURE__*/React.createElement("span", {
      className: "hb-cl2",
      title: value ? value.basis : error
    }, stats ? '本周显式 ' + stats.configured_days + ' 天 · 服务默认 ' + stats.default_days + ' 天' : error || pending))), /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-stats"
    }, [[standardText, '标准工时 / 日', standard && standard.message], [stats && stats.work_days != null ? stats.work_days + ' 天' : pending, '本周工作日', '有工时且至少允许普通件或急件的班次起始日'], [rest, '休息 / 无许可', stats && stats.known_rest_dates.join('、')]].map(([text, label, title]) => /*#__PURE__*/React.createElement("span", {
      className: "hb-cs",
      key: label,
      style: {
        minWidth: 0
      },
      title: title || undefined
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-csv",
      style: {
        fontSize: 12,
        whiteSpace: 'normal',
        letterSpacing: 0
      }
    }, text), /*#__PURE__*/React.createElement("span", {
      className: "hb-csl"
    }, label)))), /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-strip-cap",
      style: {
        flexWrap: 'wrap'
      }
    }, caption), /*#__PURE__*/React.createElement("span", {
      className: "hb-cal-strip"
    }, days.map(day => {
      const effective = day.effective,
        rest = effective && effective.is_rest;
      return /*#__PURE__*/React.createElement("span", {
        className: 'hb-seg' + (rest ? ' rest' : ''),
        key: day.date,
        "data-calendar-date": day.date,
        "data-calendar-source": day.source,
        "data-calendar-status": day.status,
        title: value ? dayText(day) : error || pending
      }, /*#__PURE__*/React.createElement("span", {
        className: "hb-sl"
      }, weekdays[day.weekday]), /*#__PURE__*/React.createElement("span", {
        className: "hb-sb",
        style: !effective ? {
          background: 'var(--ui-border)'
        } : {},
        "aria-label": value ? dayText(day) : weekdays[day.weekday] + ' ' + pending
      }), /*#__PURE__*/React.createElement("span", {
        className: "hb-sl"
      }, effective ? rest ? effective.rest_reason === 'priorities_disabled' ? '禁排' : '休' : amount(effective.effective_hours) + 'h' : '?'), /*#__PURE__*/React.createElement("span", {
        className: "hb-sl"
      }, value ? day.explicit ? '显式' : '默认' : '?'));
    })), value && /*#__PURE__*/React.createElement("span", {
      className: "hb-cl2",
      title: value.basis,
      "data-calendar-week-hours": true
    }, "\u672C\u5468\u6709\u6548 ", stats.effective_hours == null ? '无法核实' : amount(stats.effective_hours) + ' h', " \xB7 \u666E\u901A ", amount(stats.normal_effective_hours), " / \u6025\u4EF6 ", amount(stats.urgent_effective_hours), " h", /*#__PURE__*/React.createElement("br", null), "\u5DE5\u5382\u65E5\u671F ", value.factory_today, " \xB7 \u73ED\u6B21\u8D77\u59CB\u65E5\u53E3\u5F84", /*#__PURE__*/React.createElement("br", null), /*#__PURE__*/React.createElement("span", {
      title: holiday.basis + (holiday.issues.length ? '；' + holiday.issues.map(issue => issue.message).join('；') : '')
    }, "\u5047\u671F\u5F55\u5165\u9ED8\u8BA4\u6548\u7387\uFF1A", holiday.status === 'known' ? amount(holiday.value * 100) + '%' : labels[holiday.status]), stats.unavailable_days > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("br", null), stats.unavailable_days, " \u5929\u65E0\u6CD5\u6838\u5B9E"))));
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
    const tile = (key, tone) => {
      const item = items[key],
        count = counts[key],
        text = count && number(count.total) ? count.total + ' ' + C.nodes[key].unit : summary.loading ? '待读取' : '无法核实';
      const details = itemText(item, key),
        issues = item && item.issues || [];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: 'hb-tile ' + tone + (node === key ? ' on' : ''),
        key: key,
        disabled: disabled,
        "data-rail-node": key,
        title: [C.nodes[key].label, details, ...issues.map(issue => issue.message), count && count.error].filter(Boolean).join('；'),
        "aria-pressed": node === key,
        onClick: () => onNode(key)
      }, /*#__PURE__*/React.createElement("span", {
        className: 'hb-tico ' + tone
      }, /*#__PURE__*/React.createElement(Icon, {
        name: C.nodes[key].icon
      })), /*#__PURE__*/React.createElement("span", {
        className: "hb-tbody"
      }, /*#__PURE__*/React.createElement("span", {
        className: "hb-tname"
      }, C.nodes[key].label), /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta"
      }, text), details && /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta"
      }, details), key === 'process' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta",
        style: {
          fontWeight: 600,
          whiteSpace: 'normal'
        }
      }, process.lead), process.lines.map(line => /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta",
        key: line,
        style: {
          whiteSpace: 'normal',
          overflowWrap: 'anywhere'
        }
      }, line))), key !== 'process' && item && item.status === 'unavailable' && /*#__PURE__*/React.createElement("span", {
        className: "hb-tmeta"
      }, "\u5173\u8054\u91CF\u65E0\u6CD5\u6838\u5B9E")));
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
    }, tone === 'int' ? '工时口径' : '周期口径'), /*#__PURE__*/React.createElement("span", {
      className: "hb-lane-count"
    }, keys.length, " \u9879")), /*#__PURE__*/React.createElement("div", {
      className: "hb-lane-row"
    }, keys.map(key => tile(key, tone))));
    return /*#__PURE__*/React.createElement("section", {
      className: "rail",
      "aria-label": "\u4EA7\u80FD\u94FE\u4E3B\u7EBF",
      "aria-busy": !!summary.loading
    }, /*#__PURE__*/React.createElement("div", {
      className: "rail-bar"
    }, /*#__PURE__*/React.createElement("span", {
      className: "rail-cap"
    }, "\u4EA7\u80FD\u94FE\u4E3B\u7EBF"), /*#__PURE__*/React.createElement("span", {
      className: "rail-status muted"
    }, "\u57FA\u7840\u8D44\u6599 \xB7 ", summary.error ? '无法核实' : summary.loading ? '读取中' : '只读汇总')), /*#__PURE__*/React.createElement("div", {
      className: "flow"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-hub",
      style: {
        width: '100%'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-block hero"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-bhead"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-bdot io"
    }), /*#__PURE__*/React.createElement("span", {
      className: "hb-bname"
    }, "\u6570\u636E\u8F93\u5165"), /*#__PURE__*/React.createElement("span", {
      className: "hb-bmeas"
    }, "2 \u6E90")), /*#__PURE__*/React.createElement("div", {
      className: "hb-bbody"
    }, tile('process', 'io'), tile('material', 'io'))), /*#__PURE__*/React.createElement("div", {
      className: "hb-flowarr"
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
    }, "\u5DE5\u5E8F \xB7 \u4E24\u6761\u94FE"), /*#__PURE__*/React.createElement("span", {
      className: "hb-bnum"
    }, "5 \u73AF\u8282")), /*#__PURE__*/React.createElement("div", {
      className: "hb-bbody"
    }, lane('自制链', 'int', ['op_int', 'machine', 'operator']), lane('外协链', 'ext', ['op_ext', 'supplier']))), /*#__PURE__*/React.createElement("div", {
      className: "hb-flowarr"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right"
    })), /*#__PURE__*/React.createElement(CalendarSummary, {
      value: value.calendar,
      loading: summary.loading,
      error: summary.error || value.calendar_error,
      node: node,
      disabled: disabled,
      onNode: onNode
    }))), /*#__PURE__*/React.createElement("div", {
      className: "rail-foot"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-ready"
    }, /*#__PURE__*/React.createElement("div", {
      className: "hb-r-top",
      style: {
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "hb-rl1"
    }, "\u4EA7\u80FD\u5C31\u7EEA\u5EA6"), /*#__PURE__*/React.createElement("span", {
      className: "hb-rl2"
    }, summary.loading ? '待读取' : summary.error ? '无法核实' : '未知'), /*#__PURE__*/React.createElement("span", {
      className: "hb-r-tag",
      style: {
        whiteSpace: 'normal',
        flexShrink: 1
      }
    }, summary.error || value.readiness_error || process.lead), /*#__PURE__*/React.createElement("span", {
      className: "hb-r-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      className: "hb-r-next",
      icon: "arrow-right",
      disabled: disabled,
      reason: typeof onNavigate !== 'function' ? '批次导航尚未接入。' : '',
      onClick: () => onNavigate('batches')
    }, "\u4E0B\u4E00\u6B65 \xB7 \u6279\u6B21\u7BA1\u7406")), /*#__PURE__*/React.createElement("div", {
      className: "hb-cl2",
      style: {
        padding: '0 18px 12px'
      },
      role: "status"
    }, readiness ? readiness.message : '未获得整体就绪口径；未推定就绪率。'), /*#__PURE__*/React.createElement("div", {
      className: "hb-r-floor",
      "aria-label": "\u6574\u4F53\u5C31\u7EEA\u5EA6\u672A\u77E5"
    }))));
  }
  window.ResourceRail = ResourceRail;
})();
