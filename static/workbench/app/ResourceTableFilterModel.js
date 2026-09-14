(function () {
  'use strict';

  const C = window.APSResourceContract;
  const keyPattern = /^[0-9a-f]{64}$/;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  function rule(value) {
    if (value === null || value === undefined) return {
      mode: 'exclude',
      values: []
    };
    if (!C.object(value) || !['include', 'exclude'].includes(value.mode) || !Array.isArray(value.values) || Object.keys(value).some(key => !['mode', 'values'].includes(key)) || value.values.some(key => typeof key !== 'string' || !keyPattern.test(key))) throw C.failure('本列筛选规则不完整，请清除本列后重新选择。');
    const values = Array.from(new Set(value.values)).sort();
    if (values.length > 50000) throw C.failure('本列筛选超过 50000 个值，请先清除或减少原条件。');
    return {
      mode: value.mode,
      values
    };
  }
  function checked(value, key) {
    const selected = rule(value);
    return selected.mode === 'include' ? selected.values.includes(key) : !selected.values.includes(key);
  }
  function toggle(value, key, enabled) {
    return toggleKeys(value, [key], enabled);
  }
  function toggleKeys(value, changed, enabled) {
    if (!Array.isArray(changed) || changed.some(key => typeof key !== 'string' || !keyPattern.test(key))) throw C.failure('列值编号无效，筛选没有改动。');
    const selected = rule(value),
      keys = new Set(selected.values);
    changed.forEach(key => {
      if (selected.mode === 'include' === enabled) keys.add(key);else keys.delete(key);
    });
    if (keys.size > 50000) throw C.failure('本次选择会使本列筛选超过 50000 个值，原条件没有改动。请先清除或减少已选范围。');
    return {
      mode: selected.mode,
      values: Array.from(keys).sort()
    };
  }
  function groupState(value, keys) {
    const selected = rule(value),
      set = new Set(selected.values);
    const matches = keys.reduce((sum, key) => sum + (selected.mode === 'include' === set.has(key) ? 1 : 0), 0);
    return {
      all: keys.length > 0 && matches === keys.length,
      mixed: matches > 0 && matches < keys.length
    };
  }
  function toolbarScope(scope) {
    const result = {};
    ['query', 'status', 'category', 'source'].forEach(key => {
      if (scope && scope[key] !== undefined) result[key] = scope[key];
    });
    return result;
  }
  function active(value) {
    const selected = rule(value);
    return selected.mode === 'include' || selected.values.length > 0;
  }
  function signature(value) {
    if (Array.isArray(value)) return '[' + value.map(signature).join(',') + ']';
    if (C.object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + signature(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  function envelope(raw, request) {
    if (raw && raw.ok === false) throw raw;
    const meta = raw && raw.meta,
      data = raw && raw.data;
    const invalid = !C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(meta) || !['production', 'demo'].includes(meta.source) || meta.time_basis !== 'factory_local' || !['snapshot_ref', 'request_ref', 'as_of'].every(key => typeof meta[key] === 'string' && meta[key]) || !Array.isArray(raw.warnings) || !raw.warnings.every(row => C.object(row) && typeof row.message === 'string') || !C.object(data) || data.column !== request.column || data.basis !== 'toolbar_scope';
    if (invalid) throw C.failure('读到的列值不完整，没有当成空列表。请回到第 1 页重新查询。');
    if (request.snapshot_ref && meta.snapshot_ref !== request.snapshot_ref) throw C.failure('列值已经更新，没有混用不同页的数据。请回到第 1 页重新查询。');
    return data;
  }
  function facets(raw, request) {
    const data = envelope(raw, request),
      page = data.page;
    const invalid = !count(data.row_count) || !C.object(page) || page.number !== request.page || page.size !== request.size || !count(page.total) || page.pages !== Math.max(1, Math.ceil(page.total / page.size)) || page.number > page.pages || !Array.isArray(data.options) || data.options.length !== Math.min(page.size, Math.max(0, page.total - (page.number - 1) * page.size));
    if (invalid) throw C.failure('读到的列值不完整，没有当成空列表。请回到第 1 页重新查询。');
    const keys = new Set();
    for (const option of data.options) {
      if (!C.object(option) || typeof option.key !== 'string' || !keyPattern.test(option.key) || keys.has(option.key) || typeof option.label !== 'string' || !count(option.count)) throw C.failure('列值编号、文字或数量不正确，请回到第 1 页重新查询。');
      keys.add(option.key);
    }
    return raw;
  }
  function selection(raw, request) {
    const data = envelope(raw, request);
    if (!count(data.total) || !Array.isArray(data.keys) || data.total !== data.keys.length || data.total > 50000 || request.expected_total !== undefined && data.total !== request.expected_total || data.keys.some(key => typeof key !== 'string' || !keyPattern.test(key)) || new Set(data.keys).size !== data.total) throw C.failure('全部匹配值不完整或超过 50000 个，筛选没有改动。请回到第 1 页重新查询。');
    return raw;
  }
  window.ResourceTableFilterModel = {
    rule,
    checked,
    toggle,
    toggleKeys,
    groupState,
    toolbarScope,
    active,
    signature,
    facets,
    selection
  };
})();
