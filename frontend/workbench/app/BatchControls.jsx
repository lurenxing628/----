(function () {
  'use strict';
  const B = window.APSBatchContract;
  // Lucide v1.8.0 ISC: icons/funnel, copy, arrow-left. Existing assets/lucide-LICENSE applies.
  Object.assign(window.APSFieldReports.iconNodes, {
    filter: [['path', { d: 'M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z' }]],
    copy: [['rect', { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' }], ['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]],
    'arrow-left': [['path', { d: 'm12 19-7-7 7-7' }], ['path', { d: 'M19 12H5' }]]
  });
  function Field({ label, children, full = false }) {
    const id = React.useId();
    return <div className={'field' + (full ? ' full' : '')}><label htmlFor={id}>{label}</label>{React.cloneElement(children, { id, 'aria-label': label })}</div>;
  }
  function BaseFields({ value, setValue, disabled, entity, choices }) {
    const set = (key, next) => setValue(current => ({ ...current, [key]: next }));
    const input = (key, label, type = 'text') => <Field key={key} label={label}><input type={type} value={value[key]} disabled={disabled}
      min={type === 'number' ? 1 : undefined} step={type === 'number' ? 1 : undefined} onChange={event => set(key, event.target.value)} /></Field>;
    const select = (key, label, options) => <Field label={label}><select value={value[key]} disabled={disabled} onChange={event => set(key, event.target.value)}>
      {!options.some(row => row[0] === value[key]) && <option value={value[key]}>原值待核对</option>}{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>;
    return <div className="fgrid batch-fields">
      {entity ? <><Field label="批次号"><input disabled value={entity.business_code} /></Field><Field label="图号"><input disabled value={entity.relationships.part_no + ' · ' + entity.label} /></Field></>
        : <>{input('business_code', '批次号')}<Field label="图号"><select value={value.part_ref} disabled={disabled || !choices} onChange={event => set('part_ref', event.target.value)}>
          <option value="">请选择图号</option>{choices && choices.parts.map(row => <option key={row.ref} value={row.ref}>{row.business_code} · {row.label}</option>)}</select></Field></>}
      {input('quantity', '数量', 'number')}{input('due_date', '交期', 'date')}{select('priority', '优先级', B.priority)}
      {select('ready_status', '齐套显示', B.ready)}{input('ready_date', '齐套日期', 'date')}{input('remark', '备注')}
    </div>;
  }
  function Styles() {
    return <style>{`
      .plana.batch-workspace { padding:0; max-width:none; width:100%; min-width:0; color:var(--ui-text); letter-spacing:0; }
      .batch-workspace h2 { font-size:18px; margin:0; line-height:1.5; }
      .batch-workspace h3 { font-size:15px; margin:0 0 14px; line-height:1.5; }
      .batch-workspace .batch-band { padding:18px 0; border-bottom:1px solid var(--ui-border); }
      .batch-workspace .toolbar { flex-wrap:wrap; gap:8px; }
      .batch-workspace .toolbar .search { flex:1 1 220px; min-width:160px; max-width:420px; }
      .batch-workspace .pager { color:var(--ui-info-muted); }
      .batch-workspace table { width:100%; table-layout:fixed; }
      .batch-workspace td { white-space:normal !important; overflow-wrap:anywhere; }
      .batch-workspace .batch-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
      .batch-workspace .field { min-width:0; }
      .batch-workspace .field input,.batch-workspace .field select { width:100%; min-width:0; max-width:100%; box-sizing:border-box; }
      .batch-workspace .batch-readiness { display:flex; flex-wrap:wrap; gap:12px 24px; }
      .batch-workspace .batch-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
      .batch-workspace .batch-progress { display:flex; gap:8px; align-items:center; }
      .batch-workspace progress { width:54px; height:6px; accent-color:var(--ui-success); }
      .batch-workspace .batch-head { display:flex; gap:4px; align-items:center; }
      .batch-workspace .batch-column-resizer { position:absolute; right:0; top:0; bottom:0; width:7px; cursor:col-resize; touch-action:none; }
      .batch-workspace .batch-column-resizer:hover,.batch-workspace .batch-column-resizer:focus { background:var(--ui-border); }
      .batch-workspace .batch-preview { overflow:auto; max-height:40vh; }
      .batch-workspace .batch-preview table { min-width:600px; }
      .batch-workspace .modal { display:flex; flex-direction:column; max-width:calc(100vw - 24px); max-height:calc(100vh - 24px); }
      .batch-workspace .modal-head,.batch-workspace .modal-f { flex-shrink:0; }
      .batch-workspace .modal-b { flex:1 1 auto; min-height:0; overflow:auto; }
      .batch-workspace .batch-value-list { max-height:42vh; overflow:auto; display:grid; gap:8px; padding:8px 0; }
      .batch-workspace .batch-value-list label { display:flex; gap:8px; align-items:center; overflow-wrap:anywhere; }
      .batch-workspace .batch-preview pre { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font-family:inherit; }
      @media(max-width:600px) { .batch-workspace .batch-fields { grid-template-columns:minmax(0,1fr); } .batch-workspace .modal-b { padding:14px; } }
    `}</style>;
  }
  window.BatchControls = { Field, BaseFields, Styles };
})();
