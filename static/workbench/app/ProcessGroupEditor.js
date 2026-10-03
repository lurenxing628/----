(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    E = window.ProcessStageEditor;
  const {
    Button,
    Modal
  } = window.ResourceControls;
  const build = () => ({
    groups: [],
    discard_group_refs: []
  });
  function reconcile(draft, _before, after) {
    const groupRefs = new Set(after.external_groups.map(row => row.ref));
    const operationRefs = new Set(E.active(after).filter(row => row.source === 'external').map(row => row.ref));
    const groups = [];
    draft.groups.forEach(row => {
      if (row.ref !== null && !groupRefs.has(row.ref)) return;
      const refs = row.operation_refs.filter(ref => operationRefs.has(ref));
      if (refs.length > 0 || row.operation_refs.length === 0) groups.push({
        ...row,
        operation_refs: refs
      });
    });
    return {
      groups,
      discard_group_refs: draft.discard_group_refs.filter(ref => groupRefs.has(ref))
    };
  }
  function input(draft) {
    return {
      groups: draft.groups.map(row => {
        if (!row.operation_refs.length || !row.supplier_ref || !Number.isFinite(Number(row.total_days)) || Number(row.total_days) <= 0) throw C.failure('每段请选择连续外协工序、供应商，并填写大于 0 的整段周期。');
        return {
          ref: row.ref,
          operation_refs: row.operation_refs,
          supplier_ref: row.supplier_ref,
          total_days: Number(row.total_days)
        };
      }),
      discard_group_refs: draft.discard_group_refs
    };
  }
  function ProcessGroupEditor({
    adapter,
    result,
    command,
    disabled,
    onDirty,
    onClose
  }) {
    const model = E.useDraft({
      result,
      adapter,
      stage: 'groups',
      build,
      reconcile,
      saved: 0,
      onDirty
    });
    const entity = model.base.data,
      draft = model.draft,
      operations = E.active(entity),
      paging = E.usePage(operations);
    const [editing, setEditing] = React.useState(null),
      [picker, setPicker] = React.useState(null),
      [discard, setDiscard] = React.useState(false);
    const [preview, setPreview] = React.useState(null),
      [checking, setChecking] = React.useState(false),
      serial = React.useRef(0),
      request = React.useRef(null),
      reviewRoot = React.useRef(null);
    const blocked = disabled || command.locked || command.phase === 'done',
      current = draft.groups.find(row => row.key === editing);
    const validPreview = preview && preview.draft === draft && preview.base === model.base && !model.review ? preview : null;
    const reason = model.review ? '请先核对最新资料。' : entity.workflow.route.state !== 'confirmed' ? '请先确认路线。' : P.reason(entity.capabilities, 'stage_confirm', typeof adapter.stagePreview === 'function' && typeof adapter.command === 'function') || (model.base.meta.source !== 'production' ? '请先读取可保存的工艺资料。' : '') || (!model.dirty ? '请先新增、修改或解除外协段。' : '');
    React.useEffect(() => () => {
      if (request.current) request.current.abort();
      if (onDirty) onDirty('groups', false);
    }, []);
    React.useEffect(() => {
      if (!validPreview || !reviewRoot.current) return undefined;
      const frame = requestAnimationFrame(() => {
        if (reviewRoot.current) {
          reviewRoot.current.focus();
          reviewRoot.current.scrollIntoView({
            block: 'nearest'
          });
        }
      });
      return () => cancelAnimationFrame(frame);
    }, [validPreview]);
    function edit(next) {
      if (request.current) request.current.abort();
      setChecking(false);
      setPreview(null);
      model.edit(next);
    }
    function patch(values) {
      edit(old => ({
        ...old,
        groups: old.groups.map(row => row.key === editing ? {
          ...row,
          ...values
        } : row)
      }));
    }
    function members(row) {
      const refs = new Set(row.operation_refs);
      return operations.filter(op => op.source === 'external' && refs.has(op.ref));
    }
    function start(group) {
      const row = group ? {
        key: group.ref,
        ref: group.ref,
        operation_refs: operations.filter(op => op.external_group_ref === group.ref).map(op => op.ref),
        supplier_ref: group.supplier_ref,
        supplier_label: group.supplier_label,
        total_days: group.total_days === null ? '' : String(group.total_days)
      } : {
        key: 'new-' + ++serial.current,
        ref: null,
        operation_refs: [],
        supplier_ref: null,
        supplier_label: null,
        total_days: ''
      };
      if (!draft.groups.some(item => item.key === row.key)) edit(old => ({
        ...old,
        groups: old.groups.concat(row),
        discard_group_refs: old.discard_group_refs.filter(ref => ref !== row.ref)
      }));
      setEditing(row.key);
    }
    function remove(row) {
      edit(old => ({
        ...old,
        groups: old.groups.filter(item => item.key !== row.key)
      }));
      if (editing === row.key) setEditing(null);
    }
    function detach(group) {
      edit(old => ({
        groups: old.groups.filter(row => row.ref !== group.ref),
        discard_group_refs: old.discard_group_refs.includes(group.ref) ? old.discard_group_refs.filter(ref => ref !== group.ref) : old.discard_group_refs.concat(group.ref)
      }));
      if (editing === group.ref) setEditing(null);
    }
    function close() {
      if (!blocked) {
        if (model.dirty) setDiscard(true);else onClose();
      }
    }
    async function check() {
      if (blocked || checking || reason) return;
      const controller = new AbortController();
      request.current = controller;
      setChecking(true);
      model.setError(null);
      try {
        const body = input(draft),
          raw = await adapter.stagePreview(entity.ref, 'groups_confirm', body, model.base.meta.snapshot_ref, controller.signal);
        const response = P.stagePreview(raw, entity.ref, 'groups_confirm');
        if (!controller.signal.aborted) setPreview({
          response,
          body,
          draft,
          base: model.base
        });
      } catch (error) {
        if (!controller.signal.aborted) model.setError(error);
      } finally {
        if (request.current === controller) {
          request.current = null;
          setChecking(false);
        }
      }
    }
    async function save() {
      if (blocked || !validPreview || reason) return;
      await command.submit('process', 'groups_confirm', entity.ref, validPreview.response.data.write_context, validPreview.body);
    }
    const editedRefs = new Set(draft.groups.map(row => row.ref).filter(Boolean)),
      removedRefs = new Set(draft.discard_group_refs);
    const currentMembers = current ? members(current) : [];
    const losesSelections = model.review && !E.same(draft, reconcile(draft, entity, model.review.data));
    function label(fact) {
      return fact ? '工序 ' + (fact.sequences.join('、') || '无有效成员') + '；供应商 ' + (fact.supplier_label || fact.supplier_id || '未选') + '；' + (fact.merge_mode === 'merged' ? '整段 ' + E.value(fact.total_days) + ' 天' : '逐序周期') : '无';
    }
    return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana process-detail",
      "data-process-group-editor": true
    }, /*#__PURE__*/React.createElement(Modal, {
      title: "\u7BA1\u7406\u5916\u534F\u6BB5",
      icon: "chart-gantt",
      onClose: close,
      locked: blocked || checking,
      suspended: !!picker,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: blocked || checking,
        onClick: close
      }, "\u8FD4\u56DE\u5DE5\u65F6"), /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        disabled: blocked || checking,
        reason: reason,
        onClick: check
      }, "\u9884\u68C0\u5916\u534F\u6BB5"), /*#__PURE__*/React.createElement(Button, {
        className: "btn primary",
        icon: "check",
        disabled: blocked || checking || !validPreview,
        reason: reason,
        onClick: save
      }, "\u786E\u8BA4\u4FDD\u5B58\u5916\u534F\u6BB5"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll"
    }, /*#__PURE__*/React.createElement("p", null, "\u4E00\u6BB5\u8868\u793A\u4E00\u6B21\u9001\u51FA\u3001\u4E00\u6B21\u56DE\u5382\u3002\u53EA\u9009\u8DEF\u7EBF\u4E2D\u8FDE\u7EED\u4E14\u5C5E\u4E8E\u540C\u4E00\u5BB6\u4F9B\u5E94\u5546\u7684\u5916\u534F\u5DE5\u5E8F\uFF1B\u4E24\u6B21\u9001\u51FA\u8BF7\u5206\u522B\u5EFA\u6BB5\u3002\u6574\u6BB5\u5468\u671F\u53EA\u8BA1\u7B97\u4E00\u6B21\uFF0C\u4FEE\u6539\u540E\u8FD8\u9700\u786E\u8BA4\u5DE5\u65F6\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u62C6\u5206\u65F6\u5148\u7F29\u5C0F\u539F\u6BB5\u7684\u5DE5\u5E8F\u8303\u56F4\uFF0C\u518D\u65B0\u589E\u53E6\u4E00\u6BB5\uFF1B\u89E3\u9664\u540E\u5404\u5DE5\u5E8F\u6062\u590D\u539F\u9010\u5E8F\u5468\u671F\uFF0C\u539F\u6765\u672A\u586B\u5199\u7684\u8BF7\u8865\u9F50\u3002\u672A\u7F16\u8F91\u7684\u6BB5\u53CA\u5386\u53F2\u8BB0\u5F55\u4FDD\u7559\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DF2\u6709\u5916\u534F\u6BB5"), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: blocked || checking,
      onClick: () => start(null)
    }, "\u65B0\u589E\u5916\u534F\u6BB5")), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u5DF2\u6709\u5916\u534F\u6BB5"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F\u8303\u56F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5468\u671F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u672C\u6B21\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, entity.external_groups.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, row.start_sequence, " \u81F3 ", row.end_sequence), /*#__PURE__*/React.createElement("td", null, row.supplier_label || '未选'), /*#__PURE__*/React.createElement("td", null, row.merge_mode === 'merged' ? E.value(row.total_days) + ' 天（整段）' : '逐序设置'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      disabled: blocked || checking,
      onClick: () => start(row)
    }, editedRefs.has(row.ref) ? '继续编辑' : '修改范围 / 供应商'), /*#__PURE__*/React.createElement(Button, {
      disabled: blocked || checking,
      onClick: () => detach(row)
    }, removedRefs.has(row.ref) ? '撤销解除' : '解除此段'), removedRefs.has(row.ref) && /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u4FDD\u5B58\u65F6\u89E3\u9664")))), !entity.external_groups.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, "\u5C1A\u65E0\u5916\u534F\u6BB5\uFF0C\u53EF\u9009\u62E9\u5DE5\u5E8F\u65B0\u589E\u3002"))))), !!draft.groups.length && /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h3", null, "\u672C\u6B21\u65B0\u589E / \u4FEE\u6539"), draft.groups.map((row, index) => /*#__PURE__*/React.createElement("div", {
      className: "toolbar",
      key: row.key
    }, /*#__PURE__*/React.createElement("span", null, row.ref ? '修改' : '新增', "\u5916\u534F\u6BB5 \xB7 \u5DE5\u5E8F ", members(row).map(op => op.sequence).join('、') || '待选择', " \xB7 ", row.supplier_label || '待选供应商', " \xB7 ", row.total_days || '待填', " \u5929"), /*#__PURE__*/React.createElement(Button, {
      disabled: blocked || checking,
      "aria-label": '编辑本次第 ' + (index + 1) + ' 段',
      onClick: () => setEditing(row.key)
    }, "\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
      disabled: blocked || checking,
      onClick: () => remove(row)
    }, "\u64A4\u9500\u672C\u6B21\u7F16\u8F91")))), current && /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h3", null, current.ref ? '修改外协段' : '新外协段'), /*#__PURE__*/React.createElement(E.Search, {
      paging: paging,
      disabled: blocked || checking
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table wb-table--editable",
      "aria-label": "\u9009\u62E9\u5916\u534F\u6BB5\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u52A0\u5165\u6B64\u6BB5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5F52\u5C5E / \u4F9B\u5E94\u5546"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map(row => {
      const elsewhere = draft.groups.some(group => group.key !== current.key && group.operation_refs.includes(row.ref));
      const occupied = row.external_group_ref && row.external_group_ref !== current.ref && !editedRefs.has(row.external_group_ref) && !removedRefs.has(row.external_group_ref);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref
      }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": '外协段包含工序 ' + row.sequence,
        checked: current.operation_refs.includes(row.ref),
        disabled: blocked || checking || row.source !== 'external' || elsewhere || !!occupied,
        onChange: event => patch({
          operation_refs: event.target.checked ? current.operation_refs.concat(row.ref) : current.operation_refs.filter(ref => ref !== row.ref)
        })
      }), row.source !== 'external' ? '自制工序' : elsewhere ? '已选入另一段' : occupied ? '先编辑或解除原段' : '选择')), /*#__PURE__*/React.createElement("td", null, row.sequence, " \xB7 ", row.label), /*#__PURE__*/React.createElement("td", null, P.sourceLabel(row.source), " \xB7 ", row.source === 'internal' ? '不适用供应商' : row.supplier_label || '未选供应商'));
    })))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging,
      disabled: blocked || checking
    }), /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("span", null, "\u4F9B\u5E94\u5546\uFF1A", current.supplier_label || '未选择'), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      disabled: blocked || checking || !currentMembers.length,
      onClick: () => {
        setPicker({
          kind: 'supplier',
          source: 'external',
          sequence: currentMembers[0].sequence,
          group: {
            start_sequence: currentMembers[0].sequence,
            end_sequence: currentMembers[currentMembers.length - 1].sequence
          },
          members: currentMembers
        });
      }
    }, "\u9009\u62E9\u6574\u6BB5\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("label", null, "\u6574\u6BB5\u5468\u671F\uFF08\u5929\uFF09", /*#__PURE__*/React.createElement("input", {
      className: "wt-in",
      type: "number",
      step: "any",
      min: "0",
      "aria-label": "\u6574\u6BB5\u5916\u534F\u5468\u671F",
      value: current.total_days,
      disabled: blocked || checking,
      onChange: event => patch({
        total_days: event.target.value
      })
    })))), losesSelections && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6700\u65B0\u8D44\u6599\u4E2D\u6709\u5916\u534F\u6BB5\u6216\u5DE5\u5E8F\u5DF2\u5931\u6548\u3002\u63A5\u53D7\u540E\u4F1A\u79FB\u9664\u5931\u6548\u6BB5\u7684\u7F16\u8F91\u3001\u89E3\u9664\u9009\u62E9\u548C\u5931\u6548\u5DE5\u5E8F\u9009\u62E9\uFF0C\u4FDD\u7559\u4ECD\u6709\u6548\u7684\u6BB5\u8349\u7A3F\u3002"), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), /*#__PURE__*/React.createElement(E.Feedback, {
      model: model,
      disabled: blocked || checking
    }), validPreview && /*#__PURE__*/React.createElement("section", {
      role: "status",
      ref: reviewRoot,
      tabIndex: -1
    }, /*#__PURE__*/React.createElement("h3", null, "\u4FDD\u5B58\u524D\u6838\u5BF9"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u5916\u534F\u6BB5\u53D8\u66F4\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u64CD\u4F5C"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4FDD\u5B58\u524D"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4FDD\u5B58\u540E"))), /*#__PURE__*/React.createElement("tbody", null, validPreview.response.data.changes.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, {
      create: '新增段',
      update: '修改段',
      discard: '解除段'
    }[row.action]), /*#__PURE__*/React.createElement("td", null, label(row.before)), /*#__PURE__*/React.createElement("td", null, label(row.after)))), !validPreview.response.data.changes.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 3
    }, "\u4E0E\u5DF2\u4FDD\u5B58\u5185\u5BB9\u4E00\u81F4\uFF0C\u65E0\u9700\u6539\u53D8\u73B0\u6709\u6BB5\u3002")))))), discard && /*#__PURE__*/React.createElement("section", {
      className: "match-note is-block",
      role: "alert"
    }, /*#__PURE__*/React.createElement("p", null, "\u672C\u6B21\u5916\u534F\u6BB5\u4FEE\u6539\u5C1A\u672A\u4FDD\u5B58\u3002"), /*#__PURE__*/React.createElement(Button, {
      disabled: blocked,
      onClick: () => setDiscard(false)
    }, "\u7EE7\u7EED\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
      className: "btn danger",
      disabled: blocked,
      onClick: onClose
    }, "\u653E\u5F03\u6BB5\u4FEE\u6539\u5E76\u8FD4\u56DE")))), picker && /*#__PURE__*/React.createElement(window.ProcessSourcePicker, {
      adapter: adapter,
      target: picker,
      disabled: blocked || checking,
      onClose: () => setPicker(null),
      onSelect: row => {
        patch({
          supplier_ref: row.ref,
          supplier_label: row.label,
          ...(!current.ref && !current.total_days && row.fields.default_days > 0 ? {
            total_days: String(row.fields.default_days)
          } : {})
        });
        setPicker(null);
      }
    })), document.body);
  }
  window.ProcessGroupEditor = ProcessGroupEditor;
})();
