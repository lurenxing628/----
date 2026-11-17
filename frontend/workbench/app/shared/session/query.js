import React from '../runtime/react.js';

// result 只是当前读取身份的结果：身份一变就是 null，导出、写入和按结果身份做的事都只读它。
// shown 是展示保留值：传了 keep 时，同一个 keep 的新一轮读取进行中继续给上一次结果，免得整块清空闪烁；
// 保留值只接续一段连续的读取：读取以出错或停用结束（不在加载、也没有结果），或换了 keep，就不再保留——
// 出错或取消时旧数据已经从屏幕上撤下，重试期间再把它闪回来，会让人以为出错前的数据又有效了。没传 keep 时 shown 就是 result。
function useQuery(load, dependencies, { enabled = true, keep } = {}) {
  const [state, setState] = React.useState({ loading: enabled, result: null, error: null });
  const [revision, setRevision] = React.useState(0);
  const requested = React.useRef(null), completed = React.useRef(null), kept = React.useRef(null);
  const identity = React.useMemo(() => ({}), dependencies.concat([revision]));
  React.useEffect(() => {
    let active = true; const controller = new AbortController(), next = requested.current;
    requested.current = null;
    const previous = completed.current && completed.current.identity === identity ? completed.current : null;
    if (!enabled) { setState({ identity, loading: false, result: previous ? previous.result : null, error: null }); if (next) next.reject(new DOMException('读取已取消', 'AbortError')); return () => controller.abort(); }
    if (previous) { setState({ identity, loading: false, result: previous.result, error: null }); return () => controller.abort(); }
    setState({ identity, loading: true, result: null, error: null });
    Promise.resolve().then(() => (next ? next.load : load)(controller.signal)).then(result => {
      if (active) { completed.current = { identity, result }; setState({ identity, loading: false, result, error: null }); if (next) next.resolve(result); }
    }, error => {
      if (active) {
        setState({ identity, loading: false, result: null, error: error && error.name === 'AbortError' ? null : error });
        if (next) next.reject(error);
      }
    });
    return () => { active = false; controller.abort(); if (next) next.reject(new DOMException('读取已取消', 'AbortError')); };
  }, [identity, enabled]);
  React.useEffect(() => () => {
    const next = requested.current; requested.current = null;
    if (next) next.reject(new DOMException('读取已取消', 'AbortError'));
  }, []);
  const current = state.identity === identity ? state : { loading: enabled, result: null, error: null };
  if (current.result !== null) kept.current = keep === undefined ? null : { keep, result: current.result };
  else if (!current.loading || kept.current && kept.current.keep !== keep) kept.current = null;
  const status = current.loading ? 'loading' : current.error ? 'error' : current.result !== null ? 'ready' : 'idle';
  return {
    ...current,
    shown: current.result !== null ? current.result : kept.current && kept.current.result,
    status,
    reload: () => setRevision(value => value + 1),
    reloadAndWait: nextLoad => new Promise((resolve, reject) => {
      if (requested.current) requested.current.reject(new DOMException('读取已取消', 'AbortError'));
      requested.current = { load: nextLoad || load, resolve, reject }; setRevision(value => value + 1);
    })
  };
}

export { useQuery };
export default { useQuery };
