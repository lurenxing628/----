(function () {
  'use strict';

  const A = window.RunHistoryAPI;
  const labels = {
    all: '全部状态',
    queued: '等待计算',
    running: '正在计算',
    complete: '计算完成',
    partial: '部分完成',
    failed: '计算失败',
    interrupted: '已中断'
  };
  const fields = {
    start_date: '排产起日',
    end_date: '排产止日',
    ready_check: '齐套检查',
    missing_resource_policy: '缺资源策略',
    completed_policy: '执行策略',
    batch_count: '所选批次'
  };
  function Button({
    className = '',
    ...props
  }) {
    return /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      ...props,
      className: 'btn wb-action ' + className
    });
  }
  const timeLabel = v => v === null ? '未记录' : v.replace('T', ' ');
  const number = v => v.toLocaleString('zh-CN');
  function ErrorBox({
    error
  }) {
    return error ? /*#__PURE__*/React.createElement("div", {
      className: "rh-notice rh-error",
      role: "alert"
    }, error.code === 'snapshot_stale' && /*#__PURE__*/React.createElement("strong", null, "\u5386\u53F2\u6765\u6E90\u5DF2\u53D8\u5316\u6216\u5FEB\u7167\u5DF2\u5931\u6548\u3002 "), error.message || '排产历史读取失败，未显示替代结果。') : null;
  }
  function Filters({
    value,
    busy,
    onApply
  }) {
    const [draft, setDraft] = React.useState(value),
      [error, setError] = React.useState(null);
    React.useEffect(() => {
      setDraft(value);
      setError(null);
    }, [value]);
    const set = patch => {
      setDraft(v => ({
        ...v,
        ...patch
      }));
      setError(null);
    };
    function submit(e) {
      e.preventDefault();
      try {
        const q = {
          ...draft,
          page: 1
        };
        delete q.snapshot_ref;
        if (!q.accepted_from && !q.accepted_to) {
          delete q.accepted_from;
          delete q.accepted_to;
        }
        const next = A.scope(q);
        onApply(next);
        setError(null);
      } catch (failure) {
        setError(failure);
      }
    }
    return /*#__PURE__*/React.createElement("form", {
      className: "rh-filters",
      "aria-label": "\u6392\u4EA7\u5386\u53F2\u7B5B\u9009",
      onSubmit: submit,
      noValidate: true
    }, /*#__PURE__*/React.createElement("div", {
      className: "rh-filter-row"
    }, /*#__PURE__*/React.createElement("label", null, "\u8FD0\u884C\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5386\u53F2\u8FD0\u884C\u72B6\u6001",
      value: draft.state,
      disabled: busy,
      onChange: e => set({
        state: e.target.value
      })
    }, ['all', ...A.states].map(state => /*#__PURE__*/React.createElement("option", {
      key: state,
      value: state
    }, labels[state])))), /*#__PURE__*/React.createElement("label", null, "\u53D7\u7406\u8D77\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u5386\u53F2\u53D7\u7406\u8D77\u65E5",
      value: draft.accepted_from || '',
      disabled: busy,
      onChange: e => set({
        accepted_from: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u53D7\u7406\u6B62\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u5386\u53F2\u53D7\u7406\u6B62\u65E5",
      value: draft.accepted_to || '',
      disabled: busy,
      onChange: e => set({
        accepted_to: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5386\u53F2\u6392\u5E8F\u5B57\u6BB5",
      value: draft.sort,
      disabled: busy,
      onChange: e => set({
        sort: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "accepted_at"
    }, "\u53D7\u7406\u65F6\u95F4"), /*#__PURE__*/React.createElement("option", {
      value: "started_at"
    }, "\u5F00\u59CB\u65F6\u95F4"), /*#__PURE__*/React.createElement("option", {
      value: "finished_at"
    }, "\u7ED3\u675F\u65F6\u95F4"))), /*#__PURE__*/React.createElement("label", null, "\u987A\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5386\u53F2\u6392\u5E8F\u65B9\u5411",
      value: draft.order,
      disabled: busy,
      onChange: e => set({
        order: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "desc"
    }, "\u4ECE\u65B0\u5230\u65E7"), /*#__PURE__*/React.createElement("option", {
      value: "asc"
    }, "\u4ECE\u65E7\u5230\u65B0"))), /*#__PURE__*/React.createElement("div", {
      className: "rh-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      "aria-label": "\u67E5\u8BE2\u6392\u4EA7\u5386\u53F2",
      busy: busy
    }, "\u67E5\u8BE2"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u5386\u53F2\u7B5B\u9009",
      disabled: busy,
      onClick: () => {
        setError(null);
        onApply(A.scope({
          size: value.size
        }));
      }
    }))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }));
  }
  function Status({
    run
  }) {
    const tone = run.recovery_required || ['partial', 'interrupted'].includes(run.state) ? 'rh-warning' : run.state === 'failed' ? 'rh-danger' : run.state === 'complete' ? 'rh-success' : '';
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
      className: 'rh-state ' + tone
    }, run.recovery_required ? '恢复待核对' : labels[run.state]), /*#__PURE__*/React.createElement("small", null, run.recovery_required ? run.recovery_reason.message : {
      queued: '尚未开始计算',
      running: '运行尚未结束',
      complete: '计算结束，约束未核验',
      partial: '保留部分结果，须查看候选',
      failed: '未保存可用候选',
      interrupted: '运行中断，未自动重跑'
    }[run.state]), run.recovery_required && /*#__PURE__*/React.createElement("small", null, "\u539F\u72B6\u6001\uFF1A", labels[run.state]));
  }
  function ScopeSummary({
    value
  }) {
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", null, value.start_date || '起日未记录', " \u81F3 ", value.end_date || '止日未记录'), /*#__PURE__*/React.createElement("small", null, "\u9009\u6279 ", value.batch_count === null ? '未记录' : number(value.batch_count) + ' 个', " \xB7 \u9F50\u5957", value.ready_check === null ? '未记录' : value.ready_check ? '开启' : '关闭'), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6392\u4EA7\u8BBE\u7F6E"), /*#__PURE__*/React.createElement("small", null, "\u7F3A\u8D44\u6E90\uFF1A", {
      auto_assign: '自动分配',
      exclude: '暂不排'
    }[value.missing_resource_policy] || '未记录', " \xB7 ", value.completed_policy === 'preserve_actuals' ? '保留开工和完工记录' : '执行策略未记录')), !!value.data_gaps.length && /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", {
      className: "rh-warning"
    }, "\u53D7\u7406\u8D44\u6599\u7F3A\u9879 ", value.data_gaps.length), value.data_gaps.map(g => /*#__PURE__*/React.createElement("small", {
      key: g.field
    }, fields[g.field], "\uFF1A", g.message))));
  }
  function Table({
    runs,
    onOpen,
    canNavigate
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "rh-table",
      tabIndex: 0,
      "aria-label": "\u6392\u4EA7\u5386\u53F2\u8868\u683C\u6EDA\u52A8\u533A\u57DF"
    }, /*#__PURE__*/React.createElement("table", {
      "aria-label": "\u6392\u4EA7\u5386\u53F2"
    }, /*#__PURE__*/React.createElement("colgroup", null, [19, 18, 25, 19, 6, 6, 7].map((width, i) => /*#__PURE__*/React.createElement("col", {
      key: i,
      style: {
        width: width + '%'
      }
    }))), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u53D7\u7406\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", null, "\u8FD0\u884C\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u6392\u4EA7\u8303\u56F4"), /*#__PURE__*/React.createElement("th", null, "\u5F00\u59CB / \u7ED3\u675F\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", {
      className: "rh-num"
    }, "\u5019\u9009\u6570"), /*#__PURE__*/React.createElement("th", {
      className: "rh-num"
    }, "\u5B89\u6392\u6570"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, runs.map(run => /*#__PURE__*/React.createElement("tr", {
      key: run.run_ref,
      "data-run-ref": run.run_ref,
      "data-run-state": run.state
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("time", null, timeLabel(run.accepted_at)), /*#__PURE__*/React.createElement("details", {
      className: "rh-id"
    }, /*#__PURE__*/React.createElement("summary", {
      "aria-label": '运行记录编号 ' + run.run_ref
    }, "\u8BB0\u5F55\u7F16\u53F7"), /*#__PURE__*/React.createElement("code", null, run.run_ref))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
      run: run
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(ScopeSummary, {
      value: run.scope_summary
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("time", null, run.started_at === null ? '尚未开始' : timeLabel(run.started_at)), /*#__PURE__*/React.createElement("small", null, run.finished_at === null ? '尚未结束' : timeLabel(run.finished_at))), /*#__PURE__*/React.createElement("td", {
      className: 'rh-num' + (run.counts_final && run.candidate_count > 0 ? ' rh-accent' : '')
    }, number(run.candidate_count), !run.counts_final && /*#__PURE__*/React.createElement("small", null, "\u975E\u6700\u7EC8")), /*#__PURE__*/React.createElement("td", {
      className: "rh-num"
    }, number(run.task_count), !run.counts_final && /*#__PURE__*/React.createElement("small", null, "\u975E\u6700\u7EC8")), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      "aria-label": '查看运行 ' + run.run_ref,
      disabled: !canNavigate,
      onClick: () => onOpen(run)
    })))))));
  }
  function Pager({
    page,
    busy,
    onChange
  }) {
    const pages = Math.max(1, Math.ceil(page.total / page.size)),
      sizes = Array.from(new Set([10, 20, 50, page.size])).sort((a, b) => a - b);
    return /*#__PURE__*/React.createElement("div", {
      className: "rh-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u7B5B\u9009\u547D\u4E2D ", number(page.total), " \u6B21 \xB7 \u7B2C ", page.number, " / ", pages, " \u9875"), /*#__PURE__*/React.createElement("div", {
      className: "rh-tools"
    }, /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5386\u53F2\u6BCF\u9875\u6570\u91CF",
      value: page.size,
      disabled: busy,
      onChange: e => onChange({
        page: 1,
        size: Number(e.target.value)
      }, false)
    }, sizes.map(size => /*#__PURE__*/React.createElement("option", {
      key: size,
      value: size
    }, size)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u5386\u53F2\u4E0A\u4E00\u9875",
      disabled: busy || page.number <= 1,
      onClick: () => onChange({
        page: page.number - 1
      }, true)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u5386\u53F2\u4E0B\u4E00\u9875",
      disabled: busy || !page.has_more,
      onClick: () => onChange({
        page: page.number + 1
      }, true)
    })));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.run-history-workspace{width:100%;min-width:0;max-width:none;padding:0;color:var(--ui-text);font-size:13px;letter-spacing:0}
      .run-history-workspace *{box-sizing:border-box;letter-spacing:0}.run-history-workspace h2{font-size:17px;line-height:1.6;margin:0}
      .run-history-workspace .rh-heading,.run-history-workspace .rh-tools,.run-history-workspace .rh-pagination{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}
      .run-history-workspace .rh-heading,.run-history-workspace .rh-pagination{justify-content:space-between;padding:12px 0}.run-history-workspace .rh-heading{border-bottom:1px solid var(--ui-border)}
      .run-history-workspace .rh-muted,.run-history-workspace small{color:var(--ui-info-muted);font-size:12px;line-height:1.7}.run-history-workspace small{display:block;overflow-wrap:anywhere}
      .run-history-workspace .rh-filters{padding:14px 0;border-bottom:1px solid var(--ui-border)}.run-history-workspace .rh-filter-row{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}
      .run-history-workspace label{display:grid;gap:6px;font-size:12px;color:var(--ui-info-muted)}.run-history-workspace .rh-filter-row select{width:126px}.run-history-workspace input[type=date]{width:156px}
      .run-history-workspace select,.run-history-workspace input{font:inherit;color:var(--ui-text);background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:4px;min-height:32px;max-width:100%;padding:5px 8px}
      .run-history-workspace button{max-width:100%;white-space:nowrap}.run-history-workspace .rh-pagination label{display:flex;align-items:center;gap:8px}.run-history-workspace .rh-pagination select{width:74px}
      .run-history-workspace .rh-source{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 0;line-height:1.8;color:var(--ui-info-muted);font-size:12px}
      .run-history-workspace .rh-notice{padding:10px 12px;margin:10px 0;background:var(--ui-surface-muted);border-left:3px solid var(--ui-warning);line-height:1.7;overflow-wrap:anywhere}
      .run-history-workspace .rh-error,.run-history-workspace .rh-danger{color:var(--ui-danger-text)}.run-history-workspace .rh-error{border-color:var(--ui-danger)}
      .run-history-workspace .rh-warning{color:var(--ui-warning-text)}.run-history-workspace .rh-success{color:var(--ui-success-text)}.run-history-workspace .rh-accent{color:var(--ui-primary);font-weight:600}
      .run-history-workspace .rh-state{font-size:13px;font-weight:600}.run-history-workspace .rh-table{width:100%;overflow:auto;max-height:calc(100vh - 400px);min-height:130px;border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border)}
      .run-history-workspace .rh-table .btn{width:32px;height:32px;min-width:32px;padding:0;flex:none}
      .run-history-workspace table{border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;min-width:960px}.run-history-workspace th,.run-history-workspace td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--ui-border);vertical-align:middle;white-space:normal!important;overflow-wrap:anywhere;line-height:1.7}
      .run-history-workspace th{position:sticky;top:0;z-index:1;background:var(--ui-surface-muted);font-size:12px;color:var(--ui-info-muted);font-weight:500}.run-history-workspace tbody tr:last-child td{border-bottom:0}
      .run-history-workspace tbody tr:hover{background:var(--ui-surface-muted)}.run-history-workspace code{display:block;overflow-wrap:anywhere;font-size:12px;line-height:1.7;color:var(--ui-text);margin-top:4px;font-family:ui-monospace,monospace}.run-history-workspace .rh-id{color:var(--ui-info-muted)}
      .run-history-workspace time,.run-history-workspace .rh-num{font-variant-numeric:tabular-nums}.run-history-workspace .rh-num{text-align:right}.run-history-workspace td.rh-num{font-size:15px}
      .run-history-workspace summary{cursor:pointer;font-size:12px}.run-history-workspace .rh-empty{padding:48px 12px;text-align:center;border-block:1px solid var(--ui-border);line-height:1.8;color:var(--ui-info-muted)}
      .run-history-workspace .rh-empty strong{display:block;font-size:14px;color:var(--ui-text);margin-bottom:6px}.run-history-workspace .rh-pagination{font-size:12px;color:var(--ui-info-muted)}
      @media(max-width:760px){.run-history-workspace .rh-filter-row{gap:10px}.run-history-workspace .rh-table{max-height:500px}.run-history-workspace input[type=date]{width:148px}}
    `);
  }
  window.RunHistoryControls = {
    Button,
    ErrorBox,
    Filters,
    Table,
    Pager,
    Styles,
    timeLabel
  };
})();
