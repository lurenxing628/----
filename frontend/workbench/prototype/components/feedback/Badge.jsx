import React from "react";

/**
 * APS Badge — the status pill used in table cells and inline.
 * Two channels in one chip: tinted fill + bold text, plus an optional
 * `dot` for the third (colour-blind-safe) channel. Severity tones map
 * to the four-level system: ok→success, notice→info, warning, danger.
 */
const TONES = {
  primary:   { bg: "var(--badge-primary-bg)", fg: "var(--badge-primary-text)", dot: "var(--ui-primary)" },
  secondary: { bg: "var(--badge-secondary-bg)", fg: "var(--badge-secondary-text)", dot: "#94a3b8" },
  success:   { bg: "var(--badge-success-bg)", fg: "var(--badge-success-text)", dot: "var(--ui-success)" },
  warning:   { bg: "var(--badge-warning-bg)", fg: "var(--badge-warning-text)", dot: "var(--ui-warning)" },
  danger:    { bg: "var(--badge-danger-bg)", fg: "var(--badge-danger-text)", dot: "var(--ui-danger)" },
  // severity aliases
  ok:        { bg: "var(--badge-success-bg)", fg: "var(--badge-success-text)", dot: "var(--ui-success)" },
  notice:    { bg: "var(--badge-primary-bg)", fg: "var(--badge-primary-text)", dot: "var(--ui-primary)" },
};

export function Badge({ tone = "secondary", dot = false, children, style = {}, ...rest }) {
  const t = TONES[tone] || TONES.secondary;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: dot ? "0.35em" : 0,
        padding: "0.25em 0.6em",
        fontFamily: "var(--font-family)",
        fontSize: "0.75em",
        fontWeight: 700,
        lineHeight: 1,
        whiteSpace: "nowrap",
        verticalAlign: "baseline",
        borderRadius: "0.25rem",
        background: t.bg,
        color: t.fg,
        ...style,
      }}
      {...rest}
    >
      {dot ? <span aria-hidden="true" style={{ width: "0.5em", height: "0.5em", borderRadius: "50%", background: t.dot, flex: "none" }} /> : null}
      {children}
    </span>
  );
}
