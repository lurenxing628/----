(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls, { hours } = window.CalibrationControls;
  const scope = '已有批次工时、历史计划和执行记录保持原样。新批次使用前，须在基础资料重新确认模板工时。';
  function Facts({ row }) {
    return <dl className="cad-facts"><div><dt>模板工序</dt><dd>{row.part_no} · {row.sequence} {row.operation_label}</dd></div>
      <div><dt>模板修订</dt><dd>{row.template_revision}</dd></div><div><dt>旧定额</dt><dd>{hours(row.old_unit_hours)} / 件</dd></div>
      <div><dt>建议定额</dt><dd>{hours(row.suggested_unit_hours, '暂无建议')} / 件</dd></div>
      <div><dt>合格样本</dt><dd>{row.sample_count} 个</dd></div><div><dt>未选用实例</dt><dd>{row.excluded_count} 个</dd></div></dl>;
  }
  function Samples({ preview, detail }) {
    const rows = preview.samples;
    return <section className="cad-samples" aria-label="采用预览样本"><h4>本次采用的合格样本（{rows.length}）</h4>
      <table className="ca-table"><thead><tr><th>批次 / 工序</th><th>数量</th><th>加工小时</th><th>单件 h</th><th>来源与修订</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.sample_ref} data-adoption-sample={row.sample_ref}><td>{row.batch_code}<small>{row.operation_code}</small></td>
          <td>{row.completed_quantity}</td><td>{row.effective_processing_hours}</td><td>{row.unit_hours}</td>
          <td><details><summary>模板修订 {row.template_revision}</summary><div>实例：{row.sample_ref}</div><div>复制证据：{row.lineage_evidence_ref}</div><div>样本修订：{row.sample_revision}</div></details></td></tr>)}</tbody></table>
      {detail && <details className="cad-records"><summary>排除与未关联实例（{detail.samples.filter(row => !row.selected).length}）</summary>
        {detail.samples.filter(row => !row.selected).map(row => <div key={row.sample_ref}>{row.batch_code} · {row.template_operation_ref === null ? '未关联' : '已排除'}：
          {row.exclusion_reasons.map(item => item.message).join('；')}</div>)}</details>}</section>;
  }
  function Receipt({ value }) {
    const d = value.data;
    return <section aria-label="采用锁定回执"><p className="cad-success" role="status">已核实采用，新定额 {hours(d.new_unit_hours)} / 件，模板定额已锁定。</p>
      <dl className="cad-facts">{[['原定额', hours(d.old_unit_hours)], ['新定额', hours(d.new_unit_hours)], ['修订变化', d.template_revision_before + ' → ' + d.template_revision_after],
        ['采用时间', d.adopted_at], ['声明人', d.declared_operator], ['本机操作者', d.application_operator], ['采用原因', d.reason], ['用户确认', d.confirmed ? '已明确确认' : '未确认']].map(([label, value]) =>
        <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <p className="ca-muted">这是本次提交的持久回执。{scope}</p><div className="cad-records">回执：{value.receipt_ref}<br />采纳记录：{d.adoption_ref}</div></section>;
  }
  function Dialog({ session: s, detail, stale, onRefresh }) {
    const { saved, preview } = s, pending = saved && saved.phase === 'pending', result = saved && saved.phase === 'committed' ? saved.receipt : null;
    const other = saved && detail && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref;
    const row = saved ? saved.baseline : detail && detail.suggestion;
    const blocked = stale || other || !!s.storageError || !detail;
    const refresh = () => { s.setConsent(false); s.change(s.draft); if (typeof onRefresh === 'function') onRefresh(); };
    return <Modal title={result ? '模板采用与锁定回执' : pending ? '核实原采纳请求' : '预览并采用模板定额'} icon="check" onClose={s.close}
      footer={<><Button onClick={s.close}>{pending ? '关闭并保留请求' : '关闭'}</Button>
        {result ? <Button icon="check" onClick={s.finish}>完成核实</Button> : pending ? <Button icon="refresh-cw" busy={s.busy} onClick={s.lookup}>查询原请求</Button> : <>
          {saved && <Button disabled={s.busy || !!s.storageError} onClick={s.finish}>结束本次未采用</Button>}
          <Button icon="refresh-cw" disabled={s.busy || typeof onRefresh !== 'function'} onClick={refresh}>明确刷新所选记录</Button>
          <Button icon="search" busy={s.busy} disabled={blocked} onClick={s.inspect}>读取真实预览</Button>
          <Button icon="check" className="btn primary" busy={s.busy} disabled={blocked || !preview || !preview.validation.can_adopt || !s.consent} onClick={s.submit}>确认采用并锁定</Button></>}</>}>
      <div className="modal-body cad-body">
        {(s.error || s.storageError) && <p className="cad-notice" role="alert">{s.storageError || s.error}</p>}
        {s.storageError && <Button icon="refresh-cw" onClick={s.sync}>重读恢复记录</Button>}
        {s.notice && <p className="cad-notice" role="status">{s.notice}</p>}
        {other && <p className="cad-notice">原请求属于另一模板，当前选择不会改变原请求对象。请先核实原回执。</p>}
        {stale && !pending && !result && <p className="cad-notice">所选快照已失效，请明确刷新后重新预览。</p>}
        <p className="ca-muted">{scope}</p>{row && <Facts row={row} />}
        {result ? <Receipt value={result} /> : pending ? <dl className="cad-facts"><div><dt>原采用原因</dt><dd>{saved.input.reason}</dd></div><div><dt>原声明人</dt><dd>{saved.input.declared_operator}</dd></div></dl> : <>
          <div className="cad-fields"><label>采用原因<textarea aria-label="采用原因" rows={2} maxLength={2000} value={s.draft.reason} disabled={s.busy} onChange={e => s.change({ ...s.draft, reason: e.target.value })} /></label>
            <label>声明人<input aria-label="声明人" type="text" maxLength={100} value={s.draft.declared_operator} disabled={s.busy} onChange={e => s.change({ ...s.draft, declared_operator: e.target.value })} />
              <small>业务声明独立留痕，不代表登录身份；本机操作者另由服务记录。</small></label></div>
          {preview && <><p className={preview.validation.can_adopt ? 'cad-success' : 'cad-notice'} role="status">{preview.validation.can_adopt ? '当前预览可采用：来源、旧定额和合格样本已核对。' : '当前不能采用。'}</p>
            {preview.validation.issues.map(item => <p className="cad-notice" key={item.code}>{item.message}</p>)}
            {preview.quota_lock && <p className="cad-notice">已锁定定额 {hours(preview.quota_lock.locked_unit_hours)} / 件；锁定时间 {preview.quota_lock.locked_at}。</p>}
            <Samples preview={preview} detail={detail} />
            {preview.validation.can_adopt && <label className="cad-consent"><input type="checkbox" checked={s.consent} disabled={s.busy || blocked} onChange={e => s.setConsent(e.target.checked)} />
              <span>我已核对样本、旧定额与建议值，确认采用并锁定，仅供未来模板使用。</span></label>}
            <p className="ca-muted">预览时间：{preview.generated_at}{preview.write_context.expires_at && ' · 有效至 ' + preview.write_context.expires_at}</p></>}
        </>}
        <details className="cad-records"><summary>对象与请求记录</summary>{row && <div>模板：{row.template_operation_ref}<br />模板快照：{row.template_snapshot}</div>}
          {saved && <div data-adoption-key={saved.request_key}>原请求：{saved.request_key}</div>}</details>
      </div></Modal>;
  }
  function Styles() {
    return <style>{`
      .plana.calibration-adoption{display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap;width:auto;padding:0;max-width:100%;min-width:0;color:var(--ui-text);letter-spacing:0}
      .calibration-adoption *{box-sizing:border-box;letter-spacing:0}.calibration-adoption .modal-bg{z-index:1100}
      .calibration-adoption .modal.lg{width:900px;max-width:calc(100vw - 48px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;color:var(--ui-text);background:var(--ui-card-bg)}
      .calibration-adoption .modal-head,.calibration-adoption .modal-f{flex-shrink:0}.calibration-adoption .modal-f{gap:8px;padding:12px 20px}
      .calibration-adoption .cad-body{padding:12px 22px;overflow:auto;min-height:0;max-height:70vh;font-size:13px;line-height:1.6;color:var(--ui-text)}
      .calibration-adoption .cad-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin:0;padding:12px 0;border-bottom:1px solid var(--ui-border)}
      .calibration-adoption dt,.calibration-adoption small{color:var(--ui-info-muted);font-size:12px}.calibration-adoption dd{margin:3px 0 0;overflow-wrap:anywhere}
      .calibration-adoption .cad-fields{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:14px 0}.calibration-adoption label{display:grid;gap:5px;min-width:0;color:var(--ui-text)}
      .calibration-adoption textarea,.calibration-adoption input[type=text]{width:100%;color:var(--ui-text);background:var(--ui-card-bg);font:inherit;border:1px solid var(--ui-border);border-radius:4px;padding:8px 10px}
      .calibration-adoption textarea{resize:vertical;min-height:66px;max-height:180px}.calibration-adoption .cad-consent{display:flex;align-items:flex-start;gap:8px;margin:14px 0}
      .calibration-adoption .cad-consent input{flex:none;width:16px;height:16px;margin-top:3px;accent-color:var(--ui-info-text)}
      .calibration-adoption .cad-notice{padding:8px 12px;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);overflow-wrap:anywhere}
      .calibration-adoption .cad-success{color:var(--ui-success-text)}.calibration-adoption .cad-records{font-size:12px;color:var(--ui-info-muted);overflow-wrap:anywhere;padding-top:10px}
      .calibration-adoption h4{font-size:13px;margin:12px 0 8px}.calibration-adoption .cad-samples{min-width:0}.calibration-adoption .ca-table{min-width:0;font-size:12px}
      .calibration-adoption .ca-table th,.calibration-adoption .ca-table td{padding:7px 8px}.calibration-adoption button{white-space:normal;max-width:100%}
      .calibration-adoption .cad-inline{font-size:12px;color:var(--ui-info-muted);max-width:380px;overflow-wrap:anywhere}
      @media(max-width:700px){.calibration-adoption .cad-fields,.calibration-adoption .cad-facts{grid-template-columns:1fr}.calibration-adoption .cad-body{padding:12px}}
    `}</style>;
  }
  window.CalibrationAdoptionControls = { Button, Dialog, Styles };
})();
