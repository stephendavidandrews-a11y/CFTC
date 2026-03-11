import React from "react";
import theme from "../styles/theme";

export default function CommentsPage() {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 8, letterSpacing: "-0.02em" }}>
        Comment Analyzer
      </h2>
      <p style={{ fontSize: 13, color: theme.text.dim, marginBottom: 24 }}>
        Full comment analysis system — connects to the backend at cftc.stephenandrews.org
      </p>
      <div style={{
        background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
        padding: 60, textAlign: "center",
      }}>
        <div style={{ fontSize: 36, marginBottom: 16, opacity: 0.3 }}>{"\u2709"}</div>
        <div style={{ fontSize: 15, fontWeight: 600, color: theme.text.muted }}>Comment Analyzer Dashboard</div>
        <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 8, maxWidth: 400, margin: "8px auto 0" }}>
          Docket browser · Comment table · AI tiering & summarization · Briefing doc export · PDF downloads
        </div>
        <div style={{
          marginTop: 20, display: "inline-block", padding: "8px 20px", borderRadius: 6,
          background: "#1e3a5f", color: theme.accent.blueLight, fontSize: 12, fontWeight: 600, cursor: "pointer",
        }}>Currently Live →</div>
      </div>
    </div>
  );
}
