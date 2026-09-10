import React from "react";

const FILL = {
  primary: "var(--ui-primary)",
  success: "var(--ui-success)",
  warning: "var(--ui-warning)",
  danger:  "var(--ui-danger)",
};

/**
 * APS Meter — resource-load / progress bar. Flat track + flat fill, no
 * gradient. Auto-tones by value when `tone` is omitted (load thresholds
 * mirror the product: >=90 danger, >=75 warning, else success).
 */
export function Meter({ value = 0, tone, height = 8, style = {}, ...rest }) {
  const v = Math.max(0, Math.min(100, value));
  const auto = v >= 90 ? "danger" : v >= 75 ? "warning" : "success";
  const t = tone || auto;
  return (
    <div
      role="progressbar"
      aria-valuenow={v}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{
        height,
        borderRadius: 999,
        background: "var(--ui-surface-soft)",
        overflow: "hidden",
        ...style,
      }}
      {...rest}
    >
      <span style={{ display: "block", height: "100%", width: `${v}%`, borderRadius: "inherit", background: FILL[t] || FILL.primary, transition: "width .2s ease" }} />
    </div>
  );
}
