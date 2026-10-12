(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const ref = value => typeof value === 'string' && /^[a-f0-9]{48}$/.test(value);
  const edgeKey = edge => edge.from_task_ref + ':' + edge.to_task_ref + ':' + edge.edge_type;
  // Both workspaces validate this shared graph once, at their existing API boundary.
  function validate(graph, { scope, tasks, taskRef, time, sequence, processLabel, completeCount }) {
    if (!object(graph) || graph.scope !== scope || !['available', 'unavailable'].includes(graph.state)
      || !['nodes', 'edges', 'critical_task_refs', 'critical_edges'].every(key => Array.isArray(graph[key]))) return false;
    if (graph.state === 'unavailable') return typeof graph.reason === 'string' && !!graph.reason.trim()
      && !graph.nodes.length && !graph.edges.length && !graph.critical_task_refs.length && !graph.critical_edges.length;
    if (graph.reason !== null || completeCount !== undefined && graph.nodes.length !== completeCount) return false;
    const nodes = new Map();
    for (const node of graph.nodes) {
      if (!object(node) || !ref(node.task_ref) || !ref(node.operation_ref) || nodes.has(node.task_ref)
        || typeof node.batch_id !== 'string' || !node.batch_id.trim()
        || !(node.piece_id === null || typeof node.piece_id === 'string' && !!node.piece_id.trim())
        || !sequence(node.sequence) || !processLabel(node.process_label)
        || !time(node.start) || !time(node.end) || node.end < node.start) return false;
      nodes.set(node.task_ref, node);
    }
    if (!tasks.every(task => {
      const node = nodes.get(task[taskRef]);
      return node && ['operation_ref', 'piece_id', 'start', 'end'].every(key => node[key] === task[key]);
    })) return false;
    const critical = new Set(graph.critical_task_refs);
    if (critical.size !== graph.critical_task_refs.length || !graph.critical_task_refs.every(key => nodes.has(key))) return false;
    function edgesValid(edges, types, members) {
      const seen = new Set();
      return edges.every(edge => {
        if (!object(edge) || !nodes.has(edge.from_task_ref) || !nodes.has(edge.to_task_ref)
          || edge.from_task_ref === edge.to_task_ref || !types.includes(edge.edge_type)
          || members && (!members.has(edge.from_task_ref) || !members.has(edge.to_task_ref))) return false;
        const key = edgeKey(edge); if (seen.has(key)) return false; seen.add(key); return true;
      });
    }
    return edgesValid(graph.edges, ['process']) && edgesValid(graph.critical_edges, ['process', 'machine', 'operator'], critical);
  }
  function create(graph) {
    const nodes = new Map(graph.nodes.map(node => [node.task_ref, node])), batches = new Map();
    for (const node of graph.nodes) {
      if (!batches.has(node.batch_id)) batches.set(node.batch_id, []);
      batches.get(node.batch_id).push(node);
    }
    return { graph, nodes, batches };
  }
  function selection(index, { enabled = false, targetRef = null } = {}) {
    const { graph } = index, target = index.nodes.get(targetRef) || null;
    const critical = new Set(graph.critical_task_refs), related = new Set(), edges = new Map();
    const connection = edge => edge.from_task_ref + ':' + edge.to_task_ref;
    if (enabled && !target) graph.critical_edges.forEach(edge => edges.set(connection(edge), { ...edge, kind: 'critical' }));
    if (target) {
      // A piece shares its common operations, but those operations must not lead into sibling pieces.
      for (const node of index.batches.get(target.batch_id))
        if (target.piece_id === null || node.piece_id === null || node.piece_id === target.piece_id) related.add(node.task_ref);
      graph.edges.forEach(edge => {
        if (related.has(edge.from_task_ref) && related.has(edge.to_task_ref)) edges.set(connection(edge), { ...edge, kind: 'related' });
      });
    }
    return { graph, target, critical, related, edges: Array.from(edges.values()) };
  }
  function route(index, targetRef) {
    const target = index.nodes.get(targetRef);
    if (!target) return null;
    const nodes = index.batches.get(target.batch_id), previous = new Map(nodes.map(node => [node.task_ref, []]));
    const next = new Map(nodes.map(node => [node.task_ref, []])), groups = new Map();
    for (const edge of index.graph.edges) if (previous.has(edge.to_task_ref)) previous.get(edge.to_task_ref).push(index.nodes.get(edge.from_task_ref));
    for (const node of nodes) for (const parent of previous.get(node.task_ref)) next.get(parent.task_ref).push(node);
    const pending = new Map(nodes.map(node => [node.task_ref, previous.get(node.task_ref).length]));
    const sequence = node => node.sequence === null ? Infinity : Number(node.sequence);
    const compare = (a, b) => sequence(a) - sequence(b)
      || String(a.sequence).localeCompare(String(b.sequence), 'en', { numeric: true }) || a.task_ref.localeCompare(b.task_ref);
    let layer = nodes.filter(node => pending.get(node.task_ref) === 0);
    while (layer.length) {
      const following = [];
      for (const node of layer.sort(compare)) {
        if (!groups.has(node.piece_id)) groups.set(node.piece_id, []);
        groups.get(node.piece_id).push(node);
        for (const child of next.get(node.task_ref)) {
          const count = pending.get(child.task_ref) - 1; pending.set(child.task_ref, count);
          if (!count) following.push(child);
        }
      }
      layer = following;
    }
    return { target, count: nodes.length, previous,
      groups: Array.from(groups, ([pieceId, items]) => ({ pieceId, nodes: items }))
        .sort((a, b) => a.pieceId === null ? -1 : b.pieceId === null ? 1 : a.pieceId.localeCompare(b.pieceId, 'zh-CN', { numeric: true })) };
  }
  function locations(model, { candidate = false } = {}) {
    const result = new Map();
    for (const row of model.rows) {
      if (row.before || row.baseline) continue;
      const y = row.top + 27;
      const markHeight = row.point ? 14 : 40;
      for (const item of row.items) result.set(item.task[candidate ? 'row_ref' : 'task_ref'], {
        start: item.start, end: item.end, y, markTop: y - markHeight / 2, markBottom: y + markHeight / 2,
        top: row.top, bottom: row.top + row.height
      });
    }
    return result;
  }
  function paths(active, model, width, viewport, options) {
    const points = options && options.locations || locations(model, options), visible = new Set(), scale = width / (model.end - model.start);
    const x = value => (value - model.start) * scale;
    for (const [key, point] of points) {
      const pad = point.start === point.end ? 12 : 0;
      if (point.bottom > viewport.top && point.top < viewport.top + viewport.height
        && x(point.end) + pad >= viewport.left && x(point.start) - pad <= viewport.left + viewport.width) visible.add(key);
    }
    const drawn = active.edges.filter(edge => visible.has(edge.from_task_ref) && visible.has(edge.to_task_ref)).map(edge => {
      const from = points.get(edge.from_task_ref), to = points.get(edge.to_task_ref), a = x(from.end), b = x(to.start);
      let d, endY = to.y, arrowX = Math.min(4, b - a), arrowY = 0;
      if (b < a) {
        // A backward detour is reserved for a real overlap in the scheduled dependency.
        d = 'M' + a + ',' + from.y + ' H' + (a + 6) + ' V' + (from.bottom - 3) + ' H' + (b - 6) + ' V' + to.y + ' H' + b;
        arrowX = 4;
      } else if (from.y === to.y) {
        // Adjacent operations share one seam: a compact arrow is enough, without drawing a loop.
        d = 'M' + a + ',' + from.y + ' H' + b;
        if (a === b) arrowX = 3;
      } else {
        const down = to.y > from.y, startY = down ? from.markBottom : from.markTop;
        endY = down ? to.markTop : to.markBottom;
        if (a === b) {
          d = 'M' + a + ',' + startY + ' V' + endY;
          arrowX = 0; arrowY = Math.sign(endY - startY) * Math.min(4, Math.abs(endY - startY));
        } else {
          const middle = (a + b) / 2;
          d = 'M' + a + ',' + startY + ' H' + middle + ' V' + endY + ' H' + b;
          arrowX = Math.min(4, b - middle);
        }
      }
      const wing = Math.min(2.5, Math.abs(arrowX || arrowY));
      const cap = arrowY
        ? ' M' + (b - wing) + ',' + (endY - arrowY) + ' L' + b + ',' + endY + ' L' + (b + wing) + ',' + (endY - arrowY)
        : ' M' + (b - arrowX) + ',' + (endY - wing) + ' L' + b + ',' + endY + ' L' + (b - arrowX) + ',' + (endY + wing);
      return { ...edge, d: d + cap, top: Math.min(from.top, to.top), bottom: Math.max(from.bottom, to.bottom) };
    });
    const count = refs => Array.from(refs).filter(key => visible.has(key)).length;
    return { paths: drawn, visible, criticalVisible: count(active.critical), relatedVisible: count(active.related), focused: !!active.target };
  }
  window.GanttGraph = { validate, create, selection, route, locations, paths };
})();
