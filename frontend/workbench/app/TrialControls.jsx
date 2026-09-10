(function () {
  'use strict';
  const { Button, Icon, Modal } = window.ResourceControls;
  const timeLabel = v => v ? String(v).replace('T', ' ') : '未记录';
  const number = v => v === null || v === undefined ? '不可评估' : typeof v === 'number' ? v.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : String(v);
  const sourceLabel = identity => (identity.display_name || '原排产候选') + (identity.plan_ref && identity.version ? ' · v' + identity.version : '');
  const statusLabel = v => ({ editing: '可继续试调', saved: '已保存', discarded: '已放弃', valid: '通过', warning: '有提示', blocked: '有阻断',
    complete: '已完成', partial: '部分完成', failed: '失败', running: '计算中', queued: '待计算', interrupted: '已中断', active: '启用', inactive: '停用' }[v] || v);
  function ErrorBox({ error }) { return error ? <div className="tt-error" role="alert">{error.message || String(error)}{Array.isArray(error.fields) && error.fields.map((r, i) => <div key={i}>{r.message}</div>)}</div> : null; }
  function Pager({ page, onPage, busy, label = '记录' }) {
    const pages = page.pages === undefined ? Math.ceil(page.total / page.size) : page.pages;
    const input = React.useRef(null), [jump, setJump] = React.useState(page.number);
    React.useEffect(() => { setJump(page.number); }, [page.number]);
    function apply() { if (input.current.reportValidity()) onPage(Number(jump)); }
    return <div className="tt-pager"><span>{page.total} 项 · 第 {page.number} / {Math.max(pages, 1)} 页</span>
      <Button icon="chevron-left" aria-label={label + '上一页'} disabled={busy || page.number <= 1} onClick={() => onPage(page.number - 1)} />
      <Button icon="chevron-right" aria-label={label + '下一页'} disabled={busy || page.number >= pages} onClick={() => onPage(page.number + 1)} />
      {pages > 2 && <><input ref={input} type="number" required min="1" max={pages} step="1" value={jump} aria-label={label + '页码'} disabled={busy} style={{ width: 66 }}
        onChange={e => setJump(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); apply(); } }} />
        <Button icon="arrow-right" aria-label={'跳转' + label + '页'} disabled={busy} onClick={apply} /></>}</div>;
  }
  function Tabs({ value, options, onChange, label }) {
    return <div role="tablist" aria-label={label} className="tt-tabs">{options.map(([key, text]) => <button type="button" key={key} role="tab" tabIndex={value === key ? 0 : -1}
      aria-selected={value === key} onClick={() => onChange(key)} onKeyDown={event => {
        const index = options.findIndex(o => o[0] === value), offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
        if (!offset && !['Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + offset + options.length) % options.length;
        onChange(options[next][0]); event.currentTarget.parentElement.children[next].focus();
      }}>{text}</button>)}</div>;
  }
  function Table({ rows, columns, label, size = 20 }) {
    const [number, set] = React.useState(1), page = Math.min(number, Math.max(1, Math.ceil(rows.length / size)));
    return <><div className="tt-table-scroll"><table className="tt-table" aria-label={label}><thead><tr>{columns.map(c => <th key={c[0]}>{c[0]}</th>)}</tr></thead>
      <tbody>{rows.slice((page - 1) * size, page * size).map((row, i) => <tr key={row.change_ref || row.row_ref || row.resource_ref || i}>
        {columns.map(c => <td key={c[0]}>{c[1](row)}</td>)}</tr>)}</tbody></table>{!rows.length && <div className="tt-empty">暂无记录</div>}</div>
      {rows.length > size && <Pager page={{ number: page, size, total: rows.length }} onPage={set} label={label} />}</>;
  }
  function Issues({ rows, onSelect }) {
    if (!rows.length) return null;
    return <Table rows={rows} size={10} label="约束问题" columns={[
      ['级别', r => r.severity === 'warning' ? '提示' : '阻断'], ['问题', r => r.message],
      ['关联', r => r.task_ref && onSelect ? <Button icon="arrow-right" aria-label={'定位问题工序 ' + r.code} onClick={() => onSelect(r.task_ref)}>工序</Button> : '整体']]} />;
  }
  function Download({ data }) {
    const [error, setError] = React.useState(null);
    function save(raw = false) {
      let url, a;
      try {
        const output = raw ? window.TrialExport.raw(data) : window.TrialExport.csv(data);
        const blob = new Blob([output.text], { type: output.mime });
        url = URL.createObjectURL(blob); a = document.createElement('a'); a.href = url; a.download = output.filename;
        document.body.appendChild(a); a.click(); setError(null);
      } catch (e) { setError(e); } finally { if (a) a.remove(); if (url) setTimeout(() => URL.revokeObjectURL(url), 1000); }
    }
    return <><span className="tt-tools"><Button icon="download" onClick={() => save()}>导出对比</Button>
      <Button icon="file-down" onClick={() => save(true)}>导出原始数据</Button></span><ErrorBox error={error} /></>;
  }
  window.TrialControls = { Button, Icon, Modal, ErrorBox, Pager, Tabs, Table, Issues, Download, timeLabel, number, statusLabel, sourceLabel };
})();
