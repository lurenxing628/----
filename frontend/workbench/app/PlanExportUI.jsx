import React from './shared/runtime/react.js';
import ResourceControls from './ResourceControls.jsx';
import PlanGanttModel from './PlanGanttModel.js';
import APSPlanAPI from './PlanAPI.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { PlanSegmentUI } from './PlanGantt.jsx';

const { Button, Modal, ErrorBox } = ResourceControls;
const M = PlanGanttModel;
function PlanExportUI({ result, query, matched, disabled }) {
  const [format, setFormat] = React.useState(null), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [notice, setNotice] = React.useState('');
  const active = React.useRef(null);
  React.useEffect(() => () => { if (active.current) active.current.abort(); }, [result]);
  const reason = disabled || !result ? '先读取所选计划，才能导出当前内容。' : !result.data.plan.capabilities.export ? '当前还不能导出所选计划。' : '';
  function cancel() { if (active.current) active.current.abort(); active.current = null; setBusy(false); setFormat(null); }
  async function download() {
    if (busy || reason) return;
    const controller = new AbortController(); active.current = controller; setBusy(true); setError(null); setNotice('');
    try {
      const scope = { format, snapshot_ref: result.meta.snapshot_ref };
      if (result.data.scope.range_start !== null) { scope.range_start = result.data.scope.range_start; scope.range_end = result.data.scope.range_end; }
      // APSPlanAPI.export 校验导出范围与下载文件名（PlanContract.exportScope / download）。
      const output = await APSPlanAPI.export(result.data.plan.plan_ref, scope, controller.signal);
      if (controller.signal.aborted || active.current !== controller) return;
      APSWorkbenchTransport.saveBlob(output.filename, output.blob);
      setNotice(WorkbenchTerms.download_started(output.filename)); setFormat(null);
    } catch (failure) { if (!controller.signal.aborted && active.current === controller) setError(failure); }
    finally { if (active.current === controller) { active.current = null; setBusy(false); } }
  }
  return <><Button transfer="export" reason={reason} busy={busy} onClick={() => { setFormat('csv'); setError(null); setNotice(''); }}>导出</Button>
    {notice && <span role="status" className="plan-muted">{notice}</span>}
    {format && result && <Modal title="导出计划" icon="download" onClose={cancel} footer={<>
      <Button onClick={cancel}>{busy ? '取消导出' : '取消'}</Button><Button transfer="export" className="btn primary" busy={busy} onClick={download}>下载 {format.toUpperCase()}</Button>
    </>}><div className="modal-b plan-export-summary">
      <PlanSegmentUI value={format} options={[["csv", "CSV"], ["xlsx", "XLSX"]]} label="计划导出格式" disabled={busy} onChange={setFormat} />
      <p><strong>{result.data.plan.display_name}</strong></p><p>{M.scopeCaption(result.data)}</p>
      <p>共 {result.data.task_count} 道工序安排，按当前读取的计划内容导出。</p>
      {query.trim() && <p className="plan-danger">搜索“{query}”找到 {matched} 道安排；本次导出包含所选时间范围的全部 {result.data.task_count} 道安排。</p>}
      <ErrorBox error={error} />
    </div></Modal>}
  </>;
}
export { PlanExportUI };
export default PlanExportUI;
