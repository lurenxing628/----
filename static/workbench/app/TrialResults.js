(function () {
  'use strict';

  const U = window.TrialControls;
  function Summary({
    data
  }) {
    const c = data.comparison;
    return /*#__PURE__*/React.createElement("div", {
      className: "tt-summary"
    }, [[c.late_count, window.WorkbenchTerms.overdue_count], [c.total_delay_hours, window.WorkbenchTerms.total_tardiness_hours + '（小时）'], [c.changed_operations, '调整工序'], [c.moved_operations, '换设备工序']].map(([value, label]) => /*#__PURE__*/React.createElement("div", {
      key: label
    }, /*#__PURE__*/React.createElement("span", null, label), /*#__PURE__*/React.createElement("strong", null, U.number(value)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", null, "\u6362\u578B\u6B21\u6570"), /*#__PURE__*/React.createElement("strong", null, c.changeovers === null ? '未评估' : U.number(c.changeovers))));
  }
  function Calendar({
    resource
  }) {
    return /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u65F6\u6BB5\u4E0E\u73ED\u8868"), /*#__PURE__*/React.createElement("div", {
      className: "tt-subtable"
    }, /*#__PURE__*/React.createElement(U.Table, {
      label: "\u5360\u7528\u65F6\u6BB5",
      rows: resource.segments,
      size: 10,
      columns: [["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['并行工序', r => r.concurrent_operations]]
    }), /*#__PURE__*/React.createElement("h4", null, "\u53EF\u5DE5\u4F5C\u65F6\u6BB5"), resource.calendar.windows === null ? /*#__PURE__*/React.createElement("p", null, "\u771F\u5B9E\u73ED\u8868\u4E0D\u53EF\u7528") : /*#__PURE__*/React.createElement(U.Table, {
      label: "\u53EF\u5DE5\u4F5C\u65F6\u6BB5",
      rows: resource.calendar.windows,
      size: 10,
      columns: [["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)], ['效率', r => U.number(r.efficiency)], ['普通 / 急件', r => (r.allow_normal ? '允许' : '不允许') + ' / ' + (r.allow_urgent ? '允许' : '不允许')]]
    }), /*#__PURE__*/React.createElement(U.Issues, {
      rows: resource.calendar.issues
    }), resource.calendar.downtime_windows && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u505C\u673A\u65F6\u6BB5"), /*#__PURE__*/React.createElement(U.Table, {
      label: "\u505C\u673A\u65F6\u6BB5",
      rows: resource.calendar.downtime_windows,
      columns: [["开始", r => U.timeLabel(r.start)], ['结束', r => U.timeLabel(r.end)]]
    }))));
  }
  function Results({
    data,
    onSelect
  }) {
    const H = window.TrialAdoptionHistoryState,
      V = window.TrialViewState,
      preferences = V.useView(data);
    function readEntry() {
      try {
        const saved = history.state && history.state.trialAdoptionHistory;
        if (!data.scenario_ref || !saved || saved.scenario_ref !== data.scenario_ref) return {
          tab: null,
          error: null
        };
        if (!H) throw new Error('dependency not wired: window.TrialAdoptionHistoryState');
        return {
          tab: H.restore(data.scenario_ref).tab,
          error: null
        };
      } catch (_) {
        return {
          tab: null,
          error: new Error('本页试调页签记录无法恢复，未用默认页签覆盖。')
        };
      }
    }
    const [entry, setEntry] = React.useState(readEntry),
      name = window.TrialGantt.resourceNames(data),
      c = data.comparison;
    const tab = entry.tab || preferences.value && preferences.value.result_tab;
    function clearEntry() {
      try {
        const current = history.state,
          saved = current && current.trialAdoptionHistory;
        if (saved && saved.scenario_ref === data.scenario_ref) {
          const next = {
            ...current
          };
          delete next.trialAdoptionHistory;
          history.replaceState(next, '', location.href);
        }
        setEntry(readEntry());
      } catch (_) {
        setEntry({
          ...entry,
          error: new Error('本页试调页签记录未能清除，未清理其他页面。')
        });
      }
    }
    function selectTab(next) {
      preferences.change({
        result_tab: next
      });
      try {
        if (H) H.remember(data.scenario_ref, {
          tab: next
        });
        setEntry({
          tab: next,
          error: null
        });
      } catch (_) {
        setEntry({
          tab: next,
          error: new Error('本页试调页签记录保存失败，返回后可能无法恢复。')
        });
      }
    }
    if (!preferences.value || entry.error) return /*#__PURE__*/React.createElement("section", {
      className: "tt-results",
      "aria-label": "\u8BD5\u8C03\u7ED3\u679C\u6062\u590D"
    }, /*#__PURE__*/React.createElement(V.Notice, {
      state: preferences,
      label: "\u8BD5\u8C03\u7ED3\u679C\u67E5\u770B\u504F\u597D"
    }), entry.error && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: entry.error
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      onClick: () => setEntry(readEntry())
    }, "\u5237\u65B0\u672C\u9875\u9875\u7B7E\u8BB0\u5F55"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "rotate-ccw",
      onClick: clearEntry
    }, "\u6E05\u9664\u672C\u9875\u9875\u7B7E\u8BB0\u5F55"))));
    const arrangement = r => /*#__PURE__*/React.createElement(React.Fragment, null, name(r.machine_ref), /*#__PURE__*/React.createElement("br", null), name(r.operator_ref), /*#__PURE__*/React.createElement("br", null), U.timeLabel(r.start), /*#__PURE__*/React.createElement("br", null), U.timeLabel(r.end));
    return /*#__PURE__*/React.createElement("section", {
      className: "tt-results"
    }, /*#__PURE__*/React.createElement(V.Notice, {
      state: preferences,
      label: "\u8BD5\u8C03\u7ED3\u679C\u67E5\u770B\u504F\u597D"
    }), /*#__PURE__*/React.createElement(U.Tabs, {
      value: tab,
      onChange: selectTab,
      label: "\u8BD5\u8C03\u7ED3\u679C",
      options: [['delivery', '批次对比'], ['capacity', '资源占用'], ['history', '调整记录'], ['adoptions', '采用记录'], ['issues', '约束问题'], ['tasks', '完整任务'], ['unplanned', '未排工序']]
    }), /*#__PURE__*/React.createElement("div", {
      role: "tabpanel"
    }, tab === 'adoptions' && (window.TrialAdoptionHistory ? /*#__PURE__*/React.createElement(window.TrialAdoptionHistory, {
      data: data
    }) : /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, window.WorkbenchTerms.outcomes.unavailable)), tab === 'delivery' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tt-muted"
    }, "\u5BF9\u6BD4\u57FA\u7840\uFF1A\u539F\u8BD5\u8C03\u6765\u6E90\u3002\u4EA4\u671F\u622A\u6B62\u4E3A\u622A\u81F3\u65E5\u6B21\u65E5\u96F6\u70B9\uFF08\u4E0D\u542B\uFF09\uFF1B", c.changeover_reason), /*#__PURE__*/React.createElement(U.Table, {
      rows: c.batches,
      label: "\u6279\u6B21\u4EA4\u4ED8\u5BF9\u6BD4",
      columns: [['批次 / 零件', r => /*#__PURE__*/React.createElement(React.Fragment, null, r.batch_id, /*#__PURE__*/React.createElement("br", null), r.part_name)], ['批次数量', r => U.number(r.quantity)], ['交付截至日', r => r.due_date || '未知'], ['原完工', r => U.timeLabel(r.baseline_finish)], ['试调完工', r => U.timeLabel(r.finish)], ['提前（小时）', r => U.number(r.improvement_hours)], ['预计交付', r => ({
        on_time: '可按期',
        overdue: '预计超期',
        unavailable: '有冲突，不能评估',
        invalid_data: '交期数据无效'
      })[r.risk] || '未知'], ['超期（小时）', r => U.number(r.late_hours)]]
    })), tab === 'capacity' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tt-muted"
    }, "\u4EC5\u6B64\u8BD5\u8C03\u5360\u7528\uFF0C\u975E\u5168\u5382\u5229\u7528\u7387\u3002", U.timeLabel(data.capacity.start), " \u81F3 ", U.timeLabel(data.capacity.end)), data.capacity.reason && /*#__PURE__*/React.createElement("p", {
      className: "tt-notice"
    }, data.capacity.reason), /*#__PURE__*/React.createElement(U.Table, {
      label: "\u8D44\u6E90\u5360\u7528",
      rows: data.capacity.resources,
      columns: [['资源', r => (r.resource_type === 'machine' ? '设备 ' : '人员 ') + name(r.resource_ref)], ['安排（小时）', r => U.number(r.arranged_hours)], ['实际占用（小时）', r => U.number(r.occupied_hours)], ['重叠时间（小时）', r => U.number(r.overlap_hours)], ['可用（小时）', r => U.number(r.available_hours)], ['班表外时间（小时）', r => U.number(r.outside_available_hours)], ['本范围占用率', r => r.utilization === null ? '暂无数据' : U.number(r.utilization * 100) + '%'], ['依据', r => /*#__PURE__*/React.createElement(Calendar, {
        resource: r
      })]]
    })), tab === 'history' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tt-muted"
    }, "\u672C\u8349\u7A3F\u7684\u6BCF\u6B21\u8C03\u6574\u8BB0\u5F55\uFF0C\u4E0D\u662F\u6B63\u5F0F\u91C7\u7528\u8BB0\u5F55\u3002"), /*#__PURE__*/React.createElement(U.Table, {
      label: "\u8C03\u6574\u8BB0\u5F55",
      rows: data.change_history.slice().reverse(),
      columns: [['记录时间', r => U.timeLabel(r.recorded_at)], ['记录人', r => r.local_operator], ['调整前', r => arrangement(r.before)], ['调整后', r => arrangement(r.after)], ['当时约束', r => U.statusLabel(r.validation.constraints_status)], ['记录依据', r => /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u7F16\u53F7"), /*#__PURE__*/React.createElement("div", {
        className: "tt-ref"
      }, r.change_ref), /*#__PURE__*/React.createElement("div", {
        className: "tt-ref"
      }, r.task_ref))]]
    })), tab === 'issues' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u6574\u4F53\u7EA6\u675F\uFF1A", U.statusLabel(data.validation.constraints_status)), /*#__PURE__*/React.createElement(U.Issues, {
      rows: data.validation.issues,
      onSelect: onSelect
    })), tab === 'tasks' && /*#__PURE__*/React.createElement(U.Table, {
      label: "\u5B8C\u6574\u4EFB\u52A1\u660E\u7EC6",
      rows: data.tasks,
      size: 50,
      columns: [['批次 / 工序', t => /*#__PURE__*/React.createElement(U.Button, {
        icon: "arrow-right",
        onClick: () => onSelect(t.task_ref)
      }, t.batch_id + ' · ' + t.process_label + ' ' + t.sequence)], ['分件', t => t.piece_id || '整批'], ['目标量', t => U.number(t.quantity)], ['设备 / 人员', t => /*#__PURE__*/React.createElement(React.Fragment, null, name(t.machine_ref), /*#__PURE__*/React.createElement("br", null), name(t.operator_ref))], ['开始', t => U.timeLabel(t.start)], ['结束', t => U.timeLabel(t.end)], ['变更', t => t.changed ? '已调整' : '未变']]
    }), tab === 'unplanned' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tt-muted"
    }, "\u5B8C\u6574\u57FA\u7840\u672A\u6392\u5DE5\u5E8F ", data.unplanned_operations.length, " \u9053\uFF1B\u672A\u6392\u5B8C\u6574\u4E0D\u80FD\u5F53\u4F5C\u53EF\u6309\u671F\u3002"), /*#__PURE__*/React.createElement(U.Table, {
      label: "\u672A\u6392\u5DE5\u5E8F",
      rows: data.unplanned_operations,
      columns: [['工序顺序', r => r.sequence], ['分件', r => r.piece_id || '整批'], ['原因', r => r.reason.message], ['工序编号', r => /*#__PURE__*/React.createElement("span", {
        className: "tt-ref"
      }, r.operation_ref)]]
    }))));
  }
  window.TrialResults = {
    Summary,
    Results
  };
})();
