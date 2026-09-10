(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession,
    M = window.APSResourceCatalogModel;
  const {
    Modal,
    Button,
    ErrorBox,
    Issues
  } = window.ResourceControls;
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
      "aria-label": "\u641C\u7D22\u76EE\u5F55\u7F16\u53F7\u6216\u540D\u79F0",
      value: search,
      disabled: disabled,
      onChange: event => setSearch(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      "aria-label": "\u641C\u7D22\u76EE\u5F55",
      disabled: disabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u5F55\u72B6\u6001\u7B5B\u9009",
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
      "aria-label": "\u5237\u65B0\u76EE\u5F55",
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
    }), list.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u76EE\u5F55\u2026"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: list.result.warnings
    }), /*#__PURE__*/React.createElement("table", {
      className: "tbl rc-list"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u7F16\u53F7 / \u540D\u79F0"), /*#__PURE__*/React.createElement("th", null, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, kind === 'machine_group' ? '关联设备' : '关联人员'), kind === 'shift_profile' && /*#__PURE__*/React.createElement("th", null, "\u8F6E\u6362\u5929\u6570"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.entities.map(entity => /*#__PURE__*/React.createElement("tr", {
      key: entity.ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "rc-wrap"
    }, /*#__PURE__*/React.createElement("b", null, entity.business_code), /*#__PURE__*/React.createElement("div", null, entity.label)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + (entity.status === 'active' ? 'ok' : entity.status === 'inactive' ? 'off' : 'warn')
    }, /*#__PURE__*/React.createElement("span", {
      className: "dot"
    }), entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '未知')), /*#__PURE__*/React.createElement("td", null, M.memberCount(kind, entity) === null ? '未读取' : M.memberCount(kind, entity)), kind === 'shift_profile' && /*#__PURE__*/React.createElement("td", null, entity.fields.cycle_days), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
      className: "rowact"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "square-pen",
      "aria-label": '编辑 ' + entity.business_code,
      disabled: disabled,
      reason: C.blocked(entity.write_context, kind, 'update', list.result.meta.source),
      onClick: () => onOpen('update', entity.ref)
    }), /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "minus",
      "aria-label": '删除 ' + entity.business_code,
      disabled: disabled,
      reason: C.blocked(entity.write_context, kind, 'delete', list.result.meta.source),
      onClick: () => onOpen('delete', entity.ref)
    }))))), !data.entities.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: kind === 'shift_profile' ? 5 : 4,
      className: "muted"
    }, "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u76EE\u5F55\u8BB0\u5F55\u3002")))), /*#__PURE__*/React.createElement("div", {
      className: "pager"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", data.page.total, " \u6761 \xB7 \u7B2C ", data.page.number, " / ", Math.max(1, data.page.pages), " \u9875"), /*#__PURE__*/React.createElement("span", {
      className: "grow"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u76EE\u5F55\u4E0A\u4E00\u9875",
      disabled: disabled || scope.page <= 1,
      onClick: () => setScope({
        ...scope,
        page: scope.page - 1,
        snapshot_ref: list.result.meta.snapshot_ref
      })
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u76EE\u5F55\u4E0B\u4E00\u9875",
      disabled: disabled || scope.page >= data.page.pages,
      onClick: () => setScope({
        ...scope,
        page: scope.page + 1,
        snapshot_ref: list.result.meta.snapshot_ref
      })
    }))));
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
    const [discard, setDiscard] = React.useState(null),
      [lastReceipt, setLastReceipt] = React.useState(null),
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
        if (ref && result.data.ref !== ref) throw C.failure('读取对象与所选目录不一致。');
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
      setDiscard(null);
      setNeedsReview(false);
      if (target === 'close') finish();else setScope(current => ({
        ...current,
        page: 1,
        snapshot_ref: undefined
      }));
    }
    function requestClose(target = 'close') {
      if (locked) return;
      if (editor && editor.action !== 'delete' && !done && JSON.stringify(editor.draft) !== JSON.stringify(M.draft(editor.base))) {
        setDiscard(target);
        return;
      }
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
    const reason = editor ? needsReview ? '资料已变化，请重新读取并核对。' : review ? '请先核对最新资料。' : C.blocked(editor.context, kind, editor.action, editor.source) : '';
    async function submit(event) {
      event.preventDefault();
      if (locked || done || !editor || reason || discard) return;
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
    }[editor.action] : '维护') + (M.names[kind] || '资源目录');
    return /*#__PURE__*/React.createElement("div", {
      className: "plana resource-catalog",
      "data-resource-catalog": kind,
      ref: root
    }, /*#__PURE__*/React.createElement("style", null, `
        .resource-catalog .modal.lg { width:min(860px,100%); }
        .resource-catalog .modal-b.scroll { max-height:min(65vh,690px); padding-bottom:18px; }
        .resource-catalog .rc-toolbar { flex-wrap:wrap; gap:8px; margin-bottom:14px; }
        .resource-catalog .rc-toolbar .search { flex:1 1 180px; min-width:120px; max-width:270px; }
        .resource-catalog .rc-toolbar .field { min-width:130px; }
        .resource-catalog .rc-toolbar .field select { height:32px; }
        .resource-catalog table.tbl { min-width:0; width:100%; table-layout:fixed; }
        .resource-catalog .rc-list th:first-child { width:40%; }
        .resource-catalog .rc-list th:last-child { width:112px; }
        .resource-catalog .rc-wrap { overflow-wrap:anywhere; }
        .resource-catalog .rc-error { color:var(--ui-danger-text); }
        .resource-catalog .rc-pattern { margin-top:20px; border-top:1px solid var(--ui-border); padding-top:14px; }
        .resource-catalog .rc-section-head { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
        .resource-catalog .rc-section-head h3 { font-size:14px; margin:0; flex:1; }
        .resource-catalog .rc-pattern-table th { width:22%; }
        .resource-catalog .rc-pattern-table th:first-child { width:12%; }
        .resource-catalog .rc-pattern-table th:last-child { width:18%; }
        .resource-catalog .rc-pattern-table td.field { display:table-cell; }
        .resource-catalog .rc-pattern-table .field input, .resource-catalog .rc-pattern-table select { padding-left:6px; padding-right:6px; min-width:0; height:32px; }
        .resource-catalog .rc-pattern-table select { padding-right:24px; }
        .resource-catalog .rc-note { display:block; margin-top:12px; }
        .resource-catalog .rc-facts { overflow-wrap:anywhere; }
        .resource-catalog .rc-list td, .resource-catalog .rc-pattern-table td { vertical-align:middle; }
        .resource-catalog .rc-list .rowact { gap:8px; }
        .resource-catalog .rc-list .mini { width:30px; height:30px; padding:0; flex:none; }
        .resource-catalog .rc-list .mini svg { width:18px; height:18px; flex:none; }
        .resource-catalog .rc-pattern-table td { padding:8px 6px; }
      `), /*#__PURE__*/React.createElement(Modal, {
      title: title,
      icon: kind === 'shift_profile' ? 'clock-3' : 'folder-open',
      locked: locked,
      onClose: () => requestClose(),
      footer: discard ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => setDiscard(null)
      }, "\u7EE7\u7EED\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
        icon: "x",
        onClick: () => back(discard)
      }, "\u653E\u5F03\u4FEE\u6539")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => requestClose(),
        reason: locked ? '操作尚未核实，请保留当前页面。' : ''
      }, lastReceipt || done ? '完成并返回' : '关闭'), editor && !done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => requestClose('list'),
        disabled: locked
      }, "\u8FD4\u56DE\u76EE\u5F55"), /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: formId,
        className: "btn primary",
        icon: editor.action === 'delete' ? 'minus' : 'check',
        reason: reason,
        disabled: locked
      }, editor.action === 'delete' ? '确认删除' : '保存')), done && /*#__PURE__*/React.createElement(Button, {
        icon: "folder-open",
        onClick: () => back('list')
      }, "\u7EE7\u7EED\u7EF4\u62A4"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form scroll"
    }, !validKind && /*#__PURE__*/React.createElement(ErrorBox, {
      error: C.failure('不支持此类资源目录。')
    }), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u76EE\u5F55\u8D44\u6599\u2026"), validKind && showList && /*#__PURE__*/React.createElement(CatalogList, {
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
      disabled: locked || !!discard,
      onChange: change
    })), discard && /*#__PURE__*/React.createElement("div", {
      className: "match-note rc-note",
      role: "alert"
    }, "\u6709\u5C1A\u672A\u4FDD\u5B58\u7684\u4FEE\u6539\u3002\u786E\u8BA4\u653E\u5F03\u540E\u624D\u4F1A\u79BB\u5F00\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(ResourceForms.Feedback, {
      command: command
    }), command.intent && command.locked && /*#__PURE__*/React.createElement("p", {
      className: "rc-wrap muted"
    }, "\u539F\u8BF7\u6C42\uFF1A", command.intent.request_key), editor && !done && !command.locked && /*#__PURE__*/React.createElement("div", {
      className: "rc-pattern"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: busy || !!discard,
      onClick: () => {
        setReview(null);
        load(editor.action, editor.ref, true);
      }
    }, "\u91CD\u65B0\u8BFB\u53D6\u6700\u65B0\u8D44\u6599"), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), review && /*#__PURE__*/React.createElement("div", {
      className: "match-note rc-note"
    }, /*#__PURE__*/React.createElement("p", null, "\u6700\u65B0\u8D44\u6599\u5DF2\u8BFB\u53D6\uFF0C\u5DF2\u586B\u5199\u7684\u5185\u5BB9\u4FDD\u6301\u4E0D\u53D8\u3002\u8BF7\u6838\u5BF9\u540E\u7EE7\u7EED\u7F16\u8F91\u3002"), editor.ref ? /*#__PURE__*/React.createElement(Editor.Facts, {
      kind: kind,
      entity: review.data
    }) : /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u76EE\u5F55\u5171\u6709 ", review.data.page.total, " \u6761\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      disabled: locked || !!discard,
      onClick: acceptReview
    }, "\u5DF2\u6838\u5BF9\uFF0C\u7EE7\u7EED\u7F16\u8F91"))))));
  }
  window.ResourceCatalog = ResourceCatalog;
})();
