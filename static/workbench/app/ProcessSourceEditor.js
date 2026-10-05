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
  function supplierMembers(entity, draft, row) {
    const group = entity.external_groups.find(item => item.ref === row.external_group_ref);
    return group && draft[row.ref].source === 'external' ? E.active(entity).filter(item => item.external_group_ref === group.ref && draft[item.ref].source === 'external') : [row];
  }
  function supplierReason(row, target) {
    if (row.status !== 'active') return '供应商未启用，不能选择。';
    const members = target.members || [target];
    const missing = members.filter(item => !item.op_type_ref);
    if (missing.length) return '请先为工序 ' + missing.map(item => item.sequence).join('、') + ' 选择外协工种。';
    const refs = row.relationships.op_type_refs;
    if (!Array.isArray(refs)) return '供应商承接工种资料未读取，暂时不能选择。';
    const unsupported = members.filter(item => !refs.includes(item.op_type_ref));
    return unsupported.length ? '不能承接：' + unsupported.map(item => '工序 ' + item.sequence + ' ' + item.op_type_label).join('、') + '。' : '';
  }
  function locateFailure(error, entity, pageSize) {
    const paths = C.fieldErrors(error).map(row => row.path);
    const index = entity.operations.findIndex(row => paths.some(path => path === 'operations.' + row.ref + '.supplier_ref'));
    if (index >= 0) error.locate_page = Math.floor(index / pageSize) + 1;
    return error;
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
    const grouped = target.kind === 'supplier' && target.group;
    const subject = grouped ? '外协段 ' + target.group.start_sequence + ' 至 ' + target.group.end_sequence : '工序 ' + target.sequence;
    return /*#__PURE__*/React.createElement(Modal, {
      title: '选择' + title + ' · ' + subject,
      icon: "search",
      onClose: onClose,
      locked: disabled,
      footer: /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: disabled
      }, "\u53D6\u6D88")
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll"
    }, target.kind === 'supplier' && /*#__PURE__*/React.createElement("p", null, grouped ? '本次选择会统一用于本段全部工序：' : '请选择能承接本工序的供应商：', (target.members || [target]).map(row => row.sequence + ' ' + (row.op_type_label || '未选工种')).join('、'), "\u3002\u53EA\u6709\u80FD\u627F\u63A5\u5168\u90E8\u6240\u5217\u5DE5\u79CD\u7684\u542F\u7528\u4F9B\u5E94\u5546\u53EF\u4EE5\u91C7\u7528\u3002"), /*#__PURE__*/React.createElement("form", {
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
    }, "\u540D\u79F0"), target.kind === 'supplier' && /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u627F\u63A5\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9009\u62E9"))), /*#__PURE__*/React.createElement("tbody", null, data.entities.map(row => {
      const reason = target.kind === 'supplier' ? supplierReason(row, target) : '';
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref
      }, /*#__PURE__*/React.createElement("td", null, row.business_code), /*#__PURE__*/React.createElement("td", null, row.label), target.kind === 'supplier' && /*#__PURE__*/React.createElement("td", null, (row.relationships.op_types || []).map(item => item.label).join('、') || '未登记承接工种'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        reason: reason,
        disabled: disabled || !(row.status === 'active' || target.kind === 'op_type' && row.status === null) || target.kind === 'op_type' && ![target.source, "both"].includes(row.fields.category),
        "aria-label": '采用 ' + row.label,
        onClick: () => onSelect(row)
      }, "\u91C7\u7528")));
    }), !data.entities.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: target.kind === 'supplier' ? 4 : 3
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
    onResourceCommitted,
    focusRef = null
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
      paging = E.usePage(rows, focusRef),
      root = React.useRef(null);
    const groups = React.useMemo(() => P.groupIndex(entity.external_groups), [entity.external_groups]);
    E.useFocus(root, focusRef, paging.page.number);
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
      const members = supplierMembers(entity, draft, row).map(item => ({
        ...item,
        ...draft[item.ref]
      }));
      setPicker({
        ...row,
        ...draft[row.ref],
        kind,
        members,
        group: entity.external_groups.find(item => item.ref === row.external_group_ref)
      });
      onOverlay(true);
    }
    function closePicker() {
      setPicker(null);
      onOverlay(false);
    }
    function choose(row) {
      invalidate();
      model.edit(current => {
        const next = {
            ...current
          },
          members = supplierMembers(entity, current, picker);
        if (picker.kind === 'supplier') members.forEach(item => {
          next[item.ref] = {
            ...next[item.ref],
            supplier_ref: row.ref,
            supplier_label: row.label
          };
        });else {
          if (current[picker.ref].op_type_ref !== row.ref) members.forEach(item => {
            next[item.ref] = {
              ...next[item.ref],
              supplier_ref: null,
              supplier_label: null
            };
          });
          next[picker.ref] = {
            ...next[picker.ref],
            op_type_ref: row.ref,
            op_type_label: row.label
          };
        }
        return next;
      });
      closePicker();
    }
    function clearSupplier(row) {
      invalidate();
      model.edit(current => {
        const next = {
          ...current
        };
        supplierMembers(entity, current, row).forEach(item => {
          next[item.ref] = {
            ...next[item.ref],
            supplier_ref: null,
            supplier_label: null
          };
        });
        return next;
      });
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
          model.setError(locateFailure(error, entity, paging.page.size));
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
      ref: root,
      "data-process-source-editor": true
    }, active.some(row => draft[row.ref] && row.op_type_ref !== draft[row.ref].op_type_ref) && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u66F4\u6362\u5B9E\u9645\u5DE5\u79CD\u540E\uFF0C\u5C06\u6E05\u9664\u539F\u6362\u578B\u5DE5\u65F6\u3001\u5355\u4EF6\u5DE5\u65F6\u548C\u672C\u5E8F\u5916\u534F\u5468\u671F\uFF0C\u8BF7\u91CD\u65B0\u586B\u5199\u5E76\u786E\u8BA4\u3002"), /*#__PURE__*/React.createElement("div", {
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
        cycle = current.source === row.source && P.groupCycle(row, groups);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref,
        "data-process-location": row.ref,
        tabIndex: row.ref === focusRef ? -1 : undefined,
        "aria-current": row.ref === focusRef ? 'true' : undefined
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
        title: row.external_group_ref ? '清除本外协段所有工序的供应商' : '清除供应商',
        disabled: editBlocked || inactive,
        onClick: () => clearSupplier(row)
      })), row.external_group_ref && /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, "\u9009\u62E9\u6216\u6E05\u9664\u4F9B\u5E94\u5546\u4F1A\u5E94\u7528\u5230\u672C\u5916\u534F\u6BB5\u3002"))), /*#__PURE__*/React.createElement("td", null, inactive ? '已停用工序' : /*#__PURE__*/React.createElement("div", {
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
    }), entity.external_groups.length > 0 && /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u9700\u8981\u8BA9\u6BB5\u5185\u5DE5\u5E8F\u6539\u7528\u4E0D\u540C\u4F9B\u5E94\u5546\u6216\u6539\u4E3A\u81EA\u5236\u65F6\uFF0C\u8BF7\u5148\u5230\u5DE5\u65F6\u5B9A\u989D\u9875\u7BA1\u7406\u3001\u62C6\u5206\u5916\u534F\u6BB5\u3002"), preview && affected.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
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
  window.ProcessSourcePicker = Picker;
})();
