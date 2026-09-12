(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, { Button, ErrorBox } = window.ResourceControls;
  const { Tabs, Pager } = window.MasterOverviewTable;
  function MasterOverviewDetail({ result, selected, section, onSection, onPage, onLocate, onMaintain, onBack, navigation, loading, error, triggerRef, autoFocus = true }) {
    const data = result && result.data, entity = data && data.entity;
    if (!selected) return null;
    return <window.WorkbenchDetailPanel title="主数据实体详情" subtitle={entity ? entity.business_code + ' · ' + (entity.label || '名称未填') : '正在核对所选记录'} detailKey={selected.key || selected.entity_ref} onClose={onBack} triggerRef={triggerRef} autoFocus={autoFocus}><div className="mo-detail">
      <Button className="mo-link" icon="chevron-left" onClick={onBack}>返回清单</Button>
      <ErrorBox error={error} />
      {loading && <window.WorkbenchListControls.EmptyState kind="loading" title="正在核对实体详情…" />}
      {entity ? <><div className="mo-detail-head"><div><p className="mo-muted">{C.cell(entity, 'domain')} · {entity.business_code}</p><h3>{entity.label || '名称未填'}</h3></div>
        <Button className="btn mo-icon" icon="arrow-right" aria-label="定位当前实体" reason={entity.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : '')} onClick={() => onMaintain(entity.target)} /></div>
        <p className="mo-muted"><span className="mo-status" data-status={entity.status}>{C.statuses[entity.status]}</span> · 已填 {entity.filled_fields} / {entity.checked_fields} 个检查字段</p>
        {!entity.checks_complete && <p className="mo-muted">部分来源或检查无法核实。</p>}
        {selected && selected.title && <div className="mo-focus"><strong>{selected.title}</strong><p>{selected.evidence}</p></div>}
        <Tabs label="实体明细类型" value={section} onChange={onSection} values={[["issues", "待维护项", data.counts.issues], ["relations", "相关项", data.counts.relations], ["fields", "字段", data.counts.fields]]} />
        <div role="tabpanel" aria-label={section === 'fields' ? '实体字段' : section === 'relations' ? '实体相关项' : '实体待维护项'}>
          {!data.rows.length && <p className="mo-muted">{section === 'relations' ? entity.relations_complete ? '已读取记录中没有可确认的关联项。' : '关联来源不完整，不能认定无关联。' : entity.checks_complete ? '已检查字段未发现待维护项。' : '检查来源不完整，结果未知。'}</p>}
          {section === 'fields' ? data.rows.map((field, index) => <dl className="mo-field" key={index}><dt>{field.label}</dt><dd>{field.state === 'unknown' ? '未知' : field.state === 'missing' ? '未填' : C.value(field.value)}{field.state === 'invalid' ? '（原值待核对）' : ''}</dd><dd className="mo-source">{field.source}</dd></dl>)
            : <ul className="mo-detail-list">{data.rows.map((item, index) => <li key={(item.issue_ref || item.key) + ':' + index}>{section === 'relations' ? <>
              <p className="mo-muted">{item.relation}</p><button type="button" className="mo-link" onClick={() => item.domain === 'batch' ? onMaintain(item.target) : onLocate({ domain: item.domain, entity_ref: item.ref })}
                disabled={item.domain === 'batch' && !navigation}><strong>{item.business_code} · {item.label}</strong></button><p className="mo-source">{item.source}</p></>
              : <><strong>{item.title}</strong><p>{item.evidence}</p><window.WorkbenchReference entries={{ '检查规则': item.rule }} /><Button className="mo-link" icon="arrow-right" reasonDisplay="inline" reason={item.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : '')} onClick={() => onMaintain(item.target)}>{item.action}</Button></>}</li>)}</ul>}
        </div><Pager detail page={data.page} disabled={loading} onPage={onPage} />
      </> : !loading && !error && <p className="mo-muted">暂无可查看的实体。</p>}
    </div></window.WorkbenchDetailPanel>;
  }
  window.MasterOverviewDetail = MasterOverviewDetail;
})();
