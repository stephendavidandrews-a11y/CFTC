import React from "react";

export default function Badge({ bg, text, label }) {
  return (
    <span style={{
      display: "inline-block", padding: "3px 10px", borderRadius: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
      background: bg, color: text, border: `1px solid ${text}22`,
    }}>{label}</span>
  );
}
