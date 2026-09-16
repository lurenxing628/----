(function () {
  'use strict';

  const C = window.APSResourceContract;
  const {
    Button,
    ErrorBox,
    Issues,
    Status,
    Modal,
    Choice,
    Relation,
    Field,
    focusFirstInvalid
  } = window.ResourceControls;
  const icons = {
    material: 'box',
    op_type: 'wrench',
    machine: 'machine',
    operator: 'users',
    supplier: 'truck'
  };
  function Feedback({
    command,
    action,
    excludePaths = []
  }) {
    if (!command) return null;
    const phase = command.phase,
      intent = command.intent || {},
      operation = action || intent.action;
    const bulkDelete = operation === 'confirm' && ['material_bulk', 'op_type_bulk', 'machine_bulk', 'operator_bulk', 'supplier_bulk', 'process_bulk'].includes(intent.kind);
    const batchAction = command.result && command.result.data && command.result.data.action;
    const verb = intent.kind === 'calendar' && operation === 'delete' ? '清除日历配置' : operation === 'delete' || bulkDelete ? '删除' : operation === 'unlink' ? '解除关联' : intent.kind === 'batch' && operation === 'bulk_confirm' ? ['delete', 'update', 'copy'].includes(batchAction) ? {
      delete: '删除',
      update: '保存',
      copy: '复制'
    }[batchAction] : '批次操作' : operation === 'machine_permissions' ? '设备关联保存' : operation === 'import' ? '导入' : '保存';
    return /*#__PURE__*/React.createElement(React.Fragment, null, ['sending', 'checking'].includes(phase) && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, phase === 'sending' ? '正在提交' + verb + '，请勿重复操作…' : '正在查询上次' + verb + '的结果…'), phase === 'pending' && /*#__PURE__*/React.createElement("div", {
      role: "status",
      className: "match-note",
      style: {
        display: 'block'
      }
    }, /*#__PURE__*/React.createElement("p", null, window.WorkbenchTerms.outcomes.pending(verb)), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      onClick: command.check
    }, window.WorkbenchTerms.actions.query_result)), phase === 'done' && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, command.result.result === 'partial' ? '部分' + verb + '已完成，请核对逐项结果。' : command.result.result === 'unchanged' ? '内容没有变化，已确认。' : window.WorkbenchTerms.outcomes.done(verb)), /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.error,
      excludePaths: excludePaths
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: command.result && command.result.warnings || []
    }), phase === 'done' && command.result.result === 'partial' && (Array.isArray(command.result.data.items) ? /*#__PURE__*/React.createElement("ul", null, command.result.data.items.map((item, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, item.business_code || item.label || '第 ' + (index + 1) + ' 项', "\uFF1A", {
      committed: '已提交',
      unchanged: '未变化',
      failed: '失败',
      skipped: '未执行'
    }[item.result] || '结果未确认', item.error && item.error.message ? '；' + item.error.message : ''))) : /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u7ED3\u679C\u91CC\u6CA1\u6709\u9010\u9879\u660E\u7EC6\uFF0C\u8BF7\u5728\u7EF4\u62A4\u5411\u5BFC\u91CC\u6838\u5BF9\u3002\u6CA1\u6709\u5F53\u6210\u5168\u90E8\u6210\u529F\u3002")));
  }
  function LegacyFacts({
    entity
  }) {
    if (!entity) return /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u8BF7\u5728\u4EBA\u5458\u8BE6\u60C5\u4E2D\u8BBE\u7F6E\u53EF\u64CD\u4F5C\u8BBE\u5907\u3002"));
    const permissions = entity.relationships.machine_permissions;
    if (Array.isArray(permissions)) return /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, "\u53EF\u64CD\u4F5C\u8BBE\u5907"), permissions.length ? /*#__PURE__*/React.createElement("div", {
      className: "chipline"
    }, permissions.map(item => /*#__PURE__*/React.createElement("span", {
      className: "chip",
      key: item.machine_ref,
      style: {
        whiteSpace: 'normal'
      }
    }, item.business_code, " \xB7 ", item.label, item.is_primary === 'yes' ? '（主操）' : ''))) : /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u5C1A\u672A\u8BBE\u7F6E\u53EF\u64CD\u4F5C\u8BBE\u5907\u3002"), /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u5728\u4EBA\u5458\u8BE6\u60C5\u4E2D\u70B9\u201C\u7F16\u8F91\u53EF\u64CD\u4F5C\u8BBE\u5907\u201D\u7EF4\u62A4\u8BBE\u5907\u5173\u8054\u3002"));
    const facts = entity.relationships.legacy_machine_authorizations;
    return /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, "\u65E2\u6709\u8BBE\u5907\u6388\u6743\uFF08\u53EA\u8BFB\uFF09"), Array.isArray(facts) ? facts.length ? /*#__PURE__*/React.createElement("div", {
      className: "chipline"
    }, facts.map((item, index) => /*#__PURE__*/React.createElement("span", {
      className: "chip",
      key: item.ref || index,
      style: {
        whiteSpace: 'normal'
      }
    }, item.label || '设备名称未填写', item.status && item.status !== 'active' ? '（历史授权）' : ''))) : /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u65E0\u65E2\u6709\u8BBE\u5907\u6388\u6743\u3002") : Number.isSafeInteger(entity.relationships.machine_authorization_count) ? /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u5DF2\u767B\u8BB0 ", entity.relationships.machine_authorization_count, " \u9879\u8BBE\u5907\u6388\u6743\uFF0C\u660E\u7EC6\u672A\u8BFB\u53D6\u3002") : C.own(entity.relationships, 'machine_refs') ? /*#__PURE__*/React.createElement(Relation, {
      entity: entity,
      field: "machine_refs"
    }) : /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u8BBE\u5907\u6388\u6743\u5C1A\u672A\u8BFB\u53D6\u3002"), /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u6280\u80FD\u767B\u8BB0\u4E0D\u6539\u53D8\u65E2\u6709\u8BBE\u5907\u6388\u6743\u3002"));
  }
  function Remark({
    kind,
    entity
  }) {
    return C.own(entity.fields, 'remark') ? /*#__PURE__*/React.createElement("dl", {
      className: "wb-resource-remark"
    }, /*#__PURE__*/React.createElement("dt", null, C.fieldLabels(kind, entity.fields.category).remark), /*#__PURE__*/React.createElement("dd", null, C.fieldValue(kind, 'remark', entity.fields.remark))) : null;
  }
  function CurrentFields({
    kind,
    entity,
    includeRemark = true
  }) {
    const labels = C.fieldLabels(kind, entity.fields.category);
    const stock = kind === 'material' && C.own(entity.fields, 'stock_qty');
    const keys = Object.keys(labels).filter(key => C.own(entity.fields, key) && key !== 'remark' && !(stock && key === 'unit'));
    return /*#__PURE__*/React.createElement(React.Fragment, null, keys.length > 0 && /*#__PURE__*/React.createElement("dl", {
      className: "wb-resource-facts"
    }, keys.map(key => /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-fact",
      key: key,
      "data-field": key
    }, /*#__PURE__*/React.createElement("dt", null, labels[key]), /*#__PURE__*/React.createElement("dd", null, stock && key === 'stock_qty' ? /*#__PURE__*/React.createElement("span", {
      className: "wb-resource-stock"
    }, /*#__PURE__*/React.createElement("strong", null, entity.fields.stock_qty == null ? '未知' : String(entity.fields.stock_qty)), /*#__PURE__*/React.createElement("span", null, entity.fields.unit || '单位未填写')) : C.fieldValue(kind, key, entity.fields[key]))))), includeRemark && /*#__PURE__*/React.createElement(Remark, {
      kind: kind,
      entity: entity
    }));
  }
  function StockFacts({
    entity
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, "\u7269\u6599"), /*#__PURE__*/React.createElement("span", {
      style: {
        overflowWrap: 'anywhere'
      }
    }, entity.business_code, " \xB7 ", entity.label)), /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, "\u5F53\u524D\u5E93\u5B58"), /*#__PURE__*/React.createElement("span", {
      className: "wb-resource-stock"
    }, /*#__PURE__*/React.createElement("strong", null, entity.fields.stock_qty == null ? '未知' : String(entity.fields.stock_qty)), /*#__PURE__*/React.createElement("span", null, entity.fields.unit || '单位未填写'))));
  }
  function ResourceForms({
    adapter,
    kind,
    category,
    action = 'create',
    entity: initialEntity,
    acceptedEntity,
    writeContext,
    source,
    command,
    onClose,
    onReloadContext,
    refreshState = {},
    onRefresh,
    contextError,
    contextReview,
    contextBusy,
    stockOnly = false
  }) {
    const [entity, setEntity] = React.useState(initialEntity);
    const [draft, setDraft] = React.useState(() => C.draft(kind, initialEntity, category));
    const baseline = React.useRef(JSON.stringify(C.draft(kind, initialEntity, category))),
      form = React.useRef(null);
    const [error, setError] = React.useState(null),
      [catalogBusy, setCatalogBusy] = React.useState(false);
    const [deleteChecked, setDeleteChecked] = React.useState(false);
    React.useLayoutEffect(() => {
      if (!acceptedEntity || acceptedEntity === entity) return;
      if (!entity || acceptedEntity.ref !== entity.ref) {
        setError(C.failure('最新资料和正在编辑的记录不一致，已填写的内容没有被替换。'));
        return;
      }
      baseline.current = JSON.stringify(C.draft(kind, acceptedEntity, category));
      setDraft(value => C.rebaseDraft(kind, value, entity, acceptedEntity, category));
      setEntity(acceptedEntity);
    }, [acceptedEntity, kind, category]);
    const formId = React.useId();
    const opCategory = draft.fields.category;
    const adjustingStock = stockOnly && kind === 'material' && action === 'update';
    const done = command.phase === 'done',
      disabled = command.locked || done || catalogBusy || contextBusy;
    const reason = typeof adapter.command !== 'function' ? '保存功能尚未开通。' : C.blocked(writeContext, kind, action, source);
    // Deleting basic data takes the checkbox confirmation used for backup deletion; the unchecked state is the button's own reason, not a bare sentence.
    const confirmReason = action === 'delete' && !deleteChecked ? '请先勾选已核对要删除的资料及其关联关系。' : '';
    const currentError = error || command.error;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      dirty: action !== 'delete' && !done && JSON.stringify(draft) !== baseline.current,
      // Only a pending command locks the draft guard; catalog or context busy states are UI state, not an unverified request.
      message: '基础资料里有尚未保存的填写内容。',
      locked: command.locked
    });
    React.useEffect(() => {
      if (currentError) focusFirstInvalid(form.current);
    }, [currentError]);
    const fieldPaths = action === 'delete' ? [] : adjustingStock ? ['fields.stock_qty'] : ['business_code', 'label', ...(kind === 'material' ? ['fields.spec', 'fields.unit', 'fields.stock_qty', 'fields.remark'] : []), ...(kind === 'op_type' ? ['fields.remark', ...(!['internal', 'external'].includes(entity ? entity.fields.category : category) ? ['fields.category'] : []), ...(opCategory === 'external' ? ['fields.default_merge_mode'] : [])] : []), ...(kind === 'supplier' ? ['fields.default_days'] : []), ...(C.statuses[kind] ? ['fields.status'] : []), ...(C.relations[kind] || []).flatMap(field => [field.key, 'relationships.' + field.key])];
    async function close(detail) {
      if (command.locked || catalogBusy || contextBusy) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner) && !(await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) return;
      onClose();
    }
    function change(section, key, value) {
      setDraft(current => section ? {
        ...current,
        [section]: {
          ...current[section],
          [key]: value
        }
      } : {
        ...current,
        [key]: value
      });
      setError(null);
    }
    async function submit(event) {
      event.preventDefault();
      if (disabled || reason || confirmReason) return;
      try {
        const invalidNumbers = Array.from(event.currentTarget.elements).filter(element => element.type === 'number' && element.validity.badInput);
        if (invalidNumbers.length) throw C.failure('请核对标红的数字。', invalidNumbers.map(element => ({
          path: 'fields.' + element.name,
          message: '请输入有效数字。'
        })));
        const inputDraft = adjustingStock ? C.draft(kind, entity, category) : draft;
        if (adjustingStock) inputDraft.fields.stock_qty = draft.fields.stock_qty;
        const input = action === 'delete' ? {} : C.input(kind, inputDraft, entity, category);
        setError(null);
        await command.submit(kind, action, entity ? entity.ref : null, writeContext, input, draft.fields.category);
      } catch (failure) {
        setError(failure);
      }
    }
    async function catalog(field, reload) {
      setCatalogBusy(true);
      setError(null);
      let opened = false;
      const refreshParent = () => {
        reload();
        if (onReloadContext) onReloadContext();
      };
      const completed = result => {
        setCatalogBusy(false);
        if (C.receipt(result) === 'terminal') {
          refreshParent();
          if (result.result === 'partial') setError(C.failure(field.label + '只完成了一部分，请点「维护' + field.label + '」核对逐项结果。'));
        } else setError(C.failure(field.label + '的维护结果还没确认，没有当成保存成功。'));
      };
      try {
        const result = await adapter.openCatalog(field.kind, {
          refs: [],
          scope: {
            source
          },
          onCommitted: completed,
          onClosed: () => setCatalogBusy(false)
        }, new AbortController().signal);
        if (result && result.state === 'opened') {
          opened = true;
          return;
        }
        if (result && result.state === 'cancelled') return;
        if (C.receipt(result) === 'terminal' && result.result !== 'partial') {
          refreshParent();
          return;
        }
        throw C.failure(field.label + '维护没有返回明确结果，没有当成保存成功。');
      } catch (failure) {
        setError(failure);
      } finally {
        if (!opened) setCatalogBusy(false);
      }
    }
    const text = (key, label, options = {}) => /*#__PURE__*/React.createElement(Field, {
      key: key,
      label: label,
      path: options.top ? key : 'fields.' + key,
      error: currentError,
      required: options.required,
      full: options.full
    }, options.multiline ? /*#__PURE__*/React.createElement("textarea", {
      name: key,
      value: draft.fields[key],
      disabled: disabled,
      onChange: event => change('fields', key, event.target.value)
    }) : /*#__PURE__*/React.createElement("input", {
      name: key,
      value: options.top ? draft[key] : draft.fields[key],
      disabled: disabled,
      readOnly: options.readOnly,
      type: options.number ? 'number' : 'text',
      step: options.number ? 'any' : undefined,
      min: options.number ? 0 : undefined,
      style: options.number ? {
        textAlign: 'right',
        fontVariantNumeric: 'tabular-nums'
      } : undefined,
      onChange: event => change(options.top ? null : 'fields', key, event.target.value)
    }));
    const stateField = () => /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      path: "fields.status",
      error: currentError,
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      name: "status",
      value: draft.fields.status,
      disabled: disabled,
      onChange: event => change('fields', 'status', event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "",
      disabled: true
    }, "\u8BF7\u9009\u62E9\u72B6\u6001"), C.statuses[kind].filter(row => row[0] !== 'unknown').map(([value, label]) => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, label)), !C.statuses[kind].some(row => row[0] === draft.fields.status && row[0] !== 'unknown') && draft.fields.status && /*#__PURE__*/React.createElement("option", {
      value: draft.fields.status
    }, "\u65E7\u72B6\u6001 / \u539F\u56E0\u672A\u77E5\uFF08\u4FDD\u6301\u539F\u503C\uFF09")));
    return /*#__PURE__*/React.createElement(Modal, {
      title: adjustingStock ? '调整库存' : (action === 'create' ? '新增' : action === 'delete' ? '删除' : '编辑') + C.resourceName(kind, opCategory),
      icon: action === 'delete' ? 'trash-2' : icons[kind],
      onClose: close,
      guardOwner: guardOwner,
      locked: command.locked || catalogBusy || contextBusy,
      suspended: catalogBusy,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        reason: command.locked ? '结果还没确认，暂时不能关闭。' : contextBusy ? '正在读取最新资料。' : '',
        disabled: catalogBusy
      }, done ? '关闭' : '取消'), !done && /*#__PURE__*/React.createElement(Button, {
        form: formId,
        type: "submit",
        icon: action === 'delete' ? 'trash-2' : 'check',
        className: 'btn primary wb-action wb-primary',
        reason: reason || confirmReason,
        busy: disabled
      }, action === 'delete' ? '确认删除' : '保存'))
    }, /*#__PURE__*/React.createElement("form", {
      id: formId,
      ref: form,
      className: "modal-b form scroll",
      onSubmit: submit,
      noValidate: true
    }, action === 'delete' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u5220\u9664 ", /*#__PURE__*/React.createElement("b", null, entity.business_code, " \xB7 ", entity.label), "\uFF1F\u7CFB\u7EDF\u4F1A\u518D\u6B21\u6838\u5BF9\u5173\u8054\u5173\u7CFB\u548C\u5220\u9664\u6761\u4EF6\u3002"), /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: deleteChecked,
      disabled: disabled,
      onChange: event => setDeleteChecked(event.target.checked)
    }), "\u6211\u5DF2\u6838\u5BF9\u8981\u5220\u9664\u7684\u8D44\u6599\u53CA\u5176\u5173\u8054\u5173\u7CFB")) : adjustingStock ? /*#__PURE__*/React.createElement("div", {
      className: "fgrid",
      style: {
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement(StockFacts, {
      entity: entity
    }), text('stock_qty', '调整后库存' + (entity.fields.unit ? '（' + entity.fields.unit + '）' : '（单位未填写）'), {
      number: true,
      full: true
    })) : /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, text('business_code', C.codeLabel(kind), {
      top: true,
      required: action === 'create',
      readOnly: action !== 'create'
    }), text('label', C.nameLabel(kind), {
      top: true,
      required: true
    }), kind === 'material' && /*#__PURE__*/React.createElement(React.Fragment, null, text('spec', '规格'), text('unit', '单位'), text('stock_qty', '库存数量', {
      number: true
    })), kind === 'op_type' && /*#__PURE__*/React.createElement(React.Fragment, null, !['internal', 'external'].includes(entity ? entity.fields.category : category) && /*#__PURE__*/React.createElement(Field, {
      label: "\u5F52\u5C5E",
      path: "fields.category",
      error: currentError,
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      name: "category",
      value: opCategory,
      disabled: disabled,
      onChange: event => change('fields', 'category', event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "",
      disabled: true
    }, "\u8BF7\u9009\u62E9\u5F52\u5C5E"), /*#__PURE__*/React.createElement("option", {
      value: "internal"
    }, "\u81EA\u5236"), /*#__PURE__*/React.createElement("option", {
      value: "external"
    }, "\u5916\u534F"), opCategory && !['internal', 'external'].includes(opCategory) && /*#__PURE__*/React.createElement("option", {
      value: opCategory
    }, "\u539F\u5F52\u5C5E\u672A\u8BC6\u522B\uFF08\u4FDD\u6301\u539F\u503C\uFF09"))), opCategory === 'external' && /*#__PURE__*/React.createElement(Field, {
      label: "\u9ED8\u8BA4\u5468\u671F\u89C4\u5219",
      path: "fields.default_merge_mode",
      error: currentError
    }, /*#__PURE__*/React.createElement("select", {
      name: "default_merge_mode",
      value: draft.fields.default_merge_mode,
      disabled: disabled,
      onChange: event => change('fields', 'default_merge_mode', event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u672A\u586B\u5199"), /*#__PURE__*/React.createElement("option", {
      value: "separate"
    }, "\u5206\u522B\u8BBE\u7F6E"), /*#__PURE__*/React.createElement("option", {
      value: "merged"
    }, "\u5408\u5E76\u8BBE\u7F6E"), !['', 'separate', 'merged'].includes(draft.fields.default_merge_mode) && /*#__PURE__*/React.createElement("option", {
      value: draft.fields.default_merge_mode
    }, "\u539F\u5468\u671F\u89C4\u5219\u672A\u8BC6\u522B\uFF08\u4FDD\u6301\u539F\u503C\uFF09")))), (C.relations[kind] || []).map(field => /*#__PURE__*/React.createElement(Choice, {
      key: field.key,
      adapter: adapter,
      field: field,
      value: draft.relationships[field.key],
      original: entity,
      disabled: disabled,
      error: currentError,
      onChange: value => change('relationships', field.key, value),
      onCatalog: catalog,
      catalogBusy: catalogBusy
    })), kind === 'supplier' && text('default_days', '默认周期（天）', {
      number: true,
      required: true
    }), C.statuses[kind] && stateField(), entity && entity.fields.inactive_reason === 'unknown' && /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, "\u5F53\u524D\u505C\u7528\u539F\u56E0\u672A\u77E5\uFF0C\u6CA1\u6709\u5F53\u6210\u8BF7\u5047\u6216\u5F85\u590D\u6838\u3002")), entity && C.own(entity.fields, 'legacy_status') && /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, "\u539F\u59CB\u72B6\u6001\uFF08\u53EA\u8BFB\uFF09"), /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, entity.fields.legacy_status === 'inactive' ? '原停用状态，原因未登记' : '原状态：' + String(entity.fields.legacy_status))), (kind === 'material' || kind === 'op_type') && text('remark', kind === 'op_type' && opCategory === 'internal' ? '产能备注' : '备注', {
      full: true,
      multiline: true
    }), kind === 'operator' && /*#__PURE__*/React.createElement(LegacyFacts, {
      entity: entity
    })), /*#__PURE__*/React.createElement(Issues, {
      issues: entity && entity.issues || []
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: fieldPaths
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      action: action,
      excludePaths: error ? [] : fieldPaths
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: contextError
    }), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), !done && !command.locked && onReloadContext && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: contextBusy,
      disabled: catalogBusy,
      onClick: onReloadContext
    }, "\u5237\u65B0\u6700\u65B0\u8D44\u6599"), contextReview && !done && /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-review",
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u6700\u65B0\u8D44\u6599\u5DF2\u5237\u65B0\u3002\u4F60\u4FEE\u6539\u7684\u5185\u5BB9\u5DF2\u4FDD\u7559\uFF0C\u672A\u4FEE\u6539\u7684\u9879\u5DF2\u66F4\u65B0\uFF1B\u4E0B\u65B9\u663E\u793A\u5F53\u524D\u5DF2\u4FDD\u5B58\u7684\u8D44\u6599\u3002"), contextReview.data.ref ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-review-identity"
    }, /*#__PURE__*/React.createElement("strong", null, contextReview.data.business_code, " \xB7 ", contextReview.data.label), kind !== 'op_type' && /*#__PURE__*/React.createElement(Status, {
      kind: kind,
      entity: contextReview.data
    })), /*#__PURE__*/React.createElement(CurrentFields, {
      kind: kind,
      entity: contextReview.data
    }), (C.relations[kind] || []).map(field => /*#__PURE__*/React.createElement("p", {
      key: field.key
    }, field.label, "\uFF1A", /*#__PURE__*/React.createElement(Relation, {
      entity: contextReview.data,
      field: field.key
    })))) : /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u8D44\u6599\u603B\u6570\uFF1A", contextReview.data.page.total)), done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, refreshState.loading ? '正在刷新列表和详情…' : refreshState.done ? '已刷新到最新数据。' : '最新数据还没确认。请点「刷新保存结果」。'), /*#__PURE__*/React.createElement(ErrorBox, {
      error: refreshState.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: refreshState.detail && refreshState.detail.data.issues || []
    }), refreshState.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u4FDD\u5B58\u7ED3\u679C"))));
  }
  function Detail({
    adapter,
    kind,
    result,
    onClose,
    onEdit,
    onDelete,
    onAdjustStock,
    onMachinePermissions,
    onRelated,
    onBack,
    busy,
    error,
    onRetry
  }) {
    const entity = result && result.data;
    return /*#__PURE__*/React.createElement(Modal, {
      title: C.resourceName(kind, entity && entity.fields.category) + '详情',
      icon: icons[kind],
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, onBack && /*#__PURE__*/React.createElement(Button, {
        icon: "chevron-left",
        onClick: onBack
      }, "\u8FD4\u56DE\u4E0A\u4E00\u6761\u8BE6\u60C5"), /*#__PURE__*/React.createElement(Button, {
        onClick: onClose
      }, "\u5173\u95ED"), entity && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "trash-2",
        reason: C.blocked(entity.write_context, kind, 'delete', result.meta.source),
        onClick: onDelete
      }, "\u5220\u9664"), kind === 'material' && /*#__PURE__*/React.createElement(Button, {
        icon: "square-pen",
        reason: C.blocked(entity.write_context, kind, 'update', result.meta.source) || (typeof onAdjustStock !== 'function' ? '调整库存尚未开通。' : ''),
        onClick: onAdjustStock
      }, "\u8C03\u6574\u5E93\u5B58"), /*#__PURE__*/React.createElement(Button, {
        icon: "square-pen",
        className: "btn primary",
        reason: C.blocked(entity.write_context, kind, 'update', result.meta.source),
        onClick: onEdit
      }, "\u7F16\u8F91")))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll wb-resource-detail"
    }, busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u8BE6\u60C5\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), error && /*#__PURE__*/React.createElement(Button, {
      onClick: onRetry
    }, "\u5237\u65B0"), entity && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-identity"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-code"
    }, entity.business_code), /*#__PURE__*/React.createElement("h3", null, entity.label)), kind !== 'op_type' && /*#__PURE__*/React.createElement(Status, {
      kind: kind,
      entity: entity
    })), /*#__PURE__*/React.createElement(CurrentFields, {
      kind: kind,
      entity: entity,
      includeRemark: false
    }), (kind === 'op_type' || (C.relations[kind] || []).length > 0) && /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-links fgrid"
    }, kind === 'op_type' && /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("label", null, "\u6392\u4EA7\u65B9\u5F0F"), /*#__PURE__*/React.createElement("span", null, entity.fields.category === 'internal' ? '工时（换型＋单件）' : entity.fields.category === 'external' ? '周期（天）' : '未明确')), (C.relations[kind] || []).map(field => /*#__PURE__*/React.createElement("div", {
      className: "field",
      key: field.key
    }, /*#__PURE__*/React.createElement("label", null, field.label), /*#__PURE__*/React.createElement(Relation, {
      entity: entity,
      field: field.key,
      onOpen: !field.catalog && onRelated ? ref => onRelated(field.kind, ref, field.category) : undefined
    }))), kind === 'operator' && /*#__PURE__*/React.createElement(LegacyFacts, {
      entity: entity
    })), /*#__PURE__*/React.createElement(Remark, {
      kind: kind,
      entity: entity
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: entity.issues
    }), kind === 'operator' && /*#__PURE__*/React.createElement(Button, {
      icon: "machine",
      reason: C.blocked(entity.write_context, kind, 'update', result.meta.source) || (typeof onMachinePermissions !== 'function' ? '设备关联编辑未连接。' : ''),
      onClick: onMachinePermissions
    }, "\u7F16\u8F91\u53EF\u64CD\u4F5C\u8BBE\u5907"), kind === 'op_type' && ['internal', 'external'].includes(entity.fields.category) && /*#__PURE__*/React.createElement(window.ResourceDetailRelations, {
      key: entity.ref + ':' + result.meta.snapshot_ref,
      adapter: adapter,
      entity: entity,
      onOpen: onRelated
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), /*#__PURE__*/React.createElement("p", {
      className: "wb-resource-read-time"
    }, "\u8BFB\u53D6\u65F6\u95F4\uFF1A", /*#__PURE__*/React.createElement("time", {
      dateTime: result.meta.as_of
    }, window.WorkbenchFormat.dateTime(result.meta.as_of))))));
  }
  ResourceForms.Detail = Detail;
  ResourceForms.Feedback = Feedback;
  window.ResourceForms = ResourceForms;
})();
