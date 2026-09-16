(function () {
  'use strict';

  const {
      Button,
      Modal
    } = window.ResourceControls,
    A = window.RunJobAPI;
  const labels = {
    queued: '等待计算',
    running: '正在计算',
    complete: '计算完成',
    partial: '部分完成',
    failed: '计算失败',
    interrupted: '排产中断'
  };
  function Progress({
    run
  }) {
    const [now, setNow] = React.useState(Date.now);
    React.useEffect(() => {
      if (run.finished_at) return undefined;
      const timer = setInterval(() => {
        if (!document.hidden) setNow(Date.now());
      }, 1000);
      return () => clearInterval(timer);
    }, [run.run_ref, run.finished_at]);
    const progress = run.progress,
      computing = !A.terminal(run) && !run.recovery_required;
    const percent = progress && progress.total > 0 ? Math.round(progress.done / progress.total * 100) : null;
    return /*#__PURE__*/React.createElement("div", {
      className: "rj-progress",
      "data-run-progress": true
    }, /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement("strong", null, window.RunPresentation.stage(run)), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u8017\u65F6 ", window.RunPresentation.elapsed(run, now)), progress && /*#__PURE__*/React.createElement("span", {
      "data-run-progress-count": true
    }, "\u5DF2\u7B97\u5B8C ", progress.done, " / ", progress.total, " \u4E2A\u5019\u9009\u65B9\u6848 \xB7 \u6700\u8FD1\u66F4\u65B0 ", window.WorkbenchFormat.dateTime(progress.updated_at))), computing && /*#__PURE__*/React.createElement("div", {
      className: 'rj-bar' + (percent === null ? ' rj-bar-indeterminate' : ''),
      role: "progressbar",
      "aria-label": "\u6392\u4EA7\u8BA1\u7B97\u8FDB\u5EA6",
      "aria-valuemin": 0,
      "aria-valuemax": 100,
      "aria-valuenow": percent === null ? undefined : percent,
      "aria-valuetext": percent === null ? '正在计算，进度未知' : '已算完 ' + progress.done + ' / ' + progress.total + ' 个候选方案'
    }, /*#__PURE__*/React.createElement("i", {
      className: "rj-bar-fill",
      style: percent === null ? undefined : {
        width: percent + '%'
      }
    })), computing && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, "\u8BA1\u7B97\u5728\u672C\u673A\u7EE7\u7EED\u8FDB\u884C\uFF1B\u8FD4\u56DE\u672C\u9875\u53EF\u67E5\u770B\u6700\u65B0\u7ED3\u679C\u3002"));
  }
  function Status({
    run
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + (run.state === 'complete' ? 'ok' : ['failed', 'partial', 'interrupted'].includes(run.state) ? 'warn' : 'off'),
      "data-run-state": run.state,
      "data-run-stage": run.stage
    }, /*#__PURE__*/React.createElement("span", {
      className: "dot"
    }), run.recovery_required ? '等待核对排产记录' : labels[run.state]);
  }
  function Scope({
    preview
  }) {
    const value = preview.normalized_input;
    return /*#__PURE__*/React.createElement("dl", {
      className: "rj-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u672C\u6B21\u6279\u6B21"), /*#__PURE__*/React.createElement("dd", null, value.batch_refs.length, " \u6279")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6392\u4EA7\u65E5\u671F"), /*#__PURE__*/React.createElement("dd", null, value.start_date, " \u81F3 ", value.end_date)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement("dd", null, value.ready_check ? '开启' : '关闭')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7F3A\u8D44\u6E90\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, value.missing_resource_policy === 'auto_assign' ? '自动分配' : '暂不排')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u6709\u62A5\u5DE5"), /*#__PURE__*/React.createElement("dd", null, "\u4FDD\u7559\u5DF2\u5F00\u5DE5\u548C\u5DF2\u5B8C\u5DE5\u7684\u8BB0\u5F55")));
  }
  function Reasons({
    rows
  }) {
    const groups = new Map();
    rows.forEach(row => {
      const id = row.code + '\n' + row.message,
        group = groups.get(id);
      if (group) group.count += 1;else groups.set(id, {
        ...row,
        count: 1
      });
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "status"
    }, Array.from(groups.values()).slice(0, 20).map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, ['run_worker_not_connected', 'run_schema_unavailable', 'execution_ledger_unavailable'].includes(row.code) ? A.message(row) : row.message, row.count > 1 ? '（' + row.count + ' 项）' : '', /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: A.details(row)
    }))), groups.size > 20 && /*#__PURE__*/React.createElement("div", null, "\u53E6\u6709 ", groups.size - 20, " \u7C7B\u539F\u56E0\uFF0C\u8BF7\u8FD4\u56DE\u6392\u4EA7\u68C0\u67E5\u6838\u5BF9\u3002"));
  }
  function Confirmation({
    preview,
    busy,
    onConfirm,
    onClose
  }) {
    const [page, setPage] = React.useState(1),
      values = preview.normalized_input.batch_refs,
      pages = Math.max(1, Math.ceil(values.length / 20));
    return /*#__PURE__*/React.createElement(Modal, {
      title: "\u786E\u8BA4\u672C\u6B21\u5019\u9009\u6392\u4EA7",
      icon: "play",
      onClose: onClose,
      locked: busy,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: busy
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        icon: "play",
        className: "btn primary",
        busy: busy,
        onClick: onConfirm
      }, "\u786E\u8BA4\u5F00\u59CB\u6392\u4EA7"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-body run-job-panel rj-confirm"
    }, /*#__PURE__*/React.createElement(Scope, {
      preview: preview
    }), /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, "\u8BA1\u7B97\u5B8C\u6210\u540E\u53EF\u6BD4\u8F83\u5019\u9009\u65B9\u6848\uFF0C\u518D\u9009\u62E9\u662F\u5426\u91C7\u7528\u4E3A\u6B63\u5F0F\u8BA1\u5212\u3002"), /*#__PURE__*/React.createElement("details", {
      className: "wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6279\u6B21\u5185\u90E8\u7F16\u53F7 \xB7 ", values.length, " \u6279"), /*#__PURE__*/React.createElement("ol", {
      className: "rj-refs",
      start: (page - 1) * 20 + 1
    }, values.slice((page - 1) * 20, page * 20).map(value => /*#__PURE__*/React.createElement("li", {
      key: value
    }, value))), /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      pages: pages,
      total: values.length,
      size: 20,
      unit: "\u6279",
      label: "\u8303\u56F4",
      onPage: setPage
    })), !!preview.warnings.length && /*#__PURE__*/React.createElement(Reasons, {
      rows: preview.warnings
    })));
  }
  function Candidates({
    run,
    api
  }) {
    const [query, setQuery] = React.useState({}),
      [catalog, setCatalog] = React.useState(null),
      [error, setError] = React.useState('');
    const [busy, setBusy] = React.useState(false),
      [revision, refresh] = React.useReducer(v => v + 1, 0);
    React.useEffect(() => {
      if (!run.candidates.length) return undefined;
      const controller = new AbortController();
      let disposed = false;
      setBusy(true);
      setCatalog(null);
      setError('');
      async function load() {
        try {
          if (typeof api.catalog !== 'function') throw new Error('dependency not wired: adapter.catalog');
          const response = await api.catalog(run.run_ref, query, controller.signal),
            data = A.catalog(response, run.run_ref, query);
          const saved = new Map(run.candidates.map(c => [c.candidate_ref, c]));
          if (data.run_state !== run.state || data.candidate_count !== saved.size || data.candidates.some(c => !saved.has(c.candidate_ref) || saved.get(c.candidate_ref).status !== c.persisted_status || saved.get(c.candidate_ref).task_count !== c.task_count)) throw new Error('候选方案列表与这次排产的结果不一致。');
          if (!disposed) setCatalog({
            ...data,
            snapshot_ref: response.meta.snapshot_ref
          });
        } catch (e) {
          if (!disposed) setError('暂时读不到候选方案列表；这次排产的结果里仍有 ' + run.candidates.length + ' 个候选方案。');
        } finally {
          if (!disposed) setBusy(false);
        }
      }
      load();
      return () => {
        disposed = true;
        controller.abort();
      };
    }, [api, run.run_ref, run.state, query, revision]);
    if (!run.candidates.length) return /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, A.terminal(run) ? '这次排产没有保存候选方案。' : '候选方案还没保存。');
    const canOpen = typeof api.openCandidate === 'function',
      selected = new Set(run.candidates.filter(c => c.selected).map(c => c.candidate_ref));
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5DF2\u4FDD\u5B58\u5019\u9009\u65B9\u6848"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DF2\u4FDD\u5B58\u5019\u9009\u65B9\u6848 \xB7 ", run.candidates.length, " \u9879"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: busy,
      onClick: () => {
        setQuery({});
        refresh();
      }
    }, "\u5237\u65B0\u5019\u9009\u65B9\u6848\u5217\u8868")), !canOpen && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, window.WorkbenchTerms.outcomes.unavailable), error && /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "alert"
    }, error), busy && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5DF2\u4FDD\u5B58\u5019\u9009\u65B9\u6848\u3002"), catalog && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rj-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u5DF2\u4FDD\u5B58\u5019\u9009"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5DF2\u4FDD\u5B58\u5019\u9009"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u5019\u9009"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DF2\u4FDD\u5B58\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, catalog.candidates.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.candidate_ref,
      "data-candidate-ref": row.candidate_ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rj-name"
    }, /*#__PURE__*/React.createElement("span", null, row.label || '生成时名称未填写', selected.has(row.candidate_ref) && /*#__PURE__*/React.createElement("span", {
      className: "rj-selected"
    }, "\u672C\u6B21\u9009\u4E2D")), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: row.candidate_ref
    }))), /*#__PURE__*/React.createElement("td", null, {
      completed: '已完成',
      partial: '部分完成',
      failed: '失败',
      skipped: '已跳过'
    }[row.status], row.completeness === 'unknown' && /*#__PURE__*/React.createElement("small", null, "\u5B8C\u6574\u6027\u5C1A\u672A\u786E\u8BA4")), /*#__PURE__*/React.createElement("td", null, row.task_count), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "eye",
      className: "mini",
      reasonDisplay: "tooltip",
      reason: canOpen ? '' : window.WorkbenchTerms.outcomes.unavailable,
      onClick: () => api.openCandidate({
        candidate_ref: row.candidate_ref,
        run_ref: row.run_ref
      })
    }, "\u8BE6\u60C5"))))))), catalog.page.total > 20 && /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: catalog.page,
      size: 20,
      unit: "\u9879",
      label: "\u5019\u9009",
      busy: busy,
      onPage: page => setQuery({
        page,
        snapshot_ref: catalog.snapshot_ref
      })
    })));
  }
  function Record({
    run,
    intent,
    paused,
    retryPaused,
    lastChecked,
    resolution,
    checking,
    verified,
    api
  }) {
    const replaced = resolution === 'context_replaced';
    const queryLabel = checking ? '正在查询结果' : replaced ? '数据库已恢复' : resolution === 'lookup_failed' ? '查询失败' : '暂未查到这次排产记录';
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u8FD9\u6B21\u6392\u4EA7\u8BB0\u5F55",
      className: "rj-record"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6700\u8FD1\u6392\u4EA7\u8BB0\u5F55"), run ? /*#__PURE__*/React.createElement(Status, {
      run: run
    }) : /*#__PURE__*/React.createElement("span", {
      role: "status",
      "data-query-state": checking ? 'querying' : resolution
    }, queryLabel)), replaced && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted",
      role: "status"
    }, "\u6570\u636E\u5E93\u5DF2\u6062\u590D\uFF0C\u4E0A\u6B21\u6392\u4EA7\u7ED3\u679C\u4E0D\u5728\u5F53\u524D\u6570\u636E\u4E2D\u3002\u8BF7\u91CD\u65B0\u68C0\u67E5\u5F53\u524D\u6279\u6B21\u540E\u5F00\u59CB\u6392\u4EA7\u3002"), (intent || run) && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        ...(intent ? {
          '操作编号': intent.request_key
        } : {}),
        ...(run ? {
          '排产编号': run.run_ref
        } : {})
      }
    }), run && !verified && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, "\u4E0B\u9762\u662F\u4E0A\u6B21\u67E5\u5230\u7684\u7ED3\u679C\uFF0C\u8FD9\u6B21\u67E5\u8BE2\u8FD8\u6CA1\u786E\u8BA4\u3002"), run && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Progress, {
      run: run
    }), /*#__PURE__*/React.createElement("div", {
      className: "rj-tools rj-muted"
    }, /*#__PURE__*/React.createElement("span", null, "\u63D0\u4EA4\uFF1A", window.WorkbenchFormat.dateTime(run.accepted_at)), run.started_at && /*#__PURE__*/React.createElement("span", null, "\u5F00\u59CB\uFF1A", window.WorkbenchFormat.dateTime(run.started_at)), run.finished_at && /*#__PURE__*/React.createElement("span", null, "\u7ED3\u675F\uFF1A", window.WorkbenchFormat.dateTime(run.finished_at))), run.recovery_required && /*#__PURE__*/React.createElement("p", {
      className: "rj-notice"
    }, "\u6B63\u5728\u6838\u5BF9\u4E0A\u6B21\u7684\u6392\u4EA7\u8BB0\u5F55\uFF0C\u7ED3\u679C\u8FD8\u6CA1\u786E\u8BA4\uFF0C\u6CA1\u6709\u91CD\u65B0\u8BA1\u7B97\u3002"), run.error && /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "alert"
    }, A.message(run.error)), /*#__PURE__*/React.createElement(Candidates, {
      key: run.run_ref,
      run: run,
      api: api
    })), !replaced && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted rj-query-summary",
      role: "status"
    }, lastChecked && /*#__PURE__*/React.createElement("span", null, "\u6700\u8FD1\u67E5\u8BE2\uFF1A", window.WorkbenchFormat.dateTime(new Date(lastChecked).toLocaleString('sv-SE').replace(' ', 'T'))), retryPaused ? /*#__PURE__*/React.createElement("span", null, "\u5DF2\u6682\u505C\u81EA\u52A8\u67E5\u8BE2\u3002\u53EF\u70B9\u300C\u67E5\u8BE2\u7ED3\u679C\u300D\u518D\u6B21\u6838\u5BF9\u539F\u8BB0\u5F55\u3002") : !A.terminal(run) && /*#__PURE__*/React.createElement("span", null, paused ? '页面已切走，返回后继续查询。' : checking ? '正在读取排产记录。' : '等待下次查询。')));
  }
  function Styles() {
    return null;
  }
  window.RunJobControls = {
    Button,
    Confirmation,
    Scope,
    Reasons,
    Record,
    Styles
  };
})();
