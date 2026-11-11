import React from '../runtime/react.js';

function useQuery(load, dependencies, enabled = true) {
  const [state, setState] = React.useState({ loading: enabled, result: null, error: null });
  const [revision, setRevision] = React.useState(0);
  const requested = React.useRef(null), completed = React.useRef(null);
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
  const status = current.loading ? 'loading' : current.error ? 'error' : current.result !== null ? 'ready' : 'idle';
  return {
    ...current,
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
