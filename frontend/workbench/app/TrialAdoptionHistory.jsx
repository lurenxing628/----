(function () {
  'use strict';
  const U = window.TrialControls, A = window.TrialAdoptionHistoryAPI, S = window.TrialAdoptionHistoryState;
  const labels = { all: '全部采用', current: '当前正式', historical: '历史正式', unavailable: '身份不可用' };
  const text = value => value === null ? '证据缺失' : value;
  function Evidence({ item, source }) {
    return <details className="wb-ref"><summary>来源与编号</summary><dl className="tah-refs">
      <dt>原来源</dt><dd>{U.sourceLabel(source.base_identity)}<br />{Object.values(source.base)[0]}</dd>
      <dt>原正式基线</dt><dd>{source.baseline.plan_ref ? 'v' + source.baseline.version + ' · ' + source.baseline.plan_ref : '当时无正式基线'}</dd>
      <dt>原场景</dt><dd>{source.scenario_ref}</dd><dt>原草稿</dt><dd>{source.draft_ref}</dd>
      <dt>保存来源</dt><dd>{source.saved_by} · {U.timeLabel(source.saved_at)}<br />{source.save_request_key}</dd>
      <dt>新正式引用</dt><dd>{item.committed_plan.plan_ref}</dd><dt>命令回执</dt><dd>{item.receipt_ref}</dd>
      <dt>原请求</dt><dd>{item.request_key}</dd><dt>提交时间 UTC</dt><dd>{item.committed_at_utc}</dd>
      <dt>字段依据</dt><dd>提交：持久命令回执；原因与声明人：回执意图散列核对；采用人及本地时间：正式历史审计；当前状态：本次正式身份读取。</dd>
    </dl></details>;
  }
  function History({ data }) {
    const ref = data.scenario_ref;
    const [query, setQuery] = React.useState(() => { try { return S.restore(ref); } catch (error) { return { error }; } });
    const [error, setError] = React.useState(null), [revision, refresh] = React.useReducer(n => n + 1, 0);
    const snapshot = React.useRef(query.snapshot_ref);
    const read = window.TrialSession.useRead(signal => A.read(ref, { page: query.page, size: query.size, status: query.status,
      ...(snapshot.current ? { snapshot_ref: snapshot.current } : {}) }, signal), [ref, query.page, query.size, query.status, revision], !query.error);
    React.useEffect(() => {
      if (!read.result) return;
      snapshot.current = read.result.meta.snapshot_ref;
      try { S.remember(ref, { page: query.page, size: query.size, status: query.status, snapshot_ref: snapshot.current, tab: 'adoptions' }); }
      catch (_) { setError(new Error('采用记录已读取，但查看状态保存失败；返回后筛选可能无法恢复。')); }
    }, [read.result]);
    function update(patch, reset = true) {
      if (reset) snapshot.current = null;
      const next = { ...query, ...patch, error: null, snapshot_ref: snapshot.current };
      try { S.remember(ref, next); } catch (_) { setError(new Error('采用记录筛选无法保存，请核对浏览器状态。')); return; }
      setError(null); setQuery(next); refresh();
    }
    const result = read.result, d = result && result.data;
    return <section className="trial-adoption-history" aria-label="本场景采用记录"><window.TrialAdoptionHistoryStyles />
      <div className="tah-toolbar"><label>采用状态<select aria-label="采用状态" value={query.status || 'all'} disabled={read.busy || !!query.error}
        onChange={e => update({ status: e.target.value, page: 1 })}>{Object.keys(labels).map(key => <option value={key} key={key}>{labels[key]}</option>)}</select></label>
        <label>每页<select aria-label="采用记录每页" value={query.size || 20} disabled={read.busy || !!query.error} onChange={e => update({ size: Number(e.target.value), page: 1 })}>
          {[10, 20, 50].map(n => <option value={n} key={n}>{n} 条</option>)}</select></label>
        <U.Button icon="refresh-cw" aria-label="刷新采用记录" title="刷新采用记录" busy={read.busy}
          onClick={() => { if (query.error) { history.replaceState({ ...history.state, trialAdoptionHistory: null }, '', location.href); } update({ page: 1, status: query.status || 'all', size: query.size || 20 }); }} />
      </div><U.ErrorBox error={query.error || error || read.error} />
      {read.busy && <p role="status" className="tah-meta">正在读取本场景采用记录与当前正式身份…</p>}
      {d && <><p className="tah-meta">{d.source.name} · 本场景共 {d.total_adoptions} 次采用 · 核对于 {U.timeLabel(result.meta.as_of)}</p>
        {!d.items.length && <p className="tt-empty" role="status">{d.total_adoptions ? '当前筛选没有采用记录。' : '尚无本场景的正式采用回执。'}</p>}
        <ol className="tah-list">{d.items.map(item => <li key={item.receipt_ref} data-adoption-receipt={item.receipt_ref}>
          <div className="tah-head"><strong>正式计划 v{item.committed_plan.version}</strong><span className={'tah-state tah-' + item.current_state}>{labels[item.current_state]}</span>
            <span>{item.committed_plan.row_count} 道工序</span><U.Button icon="arrow-right" disabled={item.current_state === 'unavailable'}
              onClick={() => { try { S.openPlan(ref, item.committed_plan.plan_ref); } catch (error) { setError(error); } }}>查看正式方案</U.Button></div>
          <p>采用人：{text(item.adoption.application_operator)} · 声明人：{text(item.adoption.declared_operator)}</p>
          <p>采用原因：{text(item.adoption.reason)}</p><p className="tah-meta">{U.timeLabel(item.adoption.adopted_at)} · 原基线 {d.source.baseline.plan_ref ? 'v' + d.source.baseline.version : '无正式基线'}</p>
          {item.evidence_gaps.map((issue, index) => <p className="tah-gap" key={index}>{issue.message}</p>)}<Evidence item={item} source={d.source} />
        </li>)}</ol><U.Pager label="采用记录" page={d.page} busy={read.busy} onPage={page => update({ page }, false)} /></>}
    </section>;
  }
  window.TrialAdoptionHistory = function TrialAdoptionHistory({ data }) {
    return data.scenario_ref ? <History key={data.scenario_ref} data={data} /> : <p className="tt-empty">当前为试调草稿，尚无已保存场景的采用记录。</p>;
  };
})();
