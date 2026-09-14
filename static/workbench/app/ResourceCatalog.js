(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession,
    M = window.APSResourceCatalogModel;
  const {
    Modal,
    Button,
    ErrorBox,
    Issues,
    focusFirstInvalid
  } = window.ResourceControls;
  const {
    EmptyState,
    Pager
  } = window.WorkbenchListControls;
  const Editor = window.ResourceCatalogEditor;
  const initialScope = () => ({
    query: '',
    status: '',
    page: 1,
    size: 20,
    sort: 'business_code',
    direction: 'asc'
  });
  function CatalogList({
    kind,
    list,
    scope,
    setScope,
    onOpen,
    disabled
  }) {
    const [search, setSearch] = React.useState(''),
      data = list.result && list.result.data;
    function filter(patch) {
      setScope(current => ({
        ...current,
        ...patch,
        page: 1,
        snapshot_ref: undefined
      }));
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("form", {
      className: "toolbar rc-toolbar",
      onSubmit: event => {
        event.preventDefault();
        filter({
          query: search
        });
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "search"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u7F16\u53F7\u6216\u540D\u79F0",
      value: search,
      disabled: disabled,
      onChange: event => setSearch(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      "aria-label": "\u641C\u7D22",
      disabled: disabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u72B6\u6001\u7B5B\u9009",
      value: scope.status,
      disabled: disabled,
      onChange: event => filter({
        status: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u72B6\u6001"), /*#__PURE__*/React.createElement("option", {
      value: "active"
    }, "\u542F\u7528"), /*#__PURE__*/React.createElement("option", {
      value: "inactive"
    }, "\u505C\u7528"), /*#__PURE__*/React.createElement("option", {
      value: "unknown"
    }, "\u65E7\u72B6\u6001\u672A\u77E5"))), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u5217\u8868",
      disabled: disabled,
      busy: list.loading,
      onClick: () => {
        filter({});
        list.reload();
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      className: "btn primary",
      disabled: disabled,
      reason: C.blocked(data && data.create_context, kind, 'create', list.result && list.result.meta.source),
      onClick: () => onOpen('create')
    }, "\u65B0\u589E", M.names[kind])), /*#__PURE__*/React.createElement(ErrorBox, {
      error: list.error
    }), list.loading && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5217\u8868"
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: list.result.warnings
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame rc-list-scroll",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table rc-list"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, M.names[kind], "\u5217\u8868"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u7F16\u53F7 / \u540D\u79F0"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, kind === 'machine_group' ? '关联设备' : '关联人员'), kind === 'shift_profile' && /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8F6E\u6362\u5929\u6570"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.entities.map(entity => /*#__PURE__*/React.createElement("tr", {
      key: entity.ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "rc-wrap wb-col-key"
    }, /*#__PURE__*/React.createElement("b", null, entity.business_code), /*#__PURE__*/React.createElement("div", null, entity.label)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + (entity.status === 'active' ? 'ok' : entity.status === 'inactive' ? 'off' : 'warn')
    }, /*#__PURE__*/React.createElement("span", {
      className: "dot"
    }), entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '旧状态未知')), /*#__PURE__*/React.createElement("td", null, M.memberCount(kind, entity) === null ? '未读取' : M.memberCount(kind, entity)), kind === 'shift_profile' && /*#__PURE__*/React.createElement("td", null, entity.fields.cycle_days), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rowact"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "square-pen",
      "aria-label": '编辑 ' + entity.business_code,
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: C.blocked(entity.write_context, kind, 'update', list.result.meta.source),
      onClick: () => onOpen('update', entity.ref)
    }), /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "minus",
      "aria-label": '删除 ' + entity.business_code,
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: C.blocked(entity.write_context, kind, 'delete', list.result.meta.source),
      onClick: () => onOpen('delete', entity.ref)
    })))))))), !data.entities.length && /*#__PURE__*/React.createElement(EmptyState, {
      kind: scope.query || scope.status ? 'filtered' : 'empty',
      title: "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u8BB0\u5F55",
      hint: "\u53EF\u6E05\u9664\u641C\u7D22\u548C\u72B6\u6001\u7B5B\u9009\u540E\u67E5\u770B\u5168\u90E8\u8BB0\u5F55\u3002",
      action: scope.query || scope.status ? /*#__PURE__*/React.createElement(Button, {
        disabled: disabled,
        onClick: () => {
          setSearch('');
          filter({
            query: '',
            status: ''
          });
        }
      }, "\u6E05\u9664\u7B5B\u9009") : undefined
    }), /*#__PURE__*/React.createElement(Pager, {
      page: data.page,
      sizes: [20],
      unit: "\u6761",
      label: "\u5217\u8868",
      disabled: disabled || list.loading,
      onPage: page => setScope({
        ...scope,
        page,
        snapshot_ref: list.result.meta.snapshot_ref
      })
    })));
  }
  function ResourceCatalog({
    kind,
    adapter,
    onClose,
    onCommitted
  }) {
    const [scope, setScope] = React.useState(initialScope),
      [editor, setEditor] = React.useState(null);
    const [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null),
      [review, setReview] = React.useState(null);
    const [lastReceipt, setLastReceipt] = React.useState(null),
      [needsReview, setNeedsReview] = React.useState(false);
    const command = S.useCommand(adapter),
      generation = React.useRef(0),
      alive = React.useRef(true),
      root = React.useRef(null),
      formId = React.useId();
    React.useEffect(() => {
      alive.current = true;
      return () => {
        alive.current = false;
        generation.current++;
      };
    }, []);
    const validKind = Object.prototype.hasOwnProperty.call(M.names, kind),
      done = command.phase === 'done';
    const locked = command.locked || busy,
      showList = !editor && !command.locked && !done;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      owner: 'resource-catalog-' + formId,
      dirty: !!(editor && editor.action !== 'delete' && !done && JSON.stringify(editor.draft) !== JSON.stringify(M.draft(editor.base))),
      locked: command.locked,
      message: (M.names[kind] || '基础资料') + '有尚未保存的填写内容。'
    });
    React.useEffect(() => {
      if (error || command.error) focusFirstInvalid(root.current);
    }, [error, command.error]);
    const list = S.useQuery(async signal => C.query(await adapter.list(kind, scope, signal), 'list'), [adapter, kind, scope], validKind && showList);
    React.useEffect(() => {
      const selector = done ? '.modal-f button:not(:disabled)' : 'input:not(:disabled):not([readonly]),select:not(:disabled)';
      const target = root.current && root.current.querySelector(selector);
      if (target) target.focus();
    }, [editor && editor.action, editor && editor.ref, done, showList]);
    React.useEffect(() => {
      if (done) setLastReceipt(command.result);
      if (command.phase === 'rejected') {
        const code = command.error && command.error.error && command.error.error.code;
        if (['stale_write', 'stale_context', 'context_expired'].includes(code)) setNeedsReview(true);
      }
    }, [command.phase, command.result, command.error]);
    async function load(action, ref, reviewing = false) {
      if (locked) return;
      const ticket = ++generation.current;
      setBusy(true);
      setError(null);
      try {
        const result = ref ? C.query(await adapter.detail(kind, ref, new AbortController().signal), 'entity') : C.query(await adapter.list(kind, {
          ...scope,
          page: 1,
          snapshot_ref: undefined
        }, new AbortController().signal), 'list');
        if (ref && result.data.ref !== ref) throw C.failure('读到的记录与所选记录不一致，请刷新后重试。');
        if (!alive.current || ticket !== generation.current) return;
        if (reviewing) setReview(result);else setEditor({
          action,
          ref,
          base: ref ? result.data : null,
          draft: M.draft(ref ? result.data : null),
          context: ref ? result.data.write_context : result.data.create_context,
          source: result.meta.source
        });
      } catch (failure) {
        if (alive.current && ticket === generation.current) setError(failure);
      } finally {
        if (alive.current && ticket === generation.current) setBusy(false);
      }
    }
    function open(action, ref = null) {
      if (locked || !command.reset()) return;
      setReview(null);
      setNeedsReview(false);
      load(action, ref);
    }
    function finish() {
      const receipt = done ? command.result : lastReceipt;
      if (receipt && onCommitted) onCommitted(receipt);else onClose();
    }
    function back(target) {
      if (locked || !command.reset()) return;
      setEditor(null);
      setReview(null);
      setError(null);
      setNeedsReview(false);
      if (target === 'close') finish();else setScope(current => ({
        ...current,
        page: 1,
        snapshot_ref: undefined
      }));
    }
    async function requestClose(target = 'close', options = {}) {
      if (locked) return;
      if (!(options.guardConfirmed && options.guardOwner === guardOwner) && !(await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) return;
      back(target);
    }
    function change(key, value) {
      setEditor(current => ({
        ...current,
        draft: {
          ...current.draft,
          [key]: value
        }
      }));
      setError(null);
    }
    function acknowledge(value) {
      setEditor(current => ({
        ...current,
        acknowledged: value
      }));
    }
    function acceptReview() {
      if (!review || locked || !command.reset()) return;
      // Refresh guards only. The original baseline and draft remain unchanged, so unseen fields are not overwritten.
      setEditor(current => ({
        ...current,
        context: current.ref ? review.data.write_context : review.data.create_context,
        source: review.meta.source
      }));
      setReview(null);
      setNeedsReview(false);
      setError(null);
    }
    const reason = editor ? needsReview ? window.WorkbenchTerms.outcomes.stale : review ? '请先核对最新资料。' : C.blocked(editor.context, kind, editor.action, editor.source) : '';
    // Deleting basic data needs the checkbox confirmation, so the unchecked state becomes the confirm button's own reason.
    const confirmReason = editor && editor.action === 'delete' && !editor.acknowledged ? '请先勾选已核对要删除的资料及其关联关系。' : '';
    async function submit(event) {
      event.preventDefault();
      if (locked || done || !editor || reason || confirmReason) return;
      try {
        const input = editor.action === 'delete' ? {} : M.input(kind, editor.draft, editor.base);
        setError(null);
        await command.submit(kind, editor.action, editor.ref, editor.context, input);
      } catch (failure) {
        setError(failure);
      }
    }
    const title = (editor && !done ? {
      create: '新增',
      update: '编辑',
      delete: '删除'
    }[editor.action] : '维护') + (M.names[kind] || '基础资料');
    return /*#__PURE__*/React.createElement("div", {
      className: "plana resource-catalog",
      "data-resource-catalog": kind,
      ref: root
    }, /*#__PURE__*/React.createElement(Modal, {
      title: title,
      icon: kind === 'shift_profile' ? 'clock-3' : 'folder-open',
      locked: locked,
      guardOwner: guardOwner,
      onClose: options => requestClose('close', options),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => requestClose(),
        reason: locked ? '操作结果还没确认，请保留当前页面。' : ''
      }, lastReceipt || done ? '完成并返回' : '关闭'), editor && !done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => requestClose('list'),
        disabled: locked
      }, "\u8FD4\u56DE\u5217\u8868"), /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: formId,
        className: "btn primary",
        icon: editor.action === 'delete' ? 'minus' : 'check',
        reason: reason || confirmReason,
        disabled: locked
      }, editor.action === 'delete' ? '确认删除' : '保存')), done && /*#__PURE__*/React.createElement(Button, {
        icon: "folder-open",
        onClick: () => back('list')
      }, "\u7EE7\u7EED\u7EF4\u62A4"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form scroll"
    }, !validKind && /*#__PURE__*/React.createElement(ErrorBox, {
      error: C.failure('不支持这类基础资料。')
    }), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u8D44\u6599\u2026"), validKind && showList && /*#__PURE__*/React.createElement(CatalogList, {
      kind: kind,
      list: list,
      scope: scope,
      setScope: setScope,
      onOpen: open,
      disabled: locked
    }), editor && !done && /*#__PURE__*/React.createElement("form", {
      id: formId,
      onSubmit: submit,
      noValidate: true
    }, /*#__PURE__*/React.createElement(Editor, {
      kind: kind,
      editor: editor,
      error: error || command.error,
      disabled: locked,
      onChange: change,
      onValidationError: setError,
      onAcknowledge: acknowledge
    })), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: editor && !done && editor.action !== 'delete' ? Editor.fieldPaths : []
    }), /*#__PURE__*/React.createElement(ResourceForms.Feedback, {
      command: command,
      excludePaths: editor && !done && editor.action !== 'delete' ? Editor.fieldPaths : []
    }), command.intent && command.locked && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '操作编号': command.intent.request_key
      }
    }), editor && !done && !command.locked && /*#__PURE__*/React.createElement("div", {
      className: "rc-pattern"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: busy,
      onClick: () => {
        setReview(null);
        load(editor.action, editor.ref, true);
      }
    }, "\u5237\u65B0\u6700\u65B0\u8D44\u6599"), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), review && /*#__PURE__*/React.createElement("div", {
      className: "match-note rc-note"
    }, /*#__PURE__*/React.createElement("p", null, "\u6700\u65B0\u8D44\u6599\u5DF2\u8BFB\u53D6\uFF0C\u5DF2\u586B\u5199\u7684\u5185\u5BB9\u4FDD\u6301\u4E0D\u53D8\u3002\u8BF7\u6838\u5BF9\u540E\u7EE7\u7EED\u7F16\u8F91\u3002"), editor.ref ? /*#__PURE__*/React.createElement(Editor.Facts, {
      kind: kind,
      entity: review.data
    }) : /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u5171\u6709 ", review.data.page.total, " \u6761\u8BB0\u5F55\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      disabled: locked,
      onClick: acceptReview
    }, "\u5DF2\u6838\u5BF9\uFF0C\u7EE7\u7EED\u7F16\u8F91"))))));
  }
  window.ResourceCatalog = ResourceCatalog;
})();
