import React from "react";

const THEME = {
  bg: "#111827",
  border: "#1f2937",
  text: "#f1f5f9",
  dim: "#64748b",
  overlay: "rgba(0,0,0,0.45)",
};

export default function DrawerShell({ isOpen, onClose, title, width = 520, children }) {
  // Close on Escape
  React.useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: THEME.overlay,
          zIndex: 500,
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? "auto" : "none",
          transition: "opacity 0.25s ease",
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width,
          maxWidth: "100vw",
          background: THEME.bg,
          borderLeft: `1px solid ${THEME.border}`,
          zIndex: 501,
          display: "flex",
          flexDirection: "column",
          transform: isOpen ? "translateX(0)" : `translateX(${width + 2}px)`,
          transition: "transform 0.28s cubic-bezier(.4,0,.2,1)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: `1px solid ${THEME.border}`,
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 700, color: THEME.text }}>{title}</span>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: THEME.dim,
              fontSize: 20,
              cursor: "pointer",
              padding: "2px 6px",
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            &#x2715;
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {children}
        </div>
      </div>
    </>
  );
}
