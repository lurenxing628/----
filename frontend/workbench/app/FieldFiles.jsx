(function () {
  'use strict';
  const C = window.FieldContract, { Button, Modal, ErrorBox, Feedback } = window.FieldControls;
  function FieldFiles({ adapter, scope, snapshot, command, onClose, onDone }) {
    const [file, setFile] = React.useState(null), [preview, setPreview] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const input = React.useRef(null), active = React.useRef(true), controller = React.useRef(null);
    React.useEffect(() => () => { active.current = false; if (controller.current) controller.current.abort(); }, []);
    const locked = busy || command.locked || command.phase === 'done';
    async function run(action) {
      setError(null); setBusy(true); controller.current = new AbortController();
      try {
        if (action === 'preview') {
          if (!file || !/\.xlsx$/i.test(file.name) || file.size > 8 * 1024 * 1024) throw window.APSResourceContract.failure('请选择不超过 8 MB 的 XLSX 文件。');
          const value = C.query(await adapter.previewFile(file, scope, snapshot, controller.current.signal), 'preview').data;
          if (active.current) setPreview(value);
        } else if (action === 'errors') C.saveFile(await adapter.downloadErrors(preview.preview_ref, controller.current.signal), '报工导入问题.xlsx');
        else C.saveFile(await adapter.download(action, scope, snapshot, controller.current.signal), action === 'template' ? '现场分次报工模板.xlsx' : '现场报工导出.xlsx');
      } catch (error) { if (active.current) setError(error); }
      finally { if (active.current) setBusy(false); }
    }
    return <Modal title="报工文件" icon="file-input" locked={busy || command.locked} onClose={onClose} footer={<>
      <Button onClick={onClose} disabled={busy || command.locked}>{command.phase === 'done' ? '关闭' : '取消'}</Button>
      {!preview && <Button icon="search" disabled={locked || !file} onClick={() => run('preview')}>预检文件</Button>}
      {preview && command.phase !== 'done' && <Button transfer="import" className="btn primary" disabled={locked || !preview.can_confirm} reason={preview.can_confirm ? C.blocked(preview.write_context, 'import_confirm') : '文件存在问题，未写入任何报工。'}
        onClick={() => command.submit('execution', 'import_confirm', preview.preview_ref, preview.write_context, { preview_ref: preview.preview_ref })}>确认导入</Button>}</>}>
      <div className="modal-b"><div className="field-toolbar" style={{ padding: '0 0 14px' }}><Button transfer="template" disabled={locked} onClick={() => run('template')}>下载模板</Button><Button transfer="export" disabled={locked} onClick={() => run('export')}>导出当前范围</Button></div>
        <div className="field-note">XLSX · 13 列 · 任务编号、工序范围、单件编号已预填，不可修改 · 兼容旧 10 列</div>
        <div className="field-upload"><Button icon="folder-open" disabled={locked} onClick={() => input.current.click()}>选择 Excel 文件</Button><span>{file ? file.name : '尚未选择文件'}</span>
          <input ref={input} hidden type="file" accept=".xlsx" aria-label="报工 XLSX 文件" disabled={locked} onChange={event => { setFile(event.target.files[0] || null); setPreview(null); setError(null); }} /></div>
        {busy && <p role="status">正在核对文件和现场记录…</p>}
        {preview && <><div className="field-files-summary">{[['total', '行数'], ['changed', '变更'], ['unchanged', '重复'], ['blank', '空白'], ['rejected', '问题']].map(([key, label]) => <span key={key}>{label} <b>{preview.summary[key] || 0}</b></span>)}</div>
          <p role="status">{preview.can_confirm ? '预检通过，尚未写入报工。' : preview.summary.rejected ? '预检未通过，未写入任何报工。' : '没有可导入的实际记录，未写入报工。'}</p>
          <div className="field-scroll wb-table-frame" data-sticky-head tabIndex="0" aria-label="文件预检表格滚动区"><table className="field-table wb-table" aria-label="文件逐行预检"><caption className="wb-visually-hidden">当前文件逐行预检结果</caption><thead><tr><th scope="col">Excel 行号</th><th scope="col">处理结果</th><th scope="col">问题</th></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}><td>{row.row_number || row.row}</td><td>{({ create: '新增', supplement: '补齐', unchanged: '重复', blank: '空白', rejected: '拒绝', committed: '将变更', pending: '未执行' })[row.result] || '待核对'}</td><td>{(row.errors || []).map(item => item.message).join('；')}</td></tr>)}</tbody></table></div>
          {preview.summary.rejected > 0 && <Button transfer="export" disabled={locked} onClick={() => run('errors')}>下载问题清单</Button>}
          {!locked && <Button icon="refresh-cw" onClick={() => { setPreview(null); run('preview'); }}>重新预检原文件</Button>}</>}
        <ErrorBox error={error} /><Feedback command={command} onDone={onDone} />
      </div>
    </Modal>;
  }
  window.FieldFiles = FieldFiles;
})();
