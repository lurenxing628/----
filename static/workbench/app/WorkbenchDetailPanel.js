(function () {
  'use strict';

  function WorkbenchDetailPanel({
    title,
    subtitle,
    actions,
    onClose,
    children,
    detailKey,
    triggerRef,
    autoFocus = true,
    className = ''
  }) {
    const panel = React.useRef(null),
      heading = React.useRef(null),
      trigger = React.useRef(document.activeElement);
    const movedFocus = React.useRef(false);
    const id = React.useId();
    React.useLayoutEffect(() => {
      if (!autoFocus) return;
      const active = triggerRef && triggerRef.current || document.activeElement;
      if (active && !panel.current.contains(active) && active !== document.body) trigger.current = active;
      heading.current.focus({
        preventScroll: true
      });
      movedFocus.current = true;
      const rect = heading.current.getBoundingClientRect(),
        shell = document.querySelector('.top-header');
      const top = shell ? shell.getBoundingClientRect().bottom : 0;
      if (window.matchMedia('(max-width: 1279px)').matches || rect.top < top || rect.bottom > innerHeight) panel.current.scrollIntoView({
        block: 'start',
        inline: 'nearest'
      });
    }, [detailKey, autoFocus]);
    React.useLayoutEffect(() => () => {
      if (!movedFocus.current) return;
      const previous = triggerRef && triggerRef.current || trigger.current;
      // Defer until React has removed the panel; never take focus away from another open dialog.
      queueMicrotask(() => {
        if (previous && previous.isConnected && !previous.disabled && previous.getClientRects().length && !document.querySelector('[role="dialog"][aria-modal="true"]')) previous.focus({
          preventScroll: true
        });
      });
    }, []);
    return /*#__PURE__*/React.createElement("aside", {
      ref: panel,
      className: 'wb-detail ' + className,
      role: "region",
      "aria-labelledby": id,
      onKeyDown: event => {
        if (event.key !== 'Escape' || event.defaultPrevented || event.target.closest('[data-wb-table-filter],.wb-control-popup,[role="dialog"]')) return;
        if (onClose) {
          event.preventDefault();
          event.stopPropagation();
          onClose();
        }
      }
    }, /*#__PURE__*/React.createElement("header", {
      className: "wb-detail-header"
    }, /*#__PURE__*/React.createElement("div", {
      className: "wb-detail-heading"
    }, /*#__PURE__*/React.createElement("h2", {
      id: id,
      ref: heading,
      tabIndex: -1
    }, title), subtitle && /*#__PURE__*/React.createElement("p", null, subtitle)), onClose && /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      icon: "x",
      "aria-label": '关闭' + title,
      onClick: onClose
    })), actions && /*#__PURE__*/React.createElement("div", {
      className: "wb-detail-actions"
    }, actions), /*#__PURE__*/React.createElement("div", {
      className: "wb-detail-body"
    }, children));
  }
  window.WorkbenchDetailPanel = WorkbenchDetailPanel;
})();
