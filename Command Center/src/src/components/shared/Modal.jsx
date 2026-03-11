import React from "react";

export default function Modal({ isOpen, onClose, title, children, width = 560 }) {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.7)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#111827", borderRadius: 12,
          border: "1px solid #1f2937",
          width, maxHeight: "85vh", overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "18px 24px", borderBottom: "1px solid #1f2937",
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: "transparent", border: "none", color: "#64748b",
              fontSize: 18, cursor: "pointer", padding: 4,
            }}
          >x</button>
        </div>
        <div style={{ padding: 24 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
