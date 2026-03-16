import React from "react";

export default function Pulse({ color }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 8, height: 8 }}>
      <span style={{
        position: "absolute", inset: 0, borderRadius: "50%", background: color,
        opacity: 0.4, animation: "pulse 2s ease-in-out infinite",
      }} />
      <span style={{
        position: "relative", width: 8, height: 8, borderRadius: "50%", background: color,
      }} />
    </span>
  );
}
