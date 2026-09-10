(function () {
  'use strict';

  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
    .wb-point{position:absolute;width:24px;height:24px;min-width:24px;min-height:24px;padding:0;border:0;background:transparent;transform:translateX(-50%);cursor:pointer;border-radius:0;color:var(--ui-text)}
    .wb-point::after{content:'';position:absolute;width:12px;height:12px;left:6px;top:6px;transform:rotate(45deg);background:var(--wb-gantt-primary-fill);border:1px solid var(--wb-gantt-primary-edge);box-sizing:border-box}
    .wb-point.plan::after,.wb-point.before::after{background:var(--wb-gantt-plan-fill);border-color:var(--wb-gantt-plan-edge)}
    .wb-point.before::after{border-style:dashed}.wb-point.critical::after{background:var(--wb-gantt-critical-fill);border-color:var(--wb-gantt-critical-edge)}
    .wb-point.success::after{background:var(--wb-gantt-success-fill);border-color:var(--wb-gantt-success-edge)}
    .wb-point:hover::after,.wb-point[aria-pressed=true]::after{border:2px solid var(--wb-gantt-gold)}
    .wb-point:focus-visible{outline:2px solid var(--wb-gantt-gold);outline-offset:-1px}
  `);
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
