(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const exact = (value, keys) => object(value) && Reflect.ownKeys(value).length === keys.length && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  function validate(value, data) {
    if (!exact(value, ['state', 'basis', 'items', 'issues']) || !Array.isArray(value.items) || value.items.length > 10000
        || !Array.isArray(value.issues) || !value.issues.every(row => exact(row, ['code', 'message']) && typeof row.code === 'string' && row.code && typeof row.message === 'string' && row.message)) return false;
    if (value.state === 'unavailable') return value.basis === null && !value.items.length && value.issues.length > 0;
    if (value.state !== 'available' || !['run_admission', 'trial_creation'].includes(value.basis) || value.issues.length) return false;
    const tasks = new Map(), operations = new Map();
    for (const item of value.items) {
      if (!exact(item, ['task_ref', 'operation_ref', 'predecessor_operation_refs']) || !ref(item.task_ref) || !ref(item.operation_ref) || tasks.has(item.task_ref)
          || !Array.isArray(item.predecessor_operation_refs) || item.predecessor_operation_refs.length > 10000
          || !item.predecessor_operation_refs.every(ref) || new Set(item.predecessor_operation_refs).size !== item.predecessor_operation_refs.length
          || item.predecessor_operation_refs.includes(item.operation_ref)) return false;
      tasks.set(item.task_ref, item.operation_ref);
      const previous = JSON.stringify(item.predecessor_operation_refs.slice().sort());
      if (operations.has(item.operation_ref) && operations.get(item.operation_ref) !== previous) return false;
      operations.set(item.operation_ref, previous);
    }
    if (!data.tasks.every(task => tasks.get(task.task_ref) === task.operation_ref)
        || data.scope.range_start === null && tasks.size !== data.tasks.length) return false;
    const incoming = new Map(), next = new Map();
    for (const [operation, encoded] of operations) {
      const parents = JSON.parse(encoded).filter(parent => operations.has(parent));
      incoming.set(operation, parents.length);
      for (const parent of parents) { if (!next.has(parent)) next.set(parent, []); next.get(parent).push(operation); }
    }
    const queue = Array.from(incoming).filter(([, count]) => count === 0).map(([operation]) => operation);
    for (let index = 0; index < queue.length; index++) for (const child of next.get(queue[index]) || []) {
      const count = incoming.get(child) - 1; incoming.set(child, count); if (!count) queue.push(child);
    }
    return queue.length === operations.size;
  }
  function relationships(data, selected) {
    const order = data.projections.process_order, task = selected && selected.task;
    if (!task || selected.before || order.state !== 'available') return null;
    const current = order.items.find(row => row.task_ref === task.task_ref);
    if (!current) return null;
    const tasks = new Map(data.tasks.map(row => [row.task_ref, row])), byOperation = new Map();
    for (const row of order.items) {
      if (!byOperation.has(row.operation_ref)) byOperation.set(row.operation_ref, []);
      byOperation.get(row.operation_ref).push(row);
    }
    const expand = operations => operations.flatMap(operation => {
      const rows = byOperation.get(operation);
      return rows ? rows.map(row => ({ task_ref: row.task_ref, task: tasks.get(row.task_ref) || null })) : [{ task_ref: null, task: null }];
    });
    const successors = new Set(order.items.filter(row => row.predecessor_operation_refs.includes(task.operation_ref)).map(row => row.operation_ref));
    return { previous: expand(current.predecessor_operation_refs), next: expand(Array.from(successors)) };
  }
  window.PlanProcessOrder = { validate, relationships };
})();
