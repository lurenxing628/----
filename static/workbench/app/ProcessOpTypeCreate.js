(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession,
    {
      Button,
      Modal,
      ErrorBox
    } = window.ResourceControls;
  const scope = {
    query: '',
    page: 1,
    size: 20,
    sort: 'business_code',
    direction: 'asc'
  };
  function ProcessOpTypeCreate({
    adapter,
    onClose,
    onCommitted
  }) {
    const command = S.useCommand(adapter),
      [initialized, setInitialized] = React.useState(false),
      [context, setContext] = React.useState(null);
    const [review, setReview] = React.useState(null),
      [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null),
      [refresh, setRefresh] = React.useState({});
    const request = React.useRef(null),
      notified = React.useRef(null);
    React.useEffect(() => {
      if (command.reset()) setInitialized(true);
    }, []);
    React.useEffect(() => () => {
      if (request.current) request.current.abort();
    }, []);
    const list = S.useQuery(async signal => C.query(await adapter.list('op_type', scope, signal), 'list'), [adapter], initialized);
    React.useEffect(() => {
      if (list.result && !context) setContext(list.result);
    }, [list.result]);
    async function reload() {
      if (busy || command.locked) return;
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setError(null);
      try {
        const next = C.query(await adapter.list('op_type', scope, controller.signal), 'list');
        if (!controller.signal.aborted) setReview(next);
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure);
      } finally {
        if (!controller.signal.aborted) setBusy(false);
        if (request.current === controller) request.current = null;
      }
    }
    async function readSaved() {
      if (command.phase !== 'done' || request.current) return;
      const controller = new AbortController();
      request.current = controller;
      setRefresh({
        loading: true
      });
      try {
        if (!command.intent || command.intent.kind !== 'op_type' || command.intent.action !== 'create' || !['committed', 'unchanged'].includes(command.result.result)) throw C.failure(window.WorkbenchTerms.outcomes.unknown('新增工种'));
        if (notified.current !== command.result.receipt_ref) {
          notified.current = command.result.receipt_ref;
          onCommitted(command.result);
        }
        const ref = C.resultRef(command.result);
        if (typeof ref !== 'string' || !ref) throw C.failure('新增结果里没有工种编号，工序还没绑定。请刷新后核对。');
        const detail = C.query(await adapter.detail('op_type', ref, controller.signal), 'entity');
        if (detail.data.ref !== ref) throw C.failure('读到的工种详情和新增结果不一致，请刷新后核对。');
        await adapter.list('op_type', scope, controller.signal);
        if (!controller.signal.aborted) setRefresh({
          done: true,
          detail
        });
      } catch (failure) {
        if (!controller.signal.aborted) setRefresh({
          error: failure
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    React.useEffect(() => {
      if (initialized && command.phase === 'done') readSaved();
    }, [initialized, command.phase, command.result && command.result.receipt_ref]);
    function close() {
      if (!command.locked && !busy && !refresh.loading && command.reset()) onClose();
    }
    if (!context) return /*#__PURE__*/React.createElement(Modal, {
      title: "\u65B0\u589E\u5DE5\u79CD",
      icon: "plus",
      onClose: close,
      locked: command.locked || busy,
      footer: /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: command.locked || busy
      }, "\u53D6\u6D88")
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: list.error
    }), list.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5DE5\u79CD\u5EFA\u6863\u8D44\u6599\u2026"), list.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: list.reload
    }, "\u5237\u65B0\u8D44\u6599"), !initialized && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u53E6\u4E00\u4E2A\u64CD\u4F5C\u8FD8\u6CA1\u5904\u7406\u5B8C\uFF0C\u8BF7\u5148\u67E5\u8BE2\u4E0A\u6B21\u7ED3\u679C\u3002"), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }))));
    return /*#__PURE__*/React.createElement(window.ResourceForms, {
      adapter: adapter,
      kind: "op_type",
      action: "create",
      writeContext: review ? null : context.data.create_context,
      source: context.meta.source,
      command: command,
      onClose: close,
      onReloadContext: reload,
      contextBusy: busy || refresh.loading,
      contextError: error,
      contextReview: review,
      onAcceptContext: () => {
        setContext(review);
        setReview(null);
        setError(null);
      },
      refreshState: refresh,
      onRefresh: readSaved
    });
  }
  window.ProcessOpTypeCreate = ProcessOpTypeCreate;
})();
