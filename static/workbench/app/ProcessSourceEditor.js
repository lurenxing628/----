(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    S = window.APSResourceSession;
  const E = window.ProcessStageEditor,
    {
      Button,
      Modal,
      ErrorBox,
      Issues
    } = window.ResourceControls;
  function build(entity) {
    return Object.fromEntries(E.active(entity).map(row => [row.ref, {
      ref: row.ref,
      source: row.source,
      op_type_ref: row.op_type_ref,
      op_type_label: row.op_type_label,
      supplier_ref: row.supplier_ref,
      supplier_label: row.supplier_label
    }]));
  }
  function reconcile(draft, before, after) {
    const next = build(after),
      original = build(before);
    E.active(after).forEach(row => {
      const current = draft[row.ref],
        previous = original[row.ref],
        fresh = next[row.ref];
      if (!current || !previous) return;
      if (current.source !== previous.source) fresh.source = current.source;
      [['op_type_ref', 'op_type_label'], ['supplier_ref', 'supplier_label']].forEach(([ref, label]) => {
        if (current[ref] === previous[ref]) return;
        if (current[ref] !== fresh[ref]) fresh[label] = current[label];
        fresh[ref] = current[ref];
      });
    });
    return next;
  }
  const complete = row => ['internal', 'external'].includes(row.source) && !!row.op_type_ref && (row.source === 'internal' || !!row.supplier_ref);
  function input(entity, draft, pageSize) {
    const operations = E.active(entity).map(row => {
      const current = draft[row.ref];
      if (!complete(current)) {
        const error = C.failure('工序 ' + row.sequence + ' 请补齐归属、工种和外协供应商。', [{
          path: 'operations.' + row.sequence,
          message: '工序 ' + row.sequence + ' 资料未填完整。'
        }]);
        error.locate_page = Math.floor(entity.operations.indexOf(row) / pageSize) + 1;
        throw error;
      }
      return {
        ref: row.ref,
        source: current.source,
        op_type_ref: current.op_type_ref,
        supplier_ref: current.source === 'internal' ? null : current.supplier_ref,
        confirmed: true
      };
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能确认归属。');
    return {
      operations,
      discard_group_refs: []
    };
  }
  function Picker({
    adapter,
    target,
    onSelect,
    onClose,
    disabled
  }) {
    const [search, setSearch] = React.useState(''),
      [scope, setScope] = React.useState({
        query: '',
        page: 1,
        size: 50
      });
    const read = S.useQuery(async signal => {
      if (typeof adapter.choices !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.choices');
      return C.query(await adapter.choices(target.kind, {
        ...scope,
        ...(target.kind === 'op_type' ? {
          category: target.source
        } : {})
      }, signal), 'choices');
    }, [adapter, target.kind, target.source, scope]);
    const data = read.result && read.result.data,
      title = target.kind === 'op_type' ? P.sourceLabel(target.source) + '工种' : '供应商';
    return /*#__PURE__*/React.createElement(Modal, {
      title: '选择' + title + ' · 工序 ' + target.sequence,
      icon: "search",
      onClose: onClose,
      locked: disabled,
      footer: /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: disabled
      }, "\u53D6\u6D88")
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll"
    }, /*#__PURE__*/React.createElement("form", {
      className: "toolbar",
      onSubmit: event => {
        event.preventDefault();
        setScope({
          query: search,
          page: 1,
          size: 50
        });
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "search"
    }, /*#__PURE__*/React.createElement(window.ResourceControls.Icon, {
      name: "search"
    }), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": '搜索' + title,
      value: search,
      onChange: event => setSearch(event.target.value),
      disabled: disabled
    })), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      disabled: disabled
    }, "\u641C\u7D22")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: () => setScope({
        query: search,
        page: 1,
        size: 50
      })
    }, "\u5237\u65B0\u9009\u9879"), read.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u9009\u9879\u2026"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: read.result.warnings
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": title + '选项',
      style: {
        width: '100%',
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, title + '选项'), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u7F16\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u540D\u79F0"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9009\u62E9"))), /*#__PURE__*/React.createElement("tbody", null, data.entities.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, row.business_code), /*#__PURE__*/React.createElement("td", null, row.label), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      disabled: disabled || !(row.status === 'active' || target.kind === 'op_type' && row.status === null) || target.kind === 'op_type' && row.fields.category !== target.source,
      "aria-label": '采用 ' + row.label,
      onClick: () => onSelect(row)
    }, "\u91C7\u7528")))), !data.entities.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 3
    }, "\u6CA1\u6709\u5339\u914D\u9009\u9879\u3002"))))), /*#__PURE__*/React.createElement(window.ResourceTables.Pager, {
      page: data.page,
      disabled: disabled || read.loading,
      onPage: page => setScope(current => ({
        ...current,
        page,
        snapshot_ref: read.result.meta.snapshot_ref
      })),
      onSize: size => setScope(current => ({
        ...current,
        size,
        page: 1,
        snapshot_ref: undefined
      }))
    }))));
  }
  function ProcessSourceEditor({
    adapter,
    result,
    command,
    disabled,
    saved,
    onDirty,
    onOverlay,
    onResourceCommitted
  }) {
    const model = E.useDraft({
      result,
      adapter,
      stage: 'source',
      build,
      reconcile,
      saved,
      onDirty
    });
    const entity = model.base.data,
      draft = model.draft,
      rows = entity.operations,
      paging = E.usePage(rows);
    const [picker, setPicker] = React.useState(null),
      [create, setCreate] = React.useState(null);
    const [preflightResult, setPreview] = React.useState(null),
      [discarded, setDiscarded] = React.useState([]),
      [checking, setChecking] = React.useState(false);
    const preview = preflightResult && preflightResult.base === model.base && preflightResult.draft === draft ? preflightResult : null;
    const request = React.useRef(null);
    const blocked = disabled || command.locked || command.phase === 'done';
    const stageReason = E.reason(model, adapter, 'source'),
      editBlocked = blocked || entity.workflow.route.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    function invalidate() {
      if (request.current) request.current.abort();
      request.current = null;
      setChecking(false);
      setPreview(null);
      setDiscarded([]);
    }
    React.useEffect(() => {
      invalidate();
    }, [model.draft, model.base, model.review, disabled, command.error]);
    React.useEffect(() => () => {
      if (request.current) request.current.abort();
    }, []);
    function change(ref, patch) {
      invalidate();
      model.edit(current => ({
        ...current,
        [ref]: {
          ...current[ref],
          ...patch
        }
      }));
    }
    function openPicker(row, kind) {
      setPicker({
        ...row,
        kind,
        source: draft[row.ref].source
      });
      onOverlay(true);
    }
    function closePicker() {
      setPicker(null);
      onOverlay(false);
    }
    function choose(row) {
      change(picker.ref, picker.kind === 'op_type' ? {
        op_type_ref: row.ref,
        op_type_label: row.label
      } : {
        supplier_ref: row.ref,
        supplier_label: row.label
      });
      closePicker();
    }
    async function preflight(commit = false) {
      if (blocked || stageReason || checking) return;
      invalidate();
      model.setError(null);
      const controller = new AbortController();
      request.current = controller;
      try {
        if (typeof adapter.stagePreview !== 'function' || typeof P.stagePreview !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.stagePreview');
        const body = input(entity, draft, paging.page.size);
        setChecking(true);
        const response = P.stagePreview(await adapter.stagePreview(entity.ref, 'source_confirm', body, model.base.meta.snapshot_ref, controller.signal), entity.ref, 'source_confirm');
        if (!controller.signal.aborted && request.current === controller) {
          setPreview({
            response,
            body,
            base: model.base,
            draft
          });
          setChecking(false);
          if (commit && !response.data.affected_groups.length) await command.submit('process', 'source_confirm', entity.ref, response.data.write_context, body);
        }
      } catch (error) {
        if (!controller.signal.aborted && request.current === controller) {
          model.setError(error);
          setChecking(false);
        }
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    const affected = preview ? preview.response.data.affected_groups : [],
      acknowledgement = affected.every(row => discarded.includes(row.ref));
    const displayGroups = Array.from(new Map(entity.external_groups.concat(affected).map(row => [row.ref, row])).values());
    const saveReason = stageReason || preview && (!acknowledgement ? '请确认解除下方受影响的外协组。' : C.blocked(preview.response.data.write_context, 'process', 'source_confirm', preview.response.meta.source));
    async function save() {
      if (blocked || checking || saveReason) return;
      if (!preview) {
        await preflight(true);
        return;
      }
      await command.submit('process', 'source_confirm', entity.ref, preview.response.data.write_context, {
        ...preview.body,
        discard_group_refs: discarded
      });
    }
    const active = E.active(entity);
    return /*#__PURE__*/React.createElement("section", {
      "data-process-source-editor": true
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(E.Search, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement("span", null, "\u5171 ", active.length, " \u9053\u6709\u6548\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: editBlocked,
      reason: !adapter.resourceAdapter || !window.ProcessOpTypeCreate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => {
        invalidate();
        setCreate({});
        onOverlay(true);
      }
    }, "\u65B0\u589E\u5DE5\u79CD")), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table wb-table--editable",
      "aria-label": "\u5F52\u5C5E\u660E\u7EC6",
      style: {
        minWidth: 950,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "归属明细"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 150
      }
    }, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 160
      }
    }, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 160
      }
    }, "\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 190
      }
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4FDD\u5B58\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map(row => {
      const current = draft[row.ref] || row,
        inactive = row.status !== 'active',
        cycle = current.source === row.source && P.groupCycle(row, entity.external_groups);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref
      }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, row.sequence), " ", row.label, cycle && /*#__PURE__*/React.createElement("div", {
        className: "muted",
        "data-process-cycle-group": row.external_group_ref
      }, cycle)), /*#__PURE__*/React.createElement("td", null, current.op_type_label || '未选工种', /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        "aria-label": '选择工序 ' + row.sequence + ' 工种',
        disabled: editBlocked || inactive || !current.source,
        onClick: () => openPicker(row, 'op_type')
      }))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
        className: "segm",
        role: "group",
        "aria-label": '工序 ' + row.sequence + ' 归属'
      }, ['internal', 'external'].map(source => /*#__PURE__*/React.createElement(Button, {
        key: source,
        className: current.source === source ? 'on ' + (source === 'internal' ? 'int' : 'ext') : '',
        "aria-pressed": current.source === source,
        disabled: editBlocked || inactive,
        onClick: () => {
          if (source !== current.source) change(row.ref, {
            source,
            op_type_ref: null,
            op_type_label: null,
            supplier_ref: null,
            supplier_label: null
          });
        }
      }, P.sourceLabel(source)))), !current.source && /*#__PURE__*/React.createElement("div", null, "\u672A\u5F52\u7C7B")), /*#__PURE__*/React.createElement("td", null, current.source === 'internal' ? '不适用' : /*#__PURE__*/React.createElement(React.Fragment, null, current.supplier_label || '未选供应商', /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        "aria-label": '选择工序 ' + row.sequence + ' 供应商',
        disabled: editBlocked || inactive || current.source !== 'external',
        onClick: () => openPicker(row, 'supplier')
      }), current.supplier_ref && /*#__PURE__*/React.createElement(Button, {
        icon: "x",
        "aria-label": '清除工序 ' + row.sequence + ' 供应商',
        disabled: editBlocked || inactive,
        onClick: () => change(row.ref, {
          supplier_ref: null,
          supplier_label: null
        })
      })))), /*#__PURE__*/React.createElement("td", null, inactive ? '已停用工序' : /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, /*#__PURE__*/React.createElement(E.Confirmation, {
        record: row.confirmation && row.confirmation.source
      })), /*#__PURE__*/React.createElement(Issues, {
        issues: row.issues
      })));
    }), !paging.rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 5
    }, rows.length ? '没有匹配的工序。' : '尚无工序记录。'))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement(E.Groups, {
      rows: displayGroups,
      affected: affected.map(row => row.ref),
      discarded: discarded,
      onDiscard: preview ? setDiscarded : undefined,
      disabled: blocked
    }), preview && affected.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: preview.response.warnings
    }), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u672C\u6B21\u4FEE\u6539\u5C06\u89E3\u9664 ", affected.length, " \u4E2A\u5916\u534F\u7EC4\uFF0C\u8BF7\u786E\u8BA4\u4E0B\u65B9\u5217\u51FA\u7684\u53D8\u5316\u3002")), /*#__PURE__*/React.createElement(E.Feedback, {
      model: model,
      disabled: blocked || checking,
      paging: paging
    }), /*#__PURE__*/React.createElement("div", {
      className: "pd-foot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u4FDD\u5B58\u5168\u90E8 ", active.length, " \u9053\u6709\u6548\u5DE5\u5E8F\uFF0C\u5305\u542B\u5176\u4ED6\u9875\u548C\u7B5B\u9009\u9690\u85CF\u7684\u5DE5\u5E8F\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      className: "btn primary",
      busy: checking,
      disabled: blocked,
      reason: saveReason,
      onClick: save
    }, "\u4FDD\u5B58\u5F52\u5C5E\u5E76\u7EE7\u7EED")), picker && ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana process-detail"
    }, /*#__PURE__*/React.createElement(Picker, {
      adapter: adapter,
      target: picker,
      onSelect: choose,
      onClose: closePicker,
      disabled: blocked
    })), document.body), create && ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana process-detail"
    }, /*#__PURE__*/React.createElement(window.ProcessOpTypeCreate, {
      adapter: adapter.resourceAdapter,
      onClose: () => {
        setCreate(null);
        onOverlay(false);
      },
      onCommitted: receipt => {
        invalidate();
        model.reload();
        if (onResourceCommitted) onResourceCommitted(receipt);
      }
    })), document.body));
  }
  window.ProcessSourceEditor = ProcessSourceEditor;
})();
