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
    missing_resource_policy: '缺设备人员时的规则',
    completed_policy: '执行规则',
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
  const timeLabel = v => window.WorkbenchFormat.dateTime(v);
  const number = v => window.WorkbenchFormat.number(v, {
    digits: 0
  });
  function ErrorBox({
    error
  }) {
    return error ? /*#__PURE__*/React.createElement("div", {
      className: "rh-notice rh-error",
      role: "alert"
    }, error.code === 'snapshot_stale' && /*#__PURE__*/React.createElement("strong", null, "\u6570\u636E\u5DF2\u66F4\u65B0\u3002 "), error.message || '排产记录读取失败，没有显示替代结果。请点「重新查询」。') : null;
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
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u7B5B\u9009",
      onSubmit: submit,
      noValidate: true
    }, /*#__PURE__*/React.createElement("div", {
      className: "rh-filter-row"
    }, /*#__PURE__*/React.createElement("label", null, "\u6392\u4EA7\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u72B6\u6001",
      value: draft.state,
      disabled: busy,
      onChange: e => set({
        state: e.target.value
      })
    }, ['all', ...A.states].map(state => /*#__PURE__*/React.createElement("option", {
      key: state,
      value: state
    }, labels[state])))), /*#__PURE__*/React.createElement("label", null, "\u63D0\u4EA4\u8D77\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u63D0\u4EA4\u8D77\u65E5",
      value: draft.accepted_from || '',
      disabled: busy,
      onChange: e => set({
        accepted_from: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u63D0\u4EA4\u6B62\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u63D0\u4EA4\u6B62\u65E5",
      value: draft.accepted_to || '',
      disabled: busy,
      onChange: e => set({
        accepted_to: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u6392\u5E8F\u9879",
      value: draft.sort,
      disabled: busy,
      onChange: e => set({
        sort: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "accepted_at"
    }, "\u63D0\u4EA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("option", {
      value: "started_at"
    }, "\u5F00\u59CB\u65F6\u95F4"), /*#__PURE__*/React.createElement("option", {
      value: "finished_at"
    }, "\u7ED3\u675F\u65F6\u95F4"))), /*#__PURE__*/React.createElement("label", null, "\u987A\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u6392\u5E8F\u65B9\u5411",
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
      "aria-label": "\u67E5\u8BE2\u6392\u4EA7\u8BB0\u5F55",
      busy: busy
    }, "\u67E5\u8BE2"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u7B5B\u9009",
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
    }, run.recovery_required ? '等待核对' : labels[run.state]), /*#__PURE__*/React.createElement("small", null, run.recovery_required ? run.recovery_reason.message : {
      queued: '尚未开始计算',
      running: '排产尚未结束',
      complete: '计算结束，约束未核验',
      partial: '保留部分结果，须查看候选',
      failed: '未保存可用候选',
      interrupted: '排产中断，未自动重跑'
    }[run.state]), run.recovery_required && /*#__PURE__*/React.createElement("small", null, "\u539F\u72B6\u6001\uFF1A", labels[run.state]));
  }
  function ScopeSummary({
    value
  }) {
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", null, value.start_date || '起日未记录', " \u81F3 ", value.end_date || '止日未记录'), /*#__PURE__*/React.createElement("small", null, "\u9009\u6279 ", value.batch_count === null ? '未记录' : number(value.batch_count) + ' 批', " \xB7 \u9F50\u5957", value.ready_check === null ? '未记录' : value.ready_check ? '开启' : '关闭'), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6392\u4EA7\u8BBE\u7F6E"), /*#__PURE__*/React.createElement("small", null, "\u7F3A\u8D44\u6E90\uFF1A", {
      auto_assign: '自动分配',
      exclude: '暂不排'
    }[value.missing_resource_policy] || '未记录', " \xB7 ", value.completed_policy === 'preserve_actuals' ? '保留开工和完工记录' : '执行规则未记录')), !!value.data_gaps.length && /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", {
      className: "rh-warning"
    }, "\u6392\u4EA7\u65F6\u8D44\u6599\u7F3A\u9879 ", value.data_gaps.length), value.data_gaps.map(g => /*#__PURE__*/React.createElement("small", {
      key: g.field
    }, fields[g.field], "\uFF1A", g.message))));
  }
  function Table({
    runs,
    onOpen,
    canNavigate
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "rh-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true,
      tabIndex: 0,
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55\u8868\u683C\u6EDA\u52A8\u533A\u57DF"
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u6392\u4EA7\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6392\u4EA7\u8BB0\u5F55"), /*#__PURE__*/React.createElement("colgroup", null, [19, 18, 25, 19, 6, 6, 7].map((width, i) => /*#__PURE__*/React.createElement("col", {
      key: i,
      style: {
        width: width + '%'
      }
    }))), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u63D0\u4EA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6392\u4EA7\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6392\u4EA7\u8303\u56F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5F00\u59CB / \u7ED3\u675F\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "rh-num"
    }, "\u5019\u9009\u6570"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "rh-num"
    }, "\u5B89\u6392\u6570"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, runs.map(run => /*#__PURE__*/React.createElement("tr", {
      key: run.run_ref,
      "data-run-ref": run.run_ref,
      "data-run-state": run.state
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("time", null, timeLabel(run.accepted_at)), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: run.run_ref,
      label: "\u8BB0\u5F55\u7F16\u53F7"
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
      run: run
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(ScopeSummary, {
      value: run.scope_summary
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("time", null, run.started_at === null ? '尚未开始' : timeLabel(run.started_at)), /*#__PURE__*/React.createElement("small", null, run.finished_at === null ? '尚未结束' : timeLabel(run.finished_at))), /*#__PURE__*/React.createElement("td", {
      className: 'rh-num' + (run.counts_final && run.candidate_count > 0 ? ' rh-accent' : '')
    }, number(run.candidate_count), !run.counts_final && /*#__PURE__*/React.createElement("small", null, "\u975E\u6700\u7EC8")), /*#__PURE__*/React.createElement("td", {
      className: "rh-num"
    }, number(run.task_count), !run.counts_final && /*#__PURE__*/React.createElement("small", null, "\u975E\u6700\u7EC8")), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      "aria-label": '查看 ' + timeLabel(run.accepted_at) + ' 提交的排产记录',
      disabled: !canNavigate,
      onClick: () => onOpen(run)
    })))))));
  }
  function Pager({
    page,
    busy,
    onChange
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "rh-pagination"
    }, /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      sizes: [10, 20, 50],
      unit: "\u6B21",
      label: "\u6392\u4EA7\u8BB0\u5F55",
      sizeLabel: "\u6392\u4EA7\u8BB0\u5F55\u6BCF\u9875\u6570\u91CF",
      busy: busy,
      onSize: size => onChange({
        page: 1,
        size
      }, false),
      onPage: number => onChange({
        page: number
      }, true)
    }));
  }
  function Styles() {
    return null;
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
