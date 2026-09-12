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
      throw new Error('无法读取场景采用恢复记录，不能开始新的采用。');
    }
    if (raw === null) return null;
    let value;
    try {
      value = JSON.parse(raw);
    } catch (_) {
      throw new Error('场景采用恢复记录损坏，请保留现场，不能换请求重提。');
    }
    A.check(valid(value), '场景采用恢复记录不完整，请保留现场，不能换请求重提。');
    return value;
  }
  function save(value, previous) {
    A.check(A.equal(read(), previous), '原场景采用请求已变化，未覆盖其他页面的记录。');
    A.check(value === null || valid(value));
    try {
      if (value === null) window.localStorage.removeItem(KEY);else window.localStorage.setItem(KEY, JSON.stringify(value));
    } catch (_) {
      throw new Error('无法保存场景采用恢复记录，本次未开始新的发送；请保留原请求。');
    }
    A.check(A.equal(read(), value), '场景采用恢复记录未完整保存，不能开始新的发送。');
    window.dispatchEvent(new Event(EVENT));
    return value;
  }
  function begin(preview, values, previous) {
    const scope = A.overview(preview),
      input = A.input(values);
    A.check(!previous || valid(previous) && previous.phase === 'rejected' && A.equal(previous.preview, scope) && A.equal(previous.input, input), '原请求的场景、原因和声明人已绑定，不能修改后复用原 key。');
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
    const [draft, setDraft] = React.useState(initial.saved ? initial.saved.input : {
      reason: '',
      declared_operator: ''
    });
    const [open, setOpen] = React.useState(false),
      [preview, setPreview] = React.useState(null),
      [consent, setConsent] = React.useState(false);
    const [busy, setBusy] = React.useState(false),
      [checking, setChecking] = React.useState(false),
      [error, setError] = React.useState(''),
      [notice, setNotice] = React.useState('');
    window.WorkbenchGuards.useDirtyGuard({
      dirty: !saved && (!!draft.reason || !!draft.declared_operator),
      message: '场景正式采用的原因或声明人尚未提交。'
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
          if (mounted.current) setNotice('采用已核实，但关联页面更新失败，请重新打开正式方案。');
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
        setStorageError('已收到采用回执，但恢复记录保存失败。' + e.message);
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
          setNotice('尚未观察到原请求回执；原请求仍可能完成。已保留原 key，不会自动重试，请稍后继续查询。');
        }
      } catch (e) {
        if (mounted.current && !(signal && signal.aborted)) setError('原场景采用结果尚未核实。' + e.message);
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
        setError('原采用请求属于另一场景或范围，请先核实原记录。');
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
      lock.current = true;
      setBusy(true);
      setError('');
      setNotice('');
      try {
        A.check(navigator.locks && typeof navigator.locks.request === 'function', '浏览器请求锁不可用，不能开始场景采用。');
        await navigator.locks.request(KEY, {
          ifAvailable: true
        }, async acquired => {
          A.check(acquired, '另一页面正在处理场景采用，请先核实原请求。');
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
              setError(e.message + ' 本次明确未采用；原 key 和确认内容已保留，请重新预览并勾选确认。');
            } else setError('采用响应未核实，不能当作未保存。原 key 已保留，只能查询原请求回执。');
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
        A.check(saved && saved.phase !== 'pending', '未知结果不能丢弃原请求。');
        save(null, saved);
        setOpen(false);
        setPreview(null);
        setConsent(false);
        setDraft({
          reason: '',
          declared_operator: ''
        });
        setError('');
        setNotice(saved.phase === 'committed' ? '本次采用回执已完成核实。' : '已结束明确未采用的原请求，正式计划未因该请求改变。');
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
