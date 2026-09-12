(function () {
  'use strict';

  function Styles() {
    return null;
  }
  function Marker({
    task,
    x,
    top = 12,
    title,
    selected,
    tone = '',
    onSelect,
    onHover,
    ...props
  }) {
    return /*#__PURE__*/React.createElement("button", {
      ...props,
      type: "button",
      className: 'wb-point ' + tone,
      "data-point-ref": task.task_ref || task.row_ref,
      "data-point-at": task.start,
      "aria-label": title,
      title: title,
      "aria-pressed": !!selected,
      style: {
        left: x,
        top
      },
      onClick: onSelect,
      onMouseEnter: onHover,
      onMouseLeave: () => onHover && onHover(null)
    });
  }
  window.PointGantt = {
    Styles,
    Marker
  };
})();
