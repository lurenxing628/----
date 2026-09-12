(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    A = window.APSProcessActions,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  function ProcessCollectionActions({
    adapter,
    request,
    onClose,
    onCommitted,
    onOpen,
    disabled = false
  }) {
    const [original] = React.useState(() => ({
      ...request,
      refs: request.refs && request.refs.slice(),
      scope: A.scope(request.scope)
    }));
    const [draft, setDraft] = React.useState({
      business_code: '',
      label: '',
      route_raw: '',
      remark: ''
    });
    const [error, setError] = React.useState(null),
      [discard, setDiscard] = React.useState(false),
      [job, setJob] = React.useState(null);
    const [ack, setAck] = React.useState(false),
      [now, setNow] = React.useState(Date.now()),
      [opening, setOpening] = React.useState(false);
    const [context, setContext] = React.useState(original),
      [review, setReview] = React.useState(null),
      [reading, setReading] = React.useState(false);
    const command = S.useCommand(adapter),
      notified = React.useRef(null),
      controller = React.useRef(null);
    const create = original.mode === 'create',
      recovery = original.recovery === true;
    let saved = null,
      receiptError = null;
    if (command.phase === 'done') {
      try {
        saved = A.receipt(command.result, command.intent, !create && !recovery ? original.refs : undefined);
      } catch (failure) {
        receiptError = failure;
      }
    }
    const visible = receiptError ? {
      ...command,
      phase: 'pending',
      locked: true,
      error: receiptError
    } : command;
    const done = !!saved,
      dirty = !done && Object.values(draft).some(value => value !== ''),
      locked = visible.locked || opening || reading;
    const preview = S.useQuery(async signal => A.deletePreview(await adapter.bulkPreview(A.deleteBody(original), signal), original), [adapter, job], !!job);
    const result = preview.result,
      data = result && result.data;
    React.useEffect(() => () => {
      if (controller.current) controller.current.abort();
    }, []);
    window.WorkbenchGuards.useDirtyGuard({
      dirty,
      locked: visible.locked,
      message: create ? '新增零件的图号、名称或路线填写尚未保存。' : '零件原请求尚未核实。'
    });
    React.useEffect(() => {
      if (!done || notified.current === command.result.receipt_ref) return;
      notified.current = command.result.receipt_ref;
      if (onCommitted) onCommitted(command.result);
    }, [done, command.result, onCommitted]);
    React.useEffect(() => {
      if (!data) return undefined;
      const timer = setTimeout(() => setNow(Date.now()), Math.max(0, Date.parse(data.expires_at) - Date.now() + 1));
      return () => clearTimeout(timer);
    }, [data]);
    function close(force = false) {
      if (locked) return;
      if (dirty && !force) {
        setDiscard(true);
        return;
      }
      if (command.reset()) onClose();
    }
    function preflight() {
      if (disabled || locked || done || recovery || !command.reset()) return;
      setError(null);
      setAck(false);
      try {
        if (typeof adapter.bulkPreview !== 'function') throw C.failure('零件删除预检尚未接入。');
        A.deleteBody(original);
        setJob({});
        setNow(Date.now());
      } catch (failure) {
        setError(failure);
      }
    }
    async function readCurrent() {
      if (locked || done || controller.current) return;
      const abort = new AbortController();
      controller.current = abort;
      setReading(true);
      setError(null);
      try {
        const scope = {
          ...original.scope,
          page: 1,
          size: original.page_size || 20
        };
        const value = P.list(await adapter.list('part', scope, abort.signal), scope);
        if (!abort.signal.aborted) setReview({
          ...context,
          create_context: value.data.create_context,
          source: value.meta.source
        });
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure);
      } finally {
        if (controller.current === abort) {
          controller.current = null;
          if (!abort.signal.aborted) setReading(false);
        }
      }
    }
    async function openCreated() {
      if (!saved || locked || controller.current || typeof onOpen !== 'function') return;
      const abort = new AbortController();
      controller.current = abort;
      setOpening(true);
      setError(null);
      try {
        P.detail(await adapter.detail('part', saved.entity_ref, abort.signal), saved.entity_ref);
        if (!abort.signal.aborted && command.reset()) onOpen(saved.entity_ref);
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure);
      } finally {
        if (controller.current === abort) {
          controller.current = null;
          if (!abort.signal.aborted) setOpening(false);
        }
      }
    }
    let reason = create ? A.createReason(context.create_context, context.source) : A.blocked(result, original.source, 'process_bulk.confirm');
    if (!create && data && now >= Date.parse(data.expires_at)) reason = '预检已过期，请重新预检。';
    if (!create && !reason && !ack) reason = '请先核对并勾选完整删除范围。';
    if (review) reason = '请先核对新读取的资料。';
    if (command.phase === 'rejected') reason = create ? '本次未保存，请重新读取资料后再试。' : '本次未删除，请重新预检。';
    function confirm() {
      if (disabled || locked || done || reason || recovery) return;
      setError(null);
      try {
        if (create) command.submit('process', 'create', null, context.create_context, A.createInput(draft));else command.submit('process_bulk', 'confirm', data.preview_ref, data.write_context, {
          preview_ref: data.preview_ref
        });
      } catch (failure) {
        setError(failure);
      }
    }
    return /*#__PURE__*/React.createElement("div", {
      className: 'plana rm-actions' + (data ? ' rm-wide' : '')
    }, /*#__PURE__*/React.createElement(window.ResourceMaterialPreview.Styles, null), /*#__PURE__*/React.createElement(Modal, {
      title: create ? '新增零件' : original.refs && original.refs.length === 1 ? '删除零件' : '批量删除零件',
      icon: create ? 'plus' : 'minus',
      locked: locked,
      suspended: discard,
      onClose: () => close(),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: locked,
        onClick: () => close()
      }, done ? '完成' : '取消'), !create && !recovery && !done && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        disabled: disabled || locked,
        busy: !!job && preview.loading,
        onClick: preflight
      }, job ? '重新预检' : '检查删除范围'), !recovery && !done && (create || data) && /*#__PURE__*/React.createElement(Button, {
        icon: create ? 'plus' : 'minus',
        className: 'btn ' + (create ? 'primary' : 'danger'),
        disabled: disabled || locked || preview.loading,
        reason: reason,
        onClick: confirm
      }, create ? '保存零件' : '确认删除'), done && create && /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        className: "btn primary",
        busy: opening,
        disabled: disabled || locked,
        onClick: openCreated
      }, "\u6253\u5F00\u5DE5\u827A\u8BE6\u60C5"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll rm-body"
    }, create && !recovery && !done && /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, [['business_code', '图号'], ['label', '零件名称'], ['route_raw', '路线文字（选填）'], ['remark', '备注（选填）']].map(([key, label]) => /*#__PURE__*/React.createElement("label", {
      className: 'field' + (['route_raw', 'remark'].includes(key) ? ' full' : ''),
      key: key
    }, label, ['route_raw', 'remark'].includes(key) ? /*#__PURE__*/React.createElement("textarea", {
      "aria-label": label,
      rows: key === 'route_raw' ? 4 : 2,
      disabled: disabled || locked,
      value: draft[key],
      onChange: event => setDraft({
        ...draft,
        [key]: event.target.value
      })
    }) : /*#__PURE__*/React.createElement("input", {
      "aria-label": label,
      required: true,
      disabled: disabled || locked,
      value: draft[key],
      onChange: event => setDraft({
        ...draft,
        [key]: event.target.value
      })
    })))), create && !done && !recovery && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u8FD9\u91CC\u53EA\u767B\u8BB0\u96F6\u4EF6\u548C\u8DEF\u7EBF\u539F\u6587\uFF0C\u4E0D\u4F1A\u81EA\u52A8\u786E\u8BA4\u5DE5\u827A\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: disabled || locked,
      onClick: readCurrent
    }, "\u91CD\u8BFB\u8D44\u6599\u5E76\u4FDD\u7559\u586B\u5199\u5185\u5BB9")), review && /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u5DF2\u8BFB\u53D6\u6700\u65B0\u8D44\u6599\uFF0C\u586B\u5199\u5185\u5BB9\u672A\u6539\u3002\u8BF7\u6838\u5BF9\u540E\u7EE7\u7EED\u4FDD\u5B58\u3002"), /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: () => {
        if (command.reset()) {
          setContext(review);
          setReview(null);
        }
      }
    }, "\u5DF2\u6838\u5BF9\uFF0C\u7EE7\u7EED\u7F16\u8F91")), !create && !recovery && /*#__PURE__*/React.createElement("p", null, "\u672C\u6B21\u9009\u4E2D ", original.refs.length, " \u4E2A\u96F6\u4EF6\uFF0C\u5305\u542B\u5176\u4ED6\u9875\u7684\u9009\u62E9\uFF1B\u5DF2\u88AB\u6279\u6B21\u4F7F\u7528\u7684\u96F6\u4EF6\u4E0D\u80FD\u5220\u9664\u3002\u6709\u4E00\u9879\u4E0D\u80FD\u5220\uFF0C\u672C\u6B21\u5C31\u4E00\u9879\u4E5F\u4E0D\u5220\u3002"), recovery && /*#__PURE__*/React.createElement("p", null, "\u6B63\u5728\u6838\u5B9E\u539F\u8BF7\u6C42\uFF1B\u4E0D\u4F1A\u6309\u5F53\u524D\u5217\u8868\u6216\u540C\u56FE\u53F7\u7684\u65B0\u96F6\u4EF6\u91CD\u65B0\u63D0\u4EA4\u3002"), !!job && preview.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u68C0\u67E5\u5B8C\u6574\u5220\u9664\u8303\u56F4\uFF0C\u5C1A\u672A\u5220\u9664\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: preview.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.ProcessActionPreview, {
      data: data
    }), !done && /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: ack,
      disabled: disabled || locked,
      onChange: event => setAck(event.target.checked)
    }), "\u5DF2\u6838\u5BF9\u5168\u90E8\u660E\u7EC6\uFF0C\u786E\u8BA4\u5220\u9664\u8FD9\u4E9B\u96F6\u4EF6\u3002")), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: visible
    }), done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, create ? '零件已登记，工艺仍待确认。打开详情前会重读这条原零件。' : '原请求已确认删除 ' + saved.deleted_count + ' 个零件。'))), discard && /*#__PURE__*/React.createElement(Modal, {
      title: "\u653E\u5F03\u65B0\u589E\u96F6\u4EF6\u7684\u586B\u5199\u5185\u5BB9\uFF1F",
      icon: "square-pen",
      onClose: () => setDiscard(false),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => setDiscard(false)
      }, "\u7EE7\u7EED\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
        className: "btn danger",
        onClick: () => close(true)
      }, "\u653E\u5F03\u586B\u5199\u5E76\u5173\u95ED"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, "\u672A\u4FDD\u5B58\u7684\u5185\u5BB9\u5C06\u88AB\u4E22\u5F03\u3002")));
  }
  window.ProcessCollectionActions = ProcessCollectionActions;
})();
