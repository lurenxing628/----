import React from '../runtime/react.js';

// 依附查询结果的按需子读取（计划页的原安排对照、完整工序衔接图、班表时段）。
// 分片只属于加载它的那个结果对象：同一计划重读得到新的结果对象，旧分片随之失效；结果换了身份、不再需要或卸载时取消在途读取，
// 晚到的响应不写入。read 是 useQuery 的返回：value 对齐 read.shown（重读期间继续展示旧结果的分片），loading / error 只对齐当前
// read.result（不显示上一份结果的错误）。
// when(requested)：有当前结果、它的分片还没加载也没出错时，由调用方判断这次渲染要不要加载；requested 表示当前结果上调用过 request()。
// load(signal) 产出分片值（不为 null）。request() 为当前结果登记需要并清掉错误，出错后的重试也走它。
const empty = { result: null, value: null, loading: false, error: null, requested: false };
function useResultSlice(read, { when, load }) {
  const { result, shown } = read;
  const [state, setState] = React.useState(empty);
  const own = state.result === result ? state : empty;
  const needed = Boolean(result !== null && own.value === null && own.error === null && when(own.requested));
  React.useEffect(() => {
    if (!needed) return undefined;
    const controller = new AbortController();
    setState(current => ({ ...(current.result === result ? current : empty), result, loading: true }));
    Promise.resolve().then(() => load(controller.signal)).then(value => {
      if (!controller.signal.aborted) setState(current => ({ ...current, value, loading: false }));
    }, error => {
      if (!controller.signal.aborted && error.name !== 'AbortError') setState(current => ({ ...current, loading: false, error }));
    });
    return () => controller.abort();
  }, [result, needed]);
  const request = React.useCallback(() => setState(current => current.result !== result ? { ...empty, result, requested: true }
    : current.requested && current.error === null ? current : { ...current, requested: true, error: null }), [result]);
  return { value: state.result === shown ? state.value : null, loading: own.loading, error: own.error, request };
}

export { useResultSlice };
export default { useResultSlice };
