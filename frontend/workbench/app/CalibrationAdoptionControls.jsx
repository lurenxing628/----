(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls, { hours } = window.CalibrationControls;
  const time = value => value ? window.WorkbenchFormat.dateTime(value, { seconds: true }) : '未知';
  const scope = '采用后更新模板定额并锁定；已有批次保持不变。新批次使用前请重新确认模板工时。';
  function Facts({ row }) {
    return <dl className="cad-facts"><div><dt>模板工序</dt><dd>{row.part_no} · {row.sequence} {row.operation_label}</dd></div>
      <div><dt>模板版本</dt><dd>第 {row.template_revision} 版</dd></div><div><dt>原定额</dt><dd>{hours(row.old_unit_hours)} / 件</dd></div>
      <div><dt>建议定额</dt><dd>{hours(row.suggested_unit_hours, '暂无建议')} / 件</dd></div>
      <div><dt>可用记录数</dt><dd>{row.sample_count} 条</dd></div><div><dt>未采用记录数</dt><dd>{row.excluded_count} 条</dd></div></dl>;
  }
  function Samples({ preview, detail }) {
    const rows = preview.samples;
    return <section className="cad-samples" aria-label="采用预检的完工记录"><h4>本次采用的可用完工记录（{rows.length} 条）</h4>
      <table className="ca-table"><thead><tr><th>批次 / 工序</th><th>数量</th><th>加工工时（小时）</th><th>单件（小时）</th><th>来源与版本</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.sample_ref} data-adoption-sample={row.sample_ref}><td>{row.batch_code}<small>{row.operation_code}</small></td>
          <td>{row.completed_quantity}</td><td>{row.effective_processing_hours}</td><td>{row.unit_hours}</td>
          <td><details><summary>模板第 {row.template_revision} 版</summary><window.WorkbenchReference entries={{ '完工记录编号': row.sample_ref, '来源证据编号': row.lineage_evidence_ref, '记录版本': row.sample_revision }} /></details></td></tr>)}</tbody></table>
      {detail && <details className="cad-records"><summary>排除与未关联的记录（{detail.samples.filter(row => !row.selected).length} 条）</summary>
        {detail.samples.filter(row => !row.selected).map(row => <div key={row.sample_ref}>{row.batch_code} · {row.template_operation_ref === null ? '未关联' : '已排除'}：
          {row.exclusion_reasons.map(item => item.message).join('；')}</div>)}</details>}</section>;
  }
  function Receipt({ value }) {
    const d = value.data;
    return <section aria-label="采用与锁定结果"><p className="cad-success" role="status">{window.WorkbenchTerms.outcomes.done('采用', '新定额 ' + hours(d.new_unit_hours) + ' / 件，定额已锁定（来自工时校准）')}</p>
      <dl className="cad-facts">{[['原定额', hours(d.old_unit_hours)], ['新定额', hours(d.new_unit_hours)], ['版本变化', '第 ' + d.template_revision_before + ' 版 → 第 ' + d.template_revision_after + ' 版'],
        ['采用时间', time(d.adopted_at)], ['经办人', d.declared_operator], ['记录人', d.application_operator], ['采用原因', d.reason], ['用户确认', d.confirmed ? '已确认' : '未确认']].map(([label, value]) =>
        <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <div className="cad-records"><window.WorkbenchReference entries={{ '结果编号': value.receipt_ref, '采用记录编号': d.adoption_ref }} /></div></section>;
  }
  function Dialog({ session: s, detail, stale, onRefresh }) {
    const { saved, preview } = s, pending = saved && saved.phase === 'pending', result = saved && saved.phase === 'committed' ? saved.receipt : null;
    const other = saved && detail && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref;
    const row = saved ? saved.baseline : detail && detail.suggestion;
    const blocked = stale || other || !!s.storageError || !detail;
    const refresh = () => { s.setConsent(false); s.change(s.draft); if (typeof onRefresh === 'function') onRefresh(); };
    return <Modal title={result ? '模板采用与锁定结果' : pending ? '查询上次采用结果' : '预检并采用模板定额'} icon="check" onClose={s.close}
      footer={<><Button onClick={s.close}>{pending ? '关闭并保留上次操作' : '关闭'}</Button>
        {result ? <Button icon="check" onClick={s.finish}>完成</Button> : pending ? <Button icon="refresh-cw" busy={s.busy} onClick={s.lookup}>{window.WorkbenchTerms.actions.query_result}</Button> : <>
          {saved && <Button disabled={s.busy || !!s.storageError} onClick={s.finish}>结束本次未采用</Button>}
          <Button icon="refresh-cw" disabled={s.busy || typeof onRefresh !== 'function'} onClick={refresh}>刷新所选模板</Button>
          <Button icon="search" busy={s.busy} disabled={blocked} onClick={s.inspect}>检查是否可采用</Button>
          <Button icon="check" className="btn primary" busy={s.busy} disabled={blocked || !preview || !preview.validation.can_adopt || !s.consent} onClick={s.submit}>确认采用并锁定</Button></>}</>}>
      <div className="modal-body cad-body">
        {(s.error || s.storageError) && <p className="cad-notice" role="alert">{s.storageError || s.error}</p>}
        {s.storageError && <Button icon="refresh-cw" onClick={s.sync}>刷新上次操作记录</Button>}
        {s.notice && <p className="cad-notice" role="status">{s.notice}</p>}
        {other && <p className="cad-notice">另一个模板的采用结果待确认，请先查询结果。</p>}
        {stale && !pending && !result && <p className="cad-notice">{window.WorkbenchTerms.outcomes.stale}</p>}
        <p className="ca-muted">{scope}</p>{row && <Facts row={row} />}
        {result ? <Receipt value={result} /> : pending ? <dl className="cad-facts"><div><dt>原采用原因</dt><dd>{saved.input.reason}</dd></div><div><dt>原经办人</dt><dd>{saved.input.declared_operator}</dd></div></dl> : <>
          <div className="cad-fields"><label>采用原因<textarea aria-label="采用原因" rows={2} maxLength={2000} value={s.draft.reason} disabled={s.busy} onChange={e => s.change({ ...s.draft, reason: e.target.value })} /></label>
            <label>经办人<input aria-label="经办人" type="text" maxLength={100} value={s.draft.declared_operator} disabled={s.busy} onChange={e => s.change({ ...s.draft, declared_operator: e.target.value })} /></label></div>
          {preview && <><p className={preview.validation.can_adopt ? 'cad-success' : 'cad-notice'} role="status">{preview.validation.can_adopt ? '检查通过，可以采用。' : '当前不能采用。'}</p>
            {preview.validation.issues.map(item => <p className="cad-notice" key={item.code}>{item.message}</p>)}
            {preview.quota_lock && <p className="cad-notice">定额已锁定（来自工时校准）：{hours(preview.quota_lock.locked_unit_hours)} / 件；锁定时间 {time(preview.quota_lock.locked_at)}。</p>}
            <Samples preview={preview} detail={detail} />
            {preview.validation.can_adopt && <label className="cad-consent"><input type="checkbox" checked={s.consent} disabled={s.busy || blocked} onChange={e => s.setConsent(e.target.checked)} />
              <span>确认采用并锁定新定额，用于以后新增的工序。</span></label>}
            <p className="ca-muted">预检时间：{time(preview.generated_at)}{preview.write_context.expires_at && ' · 有效至 ' + time(preview.write_context.expires_at)}</p></>}
        </>}
        <div className="cad-records" {...(saved ? { 'data-adoption-key': saved.request_key } : {})}>
          <window.WorkbenchReference entries={{ ...(row ? { '模板工序编号': row.template_operation_ref, '模板数据版本': row.template_snapshot } : {}),
            ...(saved ? { '操作编号': saved.request_key } : {}) }} /></div>
      </div></Modal>;
  }
  function Styles() {
    return null;
  }
  window.CalibrationAdoptionControls = { Button, Dialog, Styles };
})();
