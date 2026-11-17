import React from './shared/runtime/react.js';
import C from './resource-contract.js';
import { useQuery } from './shared/session/query.js';
import APSResourceAPI from './resource-api.js';
import { Button, Icon, Issues, Status, EmptyState, Pager } from './ResourceControls.jsx';
import { object } from './shared/contract/kit.js';

const names = { machines: '关联设备', operators: '关联人员', suppliers: '关联供应商' };
const count = value => Number.isSafeInteger(value) && value >= 0;
function Association({ entity, relation, onOpen }) {
  const [scope, setScope] = React.useState({ relation, query: '', page: 1, size: 5 });
  const [search, setSearch] = React.useState('');
  const read = useQuery(signal => APSResourceAPI.forNamespace('resources').relations(entity.ref, scope, signal), [entity.ref, scope]);
  const data = read.result && read.result.data, title = names[relation];
  function refresh() { setScope(current => ({ ...current, page: 1, snapshot_ref: undefined })); }
  function next(page) { setScope(current => ({ ...current, page, snapshot_ref: read.result.meta.snapshot_ref })); }
  return <section className="wb-resource-association" aria-label={title}>
    <form className="wb-resource-association-head" onSubmit={event => { event.preventDefault(); setScope({ relation, query: search.trim(), page: 1, size: 5 }); }}>
      <h4>{title}{data && <span className="muted"> {data.page.total}</span>}</h4>
      <div className="search"><span className="ic"><Icon name="search" /></span><input type="search" aria-label={'搜索' + title} value={search} placeholder="编号、名称" onChange={event => setSearch(event.target.value)} /></div>
      <Button icon="search" type="submit" aria-label={'查询' + title} busy={read.loading} />
      <Button icon="refresh-cw" aria-label={'刷新' + title} busy={read.loading} onClick={refresh} />
    </form>
    {read.loading && <EmptyState kind="loading" title={'正在读取' + title + '…'} />}
    {read.error && <EmptyState kind="error" error={read.error} action={<Button icon="refresh-cw" onClick={refresh}>刷新{title}</Button>} />}
    {data && <><p className="muted wb-resource-association-basis">{data.basis.message}</p>
      <div className="wb-resource-association-list">{data.entities.map(item => <div key={item.ref}>
        <button type="button" className="wb-resource-relation" onClick={() => onOpen(item.kind, item.ref)} aria-label={'查看' + C.resourceName(item.kind) + ' ' + item.business_code + ' ' + item.label}>
          <span className="wb-resource-relation-content"><span className="lnk">{item.business_code} · {item.label}</span>
            {item.fields.relation_source_label && <span className="muted">{item.fields.relation_source_label}</span>}
            {relation === 'operators' && <span className="muted">匹配设备授权 {count(item.fields.matching_machine_authorization_count) ? item.fields.matching_machine_authorization_count : '未知'} 项
              {typeof item.fields.qualification_matches === 'boolean' && (item.fields.qualification_matches ? ' · 工种资格匹配' : ' · 工种资格不匹配')}</span>}</span>
          <Status kind={item.kind} entity={item} /><Icon name="chevron-right" />
        </button><Issues issues={item.issues} /></div>)}</div>
      {!data.entities.length && <EmptyState kind={scope.query ? 'filtered' : 'empty'}
        action={scope.query ? <Button onClick={() => { setSearch(''); setScope({ relation, query: '', page: 1, size: 5 }); }}>清除筛选</Button> : undefined} />}
      {data.page.pages > 1 && <Pager page={data.page} sizes={[5]} unit="项" label={title} disabled={read.loading} onPage={next} />}
      <Issues issues={read.result.warnings} /></>}
  </section>;
}
function ResourceDetailRelations({ entity, onOpen }) {
  const relations = entity.fields.category === 'both' ? ['machines', 'operators', 'suppliers'] : entity.fields.category === 'internal' ? ['machines', 'operators'] : ['suppliers'];
  const available = object(entity.availability);
  return <div className="wb-resource-relations">
    {['internal', 'both'].includes(entity.fields.category) && <p className="muted">当前可用数量：设备 {available ? entity.availability.machines : '未知'} 台 · 人员 {available ? entity.availability.operators : '未知'} 人。关联列表包含停用及资格待核对的记录。</p>}
    {relations.map(relation => <Association key={relation} entity={entity} relation={relation} onOpen={onOpen} />)}
  </div>;
}

export { ResourceDetailRelations };
export default ResourceDetailRelations;
