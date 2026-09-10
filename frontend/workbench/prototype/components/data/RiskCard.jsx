import React from "react";

/**
 * APS RiskCard — one cell of the dashboard health-check grid.
 * Flush-left stack (layout "B1"): a muted label sits at the top-left, the
 * big tabular number + an optional unit (个/项/道…) reads directly beneath
 * it, and the helper is pinned to the foot — all three sharing one left
 * edge so the column scans cleanly. The number leads the hierarchy by size
 * and colour; the unit nudges the visual weight off the hard-left. A left
 * 4px severity bar (ok/notice/warning/danger) carries the status; an
 * optional nav chip sits top-right.
 *
 * Hover = soft shadow-lift; the brand ring is reserved for real
 * :focus-visible (keyboard), drawn with the severity bar still on top.
 */
const SEV = {
  ok:      "var(--ui-success)",
  notice:  "var(--ui-primary)",
  warning: "var(--ui-warning)",
  danger:  "var(--ui-danger)",
};
const VAL = {
  ok:      "var(--ui-success)",
  notice:  "var(--ui-primary)",
  warning: "var(--ui-warning)",
  danger:  "var(--ui-danger)",
};

export function RiskCard({ severity = "ok", label, value, unit, helper, href, disabled = false, style = {}, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const [keyFocus, setKeyFocus] = React.useState(false);
  const interactive = !!href && !disabled;
  const bar = SEV[severity] || SEV.ok;

  const raised = interactive && (hover || keyFocus);
  const boxShadow = keyFocus ? "var(--ui-focus-ring)" : raised ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)";

  const base = {
    display: "flex",
    flexDirection: "column",
    minHeight: 140,
    padding: "15px 18px",
    border: "1px solid var(--ui-border)",
    borderLeft: `4px solid ${bar}`,
    borderRadius: 8,
    background: raised ? "var(--ui-surface-raised)" : "var(--ui-surface-muted)",
    color: "var(--ui-text)",
    textDecoration: "none",
    fontFamily: "var(--font-family)",
    cursor: interactive ? "pointer" : "default",
    opacity: disabled ? 0.7 : 1,
    outline: "none",
    boxShadow,
    transform: raised ? "translateY(-1px)" : "none",
    transition: "box-shadow .15s ease, transform .15s ease, background-color .15s ease",
  };

  const inner = (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ui-muted)", letterSpacing: "0.02em" }}>{label}</span>
        {interactive ? (
          <span aria-hidden="true" style={{ flex: "none", width: 22, height: 22, borderRadius: 6, display: "grid", placeItems: "center", fontSize: 13, lineHeight: 1, color: raised ? "#fff" : "var(--ui-muted)", background: raised ? "var(--ui-primary)" : "var(--ui-surface-soft)", transform: raised ? "translateX(1px)" : "none", transition: "color .15s ease, background-color .15s ease, transform .15s ease" }}>→</span>
        ) : null}
      </div>
      <div style={{ marginTop: 12, display: "flex", alignItems: "baseline" }}>
        <span style={{ fontSize: 36, fontWeight: 700, color: VAL[severity] || "var(--ui-text)", fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{value}</span>
        {unit ? <span style={{ marginLeft: 5, fontSize: 14, fontWeight: 600, color: "var(--ui-muted)" }}>{unit}</span> : null}
      </div>
      {helper ? <span style={{ marginTop: "auto", paddingTop: 12, fontSize: 12, color: "var(--ui-muted)", lineHeight: 1.55, textWrap: "pretty" }}>{helper}</span> : null}
    </>
  );

  if (interactive) {
    return (
      <a
        href={href}
        style={base}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={(e) => { try { if (e.currentTarget.matches(":focus-visible")) setKeyFocus(true); } catch (_) { setKeyFocus(true); } }}
        onBlur={() => setKeyFocus(false)}
        {...rest}
      >
        {inner}
      </a>
    );
  }
  return <div style={base} aria-disabled={disabled || undefined} {...rest}>{inner}</div>;
}
