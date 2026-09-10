(function () {
  const { useState, useEffect, useMemo, useRef } = React;
  function MDIcon({ name }) {
    // Local Lucide nodes; same license as assets/lucide-LICENSE.
    const local = {
      'arrow-up-right': [['path', { d: 'M7 7h10v10' }], ['path', { d: 'M7 17 17 7' }]],
      'refresh-cw': [['path', { d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8' }], ['path', { d: 'M21 3v5h-5' }], ['path', { d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16' }], ['path', { d: 'M8 16H3v5' }]]
    };
    const nodes = local[name] || window.APSFieldReports.iconNodes[name];
    return <svg className="md-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {nodes.map(([tag, attrs], i) => React.createElement(tag, { ...attrs, key: i }))}
    </svg>;
  }
  function readModel(model) {
    try { return { overview: model.read(), error: '' }; }
    catch (error) { return { overview: window.APSMasterDataOverview.buildOverview(null), error: '基础资料读取失败：' + error.message }; }
  }
  function tabKey(event, values, value, activate) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const index = values.indexOf(value), next = event.key === 'Home' ? 0 : event.key === 'End' ? values.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + values.length) % values.length;
    const buttons = event.currentTarget.parentElement.querySelectorAll('[role="tab"]');
    activate(values[next]); buttons[next].focus();
  }
  function MasterDataOverview({ onNav, model: providedModel }) {
    const uid = 'md-' + React.useId().replace(/:/g, '');
    const api = window.APSMasterDataOverview;
    const { MetricStrip, Metric, DataTable, TransferButton, ControlButton } = window.APSWorkbenchUI;
    const model = useMemo(() => providedModel || api.createModel(), [providedModel]);
    const [source, setSource] = useState(() => readModel(model));
    const [options, setOptions] = useState({ view: 'issues', domain: 'all', status: 'all', search: '', sort: 'issues', page: 1, pageSize: 20 });
    const [selectedKey, setSelectedKey] = useState(null), [detailView, setDetailView] = useState('issues');
    const [message, setMessage] = useState(''), [relatedPage, setRelatedPage] = useState(1);
    const root = useRef(null), detailRef = useRef(null), detailOpener = useRef(null), overview = source.overview;
    const result = api.query(overview, options), isIssue = options.view === 'issues';
    const selected = result.all.find(r => r.key === selectedKey) || result.rows[0];
    const entity = selected && (isIssue ? overview.byKey.get(selected.entityKey) : selected);
    const refresh = () => { setSource(readModel(model)); setMessage(''); };
    useEffect(() => {
      const reread = () => setSource(readModel(model));
      reread(); window.addEventListener('aps:master-data-changed', reread); window.addEventListener('focus', reread);
      return () => { window.removeEventListener('aps:master-data-changed', reread); window.removeEventListener('focus', reread); };
    }, [model]);
    useEffect(() => {
      root.current.querySelectorAll('.md-table tbody tr').forEach(tr => {
        const button = tr.querySelector('[data-md-select]');
        tr.setAttribute('aria-selected', String(!!selected && !!button && button.dataset.mdSelect === selected.key));
      });
    }, [selected, result.rows]);
    useEffect(() => { setRelatedPage(1); }, [entity && entity.key, detailView]);
    function update(patch) { setOptions(old => ({ ...old, ...patch, page: patch.page || 1 })); setSelectedKey(null); setMessage(''); }
    function select(row, event) {
      detailOpener.current = event.currentTarget;
      setSelectedKey(row.key); setDetailView('issues');
      if (detailRef.current) detailRef.current.focus();
    }
    function go(target) {
      try { api.navigate(target, onNav); } catch (error) { setMessage(error.message); }
    }
    function exportRows() {
      try { const file = api.downloadCSV(overview, options); setMessage('已发起下载：' + file.filename + '，共 ' + file.rows + ' 条。'); }
      catch (error) { setMessage('导出失败：' + error.message); }
    }
    const domainName = id => api.domains.find(d => d.id === id).label;
    const identity = row => <button type="button" className="md-entity-link" data-md-select={row.key} aria-pressed={!!selected && selected.key === row.key} aria-controls={uid + '-entity-detail'} onClick={event => select(row, event)}>
      <span className="md-code">{row.code}</span><span className="md-name">{row.name || '名称未填'}</span>
    </button>;
    const columns = [
      { key: 'identity', title: '编号 / 名称', width: 250, render: identity },
      { key: 'domain', title: '数据域', width: 86, render: row => domainName(row.domain) },
      ...(isIssue ? [
        { key: 'title', title: '待维护项', width: 190 },
        { key: 'evidence', title: '当前记录', width: 240 },
      ] : [
        { key: 'state', title: '检查状态', width: 90, render: row => <span className={'md-status md-' + row.status}>{api.statusLabels[row.status]}</span> },
        { key: 'completeness', title: '已填 / 检查字段', width: 112, render: row => <span className="md-number">{row.completeness.filled} / {row.completeness.total}</span> },
        { key: 'relations', title: '关联项', width: 66, render: row => row.relations.length },
        { key: 'summary', title: '检查结果', width: 220 },
      ]),
      { key: 'action', title: '维护', width: 68, render: row => <ControlButton variant="ghost" size="sm" className="md-icon-button" aria-label={'定位 ' + row.code + (row.title ? ' ' + row.title : '')} title="去基础资料定位" onClick={() => go(row.target)}><MDIcon name="arrow-up-right" /></ControlButton> }
    ].map(c => ({ ...c, sortable: false, filterable: false }));
    const related = entity ? entity.relations.map(r => ({ ...r, entity: overview.byKey.get(r.key) })).filter(r => r.entity) : [];
    const detailRows = detailView === 'relations' ? related : entity ? detailView === 'fields' ? entity.details : entity.issues : [];
    const detailPages = Math.max(1, Math.ceil(detailRows.length / 10)), currentDetailPage = Math.min(relatedPage, detailPages);
    return <section className="md-overview" ref={root} aria-label="主数据总览">
      <header className="md-heading wb-page-heading">
        <div><h2>主数据总览</h2><p>{overview.sourceLabel}{overview.sample ? ' · 示例数据' : ''}</p></div>
        <div className="md-actions">
          <ControlButton variant="secondary" size="sm" className="md-icon-button" aria-label="刷新主数据" title="重新读取当前会话" onClick={refresh}><MDIcon name="refresh-cw" /></ControlButton>
          <TransferButton kind="export" disabled={!overview.loaded || !result.total} onClick={exportRows}>导出筛选结果</TransferButton>
          <ControlButton variant="primary" size="sm" disabled={typeof onNav !== 'function'} onClick={() => onNav('process')}>维护基础资料</ControlButton>
        </div>
      </header>
      <MetricStrip columns={4} className="md-status-strip" aria-label="总览状态">
        <Metric label="实体条目" value={overview.loaded ? overview.stats.entities : '未加载'} helper="零件、路线、资源及日历配置" />
        <Metric label="待维护项" value={overview.loaded ? overview.stats.issues : '未加载'} tone="warn" helper="按当前可检查字段计算" />
        <Metric label="涉及实体" value={overview.loaded ? overview.stats.affected : '未加载'} helper="同一实体的问题不重复计数" />
        <Metric label="已关联条目对" value={overview.loaded ? overview.stats.relations : '未加载'} helper="当前会话已匹配的关联" />
      </MetricStrip>
      <MetricStrip columns={8} className="md-domains" aria-label="主数据域数量">
        {overview.domains.map(d => <Metric key={d.id} label={d.label} value={d.count == null ? '未加载' : d.count} helper={d.loaded ? d.id === 'opType' ? overview.stats.registeredOpTypes + ' 建档 · ' + (d.count - overview.stats.registeredOpTypes) + ' 待归类' : d.attention + ' 条需维护' : '来源尚未载入'} />)}
      </MetricStrip>
      <div className="md-source-note">{overview.loaded ? '仅检查当前会话，不代表排产就绪。表格临时增删未写入源数组，切换子页后可能恢复。人员设备操作关系、批次物料需求与正式外协分组未加载。' : '尚未载入基础资料会话，暂无可核实的数量和检查结果。'}</div>
      {(source.error || message) && <div className={'md-message' + (source.error || message.startsWith('导出失败') ? ' md-message-error' : '')} role="status">{source.error || message}</div>}
      <div className="md-list-tools">
      <div className="md-tabs" role="tablist" aria-label="清单类型">
        {[['issues', '待维护项', overview.issues.length], ['entities', '实体清单', overview.entities.length]].map(([id, label, count]) => <button key={id} type="button" role="tab" id={uid + '-tab-' + id} data-md-tab={id} tabIndex={options.view === id ? 0 : -1} aria-selected={options.view === id} aria-controls={uid + '-list'} onKeyDown={e => tabKey(e, ['issues', 'entities'], id, view => update({ view, status: 'all' }))} onClick={() => update({ view: id, status: 'all' })}>{label}<span>{overview.loaded ? count : '-'}</span></button>)}
      </div>
      <div className="md-filters">
        <label>数据域<select aria-label="筛选数据域" value={options.domain} onChange={e => update({ domain: e.target.value })}><option value="all">全部数据域</option>{overview.domains.map(d => <option key={d.id} value={d.id}>{d.label}{d.loaded ? ' (' + d.count + ')' : ' · 未加载'}</option>)}</select></label>
        <label>状态<select aria-label="筛选检查状态" value={options.status} onChange={e => update({ status: e.target.value })}><option value="all">全部状态</option><option value="attention">待维护</option>{!isIssue && <><option value="checked">已检查</option><option value="inactive">停用</option></>}</select></label>
        <label className="md-search">搜索<input type="search" aria-label="搜索主数据" placeholder="编号、名称或待维护项" value={options.search} onChange={e => update({ search: e.target.value })} /></label>
        <label>排序<select aria-label="主数据排序" value={options.sort} onChange={e => update({ sort: e.target.value })}><option value="issues">待维护项多到少</option><option value="code">编号升序</option><option value="name">名称升序</option>{!isIssue && <option value="relations">关联项多到少</option>}</select></label>
      </div>
      </div>
      <div className="md-workspace">
        <div id={uid + '-list'} className="md-list" role="tabpanel" aria-labelledby={uid + '-tab-' + options.view}>
          {result.total ? <DataTable key={options.view} className="md-table" columns={columns} rows={result.rows} rowKey="key" /> : <div className="md-empty">
            <strong>{!overview.loaded ? '基础资料未加载' : options.domain !== 'all' && !overview.domains.find(d => d.id === options.domain).loaded ? '此数据域未加载' : options.search || options.domain !== 'all' || options.status !== 'all' ? '没有符合条件的记录' : isIssue ? '当前检查未发现待维护项' : '当前会话没有实体记录'}</strong>
            {overview.loaded && (options.search || options.domain !== 'all' || options.status !== 'all') && <ControlButton variant="secondary" size="sm" onClick={() => update({ search: '', domain: 'all', status: 'all' })}>清除筛选</ControlButton>}
          </div>}
          <div className="md-pagination">
            <span>共 {result.total} 条 · 第 {result.page} / {result.pages} 页</span>
            <label>每页<select aria-label="每页条数" value={options.pageSize} onChange={e => update({ pageSize: Number(e.target.value) })}>{[20, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
            <ControlButton variant="secondary" size="sm" className="md-icon-button" aria-label="上一页" title="上一页" disabled={result.page === 1} onClick={() => update({ page: result.page - 1 })}><MDIcon name="chevron-left" /></ControlButton>
            <ControlButton variant="secondary" size="sm" className="md-icon-button" aria-label="下一页" title="下一页" disabled={result.page === result.pages} onClick={() => update({ page: result.page + 1 })}><MDIcon name="chevron-right" /></ControlButton>
          </div>
        </div>
        <aside id={uid + '-entity-detail'} className="md-detail" aria-label="实体详情" ref={detailRef} tabIndex="-1">
          {entity ? <>
            {selectedKey && <button type="button" className="md-text-action" onClick={() => { if (detailOpener.current && detailOpener.current.isConnected) detailOpener.current.focus(); }}>返回清单</button>}
            <div className="md-detail-heading"><div><span className="md-muted">{domainName(entity.domain)} · {entity.code}</span><h3>{entity.name || '名称未填'}</h3></div><ControlButton variant="secondary" size="sm" className="md-icon-button" aria-label="定位当前实体" title="去基础资料定位" onClick={() => go(selected.target)}><MDIcon name="arrow-up-right" /></ControlButton></div>
            <div className="md-completeness"><span className={'md-status md-' + entity.status}>{api.statusLabels[entity.status]}</span><span>已填 {entity.completeness.filled} / {entity.completeness.total} 个检查字段</span></div>
            {isIssue && <div className="md-issue-focus"><strong>{selected.title}</strong><p>{selected.evidence}</p><p>{selected.action}</p></div>}
            <div className="md-detail-tabs" role="tablist" aria-label="实体明细类型">
              {[['issues', '待维护项 ' + entity.issues.length], ['relations', '相关项 ' + related.length], ['fields', '字段']].map(([id, label]) => <button key={id} id={uid + '-detail-tab-' + id} role="tab" type="button" tabIndex={detailView === id ? 0 : -1} aria-selected={detailView === id} aria-controls={uid + '-detail-panel'} onKeyDown={e => tabKey(e, ['issues', 'relations', 'fields'], id, setDetailView)} onClick={() => setDetailView(id)}>{label}</button>)}
            </div>
            <div id={uid + '-detail-panel'} role="tabpanel" aria-labelledby={uid + '-detail-tab-' + detailView}>
            {detailView === 'fields' ? <dl className="md-fields">{detailRows.slice((currentDetailPage - 1) * 10, currentDetailPage * 10).map(([label, value], i) => <React.Fragment key={i}><dt>{label}</dt><dd>{String(value == null || value === '' ? '未填' : value)}</dd></React.Fragment>)}</dl> : <>
              {!detailRows.length && <p className="md-muted">{detailView === 'relations' ? '当前已加载记录中没有可确认的关联项。' : '已检查字段未发现待维护项。'}</p>}
              <ul className="md-detail-list">{detailRows.slice((currentDetailPage - 1) * 10, currentDetailPage * 10).map((r, i) => <li key={r.key + ':' + i}>{detailView === 'relations' ? <button type="button" className="md-related" onClick={() => { update({ view: 'entities', domain: r.entity.domain, search: r.entity.code, status: 'all' }); setSelectedKey(r.entity.key); }}><span className="md-muted">{r.label}</span><strong>{r.entity.code} · {r.entity.name}</strong></button> : <><strong>{r.title}</strong><p>{r.evidence}</p><button type="button" className="md-text-action" onClick={() => go(r.target)}>{r.action}<MDIcon name="arrow-up-right" /></button></>}</li>)}</ul>
            </>}
            {detailPages > 1 && <div className="md-pagination"><span>{currentDetailPage} / {detailPages}</span><ControlButton variant="secondary" size="sm" disabled={currentDetailPage === 1} aria-label="详情上一页" title="详情上一页" onClick={() => setRelatedPage(currentDetailPage - 1)}><MDIcon name="chevron-left" /></ControlButton><ControlButton variant="secondary" size="sm" disabled={currentDetailPage === detailPages} aria-label="详情下一页" title="详情下一页" onClick={() => setRelatedPage(currentDetailPage + 1)}><MDIcon name="chevron-right" /></ControlButton></div>}
            </div>
          </> : <p className="md-muted">暂无可查看的实体。</p>}
        </aside>
      </div>
    </section>;
  }
  window.MasterDataOverview = MasterDataOverview;
})();
