const isPoint = row => !!row && row.event_kind === 'point' && row.duration_seconds === 0
  && row.occupies_resources === false && typeof row.start === 'string' && row.start === row.end;
function overlaps(row, low, high) {
  return isPoint(row) ? low <= row.start && row.start < high : row.start < high && row.end > low;
}
const PointContract = { isPoint, overlaps };
export { PointContract, isPoint, overlaps };
export default PointContract;
