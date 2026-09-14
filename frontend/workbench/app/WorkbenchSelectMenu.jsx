(function () {
  'use strict';
  const B = window.APSWorkbenchControlBridge;
  // Long lists get a visible filter box; short ones keep plain type-ahead, whose buffer is echoed instead of staying invisible.
  const FILTER_FROM = 8, BUFFER_MS = 700;
  function WorkbenchSelectMenu({ owner, id, menuRef, onCommit }) {
    const [rows, setRows] = React.useState(() => B.rows(owner));
    const [active, setActive] = React.useState(() => {
      const options = B.rows(owner), selected = options.find(row => row.index === owner.selectedIndex && !row.disabled);
      return (selected || options.find(row => !row.disabled) || { index: -1 }).index;
    });
    const [filter, setFilter] = React.useState(''), [typed, setTyped] = React.useState('');
    const buffer = React.useRef({ text: '', time: 0 }), expiry = React.useRef(0), box = React.useRef(null);
    React.useEffect(() => {
      const observer = new MutationObserver(() => {
        const options = B.rows(owner); setRows(options);
        setActive(index => options.some(row => row.index === index && !row.disabled) ? index : (options.find(row => !row.disabled) || { index: -1 }).index);
      });
      observer.observe(owner, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['disabled', 'hidden', 'label', 'value'] });
      return () => observer.disconnect();
    }, [owner]);
    React.useEffect(() => () => clearTimeout(expiry.current), []);
    const filterable = rows.length > FILTER_FROM;
    const needle = filterable ? filter.trim().toLocaleLowerCase() : '';
    const listed = needle ? rows.filter(row => row.label.toLocaleLowerCase().includes(needle)) : rows;
    const enabled = listed.filter(row => !row.disabled);
    // Filtering can hide the remembered option, so the focused option is always resolved against what is on screen.
    const current = enabled.some(row => row.index === active) ? active : (enabled[0] || { index: -1 }).index;
    React.useLayoutEffect(() => {
      const optionId = id + '-' + current;
      if (current >= 0) owner.setAttribute('aria-activedescendant', optionId);
      else owner.removeAttribute('aria-activedescendant');
      const node = document.getElementById(optionId);
      if (node) {
        const container = node.closest('.wb-control-popup'), rect = node.getBoundingClientRect(), bounds = container.getBoundingClientRect();
        if (rect.bottom > bounds.bottom) container.scrollTop += rect.bottom - bounds.bottom;
        else if (rect.top < bounds.top) container.scrollTop -= bounds.top - rect.top;
      }
      return () => owner.removeAttribute('aria-activedescendant');
    }, [owner, id, current]);
    function remember(text) {
      buffer.current = { text, time: Date.now() }; setTyped(text);
      clearTimeout(expiry.current);
      expiry.current = setTimeout(() => { buffer.current = { text: '', time: 0 }; setTyped(''); }, BUFFER_MS);
    }
    menuRef.current = event => {
      const index = enabled.findIndex(row => row.index === current);
      if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'PageDown', 'PageUp'].includes(event.key)) {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? enabled.length - 1 : index + ({ ArrowDown: 1, ArrowUp: -1, PageDown: 10, PageUp: -10 })[event.key];
        if (enabled.length) setActive(enabled[Math.min(enabled.length - 1, Math.max(0, next))].index);
      } else if (event.key === 'Enter' || event.key === ' ' && !buffer.current.text) {
        event.preventDefault(); if (current >= 0) onCommit(current);
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        // With a filter box on screen the typed text belongs in it, where it stays readable and narrows the list.
        if (filterable) { setFilter(text => text + event.key); box.current.focus({ preventScroll: true }); return; }
        const now = Date.now(), previous = buffer.current;
        const text = (now - previous.time < BUFFER_MS ? previous.text : '') + event.key.toLocaleLowerCase();
        remember(text);
        const repeated = text.split('').every(char => char === text[0]), prefix = repeated ? text[0] : text;
        const ordered = enabled.slice(index + (repeated ? 1 : 0)).concat(enabled.slice(0, index + (repeated ? 1 : 0)));
        const match = ordered.find(row => row.label.toLocaleLowerCase().startsWith(prefix));
        if (match) setActive(match.index);
      }
    };
    return <React.Fragment>
      {(filterable || typed) && <div className="wb-select-tools">
        {filterable && <input ref={box} className="wb-popup-search" type="search" value={filter} aria-label={'筛选' + B.label(owner) + '选项'}
          onChange={event => setFilter(event.target.value)} onKeyDown={event => {
            if (event.key === 'ArrowDown') { event.preventDefault(); if (enabled.length) { setActive(enabled[0].index); owner.focus({ preventScroll: true }); } }
            else if (event.key === 'Enter') { event.preventDefault(); if (current >= 0) onCommit(current); }
          }} />}
        {typed && <span className="wb-select-typed" role="status">正在输入 {typed}</span>}
      </div>}
      <div id={id} role="listbox" aria-label={B.label(owner)} className="wb-select-list">
        {!listed.length && <div className="wb-popup-empty" role="status">{rows.length ? '当前筛选没有匹配项' : '暂无选项'}</div>}
        {listed.map((row, index) => <React.Fragment key={row.index}>
          {row.group && (!index || listed[index - 1].group !== row.group) && <div className="wb-popup-group">{row.group}</div>}
          <div id={id + '-' + row.index} role="option" aria-selected={row.index === owner.selectedIndex}
            aria-disabled={row.disabled || undefined} data-active={row.index === current} className="wb-popup-option"
            onPointerMove={() => { if (!row.disabled) setActive(row.index); }}
            onPointerDown={event => event.preventDefault()}
            onClick={() => { if (!row.disabled) onCommit(row.index); }}>
            <span>{row.label || '未选择'}</span>{row.index === owner.selectedIndex && <window.ResourceControls.Icon name="check" />}
          </div>
        </React.Fragment>)}
      </div>
    </React.Fragment>;
  }
  window.WorkbenchSelectMenu = WorkbenchSelectMenu;
})();
