(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  const timeLabel = v => v ? window.WorkbenchFormat.compactDateTime(v) : '未记录';
  const number = v => v === null || v === undefined ? '暂无数据' : typeof v === 'number' ? window.WorkbenchFormat.number(v, { digits: Number.isInteger(v) ? 0 : 2 }) : String(v);
  const percent = v => v === null || v === undefined ? '暂无数据' : window.WorkbenchFormat.percent(v, 2);
  const hours = v => v === null || v === undefined ? '暂无数据' : window.WorkbenchFormat.hours(v, { digits: 2, trim: true });
  const sourceLabel = identity => (identity.display_name || '上次排产的候选方案') + (identity.plan_ref && identity.version ? ' · v' + identity.version : '');
  const statusLabel = v => ({ editing: '可继续试调', saved: '已保存', discarded: '已放弃', valid: '通过', warning: '有提示', blocked: '有冲突，不能采用', active: '启用', inactive: '停用' }[v] || v);
  // 排产记录和候选方案的状态叫法从词表取，和值班台、执行排产、排产记录页一致。
  const runStatusLabel = v => window.WorkbenchTerms.run_statuses[v] || v;
  const candidateStatusLabel = v => window.WorkbenchTerms.candidate_statuses[v] || v;
  function ErrorBox({ error }) { return error ? <window.WorkbenchError error={error} fields={Array.isArray(error.fields) ? error.fields : []} /> : null; }
  function Pager({ page, onPage, busy, label = '记录' }) {
    const pages = page.pages === undefined ? Math.ceil(page.total / page.size) : page.pages;
    return <window.WorkbenchControls.Pager page={{ ...page, pages: Math.max(pages, 1) }} label={label} unit="项" onPage={onPage} busy={busy}
      showPageJump={pages > 2} jumpLabel={label + '页码'} jumpActionLabel={'跳转' + label + '页'} />;
  }
  function Tabs({ value, options, onChange, label, idPrefix, panelId }) {
    return <div role="tablist" aria-label={label} className="tt-tabs">{options.map(([key, text]) => <button type="button" key={key} role="tab" tabIndex={value === key ? 0 : -1}
      id={idPrefix ? idPrefix + key : undefined} aria-controls={panelId} aria-selected={value === key} onClick={() => onChange(key)} onKeyDown={event => {
        const index = options.findIndex(o => o[0] === value), offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
        if (!offset && !['Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + offset + options.length) % options.length;
        onChange(options[next][0]); event.currentTarget.parentElement.children[next].focus();
      }}>{text}</button>)}</div>;
  }
  function Table({ rows, columns, label, size = 20 }) {
    const [number, set] = React.useState(1), page = Math.min(number, Math.max(1, Math.ceil(rows.length / size)));
    return <><div className="tt-table-scroll"><table className="tt-table" aria-label={label}><caption className="wb-visually-hidden">{label}</caption><thead><tr>{columns.map(c => <th scope="col" key={c[0]}>{c[0]}</th>)}</tr></thead>
      <tbody>{rows.slice((page - 1) * size, page * size).map((row, i) => <tr key={row.change_ref || row.row_ref || row.resource_ref || i}>
        {columns.map(c => <td key={c[0]}>{c[1](row)}</td>)}</tr>)}</tbody></table>{!rows.length && <div className="tt-empty">暂无记录</div>}</div>
      {rows.length > size && <Pager page={{ number: page, size, total: rows.length }} onPage={set} label={label} />}</>;
  }
  function Issues({ rows, onSelect }) {
    // Older saved snapshots include an adoption capability note as a blocker.
    // Adoption has its own preview/guard; this note is not a task constraint.
    const constraints = rows.filter(row => row.code !== 'scenario_adoption_not_connected');
    if (!constraints.length) return null;
    return <Table rows={constraints} size={10} label="约束问题" columns={[
      ['级别', r => r.severity === 'warning' ? '提示' : '冲突'], ['问题', r => r.message],
      ['关联', r => r.task_ref && onSelect ? <Button icon="arrow-right" aria-label="定位问题工序" onClick={() => onSelect(r.task_ref)}>工序</Button> : '整体']]} />;
  }
  // 一个「导出」按钮打开弹窗，弹窗里列出全部可下载格式；和计划、候选、现场实际甘特的导出走法一致。
  function Download({ data }) {
    const [error, setError] = React.useState(null), [open, setOpen] = React.useState(false), [notice, setNotice] = React.useState('');
    function save(section) {
      try {
        const output = window.TrialExport[section](data);
        window.APSWorkbenchTransport.saveBlob(output.filename, new Blob([output.text], { type: output.mime }));
        setError(null); setNotice(window.WorkbenchTerms.download_started(output.filename)); setOpen(false);
      } catch (e) { setError(e); }
    }
    return <><span className="tt-tools"><Button transfer="export" onClick={() => { setError(null); setNotice(''); setOpen(true); }}>导出</Button>
      {notice && <span role="status" className="tt-muted">{notice}</span>}</span>
      {open && <Modal title="导出试调方案" icon="download" onClose={() => setOpen(false)} footer={<><Button onClick={() => setOpen(false)}>取消</Button>
        <Button transfer="export" onClick={() => save('csv')}>下载 CSV（方案对比）</Button><Button transfer="export" onClick={() => save('preparation')}>下载 CSV（准备需求）</Button>
        <Button transfer="export" onClick={() => save('changeovers')}>下载 CSV（工种切换）</Button><Button transfer="export" className="btn primary" onClick={() => save('raw')}>下载 JSON（原始数据）</Button></>}>
        <div className="modal-b trial-modal-body"><p>导出当前读取的完整试调方案。空白表示该项没有值；提前量为负数表示延后。</p>
          <p>方案对比 CSV：逐批次的交付对比。普通文字保留原样，空值留空。</p>
          <p>准备需求 CSV：逐工序原需求与执行目标、准备和加工标准工时。工种切换 CSV：完整汇总与前后工序事件。</p>
          <p>原始数据 JSON：包含任务、资源、班表、报工和调整记录。</p><ErrorBox error={error} /></div></Modal>}</>;
  }
  window.TrialControls = { Button, Modal, ErrorBox, Pager, Tabs, Table, Issues, Download, timeLabel, number, percent, hours, statusLabel, runStatusLabel, candidateStatusLabel, sourceLabel };
})();
