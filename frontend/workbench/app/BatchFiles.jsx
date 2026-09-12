(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
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
    const [mode, setMode] = React.useState('overwrite'), [file, setFile] = React.useState(null), [preview, setPreview] = React.useState(null);
    const [selection, setSelection] = React.useState(selected.length ? 'selected' : 'filtered');
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [notice, setNotice] = React.useState('');
    const serial = React.useRef(0), alive = React.useRef(true), seen = React.useRef(null), form = React.useId();
    const importing = operation === 'import', done = command.phase === 'done', locked = disabled || command.locked || busy || done;
    React.useEffect(() => () => { alive.current = false; serial.current++; }, []);
    React.useEffect(() => {
      if (!importing || !done || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, 'import_confirm', preview && preview.preview_ref); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (error) { setError(error); }
    }, [done, command.result]);
    function changeMode(value) { setMode(value); setPreview(null); setError(null); serial.current++; }
    async function work(action) {
      if (locked) return;
      const id = ++serial.current; setBusy(true); setError(null); setNotice('');
      try {
        if (action === 'template') saveDownload(await adapter.downloadTemplate(), 'batches-template.xlsx');
        else if (action === 'preview') {
          const result = await adapter.importPreview(file, mode, scope, snapshot);
          const data = result && result.data;
          if (!data || data.operation !== 'batch.import_confirm' || data.mode !== mode || !Array.isArray(data.rows) || !Array.isArray(data.deleted)
              || typeof data.can_confirm !== 'boolean' || data.can_confirm && (!data.write_context || !B.context(data.write_context))) throw C.failure('文件预览资料不完整，请重新读取。');
          if (alive.current && id === serial.current) setPreview(data);
        } else {
          const result = await adapter.exportPreview(selection, { ...scope, snapshot_ref: snapshot }, selected);
          if (!result.data || typeof result.data.export_ref !== 'string' || !Number.isSafeInteger(result.data.count)) throw C.failure('导出范围未能核实。');
          const downloaded = await adapter.downloadExport(result.data.export_ref); saveDownload(downloaded, 'batches.xlsx');
          if (alive.current) setNotice('已生成 ' + result.data.count + ' 个批次的清单。');
        }
      } catch (error) { if (alive.current && id === serial.current) setError(error); }
      finally { if (alive.current && id === serial.current) setBusy(false); }
    }
    return <Modal title={importing ? '批量维护批次' : '导出批次清单'} icon="box" locked={command.locked || busy} onClose={onClose} footer={<>
      <Button onClick={onClose} disabled={command.locked || busy}>{done ? '关闭' : '取消'}</Button>
      {importing ? !done && <>{!preview ? <Button transfer="import" disabled={locked || !file} onClick={() => work('preview')}>预览导入</Button>
        : <Button transfer="import" className="btn primary" disabled={locked || !preview.can_confirm} onClick={() => command.submit('batch', 'import_confirm', preview.preview_ref, preview.write_context, { preview_ref: preview.preview_ref })}>确认导入</Button>}</>
        : <Button transfer="export" disabled={locked || selection === 'selected' && !selected.length} onClick={() => work('export')}>下载批次清单</Button>}
    </>}><div className="modal-b form"><ErrorBox error={error} />{notice && <p role="status">{notice}</p>}
      {importing ? <><Button transfer="template" disabled={locked} onClick={() => work('template')}>下载批次模板</Button>
        <div className="batch-fields" style={{ marginTop: 16 }}><window.BatchControls.Field label="导入模式"><select value={mode} disabled={locked} onChange={event => changeMode(event.target.value)}>
          <option value="overwrite">已有批次就更新，没有的就新增</option><option value="append">只新增没有的批次（已有的跳过）</option><option value="replace">先清空全部批次，再按表格重导</option>
        </select></window.BatchControls.Field><window.BatchControls.Field label="选择 Excel 文件"><input type="file" accept=".xlsx" disabled={locked} onChange={event => { setFile(event.target.files[0] || null); setPreview(null); setError(null); serial.current++; }} /></window.BatchControls.Field></div>
        <p>新建批次不自动生成工序；已有批次的空单元格不覆盖。确认前不会新增、更新或删除批次。</p>
        {preview && <><p>{preview.count} 行 · {preview.can_confirm ? '全部核对通过，一起保存' : '存在拒绝行，本批不会写入'}</p><div className="batch-preview wb-table-frame" data-sticky-head><table className="tbl wb-table" aria-label="批次导入预览"><caption className="wb-visually-hidden">批次导入预览</caption><thead><tr><th scope="col">行号 / 批次</th><th scope="col">操作</th><th scope="col">核对内容</th></tr></thead><tbody>
          {preview.rows.map(row => <PreviewRow key={row.row} row={row} />)}
        </tbody></table></div>{preview.deleted.length > 0 && <div><h3>将删除的全部批次</h3>{preview.deleted.map(row => <div key={row.entity_ref}>{row.before.business_code} · {row.before.operations.length} 道工序{row.errors.length ? ' · ' + row.errors.join('；') : ''}</div>)}</div>}
          <Issues issues={preview.warnings} /><Button onClick={() => setPreview(null)} disabled={locked}>返回核对文件</Button></>}
      </> : <div className="batch-value-list"><label><input type="radio" name={form} checked={selection === 'selected'} disabled={locked || !selected.length} onChange={() => setSelection('selected')} />导出选中 {selected.length} 个批次（含隐藏选中项）</label>
        <label><input type="radio" name={form} checked={selection === 'filtered'} disabled={locked} onChange={() => setSelection('filtered')} />导出当前筛选全部批次</label></div>}
      <window.ResourceForms.Feedback command={command} />
    </div></Modal>;
  }
  window.BatchFiles = BatchFiles;
})();
