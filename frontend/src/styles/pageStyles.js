import theme from "./theme";

/** Shared page-level style constants used across list pages. */

export const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };

export const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 20 };

export const inputStyle = {
  background: theme.bg.input,
  border: `1px solid ${theme.border.default}`,
  borderRadius: 6,
  padding: "7px 12px",
  fontSize: 13,
  color: theme.text.secondary,
  outline: "none",
  minWidth: 140,
};

export const btnPrimary = {
  padding: "8px 18px",
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 600,
  background: theme.accent.blue,
  color: "#fff",
  border: "none",
  cursor: "pointer",
};

export const btnDanger = {
  ...btnPrimary,
  background: theme.accent.red,
};

export const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};
