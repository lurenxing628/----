import React from "react";

/**
 * APS Kpi — a compact metric tile for non-severity numbers (totals,
 * rates). Muted label, 28px BOLD (700) tabular numeral — the same
 * callout-numeral weight the 值班台 risk grid uses, so KPI figures sit
 * in one numeric language with the dashboard. Optional helper + trailing
 * badge. Flat card, no sparkline, no gradient.
 */
export function Kpi({ label, value, helper, badge = null, valueColor = "var(--ui-text)", style = {}, ...rest }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        padding: "16px",
        border: "1px solid var(--ui-border)",
        borderRadius: 6,
        background: "var(--ui-card-bg)",
        boxShadow: "var(--ui-shadow-sm)",
        fontFamily: "var(--font-family)",
        ...style,
      }}
      {...rest}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 13, color: "var(--ui-muted)" }}>{label}</span>
        {badge}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.2, color: valueColor, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {helper ? <div style={{ fontSize: 12, color: "var(--ui-muted)", lineHeight: 1.5 }}>{helper}</div> : null}
    </div>
  );
}
