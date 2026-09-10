(function () {
  'use strict';
  const C = window.APSResourceContract;
  // Existing Plan A rail paths; action icons use the bundled Lucide subset.
  const railPaths = {
    machine: ['M3 20h18', 'M5 20V9l5 3V9l5 3V6l4 2v12'],
    wrench: ['M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z'],
    truck: ['M3 6h11v9H3z', 'M14 9h3.5L21 12.2V15h-7z'],
    'arrow-right': ['M5 12h13M13 6l6 6-6 6']
  };
  function Icon({ name }) {
    const nodes = window.APSFieldReports && window.APSFieldReports.iconNodes[name];
    if (nodes) return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {nodes.map(([tag, attrs], index) => React.createElement(tag, { ...attrs, key: index }))}</svg>;
    if (name === 'refresh-cw' && typeof SMIcon === 'function') return <SMIcon name={name} />;
    if (railPaths[name]) return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {railPaths[name].map((d, index) => <path key={index} d={d} />)}
      {name === 'truck' && <><circle cx="7" cy="18" r="1.9" /><circle cx="17" cy="18" r="1.9" /></>}</svg>;
    return typeof Ico === 'function' ? <Ico name={name} /> : null;
  }
  function Button({ icon, transfer, children, reason, busy, className = 'btn', ...props }) {
    const title = reason || props.title || (typeof children === 'string' ? children : props['aria-label']);
    if (className.split(/\s+/).includes('primary')) className = Array.from(new Set(className.split(/\s+/).concat(['wb-action', 'wb-primary']))).join(' ');
    return <span title={title} style={{ display: 'inline-flex', maxWidth: '100%' }}>
      <button {...props} type={props.type || 'button'} className={className + (transfer ? ' wb-action wb-transfer' : '')} data-wb-transfer={transfer} disabled={!!reason || busy || props.disabled}
        style={className.startsWith('mini') ? { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5, ...props.style } : props.style}
        title={title} aria-label={props['aria-label'] || (reason && typeof children === 'string' ? children + '：' + reason : undefined)} aria-busy={busy || undefined}>
        {transfer ? <window.APSWorkbenchUI.TransferIcon kind={transfer} /> : icon && <Icon name={icon} />}{children}</button></span>;
  }
  function ErrorBox({ error }) {
    if (!error) return null;
    return <div role="alert" className="match-note" style={{ display: 'block', color: 'var(--ui-danger-text)', overflowWrap: 'anywhere' }}>
      <div>{C.message(error)}</div>{C.fieldErrors(error).map((row, index) => <div key={index}>{row.message}</div>)}</div>;
  }
  function Issues({ issues = [] }) {
    return issues.length ? <div className="match-note" role="status" style={{ display: 'block', overflowWrap: 'anywhere' }}>
      {issues.map((issue, index) => <div key={index}>{typeof issue === 'string' ? issue : issue.message || '该记录存在待核对问题。'}</div>)}</div> : null;
  }
  function Status({ kind, entity }) {
    const value = entity.status, tone = value === 'active' ? 'ok' : value === 'inactive' && entity.fields.inactive_reason !== 'unknown' ? 'off' : 'warn';
    return <span className={'pill ' + tone} style={{ whiteSpace: 'normal' }}><span className="dot" />{C.statusLabel(kind, value, entity.fields)}</span>;
  }
  const ModalFocusParent = React.createContext(null), modalStack = [];
  const modalSelector = 'button,input,select,textarea,a[href],[tabindex]';
  let modalFocusQueued = false, modalRestores = [];
  function modalVisible(node) {
    return !!(node && node.isConnected && node.getClientRects().length && !node.closest('[hidden],[inert],[aria-hidden="true"]') &&
      !['hidden', 'collapse'].includes(getComputedStyle(node).visibility));
  }
  function modalFocusable(node) { return modalVisible(node) && node.matches(modalSelector) && !node.matches(':disabled') && typeof node.focus === 'function'; }
  function topModal() { return modalStack.slice().reverse().find(entry => !entry.suspended && modalVisible(entry.root)); }
  function modalItems(entry) { return Array.from(entry.root.querySelectorAll(modalSelector)).filter(node => node.tabIndex >= 0 && modalFocusable(node)); }
  function focusModal(entry, preferred) {
    const items = modalItems(entry);
    const target = [preferred, entry.last].find(node => modalFocusable(node) && entry.root.contains(node)) ||
      items.find(node => node.matches('input,select,textarea')) || items[0] || entry.root;
    if (document.activeElement !== target) target.focus();
  }
  function syncModalFocus() {
    if (modalFocusQueued) return;
    modalFocusQueued = true;
    // React may clean up parents before children, or replay effects. Restore only after the commit settles.
    queueMicrotask(() => {
      modalFocusQueued = false;
      const restores = modalRestores; modalRestores = [];
      const top = topModal(), candidates = [];
      restores.reverse().forEach(entry => { for (let item = entry; item; item = item.parent) candidates.push(item.previous); });
      if (top) {
        const previous = candidates.find(node => modalFocusable(node) && top.root.contains(node));
        if (previous || !top.root.contains(document.activeElement) || !modalFocusable(document.activeElement)) focusModal(top, previous);
      } else {
        const previous = candidates.find(node => modalFocusable(node) && !modalStack.some(entry => entry.root.contains(node)));
        if (previous) previous.focus();
      }
    });
  }
  function modalKeydown(event) {
    const entry = topModal();
    if (!entry || event.defaultPrevented) return;
    if (event.key === 'Escape' && event.target.closest && event.target.closest('[data-wb-table-filter],.wb-control-popup')) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!entry.locked) entry.close(); }
    if (event.key === 'Tab') {
      const items = modalItems(entry), start = items[0] || entry.root, end = items[items.length - 1] || entry.root;
      if (event.shiftKey && (document.activeElement === start || document.activeElement === entry.root || !entry.root.contains(document.activeElement))) { event.preventDefault(); end.focus(); }
      else if (!event.shiftKey && (document.activeElement === end || document.activeElement === entry.root || !entry.root.contains(document.activeElement))) { event.preventDefault(); start.focus(); }
    }
  }
  function retainModalFocus(event) {
    const entry = topModal();
    if (!entry) return;
    if (entry.root.contains(event.target)) entry.last = event.target;
    else focusModal(entry);
  }
  function mountModal(entry) {
    // Portal descendants retain React ancestry even when their DOM is outside the parent dialog.
    const index = modalStack.findIndex(item => { for (let parent = item.parent; parent; parent = parent.parent) if (parent === entry) return true; return false; });
    modalStack.splice(index < 0 ? modalStack.length : index, 0, entry);
    if (modalStack.length === 1) {
      document.addEventListener('keydown', modalKeydown); document.addEventListener('focusin', retainModalFocus);
    }
    syncModalFocus();
    return () => {
      modalStack.splice(modalStack.indexOf(entry), 1); modalRestores.push(entry);
      if (!modalStack.length) {
        document.removeEventListener('keydown', modalKeydown); document.removeEventListener('focusin', retainModalFocus);
      }
      syncModalFocus();
    };
  }
  function Modal({ title, icon, children, footer, onClose, locked, labelId, suspended }) {
    const ref = React.useRef(null), entry = React.useRef({}), parent = React.useContext(ModalFocusParent);
    const backdropStart = React.useRef(false), id = React.useId();
    React.useLayoutEffect(() => {
      Object.assign(entry.current, { root: ref.current, close: onClose, locked, suspended });
      syncModalFocus();
    });
    React.useLayoutEffect(() => {
      entry.current.previous = document.activeElement;
      entry.current.parent = parent || modalStack.slice().reverse().find(item => item.root.contains(entry.current.previous)) || null;
      return mountModal(entry.current);
    }, []);
    const canClose = () => topModal() === entry.current && !entry.current.locked;
    return <ModalFocusParent.Provider value={entry.current}><div className="modal-bg" style={suspended ? { visibility: 'hidden' } : undefined}
      onPointerDown={event => { backdropStart.current = canClose() && event.button === 0 && event.target === event.currentTarget; }}
      onPointerUp={event => { backdropStart.current = backdropStart.current && event.target === event.currentTarget; }}
      onPointerCancel={() => { backdropStart.current = false; }}
      onClick={event => {
        const dismiss = backdropStart.current && event.target === event.currentTarget;
        backdropStart.current = false;
        if (dismiss && canClose()) entry.current.close();
      }}><div className="modal lg" role="dialog" aria-modal={suspended ? undefined : true} aria-labelledby={labelId || id} ref={ref} tabIndex={-1}>
      <div className="modal-head"><span className="modal-ico"><Icon name={icon} /></span><div style={{ minWidth: 0, overflowWrap: 'anywhere' }}><div className="modal-h2" id={labelId || id}>{title}</div></div>
        <span style={{ marginLeft: 'auto' }}><Button className="modal-x" icon="x" aria-label="关闭" onClick={() => { if (canClose()) entry.current.close(); }} reason={locked ? '操作尚未核实，请保留当前页面。' : ''} /></span></div>
      {children}<div className="modal-f wb-actions" style={{ flexWrap: 'wrap', marginLeft: 0, width: '100%', boxSizing: 'border-box' }}>{footer}</div></div></div></ModalFocusParent.Provider>;
  }
  function relationLabels(entity, key) {
    if (!entity) return [];
    const objects = { op_type_ref: 'op_type', group_ref: 'group', shift_profile_ref: 'shift_profile', skill_refs: 'skills', op_type_refs: 'op_types' };
    const related = entity.relationships[objects[key]], refs = entity.relationships[key];
    if (Array.isArray(related) && Array.isArray(refs)) return refs.map(ref => ({ ref, label: (related.find(item => item.ref === ref) || {}).label }));
    if (C.object(related) && related.ref === refs) return [{ ref: refs, label: related.label }];
    const map = { op_type_ref: 'op_type_label', group_ref: 'group_label', shift_profile_ref: 'shift_profile_label', skill_refs: 'skill_labels', op_type_refs: 'op_type_labels', machine_refs: 'machine_labels' };
    const value = entity && entity.relationships[key], labels = entity && entity.relationships[map[key]];
    if (Array.isArray(value)) return value.map((ref, index) => ({ ref, label: Array.isArray(labels) ? labels[index] : C.object(labels) ? labels[ref] : null }));
    return value ? [{ ref: value, label: typeof labels === 'string' ? labels : null }] : [];
  }
  function Relation({ entity, field, onOpen }) {
    const items = relationLabels(entity, field);
    return items.length ? <span className="chipline">{items.map(item => onOpen ? <Button key={item.ref} className="mini" icon="arrow-right" onClick={() => onOpen(item.ref)} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere', textAlign: 'left' }}>{item.label || '关联名称未提供'}</Button> : <span className="chip" key={item.ref} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{item.label || '关联名称未提供'}</span>)}</span> : <span className="muted">{entity.relationships[field] === null || Array.isArray(entity.relationships[field]) ? '未绑定' : '待读取'}</span>;
  }
  function Choice({ adapter, field, value, original, onChange, disabled, onCatalog, catalogBusy }) {
    const [search, setSearch] = React.useState(''), [query, setQuery] = React.useState('');
    const [searching, setSearching] = React.useState(false);
    const [page, setPage] = React.useState(1), [snapshot, setSnapshot] = React.useState(undefined);
    const [known, setKnown] = React.useState({});
    const id = React.useId();
    const S = window.APSResourceSession;
    const request = S.useQuery(async signal => {
      if (typeof adapter.choices !== 'function') throw C.failure('暂时无法读取可选资料，请稍后重试。');
      const scope = { query, page, size: 50 };
      if (field.category) scope.category = field.category;
      if (snapshot) scope.snapshot_ref = snapshot;
      return C.query(await adapter.choices(field.kind, scope, signal), 'choices');
    }, [adapter, field.kind, field.category, query, page, snapshot]);
    const response = request.result;
    React.useEffect(() => {
      if (!response) return;
      setKnown(current => {
        const result = { ...current };
        response.data.entities.forEach(item => { result[item.ref] = item; }); return result;
      });
    }, [response]);
    const selected = field.multiple ? value : value ? [value] : [];
    const originals = relationLabels(original, field.key);
    const rows = response ? response.data.entities : [];
    const available = new Map(rows.map(item => [item.ref, item]));
    selected.forEach(ref => {
      if (!available.has(ref)) {
        const old = originals.find(item => item.ref === ref);
        available.set(ref, known[ref] || { ref, label: old && old.label || '原关联（未在当前选项中）', status: 'missing', fields: {} });
      }
    });
    function selectable(item) { return (item.status === 'active' || field.kind === 'op_type' && item.status === null) && (!field.category || item.fields.category === field.category); }
    function choose(ref, checked) {
      if (field.multiple) onChange(checked ? selected.concat(ref) : selected.filter(item => item !== ref));
      else onChange(ref);
    }
    const changePage = next => { setSnapshot(response.meta.snapshot_ref); setPage(next); };
    const options = Array.from(available.values());
    return <div className={'field' + (field.multiple ? ' full' : '')} style={{ minWidth: 0 }}>
      <label htmlFor={id}>{field.label}</label>
      {searching && <div className="rowact"><div className="search" style={{ maxWidth: '100%', flex: '1 1 auto', minWidth: 0 }}><span className="ic"><Icon name="search" /></span>
        <input aria-label={'搜索' + field.label} value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} onKeyDown={event => {
          if (event.key === 'Enter') { event.preventDefault(); setQuery(search); setPage(1); setSnapshot(undefined); request.reload(); }
        }} /></div><Button icon="search" aria-label={'执行' + field.label + '搜索'} disabled={disabled} onClick={() => { setQuery(search); setPage(1); setSnapshot(undefined); request.reload(); }} /></div>}
      {field.multiple ? <div id={id} role="group" aria-label={field.label} className="fchips" style={{ maxHeight: 160, overflowY: 'auto' }}>
        {options.map(item => <label key={item.ref} className={'fchip' + (selected.includes(item.ref) ? ' on' : '')} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'normal', overflowWrap: 'anywhere' }}>
          <input type="checkbox" style={{ width: 15, height: 15, padding: 0, flex: 'none' }} checked={selected.includes(item.ref)}
            disabled={disabled || (!selected.includes(item.ref) && !selectable(item))} onChange={event => choose(item.ref, event.target.checked)} />
          {item.label}{!selectable(item) ? '（停用 / 未核实）' : ''}</label>)}</div> :
        <select id={id} value={value} disabled={disabled} onChange={event => choose(event.target.value)}>
          <option value="">未绑定</option>{options.map(item => <option key={item.ref} value={item.ref} disabled={!selectable(item) && item.ref !== value}>
            {item.label}{!selectable(item) ? '（停用 / 未核实）' : ''}</option>)}</select>}
      {request.loading && <span role="status" className="fhint">正在读取选项…</span>}
      <ErrorBox error={request.error} />
      {request.error && <Button disabled={disabled} onClick={() => { setPage(1); setSnapshot(undefined); request.reload(); }}>重读选项</Button>}
      {response && <div className="rowact" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="fhint">{response.data.page.total} 项{response.data.page.pages > 1 ? ' · 第 ' + response.data.page.number + ' 页' : ''}</span>
        <Button icon="search" aria-label={'查找' + field.label} aria-expanded={searching} disabled={disabled} onClick={() => setSearching(value => !value)} />
        {response.data.page.pages > 1 && <><Button icon="chevron-left" aria-label={field.label + '上一页'} disabled={disabled || page <= 1} onClick={() => changePage(page - 1)} />
        <Button icon="chevron-right" aria-label={field.label + '下一页'} disabled={disabled || page >= response.data.page.pages} onClick={() => changePage(page + 1)} /></>}</div>}
      {field.catalog && <Button icon="plus" busy={catalogBusy} disabled={disabled} reason={typeof adapter.openCatalog !== 'function' ? '暂不支持维护' + field.label + '。' : ''} onClick={() => onCatalog(field, request.reload)}>维护{field.label}</Button>}
    </div>;
  }
  window.ResourceControls = { Icon, Button, ErrorBox, Issues, Status, Modal, Relation, relationLabels, Choice };
})();
