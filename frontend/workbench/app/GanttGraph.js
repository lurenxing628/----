(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const ref = value => typeof value === 'string' && /^[a-f0-9]{48}$/.test(value);
  const edgeKey = edge => edge.from_task_ref + ':' + edge.to_task_ref + ':' + edge.edge_type;
  const connection = edge => edge.from_task_ref + ':' + edge.to_task_ref;
  // Workspaces validate this shared graph once, at their existing API boundary.
  function validate(graph, { scope, tasks, taskRef, time, sequence, processLabel, completeCount }) {
    if (!object(graph) || Reflect.ownKeys(graph).length !== 6 || graph.scope !== scope || !['available', 'unavailable'].includes(graph.state)
      || !['nodes', 'critical_task_refs', 'critical_edges'].every(key => Array.isArray(graph[key]))) return false;
    if (graph.state === 'unavailable') return typeof graph.reason === 'string' && !!graph.reason.trim()
      && !graph.nodes.length && !graph.critical_task_refs.length && !graph.critical_edges.length;
    if (graph.reason !== null || completeCount !== undefined && graph.nodes.length !== completeCount) return false;
    const nodes = new Map();
    for (const node of graph.nodes) {
      if (!object(node) || !ref(node.task_ref) || !ref(node.operation_ref) || nodes.has(node.task_ref)
        || typeof node.batch_id !== 'string' || !node.batch_id.trim()
        || !(node.piece_id === null || typeof node.piece_id === 'string' && !!node.piece_id.trim())
        || !sequence(node.sequence) || !processLabel(node.process_label)
        || !time(node.start) || !time(node.end) || node.end < node.start
        || !Array.isArray(node.predecessor_operation_refs) || !node.predecessor_operation_refs.every(ref)
        || new Set(node.predecessor_operation_refs).size !== node.predecessor_operation_refs.length
        || node.predecessor_operation_refs.includes(node.operation_ref)) return false;
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
    return edgesValid(graph.critical_edges, ['process', 'machine', 'operator'], critical);
  }
  function create(graph) {
    const nodes = new Map(), operations = new Map(), batchFacts = new Map(), missingPredecessors = new Map();
    for (const [order, node] of graph.nodes.entries()) {
      nodes.set(node.task_ref, node); operations.set(node.operation_ref, node);
      if (!batchFacts.has(node.batch_id)) {
        const facts = { nodes: [], pieces: new Map(), edges: [], commonEdges: [], pieceEdges: new Map(),
          previous: new Map(), route: null };
        batchFacts.set(node.batch_id, facts);
      }
      const facts = batchFacts.get(node.batch_id);
      facts.nodes.push(node); facts.previous.set(node.task_ref, []);
      if (!facts.pieces.has(node.piece_id)) facts.pieces.set(node.piece_id, []);
      facts.pieces.get(node.piece_id).push({ node, order });
    }
    let order = 0;
    for (const to of graph.nodes) {
      const facts = batchFacts.get(to.batch_id); let missing = 0;
      for (const parent of to.predecessor_operation_refs) {
        const from = operations.get(parent);
        if (!from) { missing++; continue; }
        if (from.batch_id !== to.batch_id) continue;
        facts.previous.get(to.task_ref).push(from);
        const edge = { from_task_ref: from.task_ref, to_task_ref: to.task_ref, edge_type: 'process' };
        const record = { edge, order: order++ }; facts.edges.push(record);
        if (from.piece_id === null && to.piece_id === null) facts.commonEdges.push(record);
        else if (from.piece_id === null || to.piece_id === null || from.piece_id === to.piece_id) {
          const piece = from.piece_id === null ? to.piece_id : from.piece_id;
          if (!facts.pieceEdges.has(piece)) facts.pieceEdges.set(piece, []);
          facts.pieceEdges.get(piece).push(record);
        }
      }
      missingPredecessors.set(to.task_ref, missing);
    }
    const criticalEdges = new Map();
    graph.critical_edges.forEach(edge => criticalEdges.set(connection(edge), { ...edge, kind: 'critical' }));
    return { graph, nodes, batchFacts, missingPredecessors, critical: new Set(graph.critical_task_refs),
      global: edgeFacts(Array.from(criticalEdges.values())), empty: edgeFacts([]), selected: null };
  }
  function edgeFacts(edges) {
    const adjacency = new Map();
    edges.forEach((edge, order) => {
      if (!adjacency.has(edge.from_task_ref)) adjacency.set(edge.from_task_ref, []);
      adjacency.get(edge.from_task_ref).push({ edge, order });
    });
    return { adjacency };
  }
  function selection(index, { enabled = false, targetRef = null } = {}) {
    const { graph } = index, target = index.nodes.get(targetRef) || null;
    if (!target) return { graph, target, critical: index.critical, related: index.emptyRelated || (index.emptyRelated = new Set()),
      ...(enabled ? index.global : index.empty) };
    let selected = index.selected;
    if (!selected || selected.batch !== target.batch_id || selected.piece !== target.piece_id) {
      const facts = index.batchFacts.get(target.batch_id), related = new Set(), edges = new Map();
      // A piece shares its common operations, but those operations must not lead into sibling pieces.
      const members = target.piece_id === null ? facts.nodes : [...(facts.pieces.get(null) || []), ...facts.pieces.get(target.piece_id)]
        .sort((a, b) => a.order - b.order).map(item => item.node);
      members.forEach(node => related.add(node.task_ref));
      const selectedEdges = target.piece_id === null ? facts.edges : [...facts.commonEdges, ...(facts.pieceEdges.get(target.piece_id) || [])]
        .sort((a, b) => a.order - b.order);
      selectedEdges.forEach(({ edge }) => edges.set(connection(edge), { ...edge, kind: 'related' }));
      selected = { batch: target.batch_id, piece: target.piece_id, related, ...edgeFacts(Array.from(edges.values())) };
      index.selected = selected;
    }
    return { graph, target, critical: index.critical, related: selected.related, adjacency: selected.adjacency };
  }
  function route(index, targetRef) {
    const target = index.nodes.get(targetRef);
    if (!target) return null;
    const facts = index.batchFacts.get(target.batch_id);
    if (facts.route) return { target, ...facts.route };
    const { nodes, previous } = facts, next = new Map(nodes.map(node => [node.task_ref, []])), groups = new Map();
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
    facts.route = { count: nodes.length, previous,
      groups: Array.from(groups, ([pieceId, items]) => ({ pieceId, nodes: items }))
        .sort((a, b) => a.pieceId === null ? -1 : b.pieceId === null ? 1 : a.pieceId.localeCompare(b.pieceId, 'zh-CN', { numeric: true })) };
    return { target, ...facts.route };
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
  function locationIndex(points) {
    const buckets = new Map(); let order = 0;
    for (const [ref, point] of points) {
      if (!buckets.has(point.top)) buckets.set(point.top, { top: point.top, bottom: point.bottom, entries: [] });
      const bucket = buckets.get(point.top);
      bucket.bottom = Math.max(bucket.bottom, point.bottom); bucket.entries.push({ ref, point, order: order++ });
    }
    const rows = Array.from(buckets.values()).sort((a, b) => a.top - b.top); let bottom = -Infinity;
    for (const row of rows) { bottom = Math.max(bottom, row.bottom); row.lastBottom = bottom; }
    return { locations: points, rows };
  }
  function paths(active, model, width, viewport, { locationIndex: prepared }) {
    const points = prepared.locations, visible = new Set(), visibleEntries = [], span = model.end > model.start ? model.end - model.start : 1, scale = width / span;
    const x = value => (value - model.start) * scale;
    let low = 0, high = prepared.rows.length;
    while (low < high) { const mid = (low + high) >> 1; if (prepared.rows[mid].lastBottom <= viewport.top) low = mid + 1; else high = mid; }
    for (let row = low; row < prepared.rows.length && prepared.rows[row].top < viewport.top + viewport.height; row++) {
      for (const entry of prepared.rows[row].entries) {
        const { point } = entry, pad = point.start === point.end ? 12 : 0;
        if (point.bottom > viewport.top
          && x(point.end) + pad >= viewport.left && x(point.start) - pad <= viewport.left + viewport.width) visibleEntries.push(entry);
      }
    }
    visibleEntries.sort((a, b) => a.order - b.order);
    let criticalVisible = 0, relatedVisible = 0;
    for (const { ref } of visibleEntries) {
      visible.add(ref); if (active.critical.has(ref)) criticalVisible++; if (active.related.has(ref)) relatedVisible++;
    }
    const adjacency = active.adjacency, drawnEdges = [];
    for (const ref of visible) for (const edge of adjacency.get(ref) || []) if (visible.has(edge.edge.to_task_ref)) drawnEdges.push(edge);
    drawnEdges.sort((a, b) => a.order - b.order);
    const drawn = drawnEdges.map(({ edge }) => {
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
    return { paths: drawn, visible, criticalVisible, relatedVisible, focused: !!active.target };
  }
  window.GanttGraph = { validate, create, selection, route, locations, locationIndex, paths };
})();
