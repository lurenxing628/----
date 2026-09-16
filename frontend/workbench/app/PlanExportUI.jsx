(function () {
  'use strict';
  const { Button, Modal, ErrorBox } = window.ResourceControls;
  const C = window.APSResourceContract, P = window.APSPlanContract, M = window.PlanGanttModel;
  function filename(disposition, format) {
    const unicode = /filename\*=UTF-8''([^;]+)/i.exec(disposition), plain = /filename="([^"\r\n]+)"|filename=([^;\s]+)/i.exec(disposition);
    const name = unicode ? decodeURIComponent(unicode[1]) : plain && (plain[1] || plain[2]);
    if (!name || /[/\\\u0000-\u001f]/.test(name) || !name.toLowerCase().endsWith('.' + format)) throw C.failure('导出文件名不正确，已停止下载。');
    return name;
  }
  function PlanExportUI({ adapter, result, query, matched, disabled }) {
    const [format, setFormat] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [notice, setNotice] = React.useState('');
    const active = React.useRef(null);
    React.useEffect(() => () => { if (active.current) active.current.abort(); }, [adapter, result]);
    const reason = disabled || !result ? '先读取所选计划，才能导出当前内容。' : !result.data.plan.capabilities.export || typeof adapter.export !== 'function' ? '当前还不能导出所选计划。' : '';
    function cancel() { if (active.current) active.current.abort(); active.current = null; setBusy(false); setFormat(null); }
    async function download() {
      if (busy || reason) return;
      const controller = new AbortController(); active.current = controller; setBusy(true); setError(null); setNotice('');
      try {
        const scope = { format, snapshot_ref: result.meta.snapshot_ref };
        if (result.data.scope.range_start !== null) { scope.range_start = result.data.scope.range_start; scope.range_end = result.data.scope.range_end; }
        P.exportScope(result.data.plan.plan_ref, scope);
        const output = P.download(await adapter.export(result.data.plan.plan_ref, scope, controller.signal), format);
        if (controller.signal.aborted || active.current !== controller) return;
        if (!(output.blob instanceof Blob)) throw C.failure('导出附件不是有效文件。');
        const name = filename(output.disposition, format), url = URL.createObjectURL(output.blob), anchor = document.createElement('a');
        try { anchor.href = url; anchor.download = name; document.body.appendChild(anchor); anchor.click(); }
        finally { anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
        setNotice('已发起下载：' + name); setFormat(null);
      } catch (failure) { if (!controller.signal.aborted && active.current === controller) setError(failure); }
      finally { if (active.current === controller) { active.current = null; setBusy(false); } }
    }
    return <><Button transfer="export" reason={reason} busy={busy} onClick={() => { setFormat('csv'); setError(null); setNotice(''); }}>导出</Button>
      {notice && <span role="status" className="plan-muted">{notice}</span>}
      {format && result && <Modal title="导出计划" icon="download" onClose={cancel} footer={<>
        <Button onClick={cancel}>{busy ? '取消导出' : '取消'}</Button><Button transfer="export" className="btn primary" busy={busy} onClick={download}>下载 {format.toUpperCase()}</Button>
      </>}><div className="modal-b plan-export-summary">
        <window.PlanSegmentUI value={format} options={[["csv", "CSV"], ["xlsx", "XLSX"]]} label="计划导出格式" disabled={busy} onChange={setFormat} />
        <p><strong>{result.data.plan.display_name}</strong></p><p>导出时间范围：{M.timeLabel(result.data.time_scope.range_start)} → {M.timeLabel(result.data.time_scope.range_end)}（不含结束时刻）</p>
        <p>共 {result.data.task_count} 道工序安排，按当前读取的计划内容导出。</p>
        {query.trim() && <p className="plan-danger">搜索“{query}”找到 {matched} 道安排；本次导出包含所选时间范围的全部 {result.data.task_count} 道安排。</p>}
        <ErrorBox error={error} />
      </div></Modal>}
    </>;
  }
  window.PlanExportUI = PlanExportUI;
})();
