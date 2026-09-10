/* Real source editor, extracted Steps/style and BatchFiles; in-memory adapters, no persistence.
   Subtab specimens mirror ProcessWorkspace presentation; the original source hash is recorded. */
(function () {
  'use strict';
  const { Button } = window.ResourceControls;
  const ref = value => String(value).padStart(48, '0');
  const context = { write_token: 'az-mock-only', capabilities: { 'batch.import_confirm': true }, blocked_reasons: [] };
  const command = { phase: 'idle', locked: false, error: null, result: null,
    submit: (...args) => { window.az.submissions.push(args); } };
  const stamp = state => ({ state, confirmed_at: null, confirmed_by: null });
  function Source({ disabled }) {
    const result = React.useMemo(() => ({ meta: { source: 'production', snapshot_ref: 'az-memory-only' }, data: {
      ref: ref(1), external_groups: [], capabilities: { stage_confirm: true },
      workflow: { route: stamp('confirmed'), source: stamp('unconfirmed') },
      operations: ['internal', 'external'].map((source, index) => ({ ref: ref(index + 2), sequence: (index + 1) * 10,
        label: index ? '表面处理' : '精加工', source, status: 'active', op_type_ref: ref(index + 5),
        op_type_label: index ? '表面处理' : '精加工', supplier_ref: index ? ref(9) : null, supplier_label: index ? '外协供应商' : null,
        confirmation: { source: stamp('unconfirmed') }, issues: [] }))
    } }), []);
    const adapter = React.useMemo(() => ({ command() { throw new Error('Source writes are outside this visual fixture'); } }), []);
    return <window.ProcessSourceEditor result={result} adapter={adapter} command={command} disabled={disabled} saved={0} onOverlay={() => {}} />;
  }
  function Contrast() {
    const [disabled, setDisabled] = React.useState(false), [stage, setStage] = React.useState('source');
    const [tab, setTab] = React.useState('source'), [mode, setMode] = React.useState('text');
    window.az.disable = setDisabled;
    return <main className="plana" style={{ padding: 24 }}>
      <h2>工艺资料</h2>
      <div data-secondary-copy-surfaces>
        {['bg', 'card-bg', 'surface-soft', 'surface-muted'].map(surface => <p key={surface}
          data-secondary-copy={surface} className="muted" style={{ background: 'var(--ui-' + surface + ')' }}>
          产能链 / 物料资料 · 共 25 条 · 第 1 / 2 页</p>)}
      </div>
      <div className="subtabs" role="tablist" aria-label="工艺阶段">
        {window.APSProcessContract.stages.map(([key, label]) => <Button key={key} className={'subtab' + (tab === key ? ' on' : '')}
          role="tab" aria-selected={tab === key} disabled={disabled} onClick={() => setTab(key)}>{label}<b className="cnt">12</b></Button>)}
      </div>
      <section className="process-detail"><window.AZProcessDetailStyles />
        <window.AZProcessSteps entity={{ workflow: { route: stamp('confirmed'), source: stamp('unconfirmed'), hours: stamp('locked') } }}
          stage={stage} onStage={setStage} disabled={disabled} />
        <Source disabled={disabled} />
      </section>
      <div className="process-detail"><div className="seg re-mode" role="tablist" aria-label="路线录入模式">
        {['text', 'rows'].map(key => <Button key={key} role="tab" className={mode === key ? 'on' : ''} aria-selected={mode === key} disabled={disabled} onClick={() => setMode(key)}>{key === 'text' ? '整条录入' : '逐行表格'}</Button>)}
      </div></div>
      <div className="toolbar"><Button className="btn primary" disabled={disabled}>保存资料</Button>
        <Button className="btn danger" disabled={disabled}>删除资料</Button></div>
    </main>;
  }
  function Batch({ spec }) {
    const [opened, setOpened] = React.useState(true);
    const adapter = React.useMemo(() => ({
      async importPreview(file, mode) {
        window.az.previews.push({ file: file.name, mode });
        const count = spec.count || 80;
        return { data: { operation: 'batch.import_confirm', mode, preview_ref: 'a'.repeat(32),
          write_context: spec.rejected ? null : context, can_confirm: !spec.rejected, count,
          rows: Array.from({ length: count }, (_, index) => ({ row: index + 2, business_code: 'AZ-NEW-' + index,
            action: 'create', errors: [], before: null, input: { fields: { quantity: index + 1, remark: '核对原始记录' } } })),
          deleted: Array.from({ length: count }, (_, index) => ({ entity_ref: ref(index + 1),
            before: { business_code: 'AZ-OLD-' + String(index + 1).padStart(3, '0'), operations: [] },
            errors: spec.rejected ? ['已有计划 / 执行引用，拒绝删除'] : [] })),
          warnings: [] } };
      }
    }), [spec]);
    return <main className="plana batch-workspace"><window.BatchControls.Styles />
      {opened && <window.BatchFiles adapter={adapter} mode="import" scope={{}} selected={[]} snapshot="az-memory-only"
        command={command} onClose={() => { window.az.cancelled++; setOpened(false); }} onCommitted={() => {}} disabled={false} />}
    </main>;
  }
  let mounted;
  window.azMount = (kind, spec = {}) => {
    if (mounted) mounted.unmount();
    window.az = { submissions: [], previews: [], cancelled: 0 };
    mounted = ReactDOM.createRoot(document.getElementById('root'));
    mounted.render(<><window.WorkbenchControlStyles />{kind === 'contrast' ? <Contrast /> : <Batch spec={spec} />}</>);
  };
})();
