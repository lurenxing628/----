(function () {
  'use strict';
  const C = window.APSResourceContract, A = window.APSProcessActions, F = window.APSProcessFiles, S = window.APSResourceSession, M = window.APSResourceMaterial;
  const { Button, Modal, ErrorBox, Issues, Icon } = window.ResourceControls;
  function ProcessFileActions({ adapter, kind, mode, request, onClose, onCommitted, disabled = false }) {
    const [original] = React.useState(() => ({ ...request, scope: A.scope(request.scope), refs: request.refs && request.refs.slice() }));
    const [file, setFile] = React.useState(null), [format, setFormat] = React.useState('xlsx'), [selection, setSelection] = React.useState(original.target_ref ? 'explicit' : '');
    const [job, setJob] = React.useState(null), [error, setError] = React.useState(null), [discard, setDiscard] = React.useState(false);
    const [groups, setGroups] = React.useState([]), [now, setNow] = React.useState(Date.now());
    const [download, setDownload] = React.useState({ busy: false }), abort = React.useRef(null), alive = React.useRef(true), notified = React.useRef(null), checkedPreview = React.useRef(null);
    const command = S.useCommand(adapter), importing = mode === 'import', recovery = original.recovery === true;
    const label = kind === 'route' ? '工艺路线' : '工时定额';
    let saved = null, receiptError = null;
    if (command.phase === 'done') { try { saved = F.receipt(command.result, command.intent, kind, checkedPreview.current, original.target_ref); } catch (failure) { receiptError = failure; } }
    const visible = receiptError ? { ...command, phase: 'pending', locked: true, error: receiptError } : command, done = !!saved;
    const dirty = importing && !!file && !done, locked = visible.locked || download.busy;
    const query = S.useQuery(async signal => {
      let body;
      if (importing) {
        await M.validateFile(job.file, job.format);
        if (job.file.size > 16 * 1024 * 1024) throw C.failure('文件超过 16 MB，请缩小文件后再预检。');
        body = new FormData(); body.append('file', job.file); body.append('format', job.format); body.append('mode', 'upsert');
        if (original.target_ref) { if (!A.ref(original.target_ref)) throw C.failure('当前零件已无法核对，请返回列表重新选择。'); body.append('target_ref', original.target_ref); }
      } else body = F.exportBody(original, job.selection, job.format);
      const result = await adapter.filePreview(kind, mode, body, signal);
      return importing ? F.preview(result, kind, job.format, original) : F.exportPreview(result, kind, body);
    }, [adapter, job, kind, mode], !!job);
    const result = query.result, data = result && result.data, busy = !!job && query.loading;
    if (data && importing) checkedPreview.current = data;
    const controlsDisabled = disabled || locked || done || busy;
    React.useEffect(() => () => { alive.current = false; if (abort.current) abort.current.abort(); }, []);
    window.WorkbenchGuards.useDirtyGuard({ dirty, locked: visible.locked, message: label + '导入文件尚未保存，上次操作的结果也还没查到。' });
    React.useEffect(() => {
      if (!done || kind === 'hours' || notified.current === command.result.receipt_ref) return;
      notified.current = command.result.receipt_ref;
      if (onCommitted) onCommitted(command.result);
    }, [done, kind, command.result, onCommitted]);
    React.useEffect(() => {
      if (!data) return undefined;
      const timer = setTimeout(() => setNow(Date.now()), Math.max(0, Date.parse(data.expires_at) - Date.now() + 1));
      return () => clearTimeout(timer);
    }, [data]);
    function invalidate() { checkedPreview.current = null; setJob(null); setGroups([]); setError(null); setDownload({ busy: false }); }
    function close(force = false) {
      if (locked) return;
      if (dirty && !force) { setDiscard(true); return; }
      if (done && kind === 'hours' && notified.current !== command.result.receipt_ref) {
        notified.current = command.result.receipt_ref;
        if (onCommitted) onCommitted(command.result);
      }
      if (command.reset()) onClose();
    }
    function chooseFile(files) {
      if (controlsDisabled) return;
      invalidate(); setFile(null);
      if (!files || files.length !== 1) { setError(C.failure('一次只能选择一个 CSV 或 XLSX 文件。')); return; }
      setFile(files[0]);
    }
    function preflight() {
      if (controlsDisabled || recovery || !command.reset()) return;
      invalidate();
      if (typeof adapter.filePreview !== 'function') { setError(C.failure('dependency not wired: window.APSProcessAPI.filePreview')); return; }
      if (importing && !file) { setError(C.failure('请先选择文件。')); return; }
      if (!importing && !selection) { setError(C.failure('请先选择导出范围。')); return; }
      setJob({ file, format, selection }); setNow(Date.now());
    }
    let reason = importing ? A.blocked(result, original.source, F.operation(kind)) : '';
    if (data && now >= Date.parse(data.expires_at)) reason = '预检已过期，请重新预检。';
    if (data && importing && !reason) { try { F.confirmInput(data, groups, data.zero_review_required); } catch (failure) { reason = C.message(failure); } }
    if (command.phase === 'rejected') reason = '本次未导入，请重新预检后再确认。';
    function confirm() {
      if (!importing || controlsDisabled || recovery || !data || reason) return;
      try { command.submit('process_' + kind + '_import', 'confirm', data.preview_ref, data.write_context, F.confirmInput(data, groups, data.zero_review_required)); }
      catch (failure) { setError(failure); }
    }
    async function downloadFile(template) {
      if (controlsDisabled || !template && (!data || reason)) return;
      if (typeof adapter.fileDownload !== 'function') { setError(C.failure('dependency not wired: window.APSProcessAPI.fileDownload')); return; }
      if (!template && data.format !== format) { setError(C.failure('当前导出格式已变化，请重新预检。')); return; }
      const controller = new AbortController(); abort.current = controller; setDownload({ busy: true }); setError(null);
      try {
        const response = await adapter.fileDownload(kind, template, template ? { format } : { export_ref: data.export_ref }, controller.signal);
        if (!controller.signal.aborted && alive.current) {
          const name = await M.saveDownload(response, format, controller.signal);
          if (alive.current) setDownload({ busy: false, name });
        }
      } catch (failure) { if (alive.current && !controller.signal.aborted) { setError(failure); setDownload({ busy: false }); } }
      finally { if (abort.current === controller) abort.current = null; }
    }
    const allSkipped = data && importing && kind === 'hours' && data.skipped_count === data.rows.length;
    return <div className={'plana rm-actions' + ((data || saved) && importing ? ' rm-wide' : '')}><window.ResourceMaterialPreview.Styles />
      <Modal title={(importing ? '导入' : '导出') + label} icon={importing ? 'file-input' : 'file-output'} locked={locked} suspended={discard} onClose={() => close()}
        footer={<><Button disabled={locked} onClick={() => close()}>{done || !importing && download.name ? '完成' : '取消'}</Button>
          {!done && !recovery && <Button icon="check" disabled={disabled || locked} busy={busy} onClick={preflight}>{job ? '重新预检' : '开始预检'}</Button>}
          {!done && !recovery && data && <Button transfer={importing ? 'import' : 'export'} className="btn primary" disabled={controlsDisabled} reason={reason} onClick={importing ? confirm : () => downloadFile(false)}>{importing ? allSkipped ? '确认跳过并记录结果' : data.zero_review_required ? '按 0 导入' : '确认导入' : '下载文件'}</Button>}</>}>
        <div className="modal-b scroll rm-body">
          {recovery && !done && <p>正在查询上次导入结果，请稍候。</p>}
          {!recovery && !done && <><div className="rm-format"><span className="seclabel">文件格式</span><div className="seg" role="group" aria-label="文件格式">{['xlsx', 'csv'].map(value => <button type="button" key={value} className={format === value ? 'on' : ''} aria-pressed={format === value} disabled={controlsDisabled} onClick={() => { invalidate(); setFormat(value); }}>{value === 'xlsx' ? 'Excel (.xlsx)' : 'CSV (.csv)'}</button>)}</div></div>
            {importing ? <><div className="tmpl-row"><span className="tmpl-ico"><Icon name="file-input" /></span><div className="tmpl-t">{label}空白模板.{format}</div><Button transfer="template" disabled={controlsDisabled} onClick={() => downloadFile(true)}>下载模板</Button></div>
              <div className="field full"><label>{label}文件<input type="file" aria-label={'选择' + label + '文件'} accept=".csv,.xlsx" disabled={controlsDisabled} onChange={event => { chooseFile(event.target.files); event.target.value = ''; }} /></label>{file && <span className="fhint">{file.name} · {file.size} 字节</span>}</div>
              {original.target_ref && <p>导入范围：当前零件。</p>}</> : <fieldset disabled={controlsDisabled} style={{ border: 0, padding: 0, margin: 0 }}><legend className="seclabel">导出范围</legend>
                {(original.target_ref ? [['explicit', '当前零件']] : [['filtered', '当前筛选结果（全部页）'], ['all', '全部零件'], ['explicit', '已选零件（含其他页）']]).map(([value, title]) => <label key={value} className={'iorow' + (selection === value ? ' on' : '')}><input type="radio" name="process-export-selection" checked={selection === value} onChange={() => { invalidate(); setSelection(value); }} /><span className="iotitle">{title}</span></label>)}</fieldset>}</>}
          {busy && <p role="status">正在预检，尚未修改零件…</p>}<ErrorBox error={error} /><ErrorBox error={query.error} /><Issues issues={result && result.warnings || []} />
          {data && importing && !done && <><p className="iohint">{data.instructions}</p><window.ProcessFilePreview data={data} groups={groups} onGroups={setGroups} disabled={controlsDisabled} />
            {data.zero_review_required && <p className="process-zero-impact" role="status">以下工序的单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长：{data.rows.filter(row => row.requires_confirmation && row.after && row.after.unit_hours === 0).map(row => row.business_code + ' / 工序 ' + row.sequence).join('、')}。点击“按 0 导入”保存这些数值。</p>}
            <p>{kind === 'hours' ? '锁定跳过行不参与写入；其余行整体确认，任何一行不能提交，本批全部不修改。' : '本批整体确认；任何一行不能提交，本批全部不修改。'}</p></>}
          {data && !importing && <p role="status">已核对 {data.part_count} 个零件，导出 {data.row_count} 行{kind === 'hours' ? '工序记录' : '零件记录'}，不限当前显示页。</p>}
          {reason && data && !done && <p role="status">{reason}</p>}{download.name && <p role="status">已开始下载：{download.name}</p>}
          {importing && <window.ResourceForms.Feedback command={done && kind === 'hours' ? { ...visible, phase: 'idle' } : visible} />}
          {done && kind === 'hours' && <window.ProcessFileReceipt data={saved} />}
          {done && <p role="status">{kind === 'hours' ? '导入已完成，请继续确认工时。' : '导入已完成，请刷新资料。'}</p>}
        </div></Modal>
      {discard && <Modal title="放弃本次文件导入？" icon="file-input" onClose={() => setDiscard(false)} footer={<><Button onClick={() => setDiscard(false)}>继续核对</Button><Button className="btn danger" onClick={() => close(true)}>放弃导入并关闭</Button></>}><div className="modal-b">当前选择的文件与未提交的确认项将被丢弃。</div></Modal>}
    </div>;
  }
  window.ProcessFileActions = ProcessFileActions;
})();
