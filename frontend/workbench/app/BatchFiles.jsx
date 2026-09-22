(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, T = window.WorkbenchTerms, { Button, Modal, ErrorBox, Issues, Icon } = window.ResourceControls;
  const TEMPLATE_NAME = '批次导入模板.xlsx', EXPORT_NAME = '批次清单.xlsx';
  function saveDownload(download, filename) {
    if (!download || !download.blob || !download.blob.size) throw C.failure('未收到有效下载文件。');
    const url = URL.createObjectURL(download.blob), link = document.createElement('a');
    link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  function PreviewRow({ row }) {
    const names = { quantity: '数量', due_date: '交期', priority: '优先级', ready_status: '齐套', ready_date: '齐套日期', remark: '备注' };
    return <tr><td>{row.row} · {row.business_code}</td><td>{({ create: '新增', update: '更新', skipped: '跳过', rejected: '拒绝' })[row.action]}</td>
      <td>{row.errors.length ? row.errors.join('；') : row.input && <div>{B.fields.filter(key => key in row.input.fields).map(key =>
        <div key={key}>{names[key]}：{window.BatchControls.display(key, row.before && row.before.fields[key])} → {window.BatchControls.display(key, row.input.fields[key])}</div>)}</div>}</td></tr>;
  }
  function BatchFiles({ adapter, mode: operation, scope, selected, snapshot, command, onClose, onCommitted, disabled }) {
    const [mode, setMode] = React.useState('overwrite'), [file, setFile] = React.useState(null), [preview, setPreview] = React.useState(null), [acknowledged, setAcknowledged] = React.useState(false);
    const [selection, setSelection] = React.useState(selected.length ? 'selected' : 'filtered');
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [notice, setNotice] = React.useState('');
    const serial = React.useRef(0), alive = React.useRef(true), seen = React.useRef(null), form = React.useId();
    const importing = operation === 'import', done = command.phase === 'done', locked = disabled || command.locked || busy || done;
    // 已选文件或已有预检结果就算没做完：关闭前先确认，避免误关丢掉文件和预检。
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: importing && !done && (!!file || !!preview), locked: command.locked || busy,
      message: '批次导入还没有完成，离开会放弃已选文件和预检结果。' });
    React.useEffect(() => () => { alive.current = false; serial.current++; }, []);
    React.useEffect(() => {
      if (!importing || !done || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, 'import_confirm', preview && preview.preview_ref); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (error) { setError(error); }
    }, [done, command.result]);
    function invalidate() { setPreview(null); setError(null); setAcknowledged(false); serial.current++; }
    function changeMode(value) { setMode(value); invalidate(); }
    function chooseFile(list) { setFile(list && list[0] || null); invalidate(); }
    async function close(detail) {
      if (command.locked || busy) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner) && !await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) return;
      onClose();
    }
    async function work(action) {
      if (locked) return;
      const id = ++serial.current; setBusy(true); setError(null); setNotice('');
      try {
        if (action === 'template') { saveDownload(await adapter.downloadTemplate(), TEMPLATE_NAME); if (alive.current && id === serial.current) setNotice(T.download_started(TEMPLATE_NAME)); }
        else if (action === 'preview') {
          const result = await adapter.importPreview(file, mode, scope, snapshot);
          const data = result && result.data;
          if (!data || data.operation !== 'batch.import_confirm' || data.mode !== mode || !Array.isArray(data.rows) || !Array.isArray(data.deleted)
              || typeof data.can_confirm !== 'boolean' || data.can_confirm && (!data.write_context || !B.context(data.write_context))) throw C.failure('读到的导入预检结果不完整，没有写入批次。请再点一次「开始预检」。');
          if (alive.current && id === serial.current) setPreview(data);
        } else {
          const result = await adapter.exportPreview(selection, { ...scope, snapshot_ref: snapshot }, selected);
          if (!result.data || typeof result.data.export_ref !== 'string' || !Number.isSafeInteger(result.data.count)) throw C.failure('导出范围没有确认，文件没有生成。请刷新批次列表后重试。');
          const downloaded = await adapter.downloadExport(result.data.export_ref); saveDownload(downloaded, EXPORT_NAME);
          if (alive.current && id === serial.current) setNotice(T.download_started(EXPORT_NAME) + '（共 ' + window.WorkbenchFormat.number(result.data.count, { digits: 0 }) + ' 个批次）');
        }
      } catch (error) { if (alive.current && id === serial.current) setError(error); }
      finally { if (alive.current && id === serial.current) setBusy(false); }
    }
    // 「先清除全部批次再重导」会删掉表格以外的所有批次：主按钮按危险动作着色，且必须先核对勾选。
    const replacing = mode === 'replace', replaceReason = replacing && !acknowledged ? '请先核对将删除的全部批次，并勾选确认。' : '';
    return <div className={'plana rm-actions' + (preview ? ' rm-wide' : '')}>
      <Modal title={importing ? '批量导入批次' : '导出批次清单'} icon="box" locked={command.locked || busy} guardOwner={guardOwner} onClose={close} footer={<>
        <Button onClick={() => close()} disabled={command.locked || busy}>{done ? '关闭' : '取消'}</Button>
        {importing ? !done && <>{!preview ? <Button transfer="import" disabled={locked || !file} onClick={() => work('preview')}>开始预检</Button>
          : <Button transfer="import" className={'btn ' + (replacing ? 'danger' : 'primary')} disabled={locked || !preview.can_confirm} reason={replaceReason}
            onClick={() => command.submit('batch', 'import_confirm', preview.preview_ref, preview.write_context, { preview_ref: preview.preview_ref })}>确认导入</Button>}</>
          : <Button transfer="export" disabled={locked || selection === 'selected' && !selected.length} onClick={() => work('export')}>下载批次清单</Button>}
      </>}><div className="modal-b form"><ErrorBox error={error} />{notice && <p role="status">{notice}</p>}
        {importing ? <>
          <div className="tmpl-row"><span className="tmpl-ico"><Icon name="file-input" /></span><div><div className="tmpl-t">{TEMPLATE_NAME}</div><div className="tmpl-s">空白表头模板，不含示例批次</div></div><Button className="mini" transfer="template" disabled={locked} onClick={() => work('template')}>下载模板</Button></div>
          <div className="batch-fields" style={{ marginTop: 16 }}><window.BatchControls.Field label="导入模式"><select value={mode} disabled={locked} onChange={event => changeMode(event.target.value)}>
            <option value="overwrite">已有批次就更新，没有的就新增</option><option value="append">只新增没有的批次（已有的跳过）</option><option value="replace">先清除全部批次，再按表格重导</option>
          </select></window.BatchControls.Field></div>
          {!preview && <div className={'drop rm-upload' + (file ? ' has' : '')} aria-disabled={locked} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!locked) chooseFile(event.dataTransfer.files); }}>
            <div className="di"><Icon name="file-input" /></div><div className="dt">{file ? file.name : '选择 XLSX 文件'}</div>
            <div className="ds">{file ? window.WorkbenchFormat.number(file.size, { digits: 0 }) + ' 字节 · 只接受 .xlsx 文件' : '只接受 .xlsx 文件，也可以把文件拖到这里'}</div>
            <input type="file" aria-label="选择文件" accept=".xlsx" disabled={locked} onChange={event => { chooseFile(event.target.files); event.target.value = ''; }} /></div>}
          <p className="iohint">新批次导入后需生成工序；更新时空白单元格保留原值。</p>
          {preview && <><div className="tmpl-row"><span className="tmpl-ico"><Icon name="file-input" /></span><div><div className="tmpl-t">{file && file.name}</div>
              <div className="tmpl-s">{window.WorkbenchFormat.number(preview.count, { digits: 0 })} 行 · {preview.can_confirm ? '全部核对通过，一起保存' : '存在未通过检查的行，请修正'}</div></div>
            <Button icon="file-input" onClick={invalidate} disabled={locked}>更换文件</Button></div>
            <div className="batch-preview wb-table-frame" data-sticky-head><table className="tbl wb-table" aria-label="批次导入预检"><caption className="wb-visually-hidden">批次导入预检</caption><thead><tr><th scope="col">行号 / 批次</th><th scope="col">操作</th><th scope="col">核对内容</th></tr></thead><tbody>
              {preview.rows.map(row => <PreviewRow key={row.row} row={row} />)}
            </tbody></table></div>
            {preview.deleted.length > 0 && <div><h3>将删除的全部批次</h3>{preview.deleted.map(row => <div key={row.entity_ref}>{row.before.business_code} · {row.before.operations.length} 道工序{row.errors.length ? ' · ' + row.errors.join('；') : ''}</div>)}</div>}
            <Issues issues={preview.warnings} />
            {replacing && !done && <label className="rm-check"><input type="checkbox" checked={acknowledged} disabled={locked} onChange={event => setAcknowledged(event.target.checked)} /><span>已核对将删除的全部批次和导入明细，确认先清除再重导。</span></label>}</>}
        </> : <div className="batch-value-list"><label><input type="radio" name={form} checked={selection === 'selected'} disabled={locked || !selected.length} onChange={() => setSelection('selected')} />导出选中 {selected.length} 个批次（含隐藏选中项）</label>
          <label><input type="radio" name={form} checked={selection === 'filtered'} disabled={locked} onChange={() => setSelection('filtered')} />导出当前筛选全部批次</label></div>}
        <window.ResourceForms.Feedback command={command} />
      </div></Modal></div>;
  }
  window.BatchFiles = BatchFiles;
})();
