import React from "react";

/**
 * APS Panel — the standard content container (.card). White, 1px border,
 * 6px radius, subtle shadow. Optional header (title + description on the
 * left, actions on the right) sits on a muted strip. Flat — no glass,
 * no big radius. Pages are a stack of these.
 */
export function Panel({ title, description, headerRight = null, children, style = {}, bodyStyle = {}, ...rest }) {
  return (
    <section
      style={{
        background: "var(--ui-card-bg)",
        border: "1px solid var(--ui-border)",
        borderRadius: 6,
        boxShadow: "var(--ui-shadow-sm)",
        overflow: "hidden",
        fontFamily: "var(--font-family)",
        color: "var(--ui-text)",
        ...style,
      }}
      {...rest}
    >
      {(title || headerRight) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            padding: "12px 16px",
            background: "var(--ui-surface-muted)",
            borderBottom: "1px solid var(--ui-border)",
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "var(--ui-text)", lineHeight: 1.3 }}>{title}</h3>
            {description ? <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ui-muted)", lineHeight: 1.5 }}>{description}</p> : null}
          </div>
          {headerRight ? <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>{headerRight}</div> : null}
        </div>
      )}
      <div style={{ padding: 16, ...bodyStyle }}>{children}</div>
    </section>
  );
}
