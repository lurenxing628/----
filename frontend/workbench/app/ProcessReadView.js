import P from './ProcessContract.js';
import filters from './ResourceTableFilterModel.js';
import { failure, object, ref48 } from './shared/contract/kit.js';

const scopeKeys = ['query', 'page', 'size', 'sort', 'stage', 'column_filters'];
function read(view) {
  if (!object(view) || Object.keys(view).some(key => !['scope', 'selected_refs', 'entity_ref'].includes(key))) throw failure('上次的查看状态无法恢复，已按默认范围显示工艺列表。');
  const scope = view.scope;
  if (!object(scope) || Object.keys(scope).some(key => !scopeKeys.includes(key)) || typeof scope.query !== 'string'
      || !Number.isSafeInteger(scope.page) || scope.page < 1 || !Number.isSafeInteger(scope.size) || scope.size < 1 || scope.size > 100
      || ![undefined, ...P.stages.map(row => row[0])].includes(scope.stage) || !Array.isArray(scope.sort)
      || !object(scope.column_filters) || Object.keys(scope.column_filters).some(key => !P.columns.some(column => column.key === key)))
    throw failure('上次的查看范围或页码不正确，已按默认范围显示工艺列表。');
  const sort = P.ordering(scope);
  if (!Array.isArray(view.selected_refs) || !view.selected_refs.every(ref48) || new Set(view.selected_refs).size !== view.selected_refs.length
      || view.entity_ref !== null && !ref48(view.entity_ref)) throw failure('上次打开或勾选的零件已失效，已按默认范围显示工艺列表。');
  return {
    ...view,
    scope: { ...scope, sort, column_filters: filters.rules(scope.column_filters) }
  };
}
const APSProcessReadView = { read, scopeKeys };

export { APSProcessReadView, read, scopeKeys };
export default APSProcessReadView;
