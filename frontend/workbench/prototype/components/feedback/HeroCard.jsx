import React from "react";

/**
 * APS HeroCard — the dashboard's single most-urgent command card.
 * Shares the RiskCard design language: a NEUTRAL muted surface, a thin
 * 1px border, a 4px left severity bar, an 8px radius and a soft shadow.
 * Colour is reserved for the bar, the eyebrow severity dot+label, and the
 * big call-out NUMBERS — never a filled background tint.
 *
 * Number language (matches the 7-cell risk grid): the most-urgent figure is
 * pulled out of the sentence into a large, severity-coloured, tabular numeral.
 * `lead` is the primary number on the left (largest); `anchor` is an optional
 * secondary number on the right (smaller) that supplies the "how bad" figure.
 * The whole card is vertically centred so both numbers, the narrative and the
 * actions all share one centre-of-gravity line.
 *
 * Severity has four levels: ok (green) / notice (blue) / warning / danger.
 */
const SEV = {
  ok:      { bar: "var(--ui-success)", accent: "var(--ui-success)", word: "正常" },
  notice:  { bar: "var(--ui-primary)", accent: "var(--ui-primary)", word: "提示" },
  warning: { bar: "var(--ui-warning)", accent: "var(--ui-warning)", word: "需关注" },
  danger:  { bar: "var(--ui-danger)",  accent: "var(--ui-danger)",  word: "紧急" },
};

function NumberColumn({ data, side, accent }) {
  // side: "lead" (primary, left, flush-left) | "anchor" (secondary, right, centred)
  const isLead = side === "lead";
  const numSize = isLead ? 50 : 34;
  const unitSize = isLead ? 16 : 13;
  const numColor = data.color || accent;
  return (
    <div
      style={{
        flex: "none",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: isLead ? "flex-start" : "center",
        textAlign: isLead ? "left" : "center",
        ...(isLead
          ? { paddingRight: 22, borderRight: "1px solid var(--ui-border)" }
          : { paddingLeft: 22, borderLeft: "1px solid var(--ui-border)" }),
      }}
    >
      {data.caption ? (
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ui-muted)", whiteSpace: "nowrap", minHeight: 18, lineHeight: "18px" }}>
          {data.caption}
        </span>
      ) : null}
      <span style={{ display: "flex", alignItems: "baseline", justifyContent: isLead ? "flex-start" : "center", marginTop: 6 }}>
        <span style={{ fontSize: numSize, fontWeight: 700, color: numColor, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>
          {data.value}
        </span>
        {data.unit ? <span style={{ fontSize: unitSize, fontWeight: 600, color: "var(--ui-muted)", marginLeft: 6 }}>{data.unit}</span> : null}
      </span>
      {data.sub ? (
        <span style={{ marginTop: 8, fontSize: 12, color: "var(--ui-muted)", minHeight: 16 }}>{data.sub}</span>
      ) : null}
    </div>
  );
}

export function HeroCard({ severity = "notice", eyebrow, title, impact, evidence, lead, anchor, actions = null, style = {}, ...rest }) {
  const s = SEV[severity] || SEV.notice;
  return (
    <section
      style={{
        display: "flex",
        alignItems: "center",
        gap: 24,
        flexWrap: "wrap",
        padding: "20px 22px",
        border: "1px solid var(--ui-border)",
        borderLeft: `4px solid ${s.bar}`,
        borderRadius: 8,
        background: "var(--ui-surface-muted)",
        boxShadow: "var(--ui-shadow-sm)",
        fontFamily: "var(--font-family)",
        color: "var(--ui-text)",
        ...style,
      }}
      {...rest}
    >
      {lead ? <NumberColumn data={lead} side="lead" accent={s.accent} /> : null}

      <div style={{ flex: "1 1 320px", minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
          <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: "50%", background: s.accent, flex: "none" }} />
          <span style={{ fontSize: 12, fontWeight: 700, color: s.accent, letterSpacing: "0.04em", whiteSpace: "nowrap" }}>{s.word}</span>
          {eyebrow ? <span style={{ fontSize: 12, color: "var(--ui-muted)", fontWeight: 600, letterSpacing: "0.02em", whiteSpace: "nowrap" }}>· {eyebrow}</span> : null}
        </div>
        <h4 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--ui-text)", lineHeight: 1.42, textWrap: "pretty" }}>{title}</h4>
        {impact ? <p style={{ margin: "9px 0 0", fontSize: 14, color: "var(--ui-text)", lineHeight: 1.6, textWrap: "pretty" }}>{impact}</p> : null}
        {evidence ? <p style={{ margin: "7px 0 0", fontSize: 13, color: "var(--ui-muted)", lineHeight: 1.6, textWrap: "pretty" }}>{evidence}</p> : null}
      </div>

      {anchor ? <NumberColumn data={anchor} side="anchor" accent={s.accent} /> : null}

      {actions ? <div style={{ display: "flex", gap: 10, flexWrap: "wrap", flex: "none", alignSelf: "center" }}>{actions}</div> : null}
    </section>
  );
}
