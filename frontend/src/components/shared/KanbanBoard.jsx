import React, { useState } from "react";
import theme from "../../styles/theme";

function KanbanCard({ item, onClick, accentColor }) {
  const [hover, setHover] = useState(false);

  const deadlineColor = !item.deadline ? null
    : item.deadlineSeverity === "overdue" ? theme.accent.red
    : item.deadlineSeverity === "critical" ? theme.accent.red
    : item.deadlineSeverity === "warning" ? theme.accent.yellow
    : theme.text.faint;

  return (
    <div
      onClick={() => onClick && onClick(item)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: theme.bg.card,
        border: `1px solid ${hover ? (accentColor || theme.accent.blue) : theme.border.default}`,
        borderRadius: 8,
        padding: "12px 14px",
        cursor: "pointer",
        transition: "border-color 0.15s",
        marginBottom: 8,
      }}
    >
      {/* Type badge + priority dot */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        {item.typeBadge && (
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em",
            padding: "2px 6px", borderRadius: 3,
            background: "rgba(167,139,250,0.15)", color: theme.accent.purple,
          }}>
            {item.typeBadge}
          </span>
        )}
        {item.priority && (() => {
          const pColor = item.priority === "critical this week" ? theme.accent.red
            : item.priority === "important this month" ? theme.accent.yellow
            : theme.text.faint;
          return <span style={{ width: 6, height: 6, borderRadius: "50%", background: pColor, flexShrink: 0 }} />;
        })()}
      </div>

      {/* Title (2-line clamp) */}
      <div style={{
        fontSize: 13, fontWeight: 500, color: theme.text.primary, lineHeight: 1.3,
        display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
        overflow: "hidden", marginBottom: 6,
      }}>
        {item.title}
      </div>

      {/* RIN + Matter # */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        {item.rin && (
          <span style={{ fontSize: 10, color: theme.accent.purple, fontFamily: theme.font.mono, fontWeight: 600 }}>
            {item.rin}
          </span>
        )}
        {item.matterNumber && (
          <span style={{ fontSize: 10, color: theme.text.dim }}>
            {item.matterNumber}
          </span>
        )}
      </div>

      {/* Footer: owner + deadline */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
        {item.ownerInitials && (
          <span style={{
            fontSize: 10, fontWeight: 700, color: theme.text.muted,
            background: theme.bg.input, padding: "2px 6px", borderRadius: 4,
          }}>
            {item.ownerInitials}
          </span>
        )}
        {item.deadline && (
          <span style={{ fontSize: 10, fontWeight: 600, color: deadlineColor }}>
            {item.deadline}
          </span>
        )}
      </div>
    </div>
  );
}


export default function KanbanBoard({ columns, onCardClick }) {
  return (
    <div style={{
      display: "flex",
      gap: 12,
      overflowX: "auto",
      paddingBottom: 8,
    }}>
      {columns.map((col) => (
        <div key={col.key} style={{ minWidth: 260, maxWidth: 280, flex: "0 0 260px" }}>
          {/* Column header */}
          <div style={{
            borderTop: `3px solid ${col.color}`,
            background: theme.bg.card,
            borderRadius: "8px 8px 0 0",
            padding: "10px 14px",
            marginBottom: 8,
            border: `1px solid ${theme.border.default}`,
            borderTopColor: col.color,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: theme.text.secondary }}>
                {col.label}
              </span>
              <span style={{
                fontSize: 11, fontWeight: 600, color: col.color,
                background: `${col.color}20`,
                padding: "1px 8px", borderRadius: 10,
              }}>
                {col.items.length}
              </span>
            </div>
          </div>

          {/* Cards */}
          <div style={{ minHeight: 60 }}>
            {col.items.length === 0 ? (
              <div style={{
                padding: "20px 14px", textAlign: "center",
                fontSize: 11, color: theme.text.ghost,
                border: `1px dashed ${theme.border.subtle}`,
                borderRadius: 8,
              }}>
                No items
              </div>
            ) : (
              col.items.map((item) => (
                <KanbanCard
                  key={item.id}
                  item={item}
                  onClick={onCardClick}
                  accentColor={col.color}
                />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
