(function () {
  'use strict';
  const fields = ['event_kind', 'duration_seconds', 'occupies_resources'];
  const own = (row, key) => Object.prototype.hasOwnProperty.call(row, key);
  const isPoint = row => !!row && row.event_kind === 'point' && row.duration_seconds === 0
    && row.occupies_resources === false && typeof row.start === 'string' && row.start === row.end;
  function arrangement(row, owner) {
    if (!row) return false;
    if (fields.some(key => own(row, key))) return isPoint(row);
    // Trial original/history arrangements inherit only their own verified task's kind.
    return owner && isPoint(owner) ? row.start === row.end : row.start < row.end;
  }
  function overlaps(row, low, high) {
    return isPoint(row) ? low <= row.start && row.start < high : row.start < high && row.end > low;
  }
  window.PointContract = { fields, isPoint, arrangement, overlaps };
})();
