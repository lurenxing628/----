(function () {
  'use strict';
  const { Button, ErrorBox, Issues } = window.ResourceControls;
  const C = window.APSResourceContract, P = window.APSPlanContract, S = window.APSResourceSession;
  function Identity({ plan }) {
    const unavailable = !plan.capabilities.view;
    const text = plan.is_current_official ? '当前正式' : plan.kind === 'official' ? '历史正式' : plan.kind === 'candidate' ? '候选预览' : '场景预览';
    return <span className={'plan-state ' + (unavailable ? 'unavailable' : plan.is_current_official ? 'official' : '')}>{text}{unavailable ? ' · 不可查看' : ''}</span>;
  }
  function Catalog({ adapter, selectedRef, onSelect, autoSelect = false, disabled = false }) {
    const [collection, setCollection] = React.useState('history'), [pages, setPages] = React.useState([{}]), [index, setIndex] = React.useState(0);
    const [paused, setPaused] = React.useState(false), [collapsed, setCollapsed] = React.useState(!!selectedRef);
    const attempted = React.useRef(false), section = React.useRef(null), restoreFocus = React.useRef(false);
    const scope = React.useMemo(() => ({ collection, size: 20, ...pages[index] }), [collection, pages, index]);
    const read = S.useQuery(async signal => {
      if (typeof adapter.catalog !== 'function') throw C.failure('计划目录接口尚未接入。');
      return P.catalog(await adapter.catalog(scope, signal), scope);
    }, [adapter, scope], !paused);
    const result = read.result, data = result && result.data;
    React.useEffect(() => {
      if (attempted.current || !data || read.loading || read.error || collection !== 'history' || index !== 0) return;
      attempted.current = true;
      const plan = autoSelect && !selectedRef && !disabled ? window.PlanSelectionModel.defaultPlan(data.plans) : null;
      if (plan) { setCollapsed(true); onSelect(plan); }
    }, [data, read.loading, read.error, autoSelect, selectedRef, disabled, collection, index]);
    React.useLayoutEffect(() => {
      if (collapsed && restoreFocus.current && section.current) {
        restoreFocus.current = false; section.current.querySelector('[aria-label="展开计划目录"]').focus();
      }
    }, [collapsed]);
    function choose(plan) {
      restoreFocus.current = !!(document.activeElement && document.activeElement.closest('.plan-catalog-scroll'));
      attempted.current = true; setCollapsed(true); onSelect(plan);
    }
    function refresh(next = collection) { setCollection(next); setPages([{}]); setIndex(0); setPaused(false); read.reload(); }
    function next() {
      const page = { cursor: data.page.next_cursor, snapshot_ref: result.meta.snapshot_ref };
      setPages(current => current.slice(0, index + 1).map(item => ({ ...item, snapshot_ref: result.meta.snapshot_ref })).concat(page)); setIndex(index + 1);
    }
    return <section ref={section} className="plan-catalog" aria-label="排产方案目录" data-collapsed={collapsed}>
      <div className="plan-toolbar"><label className="plan-catalog-picker">所选计划 <select aria-label="切换所选计划" value={selectedRef || ''} disabled={disabled || read.loading || !!read.error} onChange={event => {
        const plan = data && data.plans.find(item => item.plan_ref === event.target.value && item.capabilities.view);
        if (plan) choose(plan);
      }}><option value="" disabled>请选择计划</option>{selectedRef && (!data || !data.plans.some(plan => plan.plan_ref === selectedRef)) && <option value={selectedRef}>已选计划（其他目录页）</option>}
        {data && data.plans.filter(plan => plan.plan_ref).map(plan => <option key={plan.plan_ref} value={plan.plan_ref} disabled={!plan.capabilities.view}>{plan.display_name}{plan.is_current_official ? ' · 当前正式' : ''}</option>)}</select></label>
        {!collapsed && <window.PlanSegmentUI value={collection} options={[["history", "历史版本"], ["scenario", "已存场景"]]} label="计划目录范围" onChange={refresh} disabled={disabled} />}
        <div className="plan-actions"><Button className="btn plan-icon" icon="refresh-cw" aria-label="刷新计划目录" disabled={disabled} busy={read.loading} onClick={() => refresh()} />
          {read.loading && <Button icon="x" className="btn plan-icon" aria-label="取消目录读取" onClick={() => setPaused(true)} />}
          <Button icon="chevron-down" className={'btn plan-icon' + (collapsed ? '' : ' plan-up')} aria-label={collapsed ? '展开计划目录' : '收起计划目录'} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)} /></div>
      </div>
      <ErrorBox error={read.error} />
      {(read.error || paused) && <div className="plan-pager"><span>{paused ? '目录读取已取消。' : '目录未读取成功，原选中计划未替换。'}</span><Button icon="refresh-cw" onClick={() => refresh()}>重新读取目录</Button></div>}
      {result && <Issues issues={result.warnings} />}
      {!collapsed && <div className="plan-catalog-scroll wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="可选排产方案" aria-busy={read.loading}>
        <caption className="wb-visually-hidden">可选排产方案</caption><thead><tr><th className="wb-col-key" scope="col">计划 / 方案</th><th scope="col">版本</th><th scope="col">身份</th><th scope="col">记录状态</th></tr></thead>
        <tbody>{data && data.plans.map((plan, row) => <tr key={plan.plan_ref || 'unavailable-' + row} aria-selected={!!plan.plan_ref && plan.plan_ref === selectedRef}>
          <td className="wb-col-key"><label title={plan.blocked_reasons.map(reason => reason.message).join('\n')}><input type="radio" name="plan-choice" aria-label={'选择 ' + plan.display_name} checked={!!plan.plan_ref && plan.plan_ref === selectedRef}
            disabled={disabled || !plan.capabilities.view} onChange={() => choose(plan)} /><strong>{plan.display_name}</strong></label></td>
          <td>{plan.version === null ? '未记录' : String(plan.version)}</td><td><Identity plan={plan} /></td>
          <td>{({ complete: '记录完整', partial: '部分记录', invalid: '无效记录', unknown: '无法核实' })[plan.completeness]}
            {plan.blocked_reasons.length > 0 && <div className="plan-muted">{plan.blocked_reasons.map(reason => reason.message).join('；')}</div>}</td>
        </tr>)}{(!data || !data.plans.length) && <tr><td colSpan={4}><window.WorkbenchControls.EmptyState kind={read.loading ? 'loading' : 'empty'} title={read.loading ? '正在读取计划目录…' : paused ? '读取已取消' : read.error ? '目录读取失败' : '本页没有计划记录。'} /></td></tr>}</tbody>
      </table></div>}
      {data && !collapsed && <div className="plan-pager">
        {selectedRef && !data.plans.some(plan => plan.plan_ref === selectedRef) && <span className="plan-muted">已选计划不在本段，选择保持不变</span>}
        <window.WorkbenchControls.Pager mode="cursor" page={index + 1} label="计划目录" disabled={disabled} busy={read.loading} hasPrevious={index > 0} hasNext={data.page.has_more}
          onPrevious={() => setIndex(index - 1)} onNext={next} /></div>}
    </section>;
  }
  window.PlanCatalogUI = { Catalog, Identity };
})();
