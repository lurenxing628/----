(function () {
  'use strict';

  const B = window.APSWorkbenchControlBridge;
  function WorkbenchControls() {
    const [opened, setOpened] = React.useState(null),
      current = React.useRef(null),
      popup = React.useRef(null),
      menu = React.useRef(null);
    const [position, setPosition] = React.useState({
      left: 0,
      top: 0,
      visibility: 'hidden'
    });
    const id = React.useId().replace(/:/g, '') + '-control-options';
    function close(focus) {
      const owner = current.current && current.current.owner;
      current.current = null;
      menu.current = null;
      setOpened(null);
      if (focus && owner && B.available(owner)) owner.focus({
        preventScroll: true
      });
    }
    function open(owner) {
      const type = B.kind(owner);
      if (!type) return;
      if (current.current && current.current.owner === owner) {
        close(true);
        return;
      }
      close(false);
      owner.focus({
        preventScroll: true
      });
      const value = {
        owner,
        type,
        value: owner.value,
        portal: owner.closest('[role="dialog"]') || document.body
      };
      current.current = value;
      setPosition({
        left: 0,
        top: 0,
        visibility: 'hidden'
      });
      setOpened(value);
    }
    React.useEffect(() => {
      function target(event) {
        const input = event.target.closest && event.target.closest('select,input');
        return input && input.closest('body.aps-workbench') && !input.closest('.wb-control-popup') ? input : null;
      }
      function trigger(event, input) {
        const type = B.kind(input);
        return type === 'select' || type && (event.clientX >= input.getBoundingClientRect().right - 32 || event.type === 'click' && event.detail === 0);
      }
      function pointer(event) {
        if (event.button !== 0 || popup.current && popup.current.contains(event.target)) return;
        const input = target(event);
        if (input && trigger(event, input)) {
          event.preventDefault();
          open(input);
        } else if (current.current) close(false);
      }
      function click(event) {
        const input = target(event);
        if (!input || !trigger(event, input)) return;
        event.preventDefault();
        if (event.detail === 0 && (!current.current || current.current.owner !== input)) open(input);
      }
      function key(event) {
        const value = current.current;
        if (value) {
          if (event.key === 'Escape') {
            event.preventDefault();
            event.stopImmediatePropagation();
            close(true);
            return;
          }
          if (value.type === 'select' && event.target === value.owner) {
            if (event.key === 'Tab') {
              close(false);
              return;
            }
            if (menu.current) {
              menu.current(event);
              event.stopImmediatePropagation();
            }
            return;
          }
          if (event.key === 'Tab' && popup.current && popup.current.contains(event.target)) {
            const fields = Array.from(popup.current.querySelectorAll('button:not(:disabled),input:not(:disabled),[tabindex="0"]')).filter(node => node.getClientRects().length);
            const first = fields[0],
              last = fields[fields.length - 1];
            if (event.shiftKey && event.target === first || !event.shiftKey && event.target === last) {
              event.preventDefault();
              (event.shiftKey ? last : first).focus();
            }
            event.stopImmediatePropagation();
          }
          return;
        }
        const input = target(event),
          type = B.kind(input);
        if (type && (['F4', 'Enter', ' '].includes(event.key) || event.altKey && event.key === 'ArrowDown' || type === 'select' && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key))) {
          event.preventDefault();
          event.stopImmediatePropagation();
          open(input);
        }
      }
      function focus(event) {
        if (current.current && event.target !== current.current.owner && !(popup.current && popup.current.contains(event.target))) close(false);
      }
      document.addEventListener('pointerdown', pointer, true);
      document.addEventListener('click', click, true);
      document.addEventListener('keydown', key, true);
      document.addEventListener('focusin', focus, true);
      return () => {
        document.removeEventListener('pointerdown', pointer, true);
        document.removeEventListener('click', click, true);
        document.removeEventListener('keydown', key, true);
        document.removeEventListener('focusin', focus, true);
      };
    }, []);
    React.useLayoutEffect(() => {
      if (!opened) return;
      const owner = opened.owner,
        attributes = ['aria-expanded', 'aria-controls', 'aria-haspopup'];
      const previous = attributes.map(name => owner.getAttribute(name));
      owner.setAttribute('aria-expanded', 'true');
      owner.setAttribute('aria-controls', id);
      owner.setAttribute('aria-haspopup', opened.type === 'select' ? 'listbox' : 'dialog');
      function place() {
        if (!B.available(owner) || !owner.getClientRects().length || !owner.closest('body.aps-workbench')) {
          close(false);
          return;
        }
        const rect = owner.getBoundingClientRect(),
          panel = popup.current;
        const width = Math.min(innerWidth - 16, opened.type === 'select' ? Math.max(rect.width, 180) : 320);
        const natural = Math.min(panel ? panel.scrollHeight : 320, opened.type === 'select' ? 320 : 520);
        const below = innerHeight - rect.bottom - 12,
          above = rect.top - 12;
        const down = below >= natural || below >= above;
        const maxHeight = Math.min(opened.type === 'select' ? 320 : 520, innerHeight - 16);
        const height = Math.min(natural, maxHeight),
          preferred = down ? rect.bottom + 4 : rect.top - height - 4;
        setPosition({
          left: Math.max(8, Math.min(rect.left, innerWidth - width - 8)),
          top: Math.max(8, Math.min(preferred, innerHeight - height - 8)),
          width,
          maxHeight,
          visibility: 'visible'
        });
      }
      place();
      const observer = new MutationObserver(() => {
        if (B.kind(owner) !== opened.type || owner.closest('[aria-hidden="true"]') || opened.type !== 'select' && owner.value !== opened.value) close(false);
      });
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['disabled', 'readonly', 'aria-hidden', 'inert', 'type', 'value', 'min', 'max', 'step']
      });
      const size = new ResizeObserver(place);
      size.observe(owner);
      if (popup.current) size.observe(popup.current);
      function viewportChanged(event) {
        if (opened.type === 'select') {
          place();
          return;
        }
        if (event.type === 'scroll' && popup.current && popup.current.contains(event.target)) return;
        close(true);
      }
      window.addEventListener('resize', viewportChanged);
      document.addEventListener('scroll', viewportChanged, true);
      if (opened.type !== 'select' && popup.current) {
        const first = popup.current.querySelector('[data-picker-initial]') || popup.current.querySelector('input:not(:disabled),button:not(:disabled)');
        (first || popup.current).focus({
          preventScroll: true
        });
      }
      return () => {
        observer.disconnect();
        size.disconnect();
        window.removeEventListener('resize', viewportChanged);
        document.removeEventListener('scroll', viewportChanged, true);
        attributes.forEach((name, index) => {
          if (previous[index] === null) owner.removeAttribute(name);else owner.setAttribute(name, previous[index]);
        });
      };
    }, [opened, id]);
    if (!opened) return null;
    const owner = opened.owner;
    function commit(value) {
      if (!B.available(owner)) {
        close(false);
        return;
      }
      if (opened.type === 'select') {
        if (!B.rows(owner).some(row => row.index === value && !row.disabled)) return;
        B.selectIndex(owner, value);
      } else {
        if (value && !window.WorkbenchDatePickerModel.validate({
          type: owner.type,
          min: owner.min,
          max: owner.max,
          step: owner.step,
          valueAttribute: owner.getAttribute('value')
        }, value).valid) return;
        B.setValue(owner, value);
      }
      close(true);
    }
    return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      ref: popup,
      className: "wb-control-popup",
      style: {
        position: 'fixed',
        zIndex: 'var(--wb-z-popup)',
        ...position
      },
      role: opened.type === 'select' ? undefined : 'dialog',
      "aria-modal": opened.type === 'select' ? undefined : true,
      id: opened.type === 'select' ? undefined : id,
      "aria-label": opened.type === 'select' ? undefined : '选择' + B.label(owner),
      tabIndex: -1
    }, opened.type === 'select' ? /*#__PURE__*/React.createElement(window.WorkbenchSelectMenu, {
      owner: owner,
      id: id,
      menuRef: menu,
      onCommit: commit
    }) : /*#__PURE__*/React.createElement(window.WorkbenchDatePicker, {
      type: opened.type,
      value: opened.value,
      valueAttribute: owner.getAttribute('value'),
      min: owner.min,
      max: owner.max,
      step: owner.step,
      label: B.label(owner),
      onCommit: commit,
      onClose: () => close(true)
    })), opened.portal);
  }
  window.WorkbenchControls = WorkbenchControls;
})();
