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
    interrupted: '运行中断'
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
    return /*#__PURE__*/React.createElement("p", {
      className: "rj-progress",
      "data-run-progress": true
    }, /*#__PURE__*/React.createElement("strong", null, window.RunPresentation.stage(run)), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u8017\u65F6 ", window.RunPresentation.elapsed(run, now)));
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
    }), run.recovery_required ? '等待核对运行' : labels[run.state]);
  }
  function Scope({
    preview
  }) {
    const value = preview.normalized_input;
    return /*#__PURE__*/React.createElement("dl", {
      className: "rj-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u672C\u6B21\u6279\u6B21"), /*#__PURE__*/React.createElement("dd", null, value.batch_refs.length, " \u6279")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u8BA1\u5212\u7A97\u53E3"), /*#__PURE__*/React.createElement("dd", null, value.start_date, " \u81F3 ", value.end_date)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement("dd", null, value.ready_check ? '开启' : '关闭')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7F3A\u8D44\u6E90\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, value.missing_resource_policy === 'auto_assign' ? '自动分配' : '暂不排')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u6709\u6267\u884C"), /*#__PURE__*/React.createElement("dd", null, "\u4FDD\u7559\u5F00\u5DE5\u548C\u5B8C\u5DE5\u4E8B\u5B9E")));
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
    }, ['run_worker_not_connected', 'run_schema_unavailable', 'execution_ledger_unavailable'].includes(row.code) ? A.message(row) : row.message, row.count > 1 ? '（' + row.count + ' 项）' : '')), groups.size > 20 && /*#__PURE__*/React.createElement("div", null, "\u53E6\u6709 ", groups.size - 20, " \u7C7B\u539F\u56E0\uFF0C\u8BF7\u8FD4\u56DE\u6392\u4EA7\u68C0\u67E5\u6838\u5BF9\u3002"));
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
    }), /*#__PURE__*/React.createElement("div", {
      className: "rj-notice"
    }, "\u4EC5\u8BA1\u7B97\u5E76\u4FDD\u5B58\u5019\u9009\uFF0C\u4E0D\u66FF\u6362\u6B63\u5F0F\u8BA1\u5212\u3002\u65E5\u5386\u53EF\u884C\u6027\u5C1A\u672A\u9A8C\u8BC1\uFF0C\u6700\u7EC8\u7ED3\u679C\u4EE5\u672C\u6B21\u8BA1\u7B97\u8BB0\u5F55\u4E3A\u51C6\u3002"), /*#__PURE__*/React.createElement("details", {
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
          if (typeof api.catalog !== 'function') throw new Error('候选目录尚未接入。');
          const response = await api.catalog(run.run_ref, query, controller.signal),
            data = A.catalog(response, run.run_ref, query);
          const saved = new Map(run.candidates.map(c => [c.candidate_ref, c]));
          if (data.run_state !== run.state || data.candidate_count !== saved.size || data.candidates.some(c => !saved.has(c.candidate_ref) || saved.get(c.candidate_ref).status !== c.persisted_status || saved.get(c.candidate_ref).task_count !== c.task_count)) throw new Error('候选目录与运行回执不一致。');
          if (!disposed) setCatalog({
            ...data,
            snapshot_ref: response.meta.snapshot_ref
          });
        } catch (e) {
          if (!disposed) setError('候选目录暂时无法核实；运行回执仍保留 ' + run.candidates.length + ' 项候选。');
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
    }, A.terminal(run) ? '本次没有保存候选结果。' : '候选结果尚未保存。');
    const canOpen = typeof api.openCandidate === 'function',
      selected = new Set(run.candidates.filter(c => c.selected).map(c => c.candidate_ref));
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5DF2\u4FDD\u5B58\u5019\u9009"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DF2\u4FDD\u5B58\u5019\u9009 \xB7 ", run.candidates.length, " \u9879"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u5019\u9009\u76EE\u5F55",
      busy: busy,
      onClick: () => {
        setQuery({});
        refresh();
      }
    })), !canOpen && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, "\u5019\u9009\u8BE6\u60C5\u9875\u9762\u5C1A\u672A\u63A5\u5165\uFF0C\u6682\u4E0D\u80FD\u9884\u89C8\u3002"), error && /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "alert"
    }, error), busy && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5DF2\u4FDD\u5B58\u5019\u9009\u3002"), catalog && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
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
    }, /*#__PURE__*/React.createElement("span", null, row.label || '生成时未记录名称', selected.has(row.candidate_ref) && /*#__PURE__*/React.createElement("span", {
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
      reason: canOpen ? '' : '候选详情页面尚未接入，暂不能预览。',
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
    checking,
    verified,
    api
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u672C\u6B21\u8FD0\u884C\u8BB0\u5F55",
      className: "rj-record"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rj-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8FD0\u884C\u8BB0\u5F55"), run ? /*#__PURE__*/React.createElement(Status, {
      run: run
    }) : /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u6B63\u5728\u6838\u5B9E\u539F\u8BF7\u6C42")), (intent || run) && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        ...(intent ? {
          '请求编号': intent.request_key
        } : {}),
        ...(run ? {
          '运行编号': run.run_ref
        } : {})
      }
    }), run && !verified && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted"
    }, "\u4EE5\u4E0B\u4E3A\u4E0A\u6B21\u5DF2\u6838\u5B9E\u7ED3\u679C\uFF0C\u672C\u6B21\u67E5\u8BE2\u5C1A\u672A\u786E\u8BA4\u3002"), run && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Progress, {
      run: run
    }), /*#__PURE__*/React.createElement("div", {
      className: "rj-tools rj-muted"
    }, /*#__PURE__*/React.createElement("span", null, "\u53D7\u7406\uFF1A", window.WorkbenchFormat.dateTime(run.accepted_at)), run.started_at && /*#__PURE__*/React.createElement("span", null, "\u5F00\u59CB\uFF1A", window.WorkbenchFormat.dateTime(run.started_at)), run.finished_at && /*#__PURE__*/React.createElement("span", null, "\u7ED3\u675F\uFF1A", window.WorkbenchFormat.dateTime(run.finished_at))), run.recovery_required && /*#__PURE__*/React.createElement("p", {
      className: "rj-notice"
    }, "\u672C\u673A\u6B63\u5728\u6838\u5BF9\u539F\u6267\u884C\u8BB0\u5F55\uFF0C\u7ED3\u679C\u5C1A\u672A\u786E\u5B9A\uFF0C\u6CA1\u6709\u91CD\u65B0\u8BA1\u7B97\u3002"), run.error && /*#__PURE__*/React.createElement("div", {
      className: "rj-notice",
      role: "alert"
    }, A.message(run.error)), /*#__PURE__*/React.createElement(Candidates, {
      key: run.run_ref,
      run: run,
      api: api
    })), !A.terminal(run) && /*#__PURE__*/React.createElement("p", {
      className: "rj-muted",
      role: "status"
    }, paused ? '页面不可见，已暂停查询；返回后继续核实原运行。' : checking ? '正在查询原运行记录。' : '等待下一次查询，不会重复提交排产。'));
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
