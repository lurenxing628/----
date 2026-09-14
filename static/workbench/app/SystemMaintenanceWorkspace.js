(function () {
  'use strict';

  const A = window.SystemMaintenanceAPI,
    C = window.SystemMaintenanceControls;
  function useCommand(api, onChanged) {
    const [initial] = React.useState(A.inspectPending),
      [intent, setIntent] = React.useState(initial.intent),
      [storageError, setStorageError] = React.useState(initial.storageError);
    const [result, setResult] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const [host, setHost] = React.useState(null),
      [hostError, setHostError] = React.useState(null),
      [hostBusy, setHostBusy] = React.useState(true);
    const startedHere = React.useRef(false);
    const [selection, setSelection] = React.useState(null);
    const current = React.useRef(intent),
      found = React.useRef(null),
      running = React.useRef(false),
      mounted = React.useRef(true),
      changed = React.useRef(onChanged);
    changed.current = onChanged;
    function settle(value) {
      found.current = value;
      if (mounted.current) {
        setResult(value);
        if (value && value.host) setHost(value.host);
      }
    }
    async function inspectHost() {
      if (mounted.current) setHostBusy(true);
      try {
        const value = await api.host();
        if (mounted.current) {
          setHost(value);
          setHostError(null);
        }
        return value;
      } catch (problem) {
        if (mounted.current) setHostError(problem);
        return null;
      } finally {
        if (mounted.current) setHostBusy(false);
      }
    }
    async function lookup() {
      const original = current.current;
      if (!original || running.current) return;
      running.current = true;
      setBusy(true);
      setError(null);
      try {
        settle(await api.lookup(original, found.current && found.current.kind === 'file_operation' ? found.current.operation.job_ref : null));
      } catch (problem) {
        if (mounted.current) setError(problem);
      } finally {
        await inspectHost();
        running.current = false;
        if (mounted.current) setBusy(false);
      }
    }
    React.useEffect(() => {
      mounted.current = true;
      function reload(event) {
        if (event && event.type === 'storage' && event.key !== A.PENDING_KEY && event.key !== null) return;
        if (running.current) return;
        const state = A.inspectPending();
        setStorageError(state.storageError);
        if (current.current && (!state.intent || state.intent.request_key !== current.current.request_key)) {
          setStorageError(new Error('本机存的上次操作记录已变化，页面仍然停在等待确认的状态。请不要再操作，联系维护人员。'));
          lookup();
          return;
        }
        if (!state.storageError && !current.current) {
          current.current = state.intent;
          setIntent(state.intent);
          settle(null);
          setError(null);
        }
        if (state.intent) lookup();
      }
      if (current.current) lookup();else inspectHost();
      window.addEventListener('online', reload);
      window.addEventListener('storage', reload);
      return () => {
        mounted.current = false;
        window.removeEventListener('online', reload);
        window.removeEventListener('storage', reload);
      };
    }, [api]);
    async function execute(action, token, input, selected = null) {
      if (running.current || current.current || storageError || !host || hostError || host.state !== 'ready' || !host.operations_available) return;
      let original;
      try {
        original = A.pending().begin(action);
      } catch (problem) {
        setStorageError(problem);
        return;
      }
      startedHere.current = action === 'restore';
      setSelection(selected);
      current.current = original;
      setIntent(original);
      settle(null);
      setError(null);
      setBusy(true);
      running.current = true;
      try {
        settle(await api.command(original, token, input));
      } catch (problem) {
        if (mounted.current) setError(problem);
        if (problem.rejected) settle({
          kind: 'rejected',
          terminal: true
        });
      } finally {
        await inspectHost();
        running.current = false;
        if (mounted.current) setBusy(false);
      }
    }
    const restorePending = !!(intent && intent.action === 'restore' && !(result && result.terminal && (result.kind === 'rejected' || !startedHere.current)));
    const suspended = !!storageError || !!hostError || !host || host.state !== 'ready' || restorePending;
    function acknowledge() {
      if (suspended || running.current || !current.current || !found.current || !found.current.terminal) return;
      try {
        A.pending().finish(current.current);
      } catch (problem) {
        setStorageError(problem);
        return;
      }
      const original = current.current,
        completed = found.current;
      current.current = null;
      setIntent(null);
      settle(null);
      setError(null);
      setStorageError(null);
      changed.current(original, completed);
    }
    return {
      intent,
      result,
      error,
      storageError,
      busy,
      host,
      hostError,
      hostBusy,
      suspended,
      inspectHost,
      selection,
      locked: suspended || !!intent || busy || !host.operations_available,
      execute,
      lookup,
      acknowledge
    };
  }
  // Keep this component mounted across tab/source changes: it owns the system-only original request.
  function Workspace({
    tab,
    source = 'current',
    theme,
    onSetTheme,
    pageSize,
    onPageSize,
    compact,
    onCompact,
    revision = 0,
    onChanged,
    onReadSuspendedChange,
    recordContexts = {},
    onRecordContext,
    api: supplied,
    children
  }) {
    const api = React.useMemo(() => supplied || A.create(), [supplied]);
    const [version, refresh] = React.useReducer(value => value + 1, 0);
    const command = useCommand(api, (intent, result) => {
      refresh();
      if (onChanged) onChanged(intent, result);
    });
    const suspended = command.suspended;
    React.useLayoutEffect(() => {
      if (onReadSuspendedChange) onReadSuspendedChange(suspended);
    }, [suspended, onReadSuspendedChange]);
    const current = source === 'current',
      enabled = current && !suspended,
      serial = revision + ':' + version;
    const [visited, setVisited] = React.useState({});
    React.useEffect(() => {
      if (enabled && ['backups', 'logs', 'config'].includes(tab)) setVisited(value => ({
        ...value,
        [tab]: true
      }));
    }, [enabled, tab]);
    return /*#__PURE__*/React.createElement("div", {
      className: "sm-maintenance-workspace plana",
      "data-system-maintenance": "v1",
      style: {
        padding: 0,
        maxWidth: 'none',
        borderRadius: 0
      }
    }, /*#__PURE__*/React.createElement(C.Styles, null), suspended && !(command.hostBusy && !command.intent && !command.hostError && !command.storageError && !command.host) ? /*#__PURE__*/React.createElement(window.SystemRestorePanel, {
      command: command,
      api: api,
      theme: theme,
      onSetTheme: onSetTheme
    }) : /*#__PURE__*/React.createElement(C.Outcome, {
      command: command
    }), suspended && command.hostBusy && !command.intent && /*#__PURE__*/React.createElement("p", {
      className: "sm-note",
      role: "status"
    }, "\u6B63\u5728\u6838\u5BF9\u8F6F\u4EF6\u7EF4\u62A4\u72B6\u6001\uFF0C\u8FD8\u6CA1\u6709\u8BFB\u53D6\u6570\u636E\u5E93\u3002"), (!current || tab === 'overview') && !suspended && children, ['backups', 'logs'].map(kind => visited[kind] || enabled && tab === kind ? /*#__PURE__*/React.createElement("div", {
      key: kind,
      hidden: !enabled || tab !== kind
    }, /*#__PURE__*/React.createElement(window.SystemMaintenanceRecords, {
      api: api,
      kind: kind,
      pageSize: pageSize,
      onPageSize: onPageSize,
      revision: serial,
      command: command,
      active: enabled && tab === kind,
      initialContext: recordContexts[kind],
      onReadContext: onRecordContext
    })) : null), (visited.config || enabled && tab === 'config') && /*#__PURE__*/React.createElement("div", {
      hidden: !enabled || tab !== 'config'
    }, /*#__PURE__*/React.createElement(window.SystemMaintenanceConfig, {
      api: api,
      revision: serial,
      command: command,
      active: enabled && tab === 'config',
      theme: theme,
      onSetTheme: onSetTheme,
      pageSize: pageSize,
      onPageSize: onPageSize,
      compact: compact,
      onCompact: onCompact
    })));
  }
  window.SystemMaintenanceWorkspace = Workspace;
})();
