(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    S = window.APSResourceSession;
  const E = window.ProcessStageEditor,
    D = window.ProcessRouteDraft;
  // The op_type page caps at 200 rows (core/models/workbench_resource_query.py), so a single read is the whole candidate list it can offer.
  const OP_TYPE_PAGE_SIZE = 200;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  // 依据可能是结构化的：数组按行列出，对应关系按「名：值」逐项列出，不把 JSON 直接上屏；原文折叠进编号区备查。
  const basisText = item => item === null || item === undefined ? '未填写' : typeof item === 'object' ? JSON.stringify(item) : String(item);
  function BasisRows({
    value
  }) {
    const rows = Array.isArray(value) ? value.map(basisText) : Object.keys(value).map(key => key + '：' + basisText(value[key]));
    return /*#__PURE__*/React.createElement(React.Fragment, null, rows.length ? rows.map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, row)) : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u672A\u586B\u5199"), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u4F9D\u636E\u539F\u6587",
      entries: {
        '依据原文': value
      }
    }));
  }
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
      className: "match-note is-block",
      role: "alert"
    }, d.diagnostics.map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, row.severity === 'error' ? '错误' : '警告', row.sequence !== undefined ? ' · 工序 ' + row.sequence : '', "\uFF1A", row.message))), /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, /*#__PURE__*/React.createElement("dt", null, "\u6574\u7406\u540E\u7684\u8DEF\u7EBF"), /*#__PURE__*/React.createElement("dd", null, d.normalized_input)), /*#__PURE__*/React.createElement("p", null, "\u539F\u6A21\u677F\uFF1A\u5DE5\u5E8F ", d.baseline.operation_count, " \xB7 \u5916\u534F\u7EC4 ", d.baseline.external_group_count, " \xB7 ", d.baseline.has_published_template ? '已有发布模板' : '无发布模板'), /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, [['added', '新增序号'], ['removed', '移除序号'], ['retained', '保留序号'], ['same_sequence_changed', '同序号内容变化']].map(([key, label]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, d.changes[key].length ? d.changes[key].join('、') : '无')))), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame wb-table-shell",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u8DEF\u7EBF\u9884\u68C0\u5DE5\u5E8F",
      style: {
        minWidth: 900,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "路线预检工序"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 90
      }
    }, "\u5DE5\u5E8F\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 160
      }
    }, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 110
      }
    }, "\u5EFA\u8BAE\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 150
      }
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 130
      }
    }, "\u5468\u671F\uFF08\u5929\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9D\u636E / \u95EE\u9898"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, row.sequence), /*#__PURE__*/React.createElement("td", null, row.op_type_name, /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, row.op_type_ref === null ? '未识别' : '已识别')), /*#__PURE__*/React.createElement("td", null, P.sourceLabel(row.source_suggestion)), /*#__PURE__*/React.createElement("td", null, row.supplier_label === null ? '未选' : row.supplier_label), /*#__PURE__*/React.createElement("td", null, P.valueText(row.external_days)), /*#__PURE__*/React.createElement("td", null, typeof row.basis === 'string' ? row.basis : /*#__PURE__*/React.createElement(BasisRows, {
      value: row.basis
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    }))))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging
    }));
  }
  // Opening the editor and taking an unedited latest route follow one rule:
  // a route without operations shows its saved route text and one blank row.
  const openingText = (data, rows) => rows.length ? D.serialize(rows) : data.fields.route_raw || '';
  const openingRows = rows => rows.length ? rows : [{
    seq: '',
    op_type_name: ''
  }];
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
    const initialRows = React.useRef(D.fromEntity(entity));
    const [mode, setMode] = React.useState('text'),
      [routeRaw, setRouteRaw] = React.useState(() => openingText(entity, initialRows.current));
    const [rows, setRows] = React.useState(() => openingRows(initialRows.current).map(row => ({
      ...row,
      key: ++sequence.current
    })));
    const draftText = mode === 'text' ? routeRaw : D.serialize(rows),
      baselineDraft = React.useRef(draftText);
    React.useLayoutEffect(() => {
      if (onDirty) onDirty('route', draftText !== baselineDraft.current);
    }, [draftText, onDirty]);
    const [state, setState] = React.useState({
      busy: false,
      result: null,
      error: null
    });
    const [discarded, setDiscarded] = React.useState([]),
      [review, setReview] = React.useState(null);
    const [mergeReview, setMergeReview] = React.useState(null),
      [mergeChoices, setMergeChoices] = React.useState({});
    const paging = E.usePage(rows),
      locked = !!command && (command.locked || command.phase === 'done');
    const blocked = disabled || locked;
    // Read the op_type catalog once on entry so the row inputs can suggest real names. Free text stays allowed and
    // the server route preflight remains the only authority on what is recognized.
    const opTypeListId = React.useId();
    const opTypes = S.useQuery(signal => Promise.resolve(adapter.choices('op_type', {
      query: '',
      page: 1,
      size: OP_TYPE_PAGE_SIZE
    }, signal)).then(result => C.query(result, 'choices')), [adapter], typeof adapter.choices === 'function');
    const opTypeNames = React.useMemo(() => opTypes.result ? Array.from(new Set(opTypes.result.data.entities.map(item => item.label).filter(Boolean))) : [], [opTypes.result]);
    function abort() {
      if (request.current) request.current.abort();
      request.current = null;
    }
    React.useEffect(() => () => abort(), []);
    React.useEffect(() => {
      invalidate();
    }, [adapter, result, disabled, active, command && command.error]);
    React.useEffect(() => {
      if (result !== context) {
        setReview(result);
        setMergeReview(null);
        setMergeChoices({});
      }
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
      setMergeReview(null);
      setMergeChoices({});
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
    async function parsedDraft(snapshot) {
      const controller = new AbortController();
      request.current = controller;
      try {
        const body = P.previewBody('text', mode === 'rows' ? D.serialize(rows) : routeRaw, rows, snapshot);
        const response = P.preview(await adapter.routePreview(entity.ref, body, controller.signal), entity.ref, body);
        if (controller.signal.aborted || request.current !== controller) return null;
        const syntaxInvalid = !response.data.operations.length || response.data.diagnostics.some(row => row.severity === 'error' && !['calibration_quota_locked', 'legacy_sequence_invalid'].includes(row.code));
        if (syntaxInvalid) {
          setState({
            busy: false,
            result: response,
            error: C.failure('当前输入还不能准确识别，已保留原输入。请按路线预检提示修正后再继续。')
          });
          return null;
        }
        return response.data.operations.map(row => ({
          seq: String(row.sequence),
          op_type_name: row.op_type_name
        }));
      } catch (error) {
        if (!controller.signal.aborted) throw error;
        return null;
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    async function switchMode(next) {
      if (next === mode || blocked || review || state.busy) return;
      if (!(mode === 'rows' ? D.serialize(rows) : routeRaw).trim()) {
        invalidate();
        setRows([{
          key: ++sequence.current,
          seq: '',
          op_type_name: ''
        }]);
        setRouteRaw('');
        setMode(next);
        return;
      }
      if (P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')) return;
      invalidate();
      setState({
        busy: true,
        result: null,
        error: null
      });
      try {
        const parsed = await parsedDraft(context.meta.snapshot_ref);
        if (!parsed) return;
        setRows(parsed.map(row => ({
          ...row,
          key: ++sequence.current
        })));
        setRouteRaw(D.serialize(parsed));
        setMode(next);
        setState({
          busy: false,
          result: null,
          error: null
        });
      } catch (error) {
        setState({
          busy: false,
          result: null,
          error
        });
      }
    }
    function acceptMerged(mergedRows) {
      const nextRows = mergedRows.map(row => ({
          ...row,
          key: ++sequence.current
        })),
        text = D.serialize(mergedRows);
      initialRows.current = D.fromEntity(review.data);
      baselineDraft.current = D.serialize(initialRows.current);
      setRows(nextRows);
      setRouteRaw(text);
      setContext(review);
      setReview(null);
      setMergeReview(null);
      setMergeChoices({});
      invalidate();
    }
    function acceptFresh() {
      const latest = D.fromEntity(review.data),
        text = openingText(review.data, latest),
        nextRows = openingRows(latest);
      initialRows.current = latest;
      baselineDraft.current = mode === 'text' ? text : D.serialize(nextRows);
      setRows(nextRows.map(row => ({
        ...row,
        key: ++sequence.current
      })));
      setRouteRaw(text);
      setContext(review);
      setReview(null);
      setMergeReview(null);
      setMergeChoices({});
      invalidate();
    }
    async function acceptLatest() {
      if (blocked || state.busy) return;
      if (mergeReview) {
        try {
          acceptMerged(D.resolve(mergeReview, mergeChoices));
        } catch (error) {
          setState({
            busy: false,
            result: null,
            error: C.failure(error.message)
          });
        }
        return;
      }
      // Nothing was typed or changed locally: there is no draft to merge, so take the latest route as is.
      if (draftText === baselineDraft.current || !draftText.trim() && !initialRows.current.length) {
        acceptFresh();
        return;
      }
      abort();
      setState({
        busy: true,
        result: null,
        error: null
      });
      try {
        const parsed = await parsedDraft(review.meta.snapshot_ref);
        if (!parsed) return;
        const merged = D.merge(initialRows.current, parsed, D.fromEntity(review.data));
        if (merged.conflicts.length) {
          setMergeReview(merged);
          setMergeChoices({});
          setState({
            busy: false,
            result: null,
            error: null
          });
        } else acceptMerged(merged.rows);
      } catch (error) {
        setState({
          busy: false,
          result: null,
          error
        });
      }
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
          setMergeReview(null);
          setMergeChoices({});
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
      role: "group",
      "aria-label": "\u8DEF\u7EBF\u5F55\u5165\u6A21\u5F0F",
      style: {
        marginBottom: 16
      }
    }, [['text', '整条录入'], ['rows', '逐行表格']].map(([value, label]) => /*#__PURE__*/React.createElement(Button, {
      key: value,
      "aria-pressed": mode === value,
      className: mode === value ? 'on' : '',
      disabled: blocked || !!review || state.busy,
      reason: P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function'),
      onClick: () => switchMode(value)
    }, label))), /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u6574\u6761\u548C\u9010\u884C\u7EF4\u62A4\u7684\u662F\u540C\u4E00\u6761\u8DEF\u7EBF\u3002\u53EF\u76F4\u63A5\u586B\u5199\u201C10: \u8F66\u524A\uFF1B20: \u70ED\u5904\u7406\uFF1B30: \u7CBE\u78E8\u201D\uFF1B\u539F\u6765\u7684\u201C10\u8F66\u524A20\u70ED\u5904\u7406\u201D\u4E5F\u80FD\u8BC6\u522B\u3002\u540D\u79F0\u542B\u6570\u5B57\u6216\u7A7A\u683C\u65F6\uFF0C\u4FDD\u7559\u5DE5\u5E8F\u53F7\u540E\u7684\u5192\u53F7\u5373\u53EF\u3002"), mode === 'text' ? /*#__PURE__*/React.createElement("label", {
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
    })) : /*#__PURE__*/React.createElement(React.Fragment, null, opTypeNames.length > 0 && /*#__PURE__*/React.createElement("datalist", {
      id: opTypeListId
    }, opTypeNames.map(name => /*#__PURE__*/React.createElement("option", {
      key: name,
      value: name
    }))), opTypeNames.length > 0 && /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u5DE5\u79CD\u8F93\u5165\u4F1A\u63D0\u793A\u5DF2\u767B\u8BB0\u7684\u5DE5\u79CD", opTypes.result.data.page.total > opTypeNames.length ? '，现有工种较多，只提示前 ' + opTypeNames.length + ' 个' : '', "\uFF1B\u672A\u767B\u8BB0\u7684\u5DE5\u79CD\u4E5F\u53EF\u4EE5\u76F4\u63A5\u8F93\u5165\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame wb-table-shell",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table wb-table--editable",
      "aria-label": "\u9010\u884C\u8DEF\u7EBF\u5F55\u5165",
      style: {
        minWidth: 620,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "逐行路线录入"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 125
      }
    }, "\u5DE5\u5E8F\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 140
      }
    }, "\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 100
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
      list: opTypeNames.length ? opTypeListId : undefined,
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
    }, "\u5F85\u9884\u68C0"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "mini danger",
      icon: "trash-2",
      "aria-label": '删除第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行',
      disabled: blocked,
      onClick: () => {
        edited();
        setRows(current => current.filter(item => item.key !== row.key));
      }
    }, "\u5220\u9664"))))))), /*#__PURE__*/React.createElement(E.Pager, {
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
    }, "\u65B0\u589E\u5DE5\u5E8F")), state.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, state.reading ? '正在刷新详情…' : '正在预检路线…'), /*#__PURE__*/React.createElement(ErrorBox, {
      error: state.error
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: opTypes.error
    }), state.refreshed && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u5237\u65B0\u8BE6\u60C5\uFF0C\u5F55\u5165\u5185\u5BB9\u4FDD\u7559\uFF1B\u8BF7\u6838\u5BF9\u540E\u91CD\u65B0\u9884\u68C0\u3002"), state.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: blocked || !!review,
      onClick: preflight
    }, "\u91CD\u8BD5\u9884\u68C0"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: blocked || state.busy,
      reason: typeof adapter.detail !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: reloadDetail
    }, window.WorkbenchTerms.refresh_latest), review && /*#__PURE__*/React.createElement(E.Review, {
      before: context.data,
      after: review.data,
      disabled: blocked || state.busy,
      onAccept: acceptLatest
    }), mergeReview && /*#__PURE__*/React.createElement("section", {
      className: "match-note is-block",
      role: "alert"
    }, /*#__PURE__*/React.createElement("p", null, "\u4EE5\u4E0B\u5DE5\u5E8F\u540C\u65F6\u88AB\u672C\u6B21\u8349\u7A3F\u548C\u6700\u65B0\u8D44\u6599\u4FEE\u6539\uFF0C\u8BF7\u9010\u9879\u9009\u62E9\u540E\uFF0C\u518D\u70B9\u201C\u5DF2\u6838\u5BF9\uFF0C\u7EE7\u7EED\u7F16\u8F91\u201D\u3002\u5176\u4F59\u5DE5\u5E8F\u4F1A\u4FDD\u7559\u672C\u5730\u4FEE\u6539\u5E76\u91C7\u7528\u6700\u65B0\u8D44\u6599\u3002"), mergeReview.conflicts.map(row => /*#__PURE__*/React.createElement("fieldset", {
      key: row.seq
    }, /*#__PURE__*/React.createElement("legend", null, "\u5DE5\u5E8F ", row.seq), [['local', '保留我的修改'], ['latest', '采用最新资料']].map(([choice, label]) => /*#__PURE__*/React.createElement("label", {
      key: choice,
      style: {
        display: 'block'
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: 'route-conflict-' + row.seq,
      checked: mergeChoices[row.seq] === choice,
      disabled: blocked,
      onChange: () => setMergeChoices(current => ({
        ...current,
        [row.seq]: choice
      }))
    }), label, "\uFF1A", row[choice] ? row[choice].op_type_name : '移除这道工序'))))), state.result && /*#__PURE__*/React.createElement(Preview, {
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
    }, "\u67E5\u8BE2\u7ED3\u679C"))));
  }
  window.ProcessRouteEntry = ProcessRouteEntry;
})();
