(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract;
  const E = window.ProcessStageEditor;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  function Preview({
    result
  }) {
    const d = result.data,
      paging = E.usePage(d.operations);
    return /*#__PURE__*/React.createElement("section", {
      "data-process-preview": true
    }, /*#__PURE__*/React.createElement("h3", null, "\u8DEF\u7EBF\u9884\u68C0"), /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, d.can_confirm_route ? '输入有效，尚未保存。' : '输入存在待处理问题，尚未保存。', " \u5DE5\u5E8F ", d.counts.operations, " \xB7 \u5DF2\u8BC6\u522B ", d.counts.recognized, " \xB7 \u672A\u8BC6\u522B ", d.counts.unknown), d.diagnostics.length > 0 && /*#__PURE__*/React.createElement("div", {
      className: "match-note",
      role: "alert",
      style: {
        display: 'block'
      }
    }, d.diagnostics.map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, row.severity === 'error' ? '错误' : '警告', row.sequence !== undefined ? ' · 工序 ' + row.sequence : '', "\uFF1A", row.message))), /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, /*#__PURE__*/React.createElement("dt", null, "\u89C4\u8303\u5316\u8F93\u5165"), /*#__PURE__*/React.createElement("dd", null, d.normalized_input)), /*#__PURE__*/React.createElement("p", null, "\u539F\u6A21\u677F\uFF1A\u5DE5\u5E8F ", d.baseline.operation_count, " \xB7 \u5916\u534F\u7EC4 ", d.baseline.external_group_count, " \xB7 ", d.baseline.has_published_template ? '已有发布模板' : '无发布模板'), /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, [['added', '新增序号'], ['removed', '移除序号'], ['retained', '保留序号'], ['same_sequence_changed', '同序号内容变化']].map(([key, label]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, d.changes[key].length ? d.changes[key].join('、') : '无')))), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u8DEF\u7EBF\u9884\u68C0\u5DE5\u5E8F",
      style: {
        minWidth: 900,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: 90
      }
    }, "\u5DE5\u5E8F\u53F7"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 160
      }
    }, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 110
      }
    }, "\u5EFA\u8BAE\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 150
      }
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 130
      }
    }, "\u5468\u671F\uFF08\u5929\uFF09"), /*#__PURE__*/React.createElement("th", null, "\u4F9D\u636E / \u95EE\u9898"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, row.sequence), /*#__PURE__*/React.createElement("td", null, row.op_type_name, /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, row.op_type_ref === null ? '未识别' : '已识别')), /*#__PURE__*/React.createElement("td", null, P.sourceLabel(row.source_suggestion)), /*#__PURE__*/React.createElement("td", null, row.supplier_label === null ? '未提供' : row.supplier_label), /*#__PURE__*/React.createElement("td", null, P.valueText(row.external_days)), /*#__PURE__*/React.createElement("td", null, typeof row.basis === 'string' ? row.basis : JSON.stringify(row.basis), /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    })))))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging
    }));
  }
  function ProcessRouteEntry({
    adapter,
    result,
    command,
    onClose,
    onDirty,
    refreshState = {},
    onRefresh,
    active = true,
    disabled = false
  }) {
    const [context, setContext] = React.useState(result);
    const entity = context.data,
      sequence = React.useRef(0),
      request = React.useRef(null);
    const [mode, setMode] = React.useState('text'),
      [routeRaw, setRouteRaw] = React.useState(entity.fields.route_raw === null ? '' : entity.fields.route_raw);
    const [rows, setRows] = React.useState(() => {
      const active = entity.operations.filter(row => row.status === 'active');
      return active.length ? active.map(row => ({
        key: ++sequence.current,
        seq: String(row.sequence),
        op_type_name: row.label
      })) : [{
        key: ++sequence.current,
        seq: '',
        op_type_name: ''
      }];
    });
    const [state, setState] = React.useState({
      busy: false,
      result: null,
      error: null
    });
    const [discarded, setDiscarded] = React.useState([]),
      [review, setReview] = React.useState(null);
    const paging = E.usePage(rows),
      locked = !!command && (command.locked || command.phase === 'done');
    const blocked = disabled || locked;
    function abort() {
      if (request.current) request.current.abort();
      request.current = null;
    }
    React.useEffect(() => () => abort(), []);
    React.useEffect(() => {
      invalidate();
    }, [adapter, result, disabled, active, command && command.error]);
    React.useEffect(() => {
      if (result !== context) setReview(result);
    }, [result]);
    function invalidate() {
      abort();
      setState({
        busy: false,
        result: null,
        error: null
      });
      setDiscarded([]);
    }
    function edited() {
      invalidate();
      if (onDirty) onDirty('route', true);
    }
    function close() {
      abort();
      onClose();
    }
    function changeRow(key, patch) {
      edited();
      setRows(current => current.map(row => row.key === key ? {
        ...row,
        ...patch
      } : row));
    }
    async function preflight() {
      if (blocked || review || state.busy || P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')) return;
      abort();
      const controller = new AbortController();
      request.current = controller;
      setState({
        busy: true,
        result: null,
        error: null
      });
      try {
        const body = P.previewBody(mode, routeRaw, rows, context.meta.snapshot_ref);
        const response = P.preview(await adapter.routePreview(entity.ref, body, controller.signal), entity.ref, body);
        if (!controller.signal.aborted && request.current === controller) {
          const {
            snapshot_ref,
            ...route
          } = body;
          setState({
            busy: false,
            result: response,
            route,
            error: null
          });
        }
      } catch (error) {
        if (!controller.signal.aborted && request.current === controller) setState({
          busy: false,
          result: null,
          error
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    async function reloadDetail() {
      if (blocked || state.busy || typeof adapter.detail !== 'function') return;
      abort();
      const controller = new AbortController();
      request.current = controller;
      setState({
        busy: true,
        result: null,
        error: null,
        reading: true
      });
      try {
        const fresh = P.detail(await adapter.detail('part', entity.ref, controller.signal), entity.ref);
        if (!controller.signal.aborted && request.current === controller) {
          setReview(fresh);
          setState({
            busy: false,
            result: null,
            error: null,
            refreshed: true
          });
        }
      } catch (error) {
        if (!controller.signal.aborted && request.current === controller) setState({
          busy: false,
          result: null,
          error
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    const affected = state.result ? state.result.data.affected_groups || [] : [];
    const saveReason = P.reason(entity.capabilities, 'stage_confirm', typeof adapter.command === 'function' && !!command) || (review ? '请先核对最新资料。' : !state.result || !state.result.data.can_confirm_route ? '请先完成当前路线预检。' : !affected.every(row => discarded.includes(row.ref)) ? '请明确勾选解除所有受影响的外协组。' : C.blocked(state.result.data.write_context, 'process', 'route_confirm', state.result.meta.source));
    async function save() {
      if (blocked || saveReason) return;
      await command.submit('process', 'route_confirm', entity.ref, state.result.data.write_context, {
        route: state.route,
        discard_group_refs: discarded
      });
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "process-route-entry"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: '录入工艺路线 · ' + entity.business_code,
      icon: "chart-gantt",
      onClose: () => {
        if (!locked) close();
      },
      locked: locked,
      suspended: !active,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: locked
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        busy: state.busy,
        disabled: blocked || !!review,
        reason: P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function'),
        onClick: preflight
      }, "\u9884\u68C0\u8DEF\u7EBF"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        disabled: blocked,
        reason: saveReason,
        onClick: save
      }, "\u786E\u8BA4\u4FDD\u5B58\u8DEF\u7EBF"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll"
    }, /*#__PURE__*/React.createElement("div", {
      className: "seg re-mode",
      role: "tablist",
      "aria-label": "\u8DEF\u7EBF\u5F55\u5165\u6A21\u5F0F",
      style: {
        marginBottom: 16
      }
    }, [['text', '整条录入'], ['rows', '逐行表格']].map(([value, label]) => /*#__PURE__*/React.createElement(Button, {
      key: value,
      role: "tab",
      "aria-selected": mode === value,
      className: mode === value ? 'on' : '',
      disabled: blocked,
      onClick: () => {
        if (mode !== value) {
          edited();
          setMode(value);
        }
      }
    }, label))), mode === 'text' ? /*#__PURE__*/React.createElement("label", {
      className: "field full"
    }, "\u8DEF\u7EBF\u6587\u5B57", /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u8DEF\u7EBF\u6587\u5B57",
      className: "re-text",
      rows: 5,
      value: routeRaw,
      disabled: blocked,
      onChange: event => {
        edited();
        setRouteRaw(event.target.value);
      },
      style: {
        width: '100%',
        resize: 'vertical'
      }
    })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u9010\u884C\u8DEF\u7EBF\u5F55\u5165",
      style: {
        minWidth: 580,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: 125
      }
    }, "\u5DE5\u5E8F\u53F7"), /*#__PURE__*/React.createElement("th", null, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 140
      }
    }, "\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 70
      }
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: row.key
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
      type: "text",
      inputMode: "numeric",
      "aria-label": '第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工序号',
      value: row.seq,
      disabled: blocked,
      className: "wt-in",
      style: {
        width: '100%'
      },
      onChange: event => changeRow(row.key, {
        seq: event.target.value
      })
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
      type: "text",
      "aria-label": '第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工种',
      value: row.op_type_name,
      disabled: blocked,
      className: "wt-in",
      style: {
        width: '100%'
      },
      onChange: event => changeRow(row.key, {
        op_type_name: event.target.value
      })
    })), /*#__PURE__*/React.createElement("td", {
      className: "muted"
    }, "\u5F85\u670D\u52A1\u9884\u68C0"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "mini danger",
      icon: "minus",
      "aria-label": '删除第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行',
      disabled: blocked,
      onClick: () => {
        edited();
        setRows(current => current.filter(item => item.key !== row.key));
      }
    })))))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: blocked,
      onClick: () => {
        edited();
        setRows(current => current.concat({
          key: ++sequence.current,
          seq: '',
          op_type_name: ''
        }));
        paging.setNumber(Math.ceil((rows.length + 1) / paging.page.size));
      }
    }, "\u6DFB\u52A0\u5DE5\u5E8F")), state.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, state.reading ? '正在重读详情…' : '正在预检路线…'), /*#__PURE__*/React.createElement(ErrorBox, {
      error: state.error
    }), state.refreshed && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u91CD\u8BFB\u8BE6\u60C5\uFF0C\u5F55\u5165\u5185\u5BB9\u4FDD\u7559\uFF1B\u8BF7\u6838\u5BF9\u540E\u91CD\u65B0\u9884\u68C0\u3002"), state.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: blocked || !!review,
      onClick: preflight
    }, "\u91CD\u8BD5\u9884\u68C0"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: blocked || state.busy,
      reason: typeof adapter.detail !== 'function' ? '工艺详情接口尚未接入。' : '',
      onClick: reloadDetail
    }, "\u91CD\u8BFB\u8BE6\u60C5\u5E76\u4FDD\u7559\u8349\u7A3F"), review && /*#__PURE__*/React.createElement(E.Review, {
      before: context.data,
      after: review.data,
      disabled: blocked,
      onAccept: () => {
        setContext(review);
        setReview(null);
        invalidate();
      }
    }), state.result && /*#__PURE__*/React.createElement(Preview, {
      result: state.result
    }), state.result && /*#__PURE__*/React.createElement(E.Groups, {
      title: "\u53D7\u5F71\u54CD\u5916\u534F\u7EC4",
      empty: "\u672C\u6B21\u9884\u68C0\u672A\u53D1\u73B0\u53D7\u5F71\u54CD\u5916\u534F\u7EC4\u3002",
      rows: affected,
      affected: affected.map(row => row.ref),
      discarded: discarded,
      onDiscard: setDiscarded,
      disabled: blocked
    }), command && /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: refreshState.error
    }), refreshState.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u91CD\u65B0\u8BFB\u53D6\u4FDD\u5B58\u7ED3\u679C"))));
  }
  window.ProcessRouteEntry = ProcessRouteEntry;
})();
