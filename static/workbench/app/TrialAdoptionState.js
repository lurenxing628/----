(function () {
  'use strict';

  const A = window.TrialAdoptionAPI,
    KEY = 'aps_workbench_trial_adoption_pending_v1',
    EVENT = KEY + '_changed';
  function valid(v) {
    try {
      return A.shape(v, ['schema_version', 'scenario_ref', 'request_key', 'input', 'preview', 'phase'], v.phase === 'committed' ? ['receipt'] : []) && v.schema_version === 1 && A.key(v.request_key) && A.equal(A.overview(v.preview), v.preview) && v.scenario_ref === v.preview.scenario_ref && A.equal(A.input(v.input), v.input) && ['pending', 'rejected', 'committed'].includes(v.phase) && (v.phase !== 'committed' || !!A.receipt(v.receipt, v));
    } catch (_) {
      return false;
    }
  }
  function read() {
    let raw;
    try {
      raw = window.localStorage.getItem(KEY);
    } catch (_) {
      throw new Error('读不到上次采用操作的记录，不能开始新的采用。请重新打开页面。');
    }
    if (raw === null) return null;
    let value;
    try {
      value = JSON.parse(raw);
    } catch (_) {
      throw new Error('上次采用操作的记录已损坏。请不要再操作，联系维护人员。');
    }
    A.check(valid(value), '上次采用操作的记录不完整。请不要再操作，联系维护人员。');
    return value;
  }
  function save(value, previous) {
    A.check(A.equal(read(), previous), '上次采用操作的记录已变化，没有覆盖其他页面的记录。');
    A.check(value === null || valid(value));
    try {
      if (value === null) window.localStorage.removeItem(KEY);else window.localStorage.setItem(KEY, JSON.stringify(value));
    } catch (_) {
      throw new Error('存不下这次采用操作的记录，这次没有提交。请点「查询结果」确认上次操作。');
    }
    A.check(A.equal(read(), value), '这次采用操作的记录没有完整存上，不能开始提交。');
    window.dispatchEvent(new Event(EVENT));
    return value;
  }
  function begin(preview, values, previous) {
    const scope = A.overview(preview),
      input = A.input(values);
    A.check(!previous || valid(previous) && previous.phase === 'rejected' && A.equal(previous.preview, scope) && A.equal(previous.input, input), '上次提交的试调方案、原因和经办人已绑定，改了内容不能沿用同一个操作编号。');
    const requestKey = previous ? previous.request_key : 'trial-adoption-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join('');
    return save({
      schema_version: 1,
      scenario_ref: scope.scenario_ref,
      request_key: requestKey,
      input,
      preview: scope,
      phase: 'pending'
    }, previous);
  }
  // A fresh draft starts from the handler this machine remembered, so the dirty guard compares against that prefill rather than an empty string.
  const remembered = () => window.WorkbenchHandlerMemory.read().value,
    empty = () => ({
      reason: '',
      declared_operator: remembered()
    });
  function useSession({
    scenarioRef,
    data,
    disabled = false,
    onAdopted
  }) {
    const api = React.useMemo(() => A.create(), []);
    const [initial] = React.useState(() => {
      try {
        return {
          saved: read(),
          error: ''
        };
      } catch (e) {
        return {
          saved: null,
          error: e.message
        };
      }
    });
    const [saved, setSaved] = React.useState(initial.saved),
      [storageError, setStorageError] = React.useState(initial.error);
    const [draft, setDraft] = React.useState(initial.saved ? initial.saved.input : empty());
    const [open, setOpen] = React.useState(false),
      [preview, setPreview] = React.useState(null),
      [consent, setConsent] = React.useState(false);
    const [busy, setBusy] = React.useState(false),
      [checking, setChecking] = React.useState(false),
      [error, setError] = React.useState(''),
      [notice, setNotice] = React.useState('');
    window.WorkbenchGuards.useDirtyGuard({
      dirty: !saved && (!!draft.reason || draft.declared_operator !== remembered()),
      message: '正式采用的原因或经办人还没提交。'
    });
    const [revision, refresh] = React.useReducer(v => v + 1, 0);
    const mounted = React.useRef(false),
      lock = React.useRef(false),
      request = React.useRef(null),
      active = React.useRef(saved),
      current = React.useRef(null);
    const callback = React.useRef(onAdopted),
      notified = React.useRef(null);
    callback.current = onAdopted;
    active.current = saved;
    let original = null,
      sourceError = '';
    try {
      original = A.source(scenarioRef, data);
    } catch (e) {
      sourceError = e.message;
    }
    current.current = {
      original,
      disabled
    };
    const identity = JSON.stringify(original);
    React.useEffect(() => {
      mounted.current = true;
      return () => {
        mounted.current = false;
        if (request.current) request.current.abort();
      };
    }, []);
    React.useEffect(() => {
      setPreview(null);
      setConsent(false);
      if (request.current) request.current.abort();
    }, [identity, disabled]);
    function sync() {
      try {
        const value = read();
        if (!A.equal(value, active.current)) {
          active.current = value;
          setSaved(value);
          setPreview(null);
          setConsent(false);
          if (value) setDraft(value.input);
        }
        setStorageError('');
      } catch (e) {
        setStorageError(e.message);
      }
    }
    React.useEffect(() => {
      const changed = e => {
        if (!e.key || e.key === KEY) sync();
      };
      window.addEventListener('storage', changed);
      window.addEventListener(EVENT, changed);
      return () => {
        window.removeEventListener('storage', changed);
        window.removeEventListener(EVENT, changed);
      };
    }, []);
    const result = saved && saved.phase === 'committed' ? saved.receipt : null;
    React.useEffect(() => {
      if (!result || notified.current === result.receipt_ref) return;
      notified.current = result.receipt_ref;
      if (typeof callback.current === 'function') {
        const failed = () => {
          if (mounted.current) setNotice('采用已确认，但相关页面没有更新成功。请重新打开正式计划。');
        };
        try {
          Promise.resolve(callback.current(result)).catch(failed);
        } catch (_) {
          failed();
        }
      }
    }, [result]);
    function accept(value, intent) {
      A.receipt(value, intent);
      if (!mounted.current) return;
      if (!A.equal(active.current, intent)) {
        sync();
        return;
      }
      const committed = {
        ...intent,
        phase: 'committed',
        receipt: value
      };
      try {
        save(committed, intent);
        active.current = committed;
        setSaved(committed);
        setError('');
        setNotice('');
      } catch (e) {
        setStorageError('已收到采用结果，但上次操作记录没存上。' + e.message);
      }
    }
    async function lookup(signal) {
      const intent = active.current;
      if (!intent || intent.phase === 'rejected' || lock.current || storageError) return;
      setChecking(true);
      try {
        const found = await api.lookup(intent, signal);
        if (!mounted.current || signal && signal.aborted) return;
        if (found) accept(found, intent);else {
          setError('');
          setNotice(window.WorkbenchTerms.outcomes.pending('采用'));
        }
      } catch (e) {
        if (mounted.current && !(signal && signal.aborted)) setError('上次采用的结果还没查到。' + e.message);
      } finally {
        if (mounted.current && !(signal && signal.aborted)) setChecking(false);
      }
    }
    React.useEffect(() => {
      if (!saved || saved.phase !== 'pending' || storageError || lock.current) return undefined;
      const controller = new AbortController();
      lookup(controller.signal);
      return () => {
        controller.abort();
        setChecking(false);
      };
    }, [saved, revision, storageError]);
    async function inspect() {
      if (lock.current || storageError || disabled || !original || saved && saved.phase !== 'rejected') return;
      if (saved && !A.equal(saved.preview, original)) {
        setError('上次采用操作属于另一个试调方案或范围，请先查询那条记录的结果。');
        return;
      }
      lock.current = true;
      setBusy(true);
      setOpen(true);
      setPreview(null);
      setConsent(false);
      setError('');
      setNotice('');
      const controller = new AbortController();
      request.current = controller;
      try {
        const value = await api.preview(original, controller.signal);
        if (mounted.current && !controller.signal.aborted && !current.current.disabled && A.equal(original, current.current.original)) setPreview(value);
      } catch (e) {
        if (mounted.current && !controller.signal.aborted) setError(e.message);
      } finally {
        lock.current = false;
        if (mounted.current) setBusy(false);
      }
    }
    async function submit() {
      if (lock.current || storageError || disabled || !original || !preview || !preview.validation.can_adopt || !consent || !A.equal(original, A.overview(preview)) || saved && saved.phase !== 'rejected') return;
      let values;
      try {
        values = A.input({
          confirm: true,
          reason: draft.reason,
          declared_operator: draft.declared_operator
        });
      } catch (e) {
        setError(e.message);
        return;
      }
      window.WorkbenchHandlerMemory.write(values.declared_operator);
      lock.current = true;
      setBusy(true);
      setError('');
      setNotice('');
      try {
        A.check(navigator.locks && typeof navigator.locks.request === 'function', '当前浏览器不支持这项操作，请用 Chrome 打开。');
        await navigator.locks.request(KEY, {
          ifAvailable: true
        }, async acquired => {
          A.check(acquired, '另一个页面正在处理这次采用，请先在那个页面点「查询结果」。');
          if (!mounted.current || current.current.disabled || !A.equal(original, current.current.original)) return;
          const intent = begin(preview, values, active.current);
          active.current = intent;
          setSaved(intent);
          setDraft(intent.input);
          setPreview(null);
          setConsent(false);
          try {
            accept(await api.adopt(intent, preview.write_context.write_token), intent);
          } catch (e) {
            if (!mounted.current) return;
            if (A.isRejected(e)) {
              const rejected = save({
                ...intent,
                phase: 'rejected'
              }, intent);
              active.current = rejected;
              setSaved(rejected);
              setError(window.WorkbenchTerms.outcomes.rejected('采用', e.message));
            } else setError(window.WorkbenchTerms.outcomes.unknown('采用'));
          }
        });
      } catch (e) {
        if (mounted.current) setStorageError(e.message);
      } finally {
        lock.current = false;
        if (mounted.current) {
          setBusy(false);
          refresh();
        }
      }
    }
    function finish() {
      try {
        A.check(saved && saved.phase !== 'pending', '结果还不确定，不能丢弃这次操作记录。');
        save(null, saved);
        setOpen(false);
        setPreview(null);
        setConsent(false);
        setDraft(empty());
        setError('');
        setNotice(saved.phase === 'committed' ? '这次采用结果已确认完成。' : '已结束这次没有采用的操作，正式计划没有因此改变。');
      } catch (e) {
        setStorageError(e.message);
      }
    }
    function close() {
      if (request.current) request.current.abort();
      setOpen(false);
      setPreview(null);
      setConsent(false);
    }
    return {
      saved,
      result,
      draft,
      open,
      preview,
      consent,
      busy: busy || checking,
      error,
      notice,
      storageError,
      sourceError,
      original,
      disabled,
      setOpen,
      setConsent,
      change: value => {
        if (!active.current) {
          setDraft(value);
          setConsent(false);
        }
      },
      inspect,
      submit,
      lookup: () => lookup(),
      sync,
      close,
      finish
    };
  }
  window.TrialAdoptionState = {
    KEY,
    EVENT,
    read,
    save,
    begin,
    valid,
    useSession
  };
})();
