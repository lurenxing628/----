(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract;
  const E = window.ProcessStageEditor;
  const { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  function Preview({ result }) {
    const d = result.data, paging = E.usePage(d.operations);
    return <section data-process-preview>
      <h3>路线预检</h3><Issues issues={result.warnings} />
      <p role="status">{d.can_confirm_route ? '输入有效，尚未保存。' : '输入存在待处理问题，尚未保存。'} 工序 {d.counts.operations} · 已识别 {d.counts.recognized} · 未识别 {d.counts.unknown}</p>
      {d.diagnostics.length > 0 && <div className="match-note" role="alert" style={{ display: 'block' }}>{d.diagnostics.map((row, index) => <div key={index}>{row.severity === 'error' ? '错误' : '警告'}{row.sequence !== undefined ? ' · 工序 ' + row.sequence : ''}：{row.message}</div>)}</div>}
      <dl className="process-fields"><dt>规范化输入</dt><dd>{d.normalized_input}</dd></dl>
      <p>原模板：工序 {d.baseline.operation_count} · 外协组 {d.baseline.external_group_count} · {d.baseline.has_published_template ? '已有发布模板' : '无发布模板'}</p>
      <dl className="process-fields">{[['added', '新增序号'], ['removed', '移除序号'], ['retained', '保留序号'], ['same_sequence_changed', '同序号内容变化']].map(([key, label]) =>
        <React.Fragment key={key}><dt>{label}</dt><dd>{d.changes[key].length ? d.changes[key].join('、') : '无'}</dd></React.Fragment>)}</dl>
      <div className="wb-table-frame"><div className="card-scroll wb-table-shell"><table className="tbl wb-table" aria-label="路线预检工序" style={{ minWidth: 900, tableLayout: 'fixed' }}>
        <thead><tr><th style={{ width: 90 }}>工序号</th><th style={{ width: 160 }}>工种</th><th style={{ width: 110 }}>建议归属</th><th style={{ width: 150 }}>供应商</th><th style={{ width: 130 }}>周期（天）</th><th>依据 / 问题</th></tr></thead>
        <tbody>{paging.rows.map((row, index) => <tr key={index}><td>{row.sequence}</td><td>{row.op_type_name}<div className="muted">{row.op_type_ref === null ? '未识别' : '已识别'}</div></td>
          <td>{P.sourceLabel(row.source_suggestion)}</td><td>{row.supplier_label === null ? '未提供' : row.supplier_label}</td><td>{P.valueText(row.external_days)}</td>
          <td>{typeof row.basis === 'string' ? row.basis : JSON.stringify(row.basis)}<Issues issues={row.issues} /></td></tr>)}</tbody>
      </table></div></div><E.Pager paging={paging} />
    </section>;
  }
  function ProcessRouteEntry({ adapter, result, command, onClose, onDirty, refreshState = {}, onRefresh, active = true, disabled = false }) {
    const [context, setContext] = React.useState(result);
    const entity = context.data, sequence = React.useRef(0), request = React.useRef(null);
    const [mode, setMode] = React.useState('text'), [routeRaw, setRouteRaw] = React.useState(entity.fields.route_raw === null ? '' : entity.fields.route_raw);
    const [rows, setRows] = React.useState(() => {
      const active = entity.operations.filter(row => row.status === 'active');
      return active.length ? active.map(row => ({ key: ++sequence.current, seq: String(row.sequence), op_type_name: row.label })) : [{ key: ++sequence.current, seq: '', op_type_name: '' }];
    });
    const [state, setState] = React.useState({ busy: false, result: null, error: null });
    const [discarded, setDiscarded] = React.useState([]), [review, setReview] = React.useState(null);
    const paging = E.usePage(rows), locked = !!command && (command.locked || command.phase === 'done');
    const blocked = disabled || locked;
    function abort() { if (request.current) request.current.abort(); request.current = null; }
    React.useEffect(() => () => abort(), []);
    React.useEffect(() => { invalidate(); }, [adapter, result, disabled, active, command && command.error]);
    React.useEffect(() => { if (result !== context) setReview(result); }, [result]);
    function invalidate() { abort(); setState({ busy: false, result: null, error: null }); setDiscarded([]); }
    function edited() { invalidate(); if (onDirty) onDirty('route', true); }
    function close() { abort(); onClose(); }
    function changeRow(key, patch) { edited(); setRows(current => current.map(row => row.key === key ? { ...row, ...patch } : row)); }
    async function preflight() {
      if (blocked || review || state.busy || P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')) return;
      abort(); const controller = new AbortController(); request.current = controller;
      setState({ busy: true, result: null, error: null });
      try {
        const body = P.previewBody(mode, routeRaw, rows, context.meta.snapshot_ref);
        const response = P.preview(await adapter.routePreview(entity.ref, body, controller.signal), entity.ref, body);
        if (!controller.signal.aborted && request.current === controller) { const { snapshot_ref, ...route } = body; setState({ busy: false, result: response, route, error: null }); }
      } catch (error) {
        if (!controller.signal.aborted && request.current === controller) setState({ busy: false, result: null, error });
      } finally { if (request.current === controller) request.current = null; }
    }
    async function reloadDetail() {
      if (blocked || state.busy || typeof adapter.detail !== 'function') return;
      abort(); const controller = new AbortController(); request.current = controller;
      setState({ busy: true, result: null, error: null, reading: true });
      try {
        const fresh = P.detail(await adapter.detail('part', entity.ref, controller.signal), entity.ref);
        if (!controller.signal.aborted && request.current === controller) { setReview(fresh); setState({ busy: false, result: null, error: null, refreshed: true }); }
      } catch (error) {
        if (!controller.signal.aborted && request.current === controller) setState({ busy: false, result: null, error });
      } finally { if (request.current === controller) request.current = null; }
    }
    const affected = state.result ? state.result.data.affected_groups || [] : [];
    const saveReason = P.reason(entity.capabilities, 'stage_confirm', typeof adapter.command === 'function' && !!command) ||
      (review ? '请先核对最新资料。' : !state.result || !state.result.data.can_confirm_route ? '请先完成当前路线预检。' :
        !affected.every(row => discarded.includes(row.ref)) ? '请明确勾选解除所有受影响的外协组。' : C.blocked(state.result.data.write_context, 'process', 'route_confirm', state.result.meta.source));
    async function save() {
      if (blocked || saveReason) return;
      await command.submit('process', 'route_confirm', entity.ref, state.result.data.write_context, { route: state.route, discard_group_refs: discarded });
    }
    return <div className="process-route-entry"><Modal title={'录入工艺路线 · ' + entity.business_code} icon="chart-gantt" onClose={() => { if (!locked) close(); }} locked={locked} suspended={!active}
      footer={<><Button onClick={close} disabled={locked}>取消</Button><Button icon="search" busy={state.busy} disabled={blocked || !!review} reason={P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')} onClick={preflight}>预检路线</Button>
        <Button icon="check" className="btn primary" disabled={blocked} reason={saveReason} onClick={save}>确认保存路线</Button></>}>
      <div className="modal-b scroll">
        <div className="seg re-mode" role="tablist" aria-label="路线录入模式" style={{ marginBottom: 16 }}>
          {[['text', '整条录入'], ['rows', '逐行表格']].map(([value, label]) => <Button key={value} role="tab" aria-selected={mode === value} className={mode === value ? 'on' : ''} disabled={blocked} onClick={() => { if (mode !== value) { edited(); setMode(value); } }}>{label}</Button>)}
        </div>
        {mode === 'text' ? <label className="field full">路线文字<textarea aria-label="路线文字" className="re-text" rows={5} value={routeRaw} disabled={blocked} onChange={event => { edited(); setRouteRaw(event.target.value); }} style={{ width: '100%', resize: 'vertical' }} /></label> : <>
          <div className="wb-table-frame"><div className="card-scroll wb-table-shell"><table className="tbl wb-table" aria-label="逐行路线录入" style={{ minWidth: 580, tableLayout: 'fixed' }}>
            <thead><tr><th style={{ width: 125 }}>工序号</th><th>工种</th><th style={{ width: 140 }}>归属</th><th style={{ width: 70 }}>操作</th></tr></thead><tbody>
              {paging.rows.map((row, index) => <tr key={row.key}><td><input type="text" inputMode="numeric" aria-label={'第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工序号'} value={row.seq} disabled={blocked} className="wt-in" style={{ width: '100%' }} onChange={event => changeRow(row.key, { seq: event.target.value })} /></td>
                <td><input type="text" aria-label={'第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工种'} value={row.op_type_name} disabled={blocked} className="wt-in" style={{ width: '100%' }} onChange={event => changeRow(row.key, { op_type_name: event.target.value })} /></td>
                <td className="muted">待服务预检</td><td><Button className="mini danger" icon="minus" aria-label={'删除第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行'} disabled={blocked} onClick={() => { edited(); setRows(current => current.filter(item => item.key !== row.key)); }} /></td></tr>)}
            </tbody></table></div></div>
          <E.Pager paging={paging} disabled={blocked} /><Button icon="plus" disabled={blocked} onClick={() => { edited(); setRows(current => current.concat({ key: ++sequence.current, seq: '', op_type_name: '' })); paging.setNumber(Math.ceil((rows.length + 1) / paging.page.size)); }}>添加工序</Button>
        </>}
        {state.busy && <p role="status">{state.reading ? '正在重读详情…' : '正在预检路线…'}</p>}<ErrorBox error={state.error} />
        {state.refreshed && <p role="status">已重读详情，录入内容保留；请核对后重新预检。</p>}
        {state.error && <Button icon="refresh-cw" disabled={blocked || !!review} onClick={preflight}>重试预检</Button>}
        <Button icon="refresh-cw" disabled={blocked || state.busy} reason={typeof adapter.detail !== 'function' ? '工艺详情接口尚未接入。' : ''} onClick={reloadDetail}>重读详情并保留草稿</Button>
        {review && <E.Review before={context.data} after={review.data} disabled={blocked} onAccept={() => { setContext(review); setReview(null); invalidate(); }} />}
        {state.result && <Preview result={state.result} />}
        {state.result && <E.Groups title="受影响外协组" empty="本次预检未发现受影响外协组。" rows={affected} affected={affected.map(row => row.ref)} discarded={discarded} onDiscard={setDiscarded} disabled={blocked} />}
        {command && <window.ResourceForms.Feedback command={command} />}
        <ErrorBox error={refreshState.error} />{refreshState.error && <Button icon="refresh-cw" onClick={onRefresh}>重新读取保存结果</Button>}
      </div>
    </Modal></div>;
  }
  window.ProcessRouteEntry = ProcessRouteEntry;
})();
