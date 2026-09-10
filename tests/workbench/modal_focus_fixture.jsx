(function () {
  'use strict';
  const { Modal, Button } = ResourceControls;
  const ref = 'a'.repeat(48);
  const context = { write_token: 'focus-test-token', capabilities: { 'op_type.create': true }, blocked_reasons: [] };
  const envelope = data => ({ ok: true, schema_version: 1, data, meta: { source: 'production', time_basis: 'factory_local',
    snapshot_ref: 'focus-snapshot', request_ref: 'focus-request', as_of: '2026-09-10T01:00:00' }, warnings: [] });
  let mounted;
  function Flow({ spec }) {
    const [open, setOpen] = React.useState(false), [child, setChild] = React.useState(false), [hidden, setHidden] = React.useState(false);
    const adapter = React.useMemo(() => ({
      list: async () => envelope({ entities: [], page: { number: 1, size: 20, total: 0, pages: 1, sort: [] }, create_context: context }),
      detail: async () => envelope({ ref, business_code: 'AY-OP-NEW', label: 'AY待建工种', status: null,
        fields: { category: 'internal' }, relationships: {}, issues: [], write_context: context }),
      command: async (kind, action, target, body) => {
        focusFixture.calls.push({ kind, action, target, body });
        if (spec.pending) return { ok: true, result: 'pending' };
        return { ok: true, result: 'committed', receipt_ref: 'focus-receipt', data: { entity_ref: ref }, warnings: [] };
      },
      lookup: async key => { focusFixture.lookups.push(key); return focusFixture.resolved ?
        { ok: true, result: 'committed', receipt_ref: 'focus-receipt', data: { entity_ref: ref }, warnings: [] } : { ok: true, result: 'pending' }; }
    }), []);
    focusFixture.parentUnmount = () => { setOpen(false); setChild(false); };
    focusFixture.remountChild = () => setChild(true);
    return <><Button id="flow-trigger" onClick={() => { setOpen(true); setHidden(true); }}>打开流程工艺</Button>
      {open && <Modal title="流程工艺" suspended={child && spec.suspend !== false} onClose={() => setOpen(false)}
        footer={<Button onClick={() => setOpen(false)}>关闭详情</Button>}>
        <div className="modal-b form"><input aria-label="原路线" defaultValue="10AY待建工种" />
          <Button id="child-trigger" onClick={() => setChild(true)}>待建工种</Button>
          {child && ReactDOM.createPortal(<div className="plana"><ProcessOpTypeCreate adapter={adapter}
            onClose={() => { focusFixture.closed.push('resource'); setChild(false); }} onCommitted={receipt => focusFixture.receipts.push(receipt)} /></div>, document.body)}
        </div></Modal>}
      {hidden && <div hidden><Modal title="已挂载隐藏路线" onClose={() => focusFixture.closed.push('hidden')}
        footer={<Button>隐藏底部</Button>}><div className="modal-b"><input aria-label="隐藏路线" /></div></Modal></div>}
    </>;
  }
  function Layer({ level, spec }) {
    const [child, setChild] = React.useState(!!spec.initial && level < 3), [locked, setLocked] = React.useState(false);
    const [suspended, setSuspended] = React.useState(false), [filter, setFilter] = React.useState(false);
    focusFixture.layers[level] = { setChild, setLocked, setSuspended };
    function close() { focusFixture.closed.push(level); if (level === 1) focusFixture.setOpen(false); else focusFixture.layers[level - 1].setChild(false); }
    const nested = child && <Layer level={level + 1} spec={spec} />;
    return <Modal title={'层 ' + level} locked={locked} suspended={suspended || child && !!spec.suspend} onClose={close}
      footer={<Button id={'end-' + level} disabled={locked} onClick={close}>关闭层 {level}</Button>}>
      <div className="modal-b form"><div className="fgrid">
        <label className="field">输入 {level}<input aria-label={'输入 ' + level} id={'input-' + level} /></label>
        <label className="field">选择 {level}<select aria-label={'选择 ' + level} defaultValue="a"><option value="a">甲</option><option value="b">乙</option></select></label>
        <label className="field">日期 {level}<input aria-label={'日期 ' + level} type="date" defaultValue="2026-09-10" /></label></div>
        {level < 3 && (spec.generic ? <span role="button" tabIndex={0} id={'next-' + level} onClick={() => setChild(true)}>打开层 {level + 1}</span> :
          <Button id={'next-' + level} onClick={() => setChild(true)}>打开层 {level + 1}</Button>)}
        <Button id={'filter-' + level} onClick={() => setFilter(true)}>列筛选 {level}</Button>
        {filter && <div data-wb-table-filter onKeyDown={event => {
          if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); setFilter(false); document.getElementById('filter-' + level).focus(); }
        }}><input autoFocus aria-label="列筛选条件" /></div>}
        {spec.portal ? nested && ReactDOM.createPortal(<div className="plana">{nested}</div>, document.body) : nested}
      </div></Modal>;
  }
  function Stack({ spec }) {
    const [open, setOpen] = React.useState(false);
    focusFixture.setOpen = setOpen;
    return <><Button id="flow-trigger" disabled={spec.disableTrigger && open} onClick={() => setOpen(true)}>打开层 1</Button>{open && <Layer level={1} spec={spec} />}</>;
  }
  function Siblings() {
    const [open, setOpen] = React.useState(false), [child, setChild] = React.useState(false);
    focusFixture.removeParent = () => setOpen(false);
    return <><Button id="flow-trigger" onClick={() => setOpen(true)}>打开独立父窗</Button>
      {open && <Modal title="独立父窗" onClose={() => setOpen(false)} footer={<Button>父窗末尾</Button>}>
        <div className="modal-b"><Button id="child-trigger" onClick={() => setChild(true)}>打开独立子窗</Button></div></Modal>}
      {child && <Modal title="独立子窗" onClose={() => setChild(false)} footer={<Button onClick={() => setChild(false)}>关闭独立子窗</Button>}>
        <div className="modal-b"><input id="sibling-input" /></div></Modal>}</>;
  }
  function EffectsProbe() {
    React.useEffect(() => { focusFixture.effects.setup++; return () => { focusFixture.effects.cleanup++; }; }, []);
    return null;
  }
  window.mountFocus = spec => {
    if (mounted) mounted.unmount();
    window.focusFixture = { layers: {}, closed: [], calls: [], receipts: [], lookups: [], effects: { setup: 0, cleanup: 0 } };
    mounted = ReactDOM.createRoot(document.getElementById('fixture-root'));
    const content = <><EffectsProbe />{spec.flow ? <Flow spec={spec} /> : spec.siblings ? <Siblings /> : <Stack spec={spec} />}</>;
    ReactDOM.flushSync(() => mounted.render(spec.strict ? <React.StrictMode>{content}</React.StrictMode> : content));
  };
  window.unmountFocus = () => { if (mounted) { mounted.unmount(); mounted = null; } };
  let controls;
  window.mountFocusControls = () => {
    if (controls) controls.unmount();
    controls = ReactDOM.createRoot(document.getElementById('controls-root'));
    ReactDOM.flushSync(() => controls.render(<><WorkbenchControlStyles /><WorkbenchControls /><WorkbenchNumberControls /></>));
  };
  mountFocusControls();
})();
