(function () {
  'use strict';

  const A = window.CalibrationAdoptionAPI,
    KEY = 'aps_calibration_adoption_pending_v1',
    EVENT = KEY + '_changed';
  function valid(value) {
    try {
      return value && value.version === 1 && A.key(value.request_key) && ['pending', 'rejected', 'committed'].includes(value.phase) && A.equal(A.input(value.input, true), value.input) && A.equal(A.binding(value.baseline), value.baseline) && (value.phase !== 'committed' || !!A.receipt(value.receipt, value));
    } catch (_) {
      return false;
    }
  }
  function read() {
    let raw;
    try {
      raw = localStorage.getItem(KEY);
    } catch (_) {
      throw new Error('无法读取上次采用操作的记录，暂时不能开始新的采用。');
    }
    if (raw === null) return null;
    let value;
    try {
      value = JSON.parse(raw);
    } catch (_) {
      throw new Error('上次采用的操作记录已损坏。请不要再操作，联系维护人员；不能换个编号重新提交。');
    }
    A.check(valid(value), '上次采用的操作记录不完整。请不要再操作，联系维护人员；不能换个编号重新提交。');
    return value;
  }
  function save(value, previous) {
    A.check(A.equal(read(), previous), '上次操作已变化，没有覆盖其他页面的采用记录。');
    A.check(value === null || valid(value));
    try {
      if (value === null) localStorage.removeItem(KEY);else localStorage.setItem(KEY, JSON.stringify(value));
    } catch (_) {
      throw new Error('无法保存这次采用操作的记录，没有开始新的采用。');
    }
    A.check(A.equal(read(), value), '这次操作没有完整保存，不能开始新的采用。');
    window.dispatchEvent(new Event(EVENT));
    return value;
  }
  function begin(preview, previous) {
    A.check(!previous || previous.phase === 'rejected', '上次操作的结果还没确认，不能开始新的采用。');
    return save({
      version: 1,
      request_key: 'calibration-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join(''),
      phase: 'pending',
      baseline: A.binding(preview.suggestion),
      input: A.input({
        ...preview.input,
        confirm: true
      }, true)
    }, previous);
  }
  function useSession({
    detail,
    stale,
    adapter
  }) {
    const api = React.useMemo(() => adapter || A.create(), [adapter]);
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
    const [draft, setDraft] = React.useState(initial.saved ? {
      reason: initial.saved.input.reason,
      declared_operator: initial.saved.input.declared_operator
    } : {
      reason: '',
      declared_operator: ''
    });
    const [open, setOpen] = React.useState(false),
      [preview, setPreview] = React.useState(null),
      [consent, setConsent] = React.useState(false);
    const [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(''),
      [notice, setNotice] = React.useState('');
    const [revision, refresh] = React.useReducer(v => v + 1, 0);
    const mounted = React.useRef(false),
      lock = React.useRef(false),
      request = React.useRef(null),
      active = React.useRef(saved),
      source = React.useRef(detail);
    active.current = saved;
    source.current = detail;
    const identity = detail ? JSON.stringify(A.binding(detail.suggestion)) : '';
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
    }, [identity, stale]);
    function sync() {
      try {
        const value = read();
        active.current = value;
        setSaved(value);
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
    function accept(value, original) {
      A.receipt(value, original);
      const committed = {
        ...original,
        phase: 'committed',
        receipt: value
      };
      save(committed, original);
      if (mounted.current) {
        setSaved(committed);
        setError('');
        setNotice('');
      }
    }
    React.useEffect(() => {
      if (!saved || saved.phase !== 'pending' || storageError || lock.current) return undefined;
      let disposed = false;
      const controller = new AbortController();
      setBusy(true);
      api.lookup(saved, controller.signal).then(value => {
        if (disposed) return;
        if (value) accept(value, saved);else setNotice('上次采用结果尚未确认，请稍后再次查询。');
      }).catch(e => {
        if (!disposed) setError('上次操作的结果还没确认。' + e.message);
      }).finally(() => {
        if (!disposed) setBusy(false);
      });
      return () => {
        disposed = true;
        controller.abort();
      };
    }, [saved, api, revision, storageError]);
    function change(value) {
      setDraft(value);
      setPreview(null);
      setConsent(false);
      setError('');
    }
    async function inspect() {
      if (lock.current || stale || storageError || !detail || saved && saved.phase !== 'rejected') return;
      if (saved && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref) {
        setError('上次操作属于另一个模板。请先点「结束本次未采用」处理完上次操作。');
        return;
      }
      let values;
      try {
        values = A.input(draft);
      } catch (e) {
        setError(e.message);
        return;
      }
      lock.current = true;
      setBusy(true);
      setPreview(null);
      setConsent(false);
      setError('');
      setNotice('');
      const controller = new AbortController();
      request.current = controller;
      try {
        const value = await api.preview(detail.suggestion, values, controller.signal);
        if (mounted.current && !controller.signal.aborted && A.equal(detail, source.current)) setPreview(value);
      } catch (e) {
        if (mounted.current && !controller.signal.aborted) setError(e.message);
      } finally {
        lock.current = false;
        if (mounted.current) setBusy(false);
      }
    }
    async function submit() {
      if (lock.current || stale || storageError || !preview || !preview.validation.can_adopt || !consent || !detail || !A.equal(A.binding(detail.suggestion), A.binding(preview.suggestion)) || !A.equal(A.input(draft), preview.input)) return;
      lock.current = true;
      setBusy(true);
      setError('');
      setNotice('');
      try {
        A.check(navigator.locks && typeof navigator.locks.request === 'function', '当前浏览器不支持这一步，请用 Chrome 打开后重试。');
        await navigator.locks.request(KEY, {
          ifAvailable: true
        }, async acquired => {
          A.check(acquired, '另一个页面正在采用，请先在那边查询结果。');
          const original = begin(preview, active.current);
          active.current = original;
          setSaved(original);
          setPreview(null);
          setConsent(false);
          try {
            accept(await api.adopt(original, preview.write_context.write_token), original);
          } catch (e) {
            if (A.isRejected(e)) {
              const rejected = save({
                ...original,
                phase: 'rejected'
              }, original);
              if (mounted.current) setSaved(rejected);
            }
            if (mounted.current) setError(A.isRejected(e) ? e.message + ' 本次没有采用；请点「刷新所选模板」后重新预检。' : window.WorkbenchTerms.outcomes.pending('采用'));
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
        A.check(saved && saved.phase !== 'pending', '结果还不确定，不能丢弃这次操作。');
        save(null, saved);
        setOpen(false);
        setPreview(null);
        setConsent(false);
      } catch (e) {
        setStorageError(e.message);
      }
    }
    return {
      saved,
      draft,
      open,
      preview,
      consent,
      busy,
      error,
      notice,
      storageError,
      setOpen,
      setConsent,
      change,
      inspect,
      submit,
      finish,
      lookup: refresh,
      sync,
      close: () => {
        if (request.current) request.current.abort();
        setOpen(false);
        setPreview(null);
        setConsent(false);
      }
    };
  }
  window.CalibrationAdoptionState = {
    KEY,
    EVENT,
    read,
    save,
    begin,
    useSession
  };
})();
