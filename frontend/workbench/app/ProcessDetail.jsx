(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, S = window.APSResourceSession, E = window.ProcessStageEditor;
  const { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  function Steps({ entity, stage, onStage, disabled }) {
    const subtitle = key => entity.workflow[key].state === 'confirmed' ? '已确认' : entity.workflow[key].state === 'locked' ? key === 'source' ? '待路线确认' : '待归属确认' : key === 'route' ? entity.workflow.route.state === 'present' ? '已有路线 · 待保存' : '待录入路线' : '待保存';
    return <div className="stepper" role="tablist" aria-label="零件工艺步骤">{[['route', '工艺路线'], ['source', '归属'], ['hours', '工时定额']].map(([key, title], index) =>
      <Button key={key} className={'stp ' + (stage === key ? 'active' : entity.workflow[key].state === 'confirmed' ? 'done' : '')} role="tab" aria-selected={stage === key} disabled={disabled} onClick={() => onStage(key)}>
        <span className="stp-n">{index + 1}</span><span className="stp-b"><span className="stp-t">{title}</span><span className="stp-s">{subtitle(key)}</span></span></Button>)}</div>;
  }
  function Operations({ entity, hours, focusRef = null }) {
    const paging = E.usePage(entity.operations, focusRef), groups = new Map(entity.external_groups.map(row => [row.ref, row])), root = React.useRef(null);
    E.useFocus(root, focusRef, paging.page.number);
    return <div ref={root}><div className="toolbar"><E.Search paging={paging} /><span>全部记录 {entity.operations.length} · 有效工序 {entity.relationships.operation_count}</span></div>
      <div className="wb-table-frame"><table className="tbl wb-table" aria-label={hours ? '已就绪工序汇总' : '路线工序明细'} style={{ minWidth: hours ? 1000 : 850, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{hours ? '已就绪工序汇总' : '路线工序明细'}</caption>
        {hours && <colgroup>{[11, 9, 8, 16, 13, 13, 11, 19].map((width, index) => <col key={index} style={{ width: width + '%' }} />)}</colgroup>}
        <thead><tr><th scope="col">工序</th><th scope="col">工种</th><th scope="col">现有归属</th><th scope="col">供应商 / 外协组</th>{hours && <><th scope="col">换型工时（小时）</th><th scope="col">单件工时（小时）</th><th scope="col">外协周期（天）</th></>}<th scope="col">确认记录 / 问题</th></tr></thead>
        <tbody>{paging.rows.map(row => { const group = groups.get(row.external_group_ref); return <tr key={row.ref} data-process-location={row.ref} tabIndex={row.ref === focusRef ? -1 : undefined} aria-current={row.ref === focusRef ? 'true' : undefined}>
          <td><b>{row.sequence}</b> {row.label}{row.ref === focusRef && <window.WorkbenchReference value={row.ref} />}</td><td>{row.op_type_label || '未选工种'}</td><td>{P.sourceLabel(row.source)}</td>
          <td>{row.source === 'internal' ? '不适用' : row.supplier_label || '未选供应商'}{group && <div>外协组 {group.start_sequence} 至 {group.end_sequence}</div>}</td>
          {hours && <><td>{row.source === 'internal' ? E.value(row.setup_hours) : '不适用'}</td><td>{row.source === 'internal' ? E.value(row.unit_hours) : '不适用'}</td><td data-process-cycle-group={row.external_days_source === 'group' ? row.external_group_ref : undefined}>{row.source === 'external' ? P.groupCycle(row, entity.external_groups) || E.value(row.external_days) : '不适用'}</td></>}
          <td>{row.status === 'active' ? '有效' : '已停用工序'}<div className="muted"><E.Confirmation record={row.confirmation[hours ? 'hours' : 'source']} /></div><Issues issues={row.issues} /></td></tr>; })}
          {!paging.rows.length && <tr><td colSpan={hours ? 8 : 5}>{entity.operations.length ? '没有匹配的工序。' : '尚无工序记录。'}</td></tr>}</tbody></table></div><E.Pager paging={paging} />
    </div>;
  }
  function RouteView({ entity, disabled, onEntry, onFileAction, previewAvailable }) {
    return <section className="process-route-section"><div className="toolbar"><h3>工艺路线</h3><span className="tb-spacer" /><Button icon="square-pen" className="btn primary" disabled={disabled} reason={P.reason(entity.capabilities, 'route_preview', previewAvailable)} onClick={onEntry}>录入路线</Button><window.ProcessFileButtons capabilities={entity.capabilities} disabled={disabled} routeOnly onAction={onFileAction} /></div>
      <Operations entity={entity} hours={false} />
      <details className="process-original"><summary>原始导入资料与保存记录</summary><dl className="process-fields">{[['route_raw', '原始路线'], ['route_parsed', '解析状态'], ['remark', '零件备注']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{key === 'route_parsed' ? entity.fields[key] === 'yes' ? '已解析' : entity.fields[key] === 'no' ? '未解析' : '解析状态未知' : E.value(entity.fields[key])}</dd></div>)}</dl><E.Confirmation record={entity.workflow.route} /><E.Groups rows={entity.external_groups} /></details></section>;
  }
  function DetailSession({ adapter, partRef, onClose, onCommitted, disabled = false, initialStage, templateOperationRef, templateExternalGroupRef, navigationReadOnly = false }) {
    const [target] = React.useState(() => { try { return E.location(initialStage, templateOperationRef, templateExternalGroupRef); } catch (error) { return { error }; } });
    const command = S.useCommand(adapter), [stage, setStage] = React.useState(target.stage || null), [current, setCurrent] = React.useState(null);
    const [browsing, setBrowsing] = React.useState(navigationReadOnly || !!initialStage || !!templateOperationRef || !!templateExternalGroupRef);
    const [entry, setEntry] = React.useState(false), [entryStarted, setEntryStarted] = React.useState(false), [overlay, setOverlay] = React.useState(false);
    const [dirty, setDirty] = React.useState({}), [discard, setDiscard] = React.useState(false), [saved, setSaved] = React.useState({ route: 0, source: 0, hours: 0 });
    const [refresh, setRefresh] = React.useState({}), [receipt, setReceipt] = React.useState(null);
    const [fileAction, setFileAction] = React.useState(null), [fileReceipt, setFileReceipt] = React.useState(null);
    const request = React.useRef(null), notified = React.useRef(null), root = React.useRef(null), fileFocus = React.useRef(null);
    const onDirty = React.useCallback((key, value) => setDirty(old => old[key] === value ? old : { ...old, [key]: value }), []);
    async function loadPart(signal) {
      if (target.error) throw target.error;
      if (typeof adapter.detail !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.detail');
      const raw = await adapter.detail('part', partRef, signal);
      if (raw && raw.data && raw.data.ref !== partRef) throw C.failure('返回的不是原零件记录，不能继续使用同图号的新零件。');
      const value = P.detail(raw, partRef);
      if (value.meta.source !== 'production') throw C.failure('未取得原零件的生产详情，不能使用样例替代。');
      if (browsing) E.locate(value.data, target);
      return value;
    }
    const detail = S.useQuery(loadPart, [adapter, partRef]);
    React.useEffect(() => { if (detail.result) setCurrent(old => old || detail.result); }, [detail.result]);
    React.useEffect(() => () => { if (request.current) request.current.abort(); }, []);
    const intent = command.intent, fileKind = intent && intent.action === 'confirm' && typeof intent.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(intent.ref) &&
      ['process_route_import', 'process_hours_import'].includes(intent.kind) ? intent.kind === 'process_route_import' ? 'route' : 'hours' : null;
    const expectedStage = intent && intent.kind === 'process' && ['route_confirm', 'source_confirm', 'hours_confirm'].includes(intent.action) ? intent.action.replace('_confirm', '') : null;
    const receiptMatches = command.phase === 'done' && expectedStage && command.intent.kind === 'process' && command.intent.ref === partRef &&
      C.object(command.result.data) && command.result.data.entity_ref === partRef && command.result.data.stage === expectedStage && ['committed', 'unchanged'].includes(command.result.result);
    const needsReceiptCheck = command.phase === 'done' && !fileKind && !receiptMatches;
    const visibleCommand = fileKind ? { ...command, phase: 'idle', result: null, error: null, locked: true } :
      needsReceiptCheck ? { ...command, phase: 'pending', locked: true, error: C.failure(window.WorkbenchTerms.outcomes.pending('保存')) } : command;
    const hasDraft = Object.values(dirty).some(Boolean);
    window.WorkbenchGuards.useDirtyGuard({ dirty: hasDraft, locked: (fileKind ? command.locked : visibleCommand.locked) || needsReceiptCheck,
      message: '零件工艺的路线、归属或工时输入尚未保存。' });
    const locked = (fileKind ? command.locked : visibleCommand.locked) || refresh.loading || overlay || !!fileAction;
    const editingBlocked = disabled || locked || command.phase === 'done' || !!fileReceipt && !refresh.done;
    const editorDisabled = disabled || refresh.loading || !!fileAction || !!fileReceipt && !refresh.done;
    React.useEffect(() => {
      if (!fileFocus.current || fileAction || discard || locked || entry) return undefined;
      const frame = requestAnimationFrame(() => {
        const previous = fileFocus.current; fileFocus.current = null;
        if (!root.current) return;
        const focusable = node => node && !node.disabled && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
        const selected = root.current.querySelector('.stepper [aria-selected="true"]');
        const target = focusable(previous) ? previous : focusable(selected) ? selected : root.current.querySelector('.modal-x');
        if (focusable(target)) target.focus();
      });
      return () => cancelAnimationFrame(frame);
    }, [fileAction, discard, locked, entry]);
    function fileRequest(recovery = false) {
      return { target_ref: partRef, source: 'production', refs: [partRef], scope: {}, snapshot_ref: current && current.meta.snapshot_ref, page_size: 20, ...(recovery ? { recovery: true } : {}) };
    }
    React.useEffect(() => {
      if (fileKind && !fileAction && !fileReceipt) setFileAction({ kind: fileKind, mode: 'import', request: fileRequest(true) });
    }, [fileKind, fileAction, fileReceipt]);
    function notify(value) {
      if (notified.current === value.receipt_ref) return;
      notified.current = value.receipt_ref; if (onCommitted) onCommitted(value);
    }
    function resetDrafts() {
      setSaved(old => ({ route: old.route + 1, source: old.source + 1, hours: old.hours + 1 }));
      setDirty({}); setEntry(false); setEntryStarted(false);
    }
    function openFile(kind, mode, abandon = false) {
      if (editingBlocked || !current || !['route', 'hours'].includes(kind) || !['import', 'export'].includes(mode)
          || typeof window.ProcessFileActions !== 'function' || P.reason(current.data.capabilities, mode, true)) return;
      if (!abandon) fileFocus.current = document.activeElement;
      if (hasDraft && !abandon) { setDiscard({ kind, mode }); return; }
      if (!command.reset()) return;
      resetDrafts(); setDiscard(false); setRefresh({}); setReceipt(null); setFileReceipt(null);
      setFileAction({ kind, mode, request: fileRequest() });
    }
    async function readSaved() {
      if (command.phase !== 'done' || !expectedStage || fileKind || request.current) return;
      const controller = new AbortController(); request.current = controller; setRefresh({ loading: true });
      try {
        if (!receiptMatches) throw C.failure(window.WorkbenchTerms.outcomes.pending('保存'));
        notify(command.result);
        const fresh = await loadPart(controller.signal);
        if (controller.signal.aborted) return;
        const key = expectedStage;
        setCurrent(fresh); setStage(fresh.data.workflow.stage); setSaved(old => ({ ...old, [key]: old[key] + 1 })); onDirty(key, false);
        if (key === 'route') { setEntry(false); setEntryStarted(false); }
        setReceipt(command.result); setRefresh({ done: true });
        if (!command.reset()) setRefresh({ error: C.failure('保存已确认，但本机还留着上次操作记录。请点「查询结果」重试。') });
      } catch (error) { if (!controller.signal.aborted) setRefresh({ error }); }
      finally { if (request.current === controller) request.current = null; }
    }
    React.useEffect(() => { if (command.phase === 'done' && expectedStage && !fileKind) readSaved(); }, [command.phase, command.result]);
    async function readFileSaved(value) {
      if (!value || request.current) return;
      const controller = new AbortController(); request.current = controller; setRefresh({ loading: true });
      try {
        const fresh = await loadPart(controller.signal);
        if (controller.signal.aborted) return;
        setCurrent(fresh); setStage(fresh.data.workflow.stage); resetDrafts(); setRefresh({ done: true });
        if (command.reset()) setFileReceipt(null);
        else setRefresh({ error: C.failure('文件已保存，但本机还留着上次操作记录。请点「查询结果」重试。') });
      } catch (error) { if (!controller.signal.aborted) setRefresh({ error: C.failure('文件已保存，但刷新零件详情失败：' + C.message(error) + ' 请点「查询结果」重试；如果这条零件已删除，不能续用同图号的新零件。') }); }
      finally { if (request.current === controller) request.current = null; }
    }
    function fileCommitted(value) {
      window.APSProcessFiles.receipt(value, command.intent, fileAction.kind, null, partRef);
      setFileReceipt(value); setReceipt(value); setFileAction(null); notify(value); readFileSaved(value);
    }
    function close() {
      if (locked) return;
      if (hasDraft) { setDiscard(true); return; }
      if (command.reset()) onClose();
    }
    const result = current, entity = result && result.data;
    const selected = stage || (entity && (entity.workflow.route.state !== 'confirmed' ? 'route' : entity.workflow.stage));
    const prerequisite = entity && (selected === 'source' && entity.workflow.route.state !== 'confirmed' ? '路线尚未确认；当前只读定位，不能确认归属。'
      : selected === 'hours' && (entity.workflow.route.state !== 'confirmed' || entity.workflow.source.state !== 'confirmed') ? '前置路线或归属尚未确认；当前只读定位，不能确认工时。' : '');
    React.useEffect(() => {
      if (!browsing || !entity || target.operationRef || target.groupRef || !root.current) return undefined;
      const frame = requestAnimationFrame(() => { const tab = root.current && root.current.querySelector('.stepper [aria-selected="true"]'); if (tab) { tab.focus(); tab.scrollIntoView({ block: 'nearest' }); } });
      return () => cancelAnimationFrame(frame);
    }, [browsing, entity, selected, target]);
    return <div className="plana process-detail" ref={root}>
      <Modal title={entity ? entity.business_code + ' · ' + entity.label : '零件工艺详情'} icon="chart-gantt" onClose={close} locked={locked} suspended={entry || overlay || !!discard || !!fileAction}
        footer={<><span className="muted" style={{ marginRight: 'auto' }}>{entity ? '此工艺已用于 ' + entity.relationships.batch_count + ' 个批次。修改后，已有批次工序不会自动更新。' : ''}</span><Button disabled={locked} onClick={close}>关闭详情</Button></>}>
        <div className="modal-b scroll pd-modal-b">
          {detail.loading && !entity && <p role="status">正在读取工艺详情…</p>}<ErrorBox error={detail.error} />{detail.error && <Button icon="refresh-cw" onClick={detail.reload}>刷新详情</Button>}
          {!fileKind && !fileReceipt && <window.ResourceForms.Feedback command={visibleCommand} />}
          {refresh.loading && (receiptMatches || fileReceipt) && <p role="status">保存已确认，正在刷新工艺详情…</p>}<ErrorBox error={refresh.error} />{refresh.error && !needsReceiptCheck && <Button icon="refresh-cw" onClick={fileReceipt ? () => readFileSaved(fileReceipt) : readSaved}>查询结果</Button>}
          {fileReceipt && !refresh.done && !refresh.loading && <p role="status">资料尚未刷新，请刷新后继续编辑。</p>}
          {receipt && refresh.done && command.phase === 'idle' && <p role="status">提交已确认，工艺详情已刷新。</p>}
          {entity && <><Issues issues={result.warnings} /><Issues issues={entity.issues} /><Steps entity={entity} stage={selected} disabled={editingBlocked} onStage={setStage} />
            {browsing && <section data-process-navigation-stage={selected}>
              <div className="toolbar"><span role="status">已按原零件记录只读定位 · {({ route: '工艺路线', source: '归属', hours: '工时定额', ready: '已就绪汇总' })[selected]}</span>
                <Button icon="square-pen" disabled={editingBlocked} reason={prerequisite} onClick={() => setBrowsing(false)}>开始维护</Button></div>
              {prerequisite && <p role="status">{prerequisite}</p>}
              <p><E.Confirmation record={entity.workflow[selected === 'ready' ? 'hours' : selected]} /></p>
              {selected === 'route' && <dl className="process-fields"><dt>原始路线</dt><dd>{E.value(entity.fields.route_raw)}</dd></dl>}
              <Operations key={selected} entity={entity} hours={selected !== 'route'} focusRef={target.operationRef} />
              <E.Groups key={'groups-' + selected} rows={entity.external_groups} focusRef={target.groupRef} />
            </section>}
            {!browsing && <>{entity.workflow.ready && <div className="toolbar"><span className="pill ok">三阶段已确认 · 已就绪</span><Button icon="check" onClick={() => setStage('ready')} disabled={editingBlocked}>查看汇总</Button></div>}
            <div hidden={selected !== 'route'}><RouteView entity={entity} disabled={editingBlocked} onFileAction={openFile} previewAvailable={typeof adapter.routePreview === 'function'} onEntry={() => { setEntryStarted(true); setEntry(true); }} /></div>
            <div hidden={selected !== 'source'}><window.ProcessSourceEditor key={saved.source} adapter={adapter} result={result} command={visibleCommand} disabled={editorDisabled} saved={saved.source} onDirty={onDirty} onOverlay={setOverlay} onResourceCommitted={onCommitted} /></div>
            <div hidden={selected !== 'hours'}><window.ProcessHoursEditor key={saved.hours} adapter={adapter} result={result} command={visibleCommand} disabled={editorDisabled} saved={saved.hours} onDirty={onDirty} onOverlay={setOverlay} onFileAction={openFile} /></div>
            {selected === 'ready' && <><Operations entity={entity} hours /><E.Groups rows={entity.external_groups} /><p><E.Confirmation record={entity.workflow.hours} /></p></>}</>}
          </>}
        </div>
      </Modal>
      {entryStarted && result && <div hidden={!entry}><window.ProcessRouteEntry adapter={adapter} result={result} command={visibleCommand} active={entry} disabled={disabled || refresh.loading} refreshState={needsReceiptCheck ? {} : refresh} onRefresh={readSaved} onDirty={onDirty} onClose={() => setEntry(false)} /></div>}
      {fileAction && <window.ProcessFileActions adapter={adapter} {...fileAction} onClose={() => setFileAction(null)} onCommitted={fileCommitted} disabled={disabled} />}
      {discard && <Modal title="放弃未保存的工艺草稿？" icon="square-pen" onClose={() => setDiscard(false)} footer={<><Button onClick={() => setDiscard(false)}>继续编辑</Button><Button className="btn danger" onClick={() => { if (discard.kind) openFile(discard.kind, discard.mode, true); else if (command.reset()) onClose(); }}>{discard.kind ? '放弃草稿并打开文件' : '放弃草稿并关闭'}</Button></>}><div className="modal-b">未保存的路线、归属和工时修改将被丢弃；已经保存成功的内容不受影响。</div></Modal>}
    </div>;
  }
  function ProcessDetail(props) { return <DetailSession key={props.partRef} {...props} />; }
  window.ProcessDetail = ProcessDetail;
})();
