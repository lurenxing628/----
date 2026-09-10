(function () {
  'use strict';

  const B = window.APSWorkbenchControlBridge;
  function WorkbenchSelectMenu({
    owner,
    id,
    menuRef,
    onCommit
  }) {
    const [rows, setRows] = React.useState(() => B.rows(owner));
    const [active, setActive] = React.useState(() => {
      const options = B.rows(owner),
        selected = options.find(row => row.index === owner.selectedIndex && !row.disabled);
      return (selected || options.find(row => !row.disabled) || {
        index: -1
      }).index;
    });
    const buffer = React.useRef({
      text: '',
      time: 0
    });
    React.useEffect(() => {
      const observer = new MutationObserver(() => {
        const options = B.rows(owner);
        setRows(options);
        setActive(index => options.some(row => row.index === index && !row.disabled) ? index : (options.find(row => !row.disabled) || {
          index: -1
        }).index);
      });
      observer.observe(owner, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['disabled', 'hidden', 'label', 'value']
      });
      return () => observer.disconnect();
    }, [owner]);
    React.useLayoutEffect(() => {
      const optionId = id + '-' + active;
      if (active >= 0) owner.setAttribute('aria-activedescendant', optionId);else owner.removeAttribute('aria-activedescendant');
      const node = document.getElementById(optionId);
      if (node) {
        const container = node.closest('.wb-control-popup'),
          rect = node.getBoundingClientRect(),
          bounds = container.getBoundingClientRect();
        if (rect.bottom > bounds.bottom) container.scrollTop += rect.bottom - bounds.bottom;else if (rect.top < bounds.top) container.scrollTop -= bounds.top - rect.top;
      }
      return () => owner.removeAttribute('aria-activedescendant');
    }, [owner, id, active]);
    const enabled = rows.filter(row => !row.disabled);
    menuRef.current = event => {
      const index = enabled.findIndex(row => row.index === active);
      if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'PageDown', 'PageUp'].includes(event.key)) {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? enabled.length - 1 : index + {
          ArrowDown: 1,
          ArrowUp: -1,
          PageDown: 10,
          PageUp: -10
        }[event.key];
        if (enabled.length) setActive(enabled[Math.min(enabled.length - 1, Math.max(0, next))].index);
      } else if (event.key === 'Enter' || event.key === ' ' && !buffer.current.text) {
        event.preventDefault();
        if (active >= 0) onCommit(active);
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        const now = Date.now(),
          previous = buffer.current;
        const text = (now - previous.time < 700 ? previous.text : '') + event.key.toLocaleLowerCase();
        buffer.current = {
          text,
          time: now
        };
        const repeated = text.split('').every(char => char === text[0]),
          prefix = repeated ? text[0] : text;
        const ordered = enabled.slice(index + (repeated ? 1 : 0)).concat(enabled.slice(0, index + (repeated ? 1 : 0)));
        const match = ordered.find(row => row.label.toLocaleLowerCase().startsWith(prefix));
        if (match) setActive(match.index);
      }
    };
    return /*#__PURE__*/React.createElement("div", {
      id: id,
      role: "listbox",
      "aria-label": B.label(owner),
      className: "wb-select-list"
    }, !rows.length && /*#__PURE__*/React.createElement("div", {
      className: "wb-popup-empty",
      role: "status"
    }, "\u6682\u65E0\u9009\u9879"), rows.map((row, index) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: row.index
    }, row.group && (!index || rows[index - 1].group !== row.group) && /*#__PURE__*/React.createElement("div", {
      className: "wb-popup-group"
    }, row.group), /*#__PURE__*/React.createElement("div", {
      id: id + '-' + row.index,
      role: "option",
      "aria-selected": row.index === owner.selectedIndex,
      "aria-disabled": row.disabled || undefined,
      "data-active": row.index === active,
      className: "wb-popup-option",
      onPointerMove: () => {
        if (!row.disabled) setActive(row.index);
      },
      onPointerDown: event => event.preventDefault(),
      onClick: () => {
        if (!row.disabled) onCommit(row.index);
      }
    }, /*#__PURE__*/React.createElement("span", null, row.label || '未选择'), row.index === owner.selectedIndex && /*#__PURE__*/React.createElement(window.ResourceControls.Icon, {
      name: "check"
    })))));
  }
  window.WorkbenchSelectMenu = WorkbenchSelectMenu;
})();
