(function () {
  'use strict';
  function serialize(rows) {
    if (rows.length === 1 && !rows[0].seq.trim() && !rows[0].op_type_name.trim()) return '';
    return rows.map(row => {
      let name = row.op_type_name;
      if (/[;；\r\n"]/.test(name) || name !== name.trim()) name = '"' + name.replace(/"/g, '""') + '"';
      return row.seq + ': ' + name;
    }).join('；');
  }
  function fromEntity(entity) {
    return entity.operations.filter(row => row.status === 'active').map(row => ({ seq: String(row.sequence), op_type_name: row.label }));
  }
  const same = (a, b) => !a && !b || !!a && !!b && a.op_type_name === b.op_type_name;
  const order = (a, b) => a.seq.length - b.seq.length || a.seq.localeCompare(b.seq);
  function merge(before, local, latest) {
    const maps = [before, local, latest].map(rows => new Map(rows.map(row => [String(row.seq), row])));
    const rows = [], conflicts = [];
    new Set([...maps[0].keys(), ...maps[1].keys(), ...maps[2].keys()]).forEach(seq => {
      const [base, draft, fresh] = maps.map(map => map.get(seq));
      if (same(draft, base)) { if (fresh) rows.push(fresh); }
      else if (same(fresh, base) || same(draft, fresh)) { if (draft) rows.push(draft); }
      else conflicts.push({ seq, before: base || null, local: draft || null, latest: fresh || null });
    });
    return { rows: rows.slice().sort(order), conflicts: conflicts.sort(order) };
  }
  function resolve(merged, choices) {
    if (merged.conflicts.some(row => !['local', 'latest'].includes(choices[row.seq]))) throw new Error('请逐项选择冲突工序要保留的内容。');
    return merged.rows.concat(merged.conflicts.map(row => row[choices[row.seq]]).filter(Boolean)).sort(order);
  }
  window.ProcessRouteDraft = { serialize, fromEntity, merge, resolve };
})();
