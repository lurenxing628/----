(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, S = window.APSResourceSession;
  const E = window.ProcessStageEditor, D = window.ProcessRouteDraft;
  // The op_type page caps at 200 rows (core/models/workbench_resource_query.py), so a single read is the whole candidate list it can offer.
  const OP_TYPE_PAGE_SIZE = 200;
  const { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  // 依据可能是结构化的：数组按行列出，对应关系按「名：值」逐项列出，不把 JSON 直接上屏；原文折叠进编号区备查。
  const basisText = item => item === null || item === undefined ? '未填写' : typeof item === 'object' ? JSON.stringify(item) : String(item);
  function BasisRows({ value }) {
    const rows = Array.isArray(value) ? value.map(basisText) : Object.keys(value).map(key => key + '：' + basisText(value[key]));
    return <>{rows.length ? rows.map((row, index) => <div key={index}>{row}</div>) : <span className="muted">未填写</span>}
      <window.WorkbenchReference label="依据原文" entries={{ '依据原文': value }} /></>;
  }
  function Preview({ result }) {
    const d = result.data, paging = E.usePage(d.operations);
    return <section data-process-preview>
      <h3>路线预检</h3><Issues issues={result.warnings} />
      <p role="status">{d.can_confirm_route ? '输入有效，尚未保存。' : '输入存在待处理问题，尚未保存。'} 工序 {d.counts.operations} · 已识别 {d.counts.recognized} · 未识别 {d.counts.unknown}</p>
      {d.diagnostics.length > 0 && <div className="match-note is-block" role="alert">{d.diagnostics.map((row, index) => <div key={index}>{row.severity === 'error' ? '错误' : '警告'}{row.sequence !== undefined ? ' · 工序 ' + row.sequence : ''}：{row.message}</div>)}</div>}
      <dl className="process-fields"><dt>整理后的路线</dt><dd>{d.normalized_input}</dd></dl>
      <p>原模板：工序 {d.baseline.operation_count} · 外协组 {d.baseline.external_group_count} · {d.baseline.has_published_template ? '已有发布模板' : '无发布模板'}</p>
      <dl className="process-fields">{[['added', '新增序号'], ['removed', '移除序号'], ['retained', '保留序号'], ['same_sequence_changed', '同序号内容变化']].map(([key, label]) =>
        <React.Fragment key={key}><dt>{label}</dt><dd>{d.changes[key].length ? d.changes[key].join('、') : '无'}</dd></React.Fragment>)}</dl>
      <div className="wb-table-frame wb-table-shell" data-sticky-head><table className="tbl wb-table" aria-label="路线预检工序" style={{ minWidth: 900, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{"路线预检工序"}</caption>
        <thead><tr><th scope="col" style={{ width: 90 }}>工序号</th><th scope="col" style={{ width: 160 }}>工种</th><th scope="col" style={{ width: 110 }}>建议归属</th><th scope="col" style={{ width: 150 }}>供应商</th><th scope="col" style={{ width: 130 }}>周期（天）</th><th scope="col">依据 / 问题</th></tr></thead>
        <tbody>{paging.rows.map((row, index) => <tr key={index}><td>{row.sequence}</td><td>{row.op_type_name}<div className="muted">{row.op_type_ref === null ? '未识别' : '已识别'}</div></td>
          <td>{P.sourceLabel(row.source_suggestion)}</td><td>{row.supplier_label === null ? '未选' : row.supplier_label}</td><td>{P.valueText(row.external_days)}</td>
          <td>{typeof row.basis === 'string' ? row.basis : <BasisRows value={row.basis} />}<Issues issues={row.issues} /></td></tr>)}</tbody>
      </table></div><E.Pager paging={paging} />
    </section>;
  }
  function ProcessRouteEntry({ adapter, result, command, onClose, onDirty, refreshState = {}, onRefresh, active = true, disabled = false }) {
    const [context, setContext] = React.useState(result);
    const entity = context.data, sequence = React.useRef(0), request = React.useRef(null);
    const initialRows = React.useRef(D.fromEntity(entity));
    const [mode, setMode] = React.useState('text'), [routeRaw, setRouteRaw] = React.useState(() => initialRows.current.length ? D.serialize(initialRows.current) : entity.fields.route_raw || '');
    const [rows, setRows] = React.useState(() => (initialRows.current.length ? initialRows.current : [{ seq: '', op_type_name: '' }]).map(row => ({ ...row, key: ++sequence.current })));
    const draftText = mode === 'text' ? routeRaw : D.serialize(rows), baselineDraft = React.useRef(draftText);
    React.useLayoutEffect(() => { if (onDirty) onDirty('route', draftText !== baselineDraft.current); }, [draftText, onDirty]);
    const [state, setState] = React.useState({ busy: false, result: null, error: null });
    const [discarded, setDiscarded] = React.useState([]), [review, setReview] = React.useState(null);
    const [mergeReview, setMergeReview] = React.useState(null), [mergeChoices, setMergeChoices] = React.useState({});
    const paging = E.usePage(rows), locked = !!command && (command.locked || command.phase === 'done');
    const blocked = disabled || locked;
    // Read the op_type catalog once on entry so the row inputs can suggest real names. Free text stays allowed and
    // the server route preflight remains the only authority on what is recognized.
    const opTypeListId = React.useId();
    const opTypes = S.useQuery(signal => Promise.resolve(adapter.choices('op_type', { query: '', page: 1, size: OP_TYPE_PAGE_SIZE }, signal)).then(result => C.query(result, 'choices')),
      [adapter], typeof adapter.choices === 'function');
    const opTypeNames = React.useMemo(() => opTypes.result ? Array.from(new Set(opTypes.result.data.entities.map(item => item.label).filter(Boolean))) : [],
      [opTypes.result]);
    function abort() { if (request.current) request.current.abort(); request.current = null; }
    React.useEffect(() => () => abort(), []);
    React.useEffect(() => { invalidate(); }, [adapter, result, disabled, active, command && command.error]);
    React.useEffect(() => { if (result !== context) { setReview(result); setMergeReview(null); setMergeChoices({}); } }, [result]);
    function invalidate() { abort(); setState({ busy: false, result: null, error: null }); setDiscarded([]); }
    function edited() { invalidate(); setMergeReview(null); setMergeChoices({}); }
    function close() { abort(); onClose(); }
    function changeRow(key, patch) { edited(); setRows(current => current.map(row => row.key === key ? { ...row, ...patch } : row)); }
    async function parsedDraft(snapshot) {
      const controller = new AbortController(); request.current = controller;
      try {
        const body = P.previewBody('text', mode === 'rows' ? D.serialize(rows) : routeRaw, rows, snapshot);
        const response = P.preview(await adapter.routePreview(entity.ref, body, controller.signal), entity.ref, body);
        if (controller.signal.aborted || request.current !== controller) return null;
        const syntaxInvalid = !response.data.operations.length || response.data.diagnostics.some(row => row.severity === 'error' && !['calibration_quota_locked', 'legacy_sequence_invalid'].includes(row.code));
        if (syntaxInvalid) { setState({ busy: false, result: response, error: C.failure('当前输入还不能准确识别，已保留原输入。请按路线预检提示修正后再继续。') }); return null; }
        return response.data.operations.map(row => ({ seq: String(row.sequence), op_type_name: row.op_type_name }));
      } catch (error) { if (!controller.signal.aborted) throw error; return null; }
      finally { if (request.current === controller) request.current = null; }
    }
    async function switchMode(next) {
      if (next === mode || blocked || review || state.busy) return;
      if (!(mode === 'rows' ? D.serialize(rows) : routeRaw).trim()) {
        invalidate(); setRows([{ key: ++sequence.current, seq: '', op_type_name: '' }]); setRouteRaw(''); setMode(next); return;
      }
      if (P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')) return;
      invalidate(); setState({ busy: true, result: null, error: null });
      try {
        const parsed = await parsedDraft(context.meta.snapshot_ref);
        if (!parsed) return;
        setRows(parsed.map(row => ({ ...row, key: ++sequence.current }))); setRouteRaw(D.serialize(parsed)); setMode(next);
        setState({ busy: false, result: null, error: null });
      } catch (error) { setState({ busy: false, result: null, error }); }
    }
    function acceptMerged(mergedRows) {
      const nextRows = mergedRows.map(row => ({ ...row, key: ++sequence.current })), text = D.serialize(mergedRows);
      initialRows.current = D.fromEntity(review.data);
      baselineDraft.current = D.serialize(initialRows.current);
      setRows(nextRows); setRouteRaw(text); setContext(review); setReview(null); setMergeReview(null); setMergeChoices({}); invalidate();
    }
    async function acceptLatest() {
      if (blocked || state.busy) return;
      if (mergeReview) { try { acceptMerged(D.resolve(mergeReview, mergeChoices)); } catch (error) { setState({ busy: false, result: null, error: C.failure(error.message) }); } return; }
      abort(); setState({ busy: true, result: null, error: null });
      try {
        const parsed = await parsedDraft(review.meta.snapshot_ref);
        if (!parsed) return;
        const merged = D.merge(initialRows.current, parsed, D.fromEntity(review.data));
        if (merged.conflicts.length) { setMergeReview(merged); setMergeChoices({}); setState({ busy: false, result: null, error: null }); }
        else acceptMerged(merged.rows);
      } catch (error) { setState({ busy: false, result: null, error }); }
    }
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
        if (!controller.signal.aborted && request.current === controller) { setReview(fresh); setMergeReview(null); setMergeChoices({}); setState({ busy: false, result: null, error: null, refreshed: true }); }
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
        <div className="seg re-mode" role="group" aria-label="路线录入模式" style={{ marginBottom: 16 }}>
          {[['text', '整条录入'], ['rows', '逐行表格']].map(([value, label]) => <Button key={value} aria-pressed={mode === value} className={mode === value ? 'on' : ''} disabled={blocked || !!review || state.busy} reason={P.reason(entity.capabilities, 'route_preview', typeof adapter.routePreview === 'function')} onClick={() => switchMode(value)}>{label}</Button>)}
        </div>
        <p className="muted">整条和逐行维护的是同一条路线。可直接填写“10: 车削；20: 热处理；30: 精磨”；原来的“10车削20热处理”也能识别。名称含数字或空格时，保留工序号后的冒号即可。</p>
        {mode === 'text' ? <label className="field full">路线文字<textarea aria-label="路线文字" className="re-text" rows={5} value={routeRaw} disabled={blocked} onChange={event => { edited(); setRouteRaw(event.target.value); }} style={{ width: '100%', resize: 'vertical' }} /></label> : <>
          {opTypeNames.length > 0 && <datalist id={opTypeListId}>{opTypeNames.map(name => <option key={name} value={name} />)}</datalist>}
          {opTypeNames.length > 0 && <p className="muted">工种输入会提示已登记的工种{opTypes.result.data.page.total > opTypeNames.length ? '，现有工种较多，只提示前 ' + opTypeNames.length + ' 个' : ''}；未登记的工种也可以直接输入。</p>}
          <div className="wb-table-frame wb-table-shell" data-sticky-head><table className="tbl wb-table wb-table--editable" aria-label="逐行路线录入" style={{ minWidth: 620, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{"逐行路线录入"}</caption>
            <thead><tr><th scope="col" style={{ width: 125 }}>工序号</th><th scope="col">工种</th><th scope="col" style={{ width: 140 }}>归属</th><th scope="col" style={{ width: 100 }}>操作</th></tr></thead><tbody>
              {paging.rows.map((row, index) => <tr key={row.key}><td><input type="text" inputMode="numeric" aria-label={'第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工序号'} value={row.seq} disabled={blocked} className="wt-in" style={{ width: '100%' }} onChange={event => changeRow(row.key, { seq: event.target.value })} /></td>
                <td><input type="text" list={opTypeNames.length ? opTypeListId : undefined} aria-label={'第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行工种'} value={row.op_type_name} disabled={blocked} className="wt-in" style={{ width: '100%' }} onChange={event => changeRow(row.key, { op_type_name: event.target.value })} /></td>
                <td className="muted">待预检</td><td><Button className="mini danger" icon="trash-2" aria-label={'删除第 ' + ((paging.page.number - 1) * paging.page.size + index + 1) + ' 行'} disabled={blocked} onClick={() => { edited(); setRows(current => current.filter(item => item.key !== row.key)); }}>删除</Button></td></tr>)}
            </tbody></table></div>
          <E.Pager paging={paging} disabled={blocked} /><Button icon="plus" disabled={blocked} onClick={() => { edited(); setRows(current => current.concat({ key: ++sequence.current, seq: '', op_type_name: '' })); paging.setNumber(Math.ceil((rows.length + 1) / paging.page.size)); }}>新增工序</Button>
        </>}
        {state.busy && <p role="status">{state.reading ? '正在刷新详情…' : '正在预检路线…'}</p>}<ErrorBox error={state.error} /><ErrorBox error={opTypes.error} />
        {state.refreshed && <p role="status">已刷新详情，录入内容保留；请核对后重新预检。</p>}
        {state.error && <Button icon="refresh-cw" disabled={blocked || !!review} onClick={preflight}>重试预检</Button>}
        <Button icon="refresh-cw" disabled={blocked || state.busy} reason={typeof adapter.detail !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={reloadDetail}>{window.WorkbenchTerms.refresh_latest}</Button>
        {review && <E.Review before={context.data} after={review.data} disabled={blocked || state.busy} onAccept={acceptLatest} />}
        {mergeReview && <section className="match-note is-block" role="alert"><p>以下工序同时被本次草稿和最新资料修改，请逐项选择后，再点“已核对，继续编辑”。其余工序会保留本地修改并采用最新资料。</p>
          {mergeReview.conflicts.map(row => <fieldset key={row.seq}><legend>工序 {row.seq}</legend>{[['local', '保留我的修改'], ['latest', '采用最新资料']].map(([choice, label]) => <label key={choice} style={{ display: 'block' }}><input type="radio" name={'route-conflict-' + row.seq} checked={mergeChoices[row.seq] === choice} disabled={blocked} onChange={() => setMergeChoices(current => ({ ...current, [row.seq]: choice }))} />{label}：{row[choice] ? row[choice].op_type_name : '移除这道工序'}</label>)}</fieldset>)}</section>}
        {state.result && <Preview result={state.result} />}
        {state.result && <E.Groups title="受影响外协组" empty="本次预检未发现受影响外协组。" rows={affected} affected={affected.map(row => row.ref)} discarded={discarded} onDiscard={setDiscarded} disabled={blocked} />}
        {command && <window.ResourceForms.Feedback command={command} />}
        <ErrorBox error={refreshState.error} />{refreshState.error && <Button icon="refresh-cw" onClick={onRefresh}>查询结果</Button>}
      </div>
    </Modal></div>;
  }
  window.ProcessRouteEntry = ProcessRouteEntry;
})();
