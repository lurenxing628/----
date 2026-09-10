(function () {
  'use strict';

  const fileKinds = ['material', 'op_type', 'machine', 'operator', 'supplier'];
  function fileAdapter(kind) {
    const adapter = window.APSResourceAPI.create(kind + '_files');
    adapter.command = (commandKind, action, ref, body, signal) => {
      if (![kind + '_import', kind + '_bulk'].includes(commandKind) || action !== 'confirm' || !body || !body.input || body.input.preview_ref !== ref) throw window.APSResourceContract.failure('确认操作与当前资源预览不一致。');
      return adapter.execute(commandKind === kind + '_import' ? 'imports/' + kind + '/confirm' : 'entities/' + kind + '/bulk-confirm', body, signal);
    };
    return adapter;
  }
  function recovery(adapters) {
    const pending = [{
      type: 'base',
      adapter: adapters.base
    }, ...fileKinds.map(kind => ({
      type: 'file',
      kind,
      adapter: adapters.files[kind]
    })), {
      type: 'catalog',
      adapter: adapters.catalog
    }, {
      type: 'calendar',
      adapter: adapters.calendar
    }, {
      type: 'process',
      adapter: adapters.process
    }].map(item => ({
      ...item,
      intent: typeof item.adapter.readPending === 'function' && item.adapter.readPending()
    })).find(item => item.intent);
    if (!pending) return null;
    const intent = pending.intent,
      kind = pending.kind || intent.kind;
    const node = pending.type === 'process' ? 'process' : pending.type === 'calendar' ? 'calendar' : kind === 'op_type' ? intent.category === 'external' ? 'op_ext' : 'op_int' : fileKinds.includes(kind) ? kind : 'material';
    const auxiliary = pending.type === 'file' ? {
      type: intent.kind === kind + '_bulk' ? 'bulk' : 'import',
      kind,
      request: {
        refs: [],
        scope: intent.category ? {
          category: intent.category
        } : {},
        recovery: true
      }
    } : pending.type === 'catalog' ? {
      type: 'catalog',
      kind,
      request: {
        recovery: true
      }
    } : null;
    return {
      node,
      auxiliary
    };
  }
  function ResourceLive({
    onNavigate,
    initialContext
  }) {
    const [auxiliary, setAuxiliary] = React.useState(null),
      [revision, setRevision] = React.useState(0);
    const [hostError, setHostError] = React.useState(null);
    const adapters = React.useMemo(() => {
      const base = window.APSResourceAPI.create(),
        calendar = window.APSResourceAPI.create('calendar');
      const files = Object.fromEntries(fileKinds.map(kind => [kind, fileAdapter(kind)])),
        catalog = window.APSResourceAPI.create('catalog');
      calendar.command = (kind, action, ref, body, signal) => {
        if (kind !== 'calendar' || !['upsert', 'delete', 'confirm'].includes(action)) throw window.APSResourceContract.failure('日历操作不正确。');
        return calendar.execute('calendar/' + (action === 'confirm' ? 'range/confirm' : action), body, signal);
      };
      const open = (type, kind, request) => {
        setHostError(null);
        setAuxiliary({
          type,
          kind,
          request
        });
        return {
          state: 'opened'
        };
      };
      base.supports = (name, kind) => name === 'openCatalog' ? ['machine_group', 'shift_profile'].includes(kind) : ['openImport', 'openExport', 'openBulk'].includes(name) && fileKinds.includes(kind);
      base.openImport = (kind, request) => open('import', kind, request);
      base.openExport = (kind, request) => open('export', kind, request);
      base.openBulk = (kind, request) => open('bulk', kind, request);
      base.openCatalog = (kind, request) => open('catalog', kind, request);
      return {
        base,
        calendar,
        files,
        catalog,
        process: window.APSProcessAPI.create(base)
      };
    }, []);
    const [boot] = React.useState(() => {
      const target = window.ResourceWorkspace.navigation(initialContext);
      try {
        return {
          target,
          recovery: recovery(adapters)
        };
      } catch (error) {
        return {
          target,
          error
        };
      }
    });
    const [deferred, setDeferred] = React.useState(() => !!boot.target.context && !!(boot.recovery || boot.error));
    const [initialNode, setInitialNode] = React.useState(() => boot.recovery ? boot.recovery.node : boot.target.node || 'material');
    const [navigationReady, setNavigationReady] = React.useState(false),
      [navigationKey, setNavigationKey] = React.useState(0);
    React.useEffect(() => {
      if (auxiliary) return;
      try {
        const pending = recovery(adapters);
        if (pending) {
          setInitialNode(pending.node);
          if (pending.auxiliary) setAuxiliary(pending.auxiliary);
        }
      } catch (error) {
        setHostError(error);
      }
    }, [adapters, auxiliary]);
    function continueNavigation() {
      try {
        const pending = recovery(adapters);
        if (pending) {
          setInitialNode(pending.node);
          if (!auxiliary && pending.auxiliary) setAuxiliary(pending.auxiliary);
          throw window.APSResourceContract.failure('仍有原请求待核实，请先处理并关闭原结果。');
        }
        if (auxiliary || !navigationReady) throw window.APSResourceContract.failure('请先关闭原结果或处理未保存草稿，再继续原导航。');
        setHostError(null);
        setDeferred(false);
        setInitialNode(boot.target.node);
        setNavigationKey(value => value + 1);
      } catch (error) {
        setHostError(error);
      }
    }
    function committed(result) {
      if (auxiliary && auxiliary.type === 'catalog') setAuxiliary(null);
      if (auxiliary && typeof auxiliary.request.onCommitted === 'function') auxiliary.request.onCommitted(result);else setRevision(value => value + 1);
    }
    function close() {
      const current = auxiliary;
      setAuxiliary(null);
      if (!current) return;
      if (typeof current.request.onClosed === 'function') current.request.onClosed();
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.ResourceControls.ErrorBox, {
      error: hostError || boot.target.error || boot.error
    }), deferred && /*#__PURE__*/React.createElement("div", {
      role: "status",
      className: "match-note",
      style: {
        display: 'block',
        margin: 12
      }
    }, /*#__PURE__*/React.createElement("p", null, "\u539F\u8BF7\u6C42\u4F18\u5148\u5904\u7406\uFF0C\u7CBE\u786E\u5BFC\u822A\u6682\u7F13\uFF1B\u5F85\u6838\u5B9E\u5199\u5165\u672A\u88AB\u8986\u76D6\u3002"), /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      icon: "arrow-right",
      onClick: continueNavigation
    }, "\u7EE7\u7EED\u539F\u5BFC\u822A")), /*#__PURE__*/React.createElement(ResourceWorkspace, {
      key: initialNode + ':' + navigationKey,
      adapter: adapters.base,
      onNavigate: onNavigate,
      initialNode: initialNode,
      externalRevision: revision,
      rememberEnabled: !auxiliary && !deferred && !hostError && !boot.error && !boot.target.error,
      initialContext: deferred || boot.error ? undefined : boot.target.context,
      onNavigationReady: setNavigationReady,
      renderPart: ({
        onRefresh,
        initialContext,
        rememberEnabled
      }) => /*#__PURE__*/React.createElement(window.ProcessWorkspace, {
        adapter: adapters.process,
        onCommitted: onRefresh,
        initialContext: initialContext,
        rememberEnabled: rememberEnabled,
        onNavigationReady: setNavigationReady
      }),
      renderCalendar: ({
        onCommitted,
        initialContext,
        rememberEnabled
      }) => /*#__PURE__*/React.createElement(window.ResourceCalendar, {
        adapter: adapters.calendar,
        onCommitted: onCommitted,
        initialContext: initialContext,
        rememberEnabled: rememberEnabled,
        onNavigationReady: setNavigationReady
      })
    }), auxiliary && (auxiliary.type === 'catalog' ? /*#__PURE__*/React.createElement(window.ResourceCatalog, {
      kind: auxiliary.kind,
      adapter: adapters.catalog,
      onClose: close,
      onCommitted: committed
    }) : auxiliary.kind === 'material' ? /*#__PURE__*/React.createElement(window.ResourceMaterialActions, {
      mode: auxiliary.type,
      request: auxiliary.request,
      adapter: adapters.files.material,
      onClose: close,
      onCommitted: committed
    }) : /*#__PURE__*/React.createElement(window.ResourceFileActions, {
      kind: auxiliary.kind,
      mode: auxiliary.type,
      request: auxiliary.request,
      adapter: adapters.files[auxiliary.kind],
      onClose: close,
      onCommitted: committed
    })));
  }
  window.ResourceLive = ResourceLive;
})();
