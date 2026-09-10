(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, filters = window.ResourceTableFilterModel;
  const scopeKeys = ['query', 'page', 'size', 'sort', 'stage', 'column_filters'];
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  function read(view) {
    if (!C.object(view) || Object.keys(view).some(key => !['scope', 'selected_refs', 'entity_ref'].includes(key))) throw C.failure('工艺恢复记录只能包含只读查看状态。');
    const scope = view.scope;
    if (!C.object(scope) || Object.keys(scope).some(key => !scopeKeys.includes(key)) || typeof scope.query !== 'string'
        || !Number.isSafeInteger(scope.page) || scope.page < 1 || !Number.isSafeInteger(scope.size) || scope.size < 1 || scope.size > 100
        || ![undefined, ...P.stages.map(row => row[0])].includes(scope.stage) || !Array.isArray(scope.sort)
        || !C.object(scope.column_filters) || Object.keys(scope.column_filters).some(key => !P.columns.some(column => column.key === key)))
      throw C.failure('工艺恢复范围或分页不正确。');
    P.ordering(scope);
    Object.values(scope.column_filters).forEach(value => filters.rule(value));
    if (!Array.isArray(view.selected_refs) || !view.selected_refs.every(ref) || new Set(view.selected_refs).size !== view.selected_refs.length
        || view.entity_ref !== null && !ref(view.entity_ref)) throw C.failure('工艺恢复引用不正确。');
    return JSON.parse(JSON.stringify(view));
  }
  window.APSProcessReadView = { read, scopeKeys };
})();
