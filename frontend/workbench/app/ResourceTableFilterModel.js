(function () {
  'use strict';
  const C = window.APSResourceContract;
  const key = value => typeof value === 'string' && value.length > 0;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  function ruleSet(value) {
    if (value === null || value === undefined) return { mode: 'exclude', keys: new Set() };
    if (!C.object(value) || !['include', 'exclude'].includes(value.mode) || !Array.isArray(value.values)
        || Object.keys(value).some(key => !['mode', 'values'].includes(key)) || !value.values.every(key))
      throw C.failure('本列筛选规则不完整，请清除本列后重新选择。');
    const keys = new Set(value.values);
    if (keys.size > 50000) throw C.failure('本列筛选超过 50000 个值，请先清除或减少原条件。');
    return { mode: value.mode, keys };
  }
  function rule(value) {
    const selected = ruleSet(value);
    return { mode: selected.mode, values: Array.from(selected.keys).sort() };
  }
  // 整组列筛选逐列规范（去重、排序）；外层对象和列名由调用方按各自的列清单先校验。
  function rules(value) {
    return Object.fromEntries(Object.keys(value).sort().map(column => [column, rule(value[column])]));
  }
  function toggle(value, key, enabled) {
    return toggleKeys(value, [key], enabled);
  }
  // changed 只来自 facets() 已校验的选项编号或 selection() 已校验的全部匹配编号。
  function toggleKeys(value, changed, enabled) {
    const { mode, keys } = ruleSet(value);
    changed.forEach(key => { if ((mode === 'include') === enabled) keys.add(key); else keys.delete(key); });
    if (keys.size > 50000) throw C.failure('本次选择会使本列筛选超过 50000 个值，原条件没有改动。请先清除或减少已选范围。');
    return { mode, values: Array.from(keys).sort() };
  }
  function groupState(value, keys) {
    const { mode, keys: set } = ruleSet(value);
    const matches = keys.reduce((sum, key) => sum + ((mode === 'include') === set.has(key) ? 1 : 0), 0);
    return { all: keys.length > 0 && matches === keys.length, mixed: matches > 0 && matches < keys.length };
  }
  function toolbarScope(scope) {
    const result = {};
    ['query', 'status', 'category', 'source'].forEach(key => { if (scope && scope[key] !== undefined) result[key] = scope[key]; });
    return result;
  }
  function active(value) {
    const selected = ruleSet(value);
    return selected.mode === 'include' || selected.keys.size > 0;
  }
  function signature(value) {
    if (Array.isArray(value)) return '[' + value.map(signature).join(',') + ']';
    if (C.object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + signature(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  // 信封（ok、schema_version、meta、warnings）已由 transport 校验，这里只核对列值本身。
  function envelope(raw, request) {
    const data = raw.data;
    if (data.column !== request.column || data.basis !== 'toolbar_scope') throw C.failure('读到的列值不完整，没有当成空列表。请回到第 1 页重新查询。');
    if (request.snapshot_ref && raw.meta.snapshot_ref !== request.snapshot_ref)
      throw C.failure('数据已更新，请回到第 1 页重新查询。');
    return data;
  }
  function facets(raw, request) {
    const data = envelope(raw, request), page = data.page;
    const invalid = !count(data.row_count) || !C.object(page) || page.number !== request.page || page.size !== request.size || !count(page.total)
      || page.pages !== Math.max(1, Math.ceil(page.total / page.size)) || page.number > page.pages
      || !Array.isArray(data.options) || data.options.length !== Math.min(page.size, Math.max(0, page.total - (page.number - 1) * page.size));
    if (invalid) throw C.failure('读到的列值不完整，没有当成空列表。请回到第 1 页重新查询。');
    const keys = new Set();
    for (const option of data.options) {
      if (!C.object(option) || !key(option.key) || keys.has(option.key)
          || typeof option.label !== 'string' || !count(option.count))
        throw C.failure('列值编号、文字或数量不正确，请回到第 1 页重新查询。');
      keys.add(option.key);
    }
    return raw;
  }
  function selection(raw, request) {
    const data = envelope(raw, request);
    if (!count(data.total) || !Array.isArray(data.keys) || data.total !== data.keys.length || data.total > 50000
        || request.expected_total !== undefined && data.total !== request.expected_total
        || !data.keys.every(key) || new Set(data.keys).size !== data.total)
      throw C.failure('全部匹配值不完整或超过 50000 个，筛选没有改动。请回到第 1 页重新查询。');
    return raw;
  }
  window.ResourceTableFilterModel = { rule, rules, toggle, toggleKeys, groupState, toolbarScope, active, signature, facets, selection };
})();
