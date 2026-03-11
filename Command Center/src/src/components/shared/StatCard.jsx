import React from "react";
import Pulse from "./Pulse";

export default function StatCard({ value, label, accent, pulse }) {
  return (
    <div style={{
      background: "#111827", borderRadius: 10, padding: "20px 24px",
      border: "1px solid #1f2937", position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: accent || "#3b82f6" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.03em" }}>{value}</div>
        {pulse && <Pulse color={accent || "#3b82f6"} />}
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginTop: 4, fontWeight: 500 }}>{label}</div>
    </div>
  );
}
