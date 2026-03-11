import React, { useState } from "react";
import theme from "../../styles/theme";

export default function QuickAdd({ placeholder = "+ Add item...", onAdd }) {
  const [value, setValue] = useState("");
  const [active, setActive] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      onAdd(trimmed);
      setValue("");
    }
  };

  if (!active) {
    return (
      <button
        onClick={() => setActive(true)}
        style={{
          background: "transparent", border: "1px dashed #1f2937",
          borderRadius: 6, padding: "6px 12px", color: theme.text.faint,
          fontSize: 12, cursor: "pointer", width: "100%", textAlign: "left",
          transition: "all 0.15s",
        }}
        onMouseEnter={(e) => { e.target.style.borderColor = theme.accent.blue; e.target.style.color = theme.text.dim; }}
        onMouseLeave={(e) => { e.target.style.borderColor = "#1f2937"; e.target.style.color = theme.text.faint; }}
      >
        {placeholder}
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", gap: 6 }}>
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => { if (!value.trim()) setActive(false); }}
        onKeyDown={(e) => { if (e.key === "Escape") { setValue(""); setActive(false); } }}
        placeholder="Title, then Enter"
        style={{
          flex: 1, background: theme.bg.input, border: `1px solid ${theme.border.active}`,
          borderRadius: 6, padding: "6px 10px", color: theme.text.primary,
          fontSize: 12, outline: "none",
        }}
      />
      <button
        type="submit"
        style={{
          background: theme.accent.blue, border: "none", borderRadius: 6,
          padding: "6px 12px", color: "#fff", fontSize: 11, fontWeight: 600,
          cursor: "pointer",
        }}
      >Add</button>
    </form>
  );
}
