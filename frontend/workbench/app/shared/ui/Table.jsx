import React from '../runtime/react.js';

function Table({ columns, rows, rowKey = 'id', caption, actionColumn = -1, className = '', style = {}, ...rest }) {
  const [colWidths, setColWidths] = React.useState({});
  const dragCleanupRef = React.useRef(null);
  React.useEffect(() => () => { if (dragCleanupRef.current) dragCleanupRef.current(); }, []);

  function startResize(e, key) {
    if (dragCleanupRef.current) dragCleanupRef.current();
    e.preventDefault();
    e.stopPropagation();
    const handle = e.currentTarget;
    const th = handle.closest('th');
    const startX = e.clientX;
    const startW = th.getBoundingClientRect().width;
    handle.classList.add('dragging');
    const move = ev => {
      const w = Math.max(56, Math.round(startW + ev.clientX - startX));
      setColWidths(prev => ({ ...prev, [key]: w }));
    };
    const up = () => {
      dragCleanupRef.current = null;
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      handle.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    dragCleanupRef.current = up;
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  const totalFixedWidth = columns.length > 0 && columns.every(col => typeof col.width === 'number')
    ? columns.reduce((sum, col) => sum + col.width, 0)
    : 0;
  const pctWidth = col => totalFixedWidth > 0 ? (col.width / totalFixedWidth * 100) + '%' : col.width;

  return (
    <div className="wb-table-shell">
      <div style={{ overflowX: 'auto', border: '1px solid var(--ui-border)', borderRadius: 8, background: 'var(--ui-card-bg)' }}>
        <table
          data-aps-rtable="1"
          className={'wb-table' + (className ? ' ' + className : '')}
          style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-family)', fontSize: 14, ...style }}
          {...rest}
        >
          {caption && <caption className="wb-visually-hidden">{caption}</caption>}
          <thead>
            <tr>
              {columns.map((col, idx) => {
                const w = colWidths[col.key] != null ? colWidths[col.key] : pctWidth(col);
                const pinned = colWidths[col.key] != null;
                const justify = col.align === 'right' ? 'flex-end' : col.align === 'center' ? 'center' : 'flex-start';
                const thClass = [
                  'aps-th',
                  idx === actionColumn ? 'rw-fixed-action' : '',
                  actionColumn >= 0 && idx === 0 ? 'rw-fixed-key' : ''
                ].filter(Boolean).join(' ') || undefined;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    className={thClass}
                    style={{
                      position: 'sticky',
                      top: 0,
                      zIndex: 2,
                      textAlign: col.align || 'left',
                      padding: '10px 12px',
                      background: 'var(--ui-table-head-bg)',
                      color: 'var(--ui-muted)',
                      fontWeight: 600,
                      fontSize: 13,
                      whiteSpace: 'nowrap',
                      borderBottom: '1px solid var(--ui-border)',
                      width: w,
                      minWidth: pinned ? w : undefined,
                      maxWidth: pinned ? w : undefined,
                    }}
                  >
                    <span className="aps-th-inner" style={{ justifyContent: justify, width: '100%' }}>
                      <span className="aps-th-label">{col.title}</span>
                    </span>
                    <span className="aps-th-resize" onMouseDown={e => startResize(e, col.key)} />
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <Row key={row[rowKey] ?? i} row={row} columns={columns} even={i % 2 === 1} actionColumn={actionColumn} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ row, columns, even, actionColumn }) {
  const [hover, setHover] = React.useState(false);
  const bg = hover ? 'var(--ui-table-row-hover-bg)' : even ? 'var(--ui-table-row-even-bg)' : 'transparent';
  return (
    <tr onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} style={{ background: bg, transition: 'background-color .12s ease' }}>
      {columns.map((col, idx) => {
        const num = col.align === 'right';
        const tdClass = [
          idx === actionColumn ? 'rw-fixed-action' : '',
          actionColumn >= 0 && idx === 0 ? 'rw-fixed-key' : ''
        ].filter(Boolean).join(' ') || undefined;
        return (
          <td
            key={col.key}
            className={tdClass}
            style={{
              textAlign: col.align || 'left',
              padding: '10px 12px',
              borderBottom: '1px solid var(--ui-border)',
              color: 'var(--ui-text)',
              verticalAlign: 'middle',
              fontVariantNumeric: num ? 'tabular-nums' : 'normal',
              whiteSpace: col.nowrap ? 'nowrap' : 'normal',
            }}
          >
            {col.render ? col.render(row) : row[col.key]}
          </td>
        );
      })}
    </tr>
  );
}

export { Table, Table as DataTable };
export default Table;
