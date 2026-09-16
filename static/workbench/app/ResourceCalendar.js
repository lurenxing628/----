(function () {
  'use strict';

  const K = window.APSCalendarContract,
    S = window.APSResourceSession;
  const {
    Button,
    ErrorBox,
    Issues,
    Modal
  } = window.ResourceControls;
  const {
    RefreshResult,
    Policy
  } = window.CalendarFields;
  function ResourceCalendar({
    adapter,
    onCommitted,
    initialContext,
    onNavigationReady,
    rememberEnabled = true
  }) {
    const [target] = React.useState(() => {
      if (initialContext == null) return {
        context: null
      };
      const parsed = window.ResourceWorkspace.navigation(initialContext);
      return parsed.context && parsed.context.kind !== 'calendar' ? {
        error: window.APSResourceContract.failure('工作日历定位类型不正确。')
      } : parsed;
    });
    const [month, setMonth] = React.useState(() => {
      const now = new Date();
      return target.context ? {
        year: Number(target.context.month.slice(0, 4)),
        month: Number(target.context.month.slice(5, 7))
      } : {
        year: now.getFullYear(),
        month: now.getMonth() + 1
      };
    });
    const [dialog, setDialog] = React.useState(null),
      [refreshState, setRefreshState] = React.useState({});
    const command = S.useCommand(adapter),
      handled = React.useRef(null),
      awaitingRefresh = React.useRef(false);
    const [deferred, setDeferred] = React.useState(() => !!target.context && command.phase !== 'idle');
    const [navigationError, setNavigationError] = React.useState(target.error || null),
      located = React.useRef(false),
      root = React.useRef(null);
    const request = S.useQuery(async signal => K.month(await adapter.query(K.path + '/month', month, signal), month.year, month.month), [adapter, month.year, month.month]);
    const result = request.result,
      data = result && result.data,
      source = result && result.meta.source;
    window.WorkbenchPageContext.useSnapshot({
      source: 'production',
      kind: 'calendar',
      month: String(month.year).padStart(4, '0') + '-' + String(month.month).padStart(2, '0'),
      ...(dialog && dialog.mode === 'view' ? {
        date: dialog.day.date
      } : {})
    }, rememberEnabled && !!data && !request.loading && !request.error && !navigationError && !deferred && command.phase === 'idle' && source === 'production' && (!dialog || dialog.mode === 'view'));
    React.useEffect(() => {
      if (onNavigationReady) onNavigationReady(!dialog && command.phase === 'idle');
    }, [dialog, command.phase, onNavigationReady]);
    React.useEffect(() => {
      if (!target.context || deferred || located.current || !data || command.phase !== 'idle') return;
      located.current = true;
      if (source !== 'production') {
        setNavigationError(window.APSResourceContract.failure('本月日历读取失败，请重新打开工作日历。'));
        return;
      }
      if (target.context.date) {
        const day = data.days.find(row => row.date === target.context.date);
        if (!day || !day.explicit) {
          setNavigationError(window.APSResourceContract.failure('这一天的单独设置已经不存在了，没有新增，也没有用默认规则代替。'));
          return;
        }
        setDialog({
          mode: 'view',
          day,
          source
        });
      }
    }, [data, source, command.phase, deferred, target]);
    function refresh() {
      awaitingRefresh.current = {
        previous: request.result
      };
      setRefreshState({
        loading: true
      });
      request.reload();
    }
    React.useEffect(() => {
      if (command.phase !== 'done' || handled.current === command.result.receipt_ref) return;
      handled.current = command.result.receipt_ref;
      refresh();
      if (typeof onCommitted === 'function') onCommitted(command.result);
    }, [command.phase, command.result]);
    React.useEffect(() => {
      if (!awaitingRefresh.current || request.loading) return;
      if (request.error) {
        awaitingRefresh.current = false;
        setRefreshState({
          error: request.error
        });
      } else if (request.result && request.result !== awaitingRefresh.current.previous) {
        awaitingRefresh.current = false;
        setRefreshState({
          done: true
        });
      }
    }, [request.loading, request.result, request.error]);
    const orphan = !dialog && (command.locked || command.phase === 'done' || command.phase === 'rejected');
    const blocked = command.locked || command.phase === 'done';
    function open(next) {
      if (blocked || !command.reset()) return;
      setRefreshState({});
      setDialog(next);
    }
    function close() {
      if (!command.reset()) return;
      setDialog(null);
    }
    function continueNavigation() {
      if (dialog || command.phase !== 'idle') {
        setNavigationError(window.APSResourceContract.failure('请先确认并关闭上次工作日历操作的结果，再继续跳转。'));
        return;
      }
      setDeferred(false);
      setNavigationError(null);
    }
    const stats = [['work_days', '本月工作日', 'primary'], ['configured', '已单独设置', 'ok'], ['overrides', '调休 / 加班', 'warn'], ['weekend_rest', '周末休息', 'neutral']];
    return /*#__PURE__*/React.createElement("section", {
      className: "resource-calendar",
      "aria-label": "\u5DE5\u4F5C\u65E5\u5386",
      ref: root
    }, /*#__PURE__*/React.createElement("div", {
      className: "crumb"
    }, /*#__PURE__*/React.createElement("span", null, "\u4EA7\u80FD\u94FE"), /*#__PURE__*/React.createElement("span", {
      className: "sep"
    }, "/"), /*#__PURE__*/React.createElement("span", null, "\u5168\u5C40"), /*#__PURE__*/React.createElement("span", {
      className: "sep"
    }, "/"), /*#__PURE__*/React.createElement("span", null, "\u5DE5\u4F5C\u65E5\u5386")), /*#__PURE__*/React.createElement("div", {
      className: "chead wb-page-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", null, "\u5DE5\u4F5C\u65E5\u5386"), /*#__PURE__*/React.createElement("p", {
      className: "cdesc"
    }, "\u5168\u5C40\u5DE5\u4F5C\u65F6\u95F4\u3001\u6548\u7387\u4E0E\u53EF\u6392\u4EA7\u8303\u56F4"))), /*#__PURE__*/React.createElement("div", {
      className: "statline wb-metrics",
      style: {
        '--wb-columns': 4
      }
    }, stats.map(([key, label, tone]) => /*#__PURE__*/React.createElement("div", {
      key: key,
      className: "stat wb-metric",
      "data-tone": tone
    }, /*#__PURE__*/React.createElement("span", {
      className: "sl wb-metric-label"
    }, label), /*#__PURE__*/React.createElement("span", {
      className: "sv wb-metric-value"
    }, data ? data.stats[key] : '未读取')))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: navigationError
    }), deferred && /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u4E0A\u6B21\u5DE5\u4F5C\u65E5\u5386\u64CD\u4F5C\u8FD8\u6CA1\u5904\u7406\u5B8C\uFF0C\u6682\u65F6\u6CA1\u6709\u8DF3\u8F6C\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      onClick: continueNavigation
    }, "\u7EE7\u7EED\u8DF3\u8F6C")), /*#__PURE__*/React.createElement("div", {
      className: "cal-wrap",
      style: {
        marginTop: 18
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "cal-panel",
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "cal-top",
      style: {
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement(Button, {
      className: "cal-nav",
      icon: "chevron-left",
      "aria-label": "\u4E0A\u4E00\u6708",
      disabled: blocked || request.loading || !data || !data.previous_month,
      onClick: () => setMonth(data.previous_month)
    }), /*#__PURE__*/React.createElement("span", {
      className: "cal-title"
    }, month.year, " \u5E74 ", month.month, " \u6708"), /*#__PURE__*/React.createElement(Button, {
      className: "cal-nav",
      icon: "chevron-right",
      "aria-label": "\u4E0B\u4E00\u6708",
      disabled: blocked || request.loading || !data || !data.next_month,
      onClick: () => setMonth(data.next_month)
    }), /*#__PURE__*/React.createElement(Button, {
      className: "cal-nav cal-today-btn",
      title: "\u56DE\u5230\u672C\u6708",
      style: {
        width: 'auto',
        padding: '0 10px',
        fontSize: 12,
        fontWeight: 600
      },
      disabled: blocked,
      onClick: () => {
        const now = new Date();
        setMonth({
          year: now.getFullYear(),
          month: now.getMonth() + 1
        });
        request.reload();
      }
    }, "\u4ECA\u5929"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u672C\u6708",
      busy: request.loading,
      disabled: blocked,
      onClick: request.reload
    }), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer",
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "calendar-days",
      className: "btn cal-batch",
      disabled: blocked || !data || request.loading,
      reason: source && source !== 'production' ? '当前不是生产数据，不能维护。' : '',
      onClick: () => open({
        mode: 'range'
      })
    }, "\u6279\u91CF\u7EF4\u62A4")), request.loading && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5DE5\u4F5C\u65E5\u5386\u2026"
    }), data && /*#__PURE__*/React.createElement("div", {
      className: "cal-grid"
    }, ['一', '二', '三', '四', '五', '六', '日'].map(day => /*#__PURE__*/React.createElement("div", {
      className: "cal-wd",
      key: day
    }, day)), data.cells.map((cell, index) => {
      if (!cell) return /*#__PURE__*/React.createElement("div", {
        key: 'empty-' + index,
        className: "cal-cell empty"
      });
      const row = data.days.find(day => day.date === cell.date),
        meta = K.tag(row);
      return /*#__PURE__*/React.createElement("button", {
        key: row.date,
        type: "button",
        className: 'cal-cell ' + meta.tone + (row.is_today ? ' today' : ''),
        style: {
          minWidth: 0,
          textAlign: 'left',
          color: 'inherit',
          fontFamily: 'inherit'
        },
        disabled: blocked,
        "data-calendar-date": row.date,
        "aria-current": target.context && target.context.date === row.date ? 'date' : undefined,
        "aria-label": row.date + ' ' + (row.explicit ? '单独设置' : '默认规则') + ' ' + meta.text,
        title: row.date + ' · ' + (row.explicit ? '单独设置' : '默认规则'),
        onClick: () => open({
          mode: 'day',
          day: row,
          source
        })
      }, /*#__PURE__*/React.createElement("span", {
        className: "d"
      }, row.day), /*#__PURE__*/React.createElement("span", {
        className: "tag",
        style: {
          whiteSpace: 'normal',
          overflowWrap: 'anywhere'
        }
      }, meta.text));
    }))), /*#__PURE__*/React.createElement("div", {
      className: "cal-panel cal-side"
    }, /*#__PURE__*/React.createElement("h3", null, "\u56FE\u4F8B"), /*#__PURE__*/React.createElement("div", {
      className: "cal-leg"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
      className: "sw cfg"
    }), "\u5DF2\u5355\u72EC\u8BBE\u7F6E\u5DE5\u65F6"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
      className: "sw rest"
    }), "\u8C03\u4F11 / \u52A0\u73ED"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
      className: "sw we"
    }), "\u5468\u672B\uFF08\u9ED8\u8BA4\u975E\u5DE5\u4F5C\uFF09")), /*#__PURE__*/React.createElement("h3", null, "\u9ED8\u8BA4\u89C4\u5219"), /*#__PURE__*/React.createElement("p", null, "\u672A\u5355\u72EC\u8BBE\u7F6E\u7684\u65E5\u671F\uFF1A\u5468\u4E00\u81F3\u5468\u4E94\u6309 8 \u5C0F\u65F6\u3001\u6548\u7387 100%\uFF0C\u666E\u901A\u4EF6\u548C\u6025\u4EF6\u90FD\u53EF\u6392\u4EA7\uFF1B\u5468\u672B\u9ED8\u8BA4\u4E0D\u6392\u4EA7\u3002"), /*#__PURE__*/React.createElement("h3", null, "\u89C4\u5219\u6765\u6E90"), /*#__PURE__*/React.createElement("p", null, "\u672C\u9875\u7EF4\u62A4\u5168\u5C40\u5DE5\u4F5C\u65E5\u5386\uFF1B\u4EBA\u5458\u73ED\u8868\u548C\u73ED\u6B21\u5355\u72EC\u8BBE\u7F6E\u3002"), data && /*#__PURE__*/React.createElement("p", null, "\u672C\u673A\u6570\u636E\u622A\u81F3 ", window.WorkbenchFormat.dateTime(data.as_of)))), dialog && dialog.mode === 'view' && /*#__PURE__*/React.createElement(Modal, {
      title: dialog.day.date + ' · 日历详情',
      icon: "calendar-days",
      onClose: close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close
      }, "\u5173\u95ED"), /*#__PURE__*/React.createElement(Button, {
        icon: "square-pen",
        onClick: () => open({
          ...dialog,
          mode: 'day'
        })
      }, "\u7EF4\u62A4\u6B64\u65E5"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form scroll"
    }, /*#__PURE__*/React.createElement(Policy, {
      value: dialog.day
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: dialog.day.issues || []
    }))), dialog && dialog.mode === 'day' && /*#__PURE__*/React.createElement(window.CalendarDayDialog, {
      adapter: adapter,
      day: dialog.day,
      source: dialog.source,
      command: command,
      onClose: close,
      refreshState: refreshState,
      onRefresh: refresh
    }), dialog && dialog.mode === 'range' && /*#__PURE__*/React.createElement(window.CalendarRangeDialog, {
      adapter: adapter,
      month: month,
      source: source,
      command: command,
      onClose: close,
      refreshState: refreshState,
      onRefresh: refresh
    }), orphan && /*#__PURE__*/React.createElement(Modal, {
      title: "\u5DE5\u4F5C\u65E5\u5386\u64CD\u4F5C\u7ED3\u679C",
      icon: "history",
      locked: command.locked,
      onClose: close,
      footer: /*#__PURE__*/React.createElement(Button, {
        disabled: command.locked,
        onClick: close
      }, "\u5173\u95ED")
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form scroll"
    }, command.intent ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, command.intent.action === 'confirm' ? '批量维护工作日历' : '维护单日设置'), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '操作编号': command.intent.request_key,
        '日期编号': command.intent.ref
      }
    })) : /*#__PURE__*/React.createElement("p", null, "\u8BFB\u4E0D\u5230\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), command.phase === 'done' && /*#__PURE__*/React.createElement(RefreshResult, {
      state: refreshState,
      onRefresh: refresh
    }))));
  }
  window.ResourceCalendar = ResourceCalendar;
})();
