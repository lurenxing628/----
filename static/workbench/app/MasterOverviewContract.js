(function () {
  'use strict';

  const domains = [['part', '零件'], ['route', '工艺路线'], ['opType', '工种'], ['equipment', '设备'], ['personnel', '人员'], ['material', '物料'], ['supplier', '供应商'], ['calendar', '日历配置']];
  const statuses = {
    attention: '待维护',
    checked: '已检查',
    inactive: '停用',
    unknown: '无法核实'
  };
  const defaults = {
    view: 'issues',
    domain: 'all',
    status: 'all',
    query: '',
    sort: 'issue_count',
    direction: 'desc',
    size: 20,
    column_filters: {}
  };
  const common = [['business_code', '编号', 148], ['label', '名称', 178], ['domain', '数据域', 84]];
  const columns = {
    entities: common.concat([['status', '检查状态', 92], ['filled_fields', '已填字段', 80], ['checked_fields', '检查字段', 80], ['relation_count', '关联项', 76], ['issue_count', '待维护项', 82], ['summary', '检查结果', 214]]),
    issues: common.concat([['title', '待维护项', 180], ['evidence', '当前记录', 260]])
  };
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  function fail(message) {
    throw new Error(message || '主数据协议不完整，未使用样例或默认数量替代。');
  }
  function canonical(value) {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  function scope(value) {
    if (!object(value) || Object.keys(value).some(key => !Object.hasOwnProperty.call(defaults, key))) fail('主数据筛选字段不正确。');
    if (value.column_filters !== undefined && !object(value.column_filters)) fail('主数据列筛选必须为对象。');
    const result = {
      ...defaults,
      ...value,
      column_filters: {
        ...(value.column_filters || {})
      }
    };
    if (!['issues', 'entities'].includes(result.view) || !['all'].concat(domains.map(row => row[0])).includes(result.domain) || !['all'].concat(Object.keys(statuses)).includes(result.status) || ![20, 50, 100].includes(result.size) || !['business_code', 'label', 'issue_count', 'relation_count'].includes(result.sort) || !['asc', 'desc'].includes(result.direction) || typeof result.query !== 'string' || result.query.length > 1000 || !object(result.column_filters)) fail('主数据筛选范围无效。');
    const allowed = columns[result.view].map(row => row[0]).concat(result.view === 'issues' ? ['status', 'action', 'rule'] : []);
    if (Object.keys(result.column_filters).some(key => !allowed.includes(key) || typeof result.column_filters[key] !== 'string' || result.column_filters[key].length > 1000)) fail('主数据列筛选无效。');
    return result;
  }
  function target(value) {
    if (!object(value) || !['process', 'batches'].includes(value.view) || !object(value.context)) fail('维护目标不完整。');
    const c = value.context;
    if (value.view === 'batches') {
      if (!ref(c.entity_ref)) fail('批次目标缺少永久引用。');
      return value;
    }
    if (c.source !== 'production' || !['material', 'op_type', 'machine', 'operator', 'supplier', 'part', 'calendar'].includes(c.kind)) fail('主数据维护目标来源或类型不正确。');
    if (value.unavailable_reason !== undefined) {
      if (typeof value.unavailable_reason !== 'string' || !value.unavailable_reason) fail();
      return value;
    }
    if (c.kind === 'calendar') {
      if (typeof c.month !== 'string' || !/^\d{4}-\d{2}$/.test(c.month) || typeof c.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(c.date)) fail('日历定位日期无法核实。');
    } else if (!ref(c.entity_ref)) fail('维护目标缺少永久引用。');
    if (c.category !== undefined && (c.kind !== 'op_type' || !['internal', 'external'].includes(c.category))) fail('工种类别不正确。');
    if (c.stage !== undefined && !['route', 'source', 'hours'].includes(c.stage)) fail('工艺阶段不正确。');
    for (const key of ['template_operation_ref', 'template_external_group_ref']) if (c[key] !== undefined && !ref(c[key])) fail('模板定位引用不正确。');
    return value;
  }
  function row(value, view) {
    if (!object(value) || !ref(view === 'issues' ? value.entity_ref : value.ref) || typeof value.key !== 'string' || !domains.some(item => item[0] === value.domain) || typeof value.business_code !== 'string' || typeof value.label !== 'string' || !Object.hasOwnProperty.call(statuses, value.status) || !count(value.issue_count) || !(value.relation_count === null || count(value.relation_count))) fail();
    target(value.target);
    if (view === 'issues') {
      if (!ref(value.issue_ref) || ['rule', 'title', 'evidence', 'action'].some(key => typeof value[key] !== 'string')) fail();
    } else if (!count(value.filled_fields) || !count(value.checked_fields) || value.filled_fields > value.checked_fields || !count(value.known_relation_count) || typeof value.checks_complete !== 'boolean' || typeof value.relations_complete !== 'boolean' || typeof value.summary !== 'string' || value.relations_complete && value.relation_count !== value.known_relation_count) fail();
    return value;
  }
  function envelope(result) {
    if (!object(result) || result.ok !== true || result.schema_version !== 1 || !object(result.data) || !object(result.meta) || result.meta.source !== 'production' || result.meta.time_basis !== 'factory_local' || !result.meta.snapshot_ref || typeof result.meta.as_of !== 'string' || !Array.isArray(result.warnings)) fail();
    return result;
  }
  function page(value, rows, size) {
    if (!object(value) || !count(value.total) || !Number.isSafeInteger(value.number) || value.number < 1 || !Number.isSafeInteger(value.pages) || value.pages !== Math.max(1, Math.ceil(value.total / value.size)) || value.number > value.pages || value.size !== size || rows.length !== Math.min(size, Math.max(0, value.total - (value.number - 1) * size))) fail('主数据分页总数无法核实。');
  }
  function list(result, expected, snapshot) {
    envelope(result);
    const data = result.data,
      actual = scope(data.scope),
      overview = data.overview;
    if (expected && canonical(actual) !== canonical(scope(expected))) fail('返回主数据范围与当前筛选不一致。');
    if (snapshot && result.meta.snapshot_ref !== snapshot) fail('主数据快照发生非预期切换。');
    if (!Array.isArray(data.rows) || !object(overview) || !Array.isArray(overview.domains) || overview.domains.length !== 8 || !object(overview.stats) || !Array.isArray(overview.gaps) || typeof overview.basis !== 'string' || typeof overview.complete !== 'boolean') fail();
    page(data.page, data.rows, actual.size);
    data.rows.forEach(item => row(item, actual.view));
    if (new Set(data.rows.map(item => item.key)).size !== data.rows.length) fail('主数据行引用重复。');
    domains.forEach(([id], index) => {
      const domain = overview.domains[index];
      if (!object(domain) || domain.id !== id || typeof domain.loaded !== 'boolean' || (domain.loaded ? !count(domain.count) || !count(domain.attention) || !count(domain.unknown) || domain.attention > domain.count || domain.unknown > domain.count : domain.count !== null || domain.attention !== null || domain.unknown !== null)) fail('主数据域数量无法核实。');
    });
    const stats = overview.stats;
    if (['entities', 'issues', 'affected', 'known_relation_pairs'].some(key => !count(stats[key])) || !(stats.relations === null || count(stats.relations)) || stats.entities !== overview.domains.reduce((sum, item) => sum + (item.loaded ? item.count : 0), 0) || stats.affected > stats.entities || stats.issues < stats.affected || stats.affected !== overview.domains.reduce((sum, item) => sum + (item.attention || 0), 0) || stats.relations !== null && stats.relations !== stats.known_relation_pairs || !overview.complete && stats.relations !== null || overview.complete !== overview.domains.every(item => item.loaded)) fail('主数据总览数量无法核实。');
    return result;
  }
  function detail(result, expected, selection, section, snapshot) {
    envelope(result);
    const data = result.data;
    if (canonical(scope(data.scope)) !== canonical(scope(expected)) || result.meta.snapshot_ref !== snapshot || data.section !== section || !object(data.entity) || data.entity.ref !== selection.entity_ref || data.entity.domain !== selection.domain || !Array.isArray(data.rows) || !object(data.counts) || ['issues', 'relations', 'fields'].some(key => !count(data.counts[key]))) fail('详情与所选实体或快照不一致。');
    row(data.entity, 'entities');
    page(data.page, data.rows, 10);
    if (data.counts[section] !== data.page.total || data.counts.issues !== data.entity.issue_count || data.counts.relations !== data.entity.known_relation_count) fail('详情总数无法核实。');
    data.rows.forEach(item => {
      if (section === 'relations') {
        if (!ref(item.ref) || !domains.map(row => row[0]).concat('batch').includes(item.domain) || ['business_code', 'label', 'relation', 'source'].some(key => typeof item[key] !== 'string')) fail();
        target(item.target);
      } else if (section === 'fields') {
        if (!object(item) || typeof item.label !== 'string' || typeof item.source !== 'string' || !['known', 'missing', 'unknown', 'invalid'].includes(item.state)) fail();
      } else {
        if (!ref(item.issue_ref) || !ref(item.entity_ref) || ['title', 'evidence', 'action', 'rule'].some(key => typeof item[key] !== 'string')) fail();
        target(item.target);
      }
    });
    return result;
  }
  function value(input) {
    return input === null || input === undefined ? '未知' : object(input) ? JSON.stringify(input) : String(input);
  }
  function cell(item, column) {
    if (column === 'domain') return (domains.find(row => row[0] === item.domain) || [null, '批次'])[1];
    if (column === 'status') return statuses[item.status];
    return value(item[column]);
  }
  window.APSMasterOverviewContract = {
    domains,
    statuses,
    defaults,
    columns,
    scope,
    target,
    list,
    detail,
    value,
    cell,
    ref,
    fail,
    canonical
  };
})();
