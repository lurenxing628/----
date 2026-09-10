(function () {
  'use strict';

  const M = window.RunCandidateModel,
    B = window.RunBaselineModel,
    {
      Button
    } = window.RunCandidateControls;
  function useBaseline(data) {
    const [enabled, setEnabled] = React.useState(false),
      [revision, refresh] = React.useReducer(v => v + 1, 0);
    const [state, setState] = React.useState({
        result: null,
        error: null,
        busy: false
      }),
      request = React.useRef(null);
    const identity = React.useMemo(() => ({}), [data, enabled, revision]);
    React.useLayoutEffect(() => {
      const controller = new AbortController();
      request.current = controller;
      setState({
        identity,
        result: null,
        error: null,
        busy: enabled
      });
      if (enabled) window.RunBaselineAPI.create().read(data, controller.signal).then(result => {
        if (!controller.signal.aborted) setState({
          identity,
          result,
          error: null,
          busy: false
        });
      }).catch(error => {
        if (!controller.signal.aborted) setState({
          identity,
          result: null,
          error: new Error(error.name === 'AbortError' ? '初始计划读取超时，未显示上次结果。' : error.message),
          busy: false
        });
      });
      return () => controller.abort();
    }, [identity]);
    function toggle(value) {
      if (request.current) request.current.abort();
      setEnabled(value);
    }
    function retry() {
      if (request.current) request.current.abort();
      refresh();
    }
    return {
      ...(state.identity === identity ? state : {
        result: null,
        error: null,
        busy: enabled
      }),
      enabled,
      toggle,
      retry
    };
  }
  function Toggle({
    state
  }) {
    return /*#__PURE__*/React.createElement("label", {
      className: "rb-toggle"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: state.enabled,
      onChange: e => state.toggle(e.target.checked)
    }), "\u521D\u59CB\u8BA1\u5212");
  }
  function Segments({
    row,
    chosen
  }) {
    const [top, setTop] = React.useState(0),
      host = React.useRef(null),
      first = Math.max(0, Math.floor(top / 76) - 2);
    React.useEffect(() => {
      const index = chosen ? row.baseline_segments.findIndex(s => s.row_ref === chosen.row_ref) : 0;
      if (host.current) host.current.scrollTop = Math.max(0, index) * 76;
    }, [row, chosen]);
    return /*#__PURE__*/React.createElement("div", {
      ref: host,
      className: "rb-segments",
      "data-baseline-segments": true,
      role: "region",
      "aria-label": "\u521D\u59CB\u8BA1\u5212\u5B8C\u6574\u5206\u6BB5",
      onScroll: e => setTop(e.currentTarget.scrollTop)
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: row.baseline_segments.length * 76,
        position: 'relative',
        minWidth: 510
      }
    }, row.baseline_segments.slice(first, first + 6).map((s, i) => /*#__PURE__*/React.createElement("div", {
      key: s.row_ref,
      "data-baseline-segment": s.row_ref,
      className: "rb-segment",
      style: {
        top: (first + i) * 76
      },
      "aria-selected": !!chosen && chosen.row_ref === s.row_ref
    }, /*#__PURE__*/React.createElement("div", null, M.timeLabel(s.start), " \u81F3 ", M.timeLabel(s.end), !s.interval_comparable && ' · 起止不可比较'), /*#__PURE__*/React.createElement("div", null, "\u8BBE\u5907 ", s.machine && s.machine.label || '未记录', " \xB7 \u4EBA\u5458 ", s.operator && s.operator.label || '未记录', " \xB7 \u8D77\u6B62\u8DE8\u5EA6 ", M.number(s.elapsed_hours), " h"), /*#__PURE__*/React.createElement("small", null, "\u521D\u59CB\u8BA1\u5212\u884C\u5F15\u7528 ", s.row_ref, s.data_gaps.map(g => ' · ' + g.message).join(''))))), !row.baseline_segments.length && /*#__PURE__*/React.createElement("div", null, "\u521D\u59CB\u8BA1\u5212\u6CA1\u6709\u8BE5\u5DE5\u5E8F\u5B89\u6392\u3002"));
  }
  function Detail({
    row,
    segment,
    workspace
  }) {
    const c = row.candidate,
      delta = row.delta;
    return /*#__PURE__*/React.createElement("div", {
      className: "rb-detail",
      role: "region",
      "aria-label": "\u521D\u59CB\u8BA1\u5212\u5DE5\u5E8F\u5BF9\u7167"
    }, /*#__PURE__*/React.createElement("strong", null, row.batch_label || '批次未记录', " \xB7 ", M.number(row.sequence), " ", row.process_label || '工序未记录', " \xB7 ", B.statusLabels[row.status]), /*#__PURE__*/React.createElement("div", {
      className: "rb-reference"
    }, "\u5DE5\u5E8F\u5F15\u7528 ", row.operation_ref), c ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u5019\u9009\u5B89\u6392\uFF1A", M.timeLabel(c.start), " \u81F3 ", M.timeLabel(c.end), " \xB7 \u8BBE\u5907 ", c.machine && c.machine.label || '未记录', " \xB7 \u4EBA\u5458 ", c.operator && c.operator.label || '未记录'), /*#__PURE__*/React.createElement("div", {
      className: "rb-reference"
    }, "\u5019\u9009\u884C\u5F15\u7528 ", c.row_ref), !workspace.tasks.some(t => t.row_ref === c.row_ref) && /*#__PURE__*/React.createElement("div", null, "\u8BE5\u5019\u9009\u5B89\u6392\u4E0D\u5728\u5F53\u524D\u5019\u9009\u9884\u89C8\u8303\u56F4\uFF1B\u6B64\u5904\u4FDD\u7559\u5B8C\u6574\u5BF9\u7167\u3002")) : /*#__PURE__*/React.createElement("div", null, "\u5019\u9009\u6CA1\u6709\u5B89\u6392\u6B64\u5DE5\u5E8F\uFF1B\u672A\u6392\u4E0D\u4EE3\u8868\u6539\u5584\u3002"), /*#__PURE__*/React.createElement(Segments, {
      key: row.operation_ref,
      row: row,
      chosen: segment
    }), row.comparison_available && /*#__PURE__*/React.createElement("div", null, "\u5B89\u6392\u53D8\u52A8\uFF08\u5019\u9009\u51CF\u521D\u59CB\u8BA1\u5212\uFF09\uFF1A\u5F00\u59CB ", M.number(delta.start_hours), " h \xB7 \u7ED3\u675F ", M.number(delta.end_hours), " h \xB7 \u8D77\u6B62\u8DE8\u5EA6 ", M.number(delta.elapsed_hours), " h", /*#__PURE__*/React.createElement("small", null, "\u8BBE\u5907\u53D8\u5316 ", delta.machine_changed === null ? '未知' : delta.machine_changed ? '有' : '无', " \xB7 \u4EBA\u5458\u53D8\u5316 ", delta.operator_changed === null ? '未知' : delta.operator_changed ? '有' : '无')), /*#__PURE__*/React.createElement("div", null, "\u751F\u6210\u65F6\u6267\u884C\uFF1A", row.execution_at_generation ? M.executionValue(row.execution_at_generation.execution_state) : '未记录', row.execution_affected && ' · 已有执行影响或数量未知'), row.reasons.concat(row.data_gaps).map((r, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, r.message)));
  }
  function ComparisonList({
    rows,
    chosen,
    onChoose
  }) {
    const [top, setTop] = React.useState(0),
      host = React.useRef(null),
      first = Math.max(0, Math.floor(top / 40) - 2);
    React.useEffect(() => {
      const index = chosen ? rows.findIndex(r => r.operation_ref === chosen.comparison.operation_ref) : -1,
        node = host.current;
      if (node && index >= 0 && (index * 40 < node.scrollTop || index * 40 + 40 > node.scrollTop + node.clientHeight)) node.scrollTop = index * 40;
    }, [chosen, rows]);
    return /*#__PURE__*/React.createElement("div", {
      ref: host,
      className: "rb-list",
      "data-baseline-list": true,
      role: "region",
      "aria-label": "\u521D\u59CB\u8BA1\u5212\u5BF9\u7167\u5217\u8868",
      onScroll: e => setTop(e.currentTarget.scrollTop)
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: rows.length * 40,
        minWidth: 570,
        position: 'relative'
      }
    }, rows.slice(first, first + 12).map((r, i) => /*#__PURE__*/React.createElement("div", {
      className: "rb-row",
      "data-baseline-operation": r.operation_ref,
      key: r.operation_ref,
      style: {
        top: (first + i) * 40
      },
      "aria-selected": !!chosen && chosen.comparison.operation_ref === r.operation_ref
    }, /*#__PURE__*/React.createElement("span", {
      title: r.batch_label || '未记录'
    }, r.batch_label || '未记录'), /*#__PURE__*/React.createElement("span", {
      title: r.process_label || '未记录'
    }, M.number(r.sequence), " ", r.process_label || '未记录'), /*#__PURE__*/React.createElement("span", null, B.statusLabels[r.status]), /*#__PURE__*/React.createElement("span", null, r.baseline_segments.length, " \u6BB5", r.execution_affected && ' · 执行影响'), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      className: "mini",
      "aria-label": '初始计划对照 ' + r.operation_ref,
      onClick: () => onChoose({
        comparison: r,
        segment: null
      })
    })))), !rows.length && /*#__PURE__*/React.createElement("div", {
      className: "rc-empty"
    }, "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u5339\u914D\u5BF9\u7167\u3002"));
  }
  function Panel({
    state,
    rows,
    chosen,
    onChoose,
    workspace
  }) {
    const [open, setOpen] = React.useState(false),
      d = state.result && state.result.data;
    React.useEffect(() => {
      if (chosen) setOpen(true);
    }, [chosen]);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("style", null, `
      .rc-gantt .rb-toggle{display:inline-flex;align-items:center;gap:5px;white-space:nowrap;font-size:12px;margin:0}.rc-gantt .rb-toggle input{width:14px;height:14px;min-height:14px;padding:0;margin:0;accent-color:var(--ui-primary)}
      .rc-gantt .rb-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--ui-info-muted);padding:4px 0}.rb-legend span{display:inline-flex;align-items:center;gap:5px}.rb-legend i{display:inline-block;width:22px;height:9px;background:var(--wb-gantt-primary-fill);border:1px solid var(--wb-gantt-primary-edge)}.rb-legend .rb-before{height:5px;background:transparent;border:1px dashed var(--ui-text)}.rb-legend .rb-selected{border:2px solid var(--wb-gantt-gold)}
      .rc-gantt .rb-panel{border-bottom:1px solid var(--ui-border);font-size:12px;min-width:0}.rb-panel summary{cursor:pointer;padding:6px 0}.rb-panel small{display:block}.rc-gantt .rb-list{max-height:240px;overflow:auto;position:relative;border-block:1px solid var(--ui-border)}.rc-gantt .rb-row{position:absolute;left:0;right:0;height:40px;display:grid;grid-template-columns:minmax(80px,1fr) minmax(120px,1.5fr) 108px 120px 36px;align-items:center;gap:8px;padding:0 5px;border-bottom:1px solid var(--ui-border)}.rb-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rb-row[aria-selected=true]{outline:1px solid var(--wb-gantt-gold);outline-offset:-1px}
      .rc-gantt .rb-detail{padding:8px 0;line-height:1.7;overflow-wrap:anywhere}.rc-gantt .rb-reference{font-size:10px;color:var(--ui-info-muted)}.rc-gantt .rb-segments{max-height:180px;overflow:auto;border-block:1px solid var(--ui-border);margin:6px 0}.rc-gantt .rb-segment{position:absolute;left:0;right:0;height:76px;border-bottom:1px solid var(--ui-border);padding:4px 6px;overflow:auto}.rb-segment[aria-selected=true]{border-left:2px solid var(--wb-gantt-gold)}
    `), state.enabled && /*#__PURE__*/React.createElement(React.Fragment, null, state.busy && /*#__PURE__*/React.createElement("div", {
      className: "rc-muted",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u53D7\u7406\u65F6\u521D\u59CB\u8BA1\u5212\u3002"), state.error && /*#__PURE__*/React.createElement("div", {
      role: "alert"
    }, state.error.message, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u8BFB\u521D\u59CB\u8BA1\u5212",
      onClick: state.retry
    })), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rb-legend"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", null), "\u5019\u9009\u5B89\u6392"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "rb-before"
    }), "\u521D\u59CB\u8BA1\u5212"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "rb-selected"
    }), "\u5DF2\u9009\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("details", {
      className: "rb-panel",
      open: open,
      onToggle: e => setOpen(e.currentTarget.open)
    }, /*#__PURE__*/React.createElement("summary", null, "\u521D\u59CB\u8BA1\u5212\u5BF9\u7167\u660E\u7EC6\uFF08", rows.length, "\uFF09 \xB7 \u8BF4\u660E"), open && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u53D7\u7406\u4E8E ", M.timeLabel(d.generation.accepted_at), " \xB7 ", d.baseline.captured_task_count, " \u6BB5\u521D\u59CB\u5B89\u6392 \xB7 \u6267\u884C\u5F71\u54CD ", d.execution_affected_count, " \u9053"), /*#__PURE__*/React.createElement("div", null, "\u5B89\u6392\u53D8\u52A8\u4E0D\u7B49\u4E8E\u6536\u76CA\uFF1B\u672A\u6392\u4E0D\u4EE3\u8868\u6539\u5584\u3002"), d.baseline.reason && /*#__PURE__*/React.createElement("div", null, d.baseline.reason.message), d.data_gaps.concat(state.result.warnings).map((g, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, g.message)), /*#__PURE__*/React.createElement(ComparisonList, {
      rows: rows,
      chosen: chosen,
      onChoose: onChoose
    }), chosen && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rc-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u521D\u59CB\u8BA1\u5212\u5DE5\u5E8F\u5BF9\u7167",
      onClick: () => onChoose(null)
    })), /*#__PURE__*/React.createElement(Detail, {
      row: chosen.comparison,
      segment: chosen.segment,
      workspace: workspace
    })))))));
  }
  window.RunBaselineControls = {
    useBaseline,
    Toggle,
    Panel
  };
})();
