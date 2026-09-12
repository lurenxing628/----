(function () {
  'use strict';
  // Load after ResourceMaterialContract.js, ResourceMaterialPreview.jsx and ResourceForms.jsx.
  // The host supplies a stable files adapter; mounting does not submit writes.
  const C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, Icon, ErrorBox, Issues } = window.ResourceControls;
  const Feedback = window.ResourceForms.Feedback, Preview = window.ResourceMaterialPreview;
  function Format({ value, onChange, disabled }) {
    return <div className="rm-format"><span className="seclabel">文件格式</span><div className="seg" role="group" aria-label="文件格式">
      {['xlsx', 'csv'].map(format => <button key={format} type="button" disabled={disabled} className={value === format ? 'on' : ''} aria-pressed={value === format} onClick={() => onChange(format)}>{format === 'xlsx' ? 'Excel (.xlsx)' : 'CSV (.csv)'}</button>)}</div></div>;
  }
  function ExportOptions({ selection, setSelection, refs, disabled, label, kind }) {
    return <fieldset style={{ border: 0, margin: 0, padding: 0 }} disabled={disabled}><legend className="seclabel">导出范围</legend>
      {[['filtered', '当前筛选结果', '当前搜索与状态筛选下的全部记录，不限当前页'], ['all', '全部' + label, '忽略搜索与状态筛选，导出全部' + label + (kind === 'op_type' ? '，保留当前工种类别' : '')], ['selected', '已选' + label, refs.length + ' 条，包含非当前页或当前筛选外的选中记录']].map(([key, title, detail]) =>
        <label key={key} className={'iorow' + (selection === key ? ' on' : '')}><input type="radio" name={kind + '-export-scope'} value={key} checked={selection === key} onChange={() => setSelection(key)} />
          <div><div className="iotitle">{title}</div><div className="iosub">{detail}</div></div></label>)}</fieldset>;
  }
  function Actions({ adapter, mode, request, onClose, onCommitted, contract: M }) {
    const [original] = React.useState(() => ({ ...request, refs: Array.isArray(request.refs) ? request.refs.slice() : request.refs, scope: { ...request.scope } }));
    const [format, setFormat] = React.useState('xlsx'), [file, setFile] = React.useState(null), [selection, setSelection] = React.useState('');
    const [job, setJob] = React.useState(null), [error, setError] = React.useState(null), [acknowledged, setAcknowledged] = React.useState(false);
    const [download, setDownload] = React.useState({ busy: false, name: null }), [now, setNow] = React.useState(Date.now());
    const command = S.useCommand(adapter), notified = React.useRef(null), alive = React.useRef(true), downloadAbort = React.useRef(null);
    const category = command.intent ? command.intent.category : original.scope.category;
    const label = M.resourceLabel ? M.resourceLabel(category) : M.label;
    const effectiveMode = command.intent && ['sending', 'pending', 'checking', 'done'].includes(command.phase)
      ? ({ [M.kind + '_import']: 'import', [M.kind + '_bulk']: 'bulk' })[command.intent.kind] || mode : mode;
    const isExport = effectiveMode === 'export', done = command.phase === 'done', recovery = original.recovery === true;
    const query = S.useQuery(async signal => {
      if (typeof adapter.preview !== 'function') throw C.failure(label + '预检接口尚未接入。');
      let body;
      if (effectiveMode === 'import') {
        await M.validateFile(job.file, job.format);
        body = new FormData(); body.append('file', job.file); body.append('format', job.format); body.append('mode', 'upsert');
        if (M.kind === 'op_type') body.append('category', M.category(original));
      } else body = M.requestBody(effectiveMode, original, job.selection);
      const raw = await adapter.preview(M.paths[effectiveMode], body, signal);
      if (isExport) {
        const result = M.exportPreview(raw, job.selection, original);
        if (job.selection === 'selected' && result.data.row_count !== M.selection(original).length)
          throw C.failure('导出预览数量与明确选中的' + label + '不一致，未开始下载。');
        return result;
      }
      return M.preview(raw, effectiveMode, effectiveMode === 'import' ? job.format : M.selection(original), original);
    }, [adapter, job, effectiveMode, M], !!job);
    const result = query.result, data = result && result.data;
    const activeRead = !!job && query.loading;
    const controlsDisabled = command.locked || done || activeRead || download.busy;
    React.useEffect(() => () => { alive.current = false; if (downloadAbort.current) downloadAbort.current.abort(); }, []);
    React.useEffect(() => {
      if (!data) return undefined;
      const remaining = Date.parse(data.expires_at) - Date.now();
      if (remaining <= 0) { setNow(Date.now()); return undefined; }
      const timer = window.setTimeout(() => setNow(Date.now()), Math.min(remaining + 1, 2147483647));
      return () => window.clearTimeout(timer);
    }, [data]);
    React.useEffect(() => {
      if (!done || notified.current === command.intent.request_key) return;
      notified.current = command.intent.request_key;
      Promise.resolve().then(() => onCommitted(command.result)).catch(failure => {
        if (alive.current) setError(C.failure('服务器已确认提交，但列表刷新失败：' + C.message(failure)));
      });
    }, [done, command.intent, command.result, onCommitted]);
    function close() {
      if (command.locked) return;
      if (!command.reset()) return;
      if (downloadAbort.current) downloadAbort.current.abort();
      onClose();
    }
    function invalidate() { setJob(null); setAcknowledged(false); setError(null); setDownload({ busy: false, name: null }); }
    function chooseFormat(value) { if (!controlsDisabled) { invalidate(); setFormat(value); } }
    function chooseFile(files) {
      if (controlsDisabled) return;
      invalidate(); setFile(null);
      if (!files || files.length !== 1) { setError(C.failure('一次只能选择一个 CSV 或 XLSX 文件。')); return; }
      setFile(files[0]);
    }
    function preflight() {
      if (controlsDisabled || recovery) return;
      if (!command.reset()) return;
      setError(null); setAcknowledged(false); setDownload({ busy: false, name: null });
      if (effectiveMode === 'import' && !file) { setError(C.failure('请先选择文件。')); return; }
      if (isExport && !selection) { setError(C.failure('请先选择导出范围。')); return; }
      try {
        if (M.category) M.category(original);
        if (effectiveMode === 'bulk' && !M.selection(original).length) throw C.failure('未选中' + label + '，本次不会删除任何记录。');
        if (effectiveMode !== 'import') M.requestBody(effectiveMode, original, selection);
        setJob({ file, format, selection }); setNow(Date.now());
      } catch (failure) { setJob(null); setError(failure); }
    }
    const needsAcknowledgement = data && !isExport && (effectiveMode === 'bulk' || data.rows.some(row => row.requires_confirmation));
    const expired = data && now >= Date.parse(data.expires_at);
    let reason = isExport ? '' : M.blocked(result, M.source(original));
    if (expired) reason = '预览已过期，请重新预检。';
    if (needsAcknowledgement && !acknowledged && !reason) reason = '请先核对并勾选确认项。';
    if (command.phase === 'rejected') reason = '本次未提交，请重新预检后再确认。';
    function confirm() {
      if (controlsDisabled || reason || !data) return;
      command.submit(M.kind + (effectiveMode === 'import' ? '_import' : '_bulk'), 'confirm', data.preview_ref,
        data.write_context, { preview_ref: data.preview_ref }, M.category ? M.category(original) : undefined);
    }
    async function downloadFile(template) {
      if (controlsDisabled || !template && (!data || expired)) return;
      if (typeof adapter.download !== 'function') { setError(C.failure('文件下载接口尚未接入。')); return; }
      if (!template && !data.formats.includes(format)) { setError(C.failure('该导出预览不支持所选文件格式，请重新预检。')); return; }
      const controller = new AbortController(); downloadAbort.current = controller;
      setDownload({ busy: true, name: null }); setError(null);
      try {
        const scope = template ? { format } : { export_ref: data.export_ref, format };
        if (template && M.kind === 'op_type') scope.category = M.category(original);
        const response = await adapter.download(template ? M.paths.template : M.paths.download, scope, controller.signal);
        if (controller.signal.aborted || !alive.current) return;
        const name = await M.saveDownload(response, format, controller.signal);
        if (alive.current) setDownload({ busy: false, name });
      } catch (failure) { if (alive.current && !controller.signal.aborted) { setDownload({ busy: false, name: null }); setError(failure); } }
      finally { if (downloadAbort.current === controller) downloadAbort.current = null; }
    }
    const title = ({ import: '批量导入', export: '批量导出', bulk: '批量删除' }[effectiveMode] || '操作') + ' · ' + label;
    const refs = Array.isArray(original.refs) ? original.refs : [];
    return <div className={'plana rm-actions' + (data && !isExport ? ' rm-wide' : '')}><Preview.Styles />
      <Modal title={title} icon={effectiveMode === 'bulk' ? 'minus' : isExport ? 'file-output' : 'file-input'} onClose={close} locked={command.locked}
        footer={<><Button onClick={close} reason={command.locked ? '结果未核实，暂不能关闭。' : ''}>{done || download.name ? '完成' : '取消'}</Button>
          {!done && !command.locked && !recovery && <Button icon="check" onClick={preflight} busy={activeRead} disabled={download.busy}>{data || query.error || command.phase === 'rejected' ? '重新预检' : '开始预检'}</Button>}
          {isExport && data && <Button transfer="export" className="btn primary wb-action wb-primary" disabled={controlsDisabled} reason={expired ? '预览已过期，请重新预检。' : ''} onClick={() => downloadFile(false)}>下载文件</Button>}
          {!isExport && !done && data && <Button icon={effectiveMode === 'bulk' ? 'minus' : 'check'} className={'btn ' + (effectiveMode === 'bulk' ? 'danger' : 'primary wb-action wb-primary')} busy={command.locked} disabled={controlsDisabled} reason={reason} onClick={confirm}>{effectiveMode === 'bulk' ? '确认删除' : '确认导入'}</Button>}</>}>
        <div className="modal-b scroll rm-body">
          {!recovery && !command.intent && M.source(original) === 'demo' && <p role="status">当前为示例数据，不允许提交{label}变更。</p>}
          {!recovery && !command.intent && !M.source(original) && <p role="status">尚未读取生产资料，不能提交{label}变更。</p>}
          {recovery && !command.intent && !command.error && <p role="status">未读到原请求标识；未执行其他{label}操作。</p>}
          {!recovery && !done && !command.locked && effectiveMode === 'import' && !data && <div className="iopane on">
            <Format value={format} onChange={chooseFormat} disabled={controlsDisabled} />
            <div className="tmpl-row"><span className="tmpl-ico"><Icon name="file-input" /></span><div><div className="tmpl-t">{label}导入模板.{format}</div><div className="tmpl-s">{M.templateHint || '空白表头模板，不含示例物料'}</div></div><Button className="mini" transfer="template" disabled={controlsDisabled} onClick={() => downloadFile(true)}>下载模板</Button></div>
            <div className={'drop rm-upload' + (file ? ' has' : '')} aria-disabled={controlsDisabled} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); chooseFile(event.dataTransfer.files); }}>
              <div className="di"><Icon name="file-input" /></div><div className="dt">{file ? file.name : '选择 CSV / XLSX 文件'}</div><div className="ds">{file ? window.WorkbenchFormat.number(file.size, { digits: 0 }) + ' 字节 · 单次导入最多 2,000 行' : '单次导入最多 2,000 行'}</div>
              <input type="file" aria-label={'选择' + label + '导入文件'} accept=".csv,.xlsx" disabled={controlsDisabled} onChange={event => { chooseFile(event.target.files); event.target.value = ''; }} /></div>
            <p className="iohint">{M.importHint || <>按编号增量更新：已有编号更新，不存在则新增；不删除文件以外的物料。空白单元格保持原值；<code>{'\\N'}</code> 仅清空规格、单位或备注。</>}</p>
          </div>}
          {!done && !command.locked && effectiveMode === 'import' && data && <div className="tmpl-row"><span className="tmpl-ico"><Icon name="file-input" /></span>
            <div><div className="tmpl-t">{file && file.name}</div><div className="tmpl-s">{format.toUpperCase()} · 按编号增量更新 · {data.rows.length} 行</div></div><Button icon="file-input" disabled={controlsDisabled} onClick={invalidate}>更换文件</Button></div>}
          {!recovery && !done && !command.locked && isExport && <div className="iopane on"><ExportOptions selection={selection} setSelection={value => { invalidate(); setSelection(value); }} refs={refs} disabled={controlsDisabled} label={label} kind={M.kind} /><Format value={format} onChange={chooseFormat} disabled={controlsDisabled} /></div>}
          {!done && effectiveMode === 'bulk' && (!recovery || command.intent) && (recovery || command.intent && !job ? <p>正在核实先前的批量删除请求，当前列表的新选择尚未提交。</p> :
            <p>本次明确选中 <b>{refs.length}</b> 条{label}，包含非当前页或当前筛选外的选中项；不会扩展成筛选结果或全库删除。</p>)}
          {activeRead && <p role="status">正在读取完整预检结果，尚未写入数据…</p>}
          <ErrorBox error={error} /><ErrorBox error={query.error} /><Issues issues={result && result.warnings || []} />
          {data && !isExport && <><Preview data={data} mode={effectiveMode} contract={M} label={label} /><p className="iohint">本批整体确认；任意一行校验不通过，全部不写入。</p>
            {needsAcknowledgement && !done && <label className="rm-check"><input type="checkbox" checked={acknowledged} disabled={controlsDisabled} onChange={event => setAcknowledged(event.target.checked)} /><span>{effectiveMode === 'bulk' ? '已核对完整删除范围及明细，确认删除这些' + label + '。' : M.kind === 'material' ? '已核对被引用物料的修改前后内容，确认这些更新。' : '已核对关键字段及引用关系的修改前后内容，确认这些更新。'}</span></label>}
            {reason && !done && <p role="status">{reason}</p>}</>}
          {data && isExport && <p role="status">已核对导出范围：<b>{data.row_count}</b> 条 · {format.toUpperCase()}{expired ? ' · 预览已过期' : ''}</p>}
          {download.busy && <p role="status">正在读取下载文件…</p>}{download.name && <p role="status">已交给浏览器下载：<b>{download.name}</b></p>}
          {!isExport && <Feedback command={command} />}
          {command.intent && <window.WorkbenchReference entries={{ '请求编号': command.intent.request_key }} />}
          {done && <p role="status">{Number.isSafeInteger(command.result.data.deleted_count) ? '已删除 ' + command.result.data.deleted_count + ' 条。' : command.result.data.summary ? '导入结果已由服务器回执确认。' : '已取得原请求的完成回执。'}</p>}
        </div></Modal></div>;
  }
  window.ResourceFileActionFlow = Actions;
  window.ResourceMaterialActions = props => <Actions {...props} contract={window.APSResourceMaterial} />;
})();
