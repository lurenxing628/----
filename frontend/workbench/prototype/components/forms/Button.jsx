import React from "react";

/**
 * APS Button — mirrors the product's .btn contract.
 * Flat, 36px tall (sm 30px), 6px radius, 1px border, subtle shadow that
 * deepens on hover; press nudges down 1px. One filled `primary` per view.
 */
export function Button({
  variant = "secondary",
  size = "md",
  disabled = false,
  type = "button",
  leadingIcon = null,
  children,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);

  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.375rem",
    minHeight: size === "sm" ? 30 : 36,
    padding: size === "sm" ? "0.25rem 0.6rem" : "0.5rem 0.95rem",
    border: "1px solid transparent",
    borderRadius: "var(--ui-radius)",
    fontFamily: "var(--font-family)",
    fontSize: size === "sm" ? "0.75rem" : "0.875rem",
    fontWeight: 500,
    lineHeight: 1.2,
    whiteSpace: "nowrap",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background-color .15s, color .15s, border-color .15s, box-shadow .15s, transform .12s",
    transform: active && !disabled ? "translateY(1px)" : "none",
    opacity: disabled ? 0.6 : 1,
  };

  const variants = {
    primary: {
      background: hover && !disabled ? "var(--ui-primary-hover)" : "var(--ui-primary)",
      borderColor: hover && !disabled ? "var(--ui-primary-hover)" : "var(--ui-primary)",
      color: "#fff",
      boxShadow: disabled ? "none" : hover ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)",
    },
    secondary: {
      background: hover && !disabled ? "var(--ui-surface-muted)" : "var(--ui-card-bg)",
      borderColor: hover && !disabled ? "#cbd5e1" : "var(--ui-border)",
      color: "var(--ui-text)",
      boxShadow: disabled ? "none" : hover ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)",
    },
    success: {
      background: "var(--ui-success)", borderColor: "var(--ui-success)", color: "#fff",
      filter: hover && !disabled ? "brightness(0.95)" : "none",
      boxShadow: disabled ? "none" : "var(--ui-shadow-sm)",
    },
    danger: {
      background: "var(--ui-danger)", borderColor: "var(--ui-danger)", color: "#fff",
      filter: hover && !disabled ? "brightness(0.95)" : "none",
      boxShadow: disabled ? "none" : "var(--ui-shadow-sm)",
    },
    ghost: {
      background: hover && !disabled ? "var(--ui-surface-muted)" : "transparent",
      borderColor: hover && !disabled ? "var(--ui-border)" : "transparent",
      color: hover && !disabled ? "var(--ui-text)" : "var(--ui-muted)",
      boxShadow: "none",
    },
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setActive(false); }}
      onMouseDown={() => setActive(true)}
      onMouseUp={() => setActive(false)}
      style={{ ...base, ...variants[variant], ...style }}
      {...rest}
    >
      {leadingIcon ? <span aria-hidden="true" style={{ display: "inline-flex" }}>{leadingIcon}</span> : null}
      {children}
    </button>
  );
}
