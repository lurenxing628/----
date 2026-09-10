import React from "react";

/**
 * APS GanttBar — a scheduling bar matching the product's frappe-gantt
 * visuals: a near-rectangular fill (4px radius), thin slate stroke, and
 * a white label with a dark halo. Status drives the fill from the gantt
 * palette; `overdue` adds the heavy red stroke; `external` makes the
 * border dashed; `critical` adds the gold key-chain outline; `dim` fades
 * non-focused bars during 沿链巡检.
 *
 * Position inside a relative lane with `left` / `width` (CSS lengths).
 */
const FILL = {
  normal:   "var(--gantt-normal)",
  urgent:   "var(--gantt-urgent)",
  critical: "var(--gantt-critical)",
  success:  "var(--ui-success)",
  primary:  "var(--ui-primary)",
};

export function GanttBar({
  status = "normal",
  left = "0%",
  width = "20%",
  top = 10,
  overdue = false,
  external = false,
  critical = false,
  dim = false,
  children,
  style = {},
  ...rest
}) {
  return (
    <div
      title={typeof children === "string" ? children : undefined}
      style={{
        position: "absolute",
        left,
        width,
        top,
        height: 30,
        borderRadius: 4,
        padding: "0 10px",
        display: "flex",
        alignItems: "center",
        background: FILL[status] || FILL.normal,
        color: "#fff",
        fontFamily: "var(--font-family)",
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1,
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
        border: external ? "1.5px dashed rgba(15,23,42,0.45)" : "1px solid rgba(15,23,42,0.16)",
        boxShadow: overdue ? "inset 0 0 0 2px var(--gantt-critical)" : "none",
        outline: critical ? "2px solid #d4a017" : "none",
        outlineOffset: critical ? "1px" : 0,
        opacity: dim ? 0.4 : 1,
        textShadow: "0 1px 1px rgba(15,23,42,0.45)",
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
