(function () {
  'use strict';
  const C = window.DashboardContract, P = window.DashboardPanels, { Button, ErrorBox } = window.ResourceControls;
  function History({ read, selected, historyPage, onPage, onSelect, rows, onHandle }) {
    const [source, setSource] = React.useState(''), result = read.result, history = result && result.data.history, item = result && result.data.item;
    React.useEffect(() => setSource(''), [selected]);
    const options = rows.slice(); if (item && !options.some(r => r.item_ref === item.item_ref)) options.push(item);
    return <section aria-label="处置历史"><div className="dy-filters"><label className="dy-search">历史条目<select aria-label="选择历史条目" value={selected || ''} onChange={e => onSelect(e.target.value || null)}><option value="">请选择条目</option>{options.map(row => <option key={row.item_ref} value={row.item_ref}>{row.subject} · {C.categories[row.category]}</option>)}</select></label>
      {item && <Button icon={item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen'} onClick={onHandle}>{item.handling.status === 'closed' ? '独立重开' : '调整当前处置'}</Button>}</div>
      {item && <div className="dy-tools"><P.Risk risk={item.risk} /><P.Status handling={item.handling} /><span>当前处置，非历史状态</span></div>}
      <ErrorBox error={read.error} />{read.loading && <div role="status" className="dy-empty">正在读取原条目历史</div>}
      {!selected && <div className="dy-empty">尚未选择历史条目。</div>}
      {history && <>{!history.items.length && <div className="dy-empty">该条目尚无处置历史。</div>}{history.items.map(h => <article className="dy-history" key={h.history_ref} data-history-sequence={h.sequence}>
        <div className="dy-heading"><b>第 {h.sequence} 次 · {C.statuses[h.before.status]} → {C.statuses[h.after.status]}{h.action === 'reopen' ? ' · 独立重开' : ''}</b><time>{h.recorded_at.replace('T', ' ')}</time></div>
        <p>{h.action === 'reopen' ? '重开原因：' + h.reason : '核实备注：' + h.after.remark}</p><div className="dy-muted">登记人 {h.local_operator} · 回执 {h.receipt_ref}</div>
        <details className="dy-evidence"><summary>变更前后及完成凭据</summary><div className="dy-scroll"><table><thead><tr><th>字段</th><th>变更前</th><th>变更后</th></tr></thead><tbody>{['status', ...C.fields].map(k => <tr key={k}><td>{C.labels[k]}</td><td>{k === 'status' ? C.statuses[h.before[k]] : P.value(h.before[k])}</td><td>{k === 'status' ? C.statuses[h.after[k]] : P.value(h.after[k])}</td></tr>)}</tbody></table></div></details>
        <Button className="mini" icon="search" aria-label={'查看第 ' + h.sequence + ' 次原始依据'} onClick={() => setSource(source === h.history_ref ? '' : h.history_ref)}>原始依据</Button>
        {source === h.history_ref && <div className="dy-note"><div>永久历史快照 {h.source_snapshot.snapshot_ref} · {h.source_snapshot.as_of}</div><P.Risk risk={h.source_snapshot.source.risk} /><P.Evidence source={h.source_snapshot.source.source} /></div>}
      </article>)}<P.Pager page={{ ...history.page, number: historyPage }} busy={read.loading} onPage={onPage} label="历史" /></>}
    </section>;
  }
  window.DashboardHistory = History;
})();
