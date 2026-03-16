import React, { useState } from "react";
import theme from "../../styles/theme";

function KanbanCard({ item, onClick, accentColor }) {
  const [hovered, setHovered] = useState(false);
  const severity = item.deadline_severity;
  const deadlineColor = severity ? theme.deadline[severity] || "#334155" : null;

  return (
    <div
      style={{
        background: theme.bg.cardHover, borderRadius: 8,
        border: `1px solid ${hovered ? (accentColor || theme.border.active) : theme.border.subtle}`,
        padding: 14, marginBottom: 8, cursor: "pointer",
        transition: "border-color 0.15s",
      }}
      onClick={() => onClick && onClick(item)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div style={{ fontWeight: 600, fontSize: 12, color: theme.text.secondary, marginBottom: 4 }}>
        {item.short_title || item.title}
      </div>
      {item.docket_number && (
        <div style={{ fontSize: 10, color: theme.text.faint, fontFamily: theme.font.mono }}>
          {item.docket_number}
        </div>
      )}
      {(item.fr_citation || item.fr_url) && (
        <div style={{ fontSize: 10, marginTop: 2 }}>
          {item.fr_url ? (
            <a
              href={item.fr_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ color: theme.accent.blueLight, textDecoration: "none", fontFamily: theme.font.mono }}
              onMouseEnter={(e) => (e.target.style.textDecoration = "underline")}
              onMouseLeave={(e) => (e.target.style.textDecoration = "none")}
            >{item.fr_citation || "FR ↗"}</a>
          ) : (
            <span style={{ color: theme.text.faint, fontFamily: theme.font.mono }}>{item.fr_citation}</span>
          )}
        </div>
      )}
      <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        {item.priority_label && item.priority_label !== "medium" && (
          <span style={{
            padding: "2px 7px", borderRadius: 4, fontSize: 9, fontWeight: 600,
            background: (theme.priority[item.priority_label] || {}).bg || "#1f2937",
            color: (theme.priority[item.priority_label] || {}).text || "#9ca3af",
          }}>
            {item.priority_label}
          </span>
        )}
        {item.lead_attorney_name && (
          <span style={{ fontSize: 10, color: theme.text.dim }}>
            {item.lead_attorney_name.split(" ").map(n => n[0]).join("")}
          </span>
        )}
        {item.chairman_priority && (
          <span style={{ fontSize: 9, color: theme.accent.yellow }}>CHAIR</span>
        )}
      </div>
      {item.next_deadline_date && (
        <div style={{
          fontSize: 10, color: deadlineColor || theme.text.dim, marginTop: 6,
          fontWeight: severity === "overdue" || severity === "critical" ? 600 : 400,
        }}>
          {severity === "overdue" ? "OVERDUE" : `Due ${item.next_deadline_date}`}
        </div>
      )}
    </div>
  );
}

export default function KanbanBoard({ columns, onCardClick }) {
  return (
    <div style={{ display: "flex", gap: 14, overflowX: "auto" }}>
      {columns.map((col) => (
        <div key={col.stage_key} style={{ flex: 1, minWidth: 200 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 12,
            paddingBottom: 10, borderBottom: `2px solid ${col.stage_color || "#6b7280"}`,
          }}>
            <span style={{ fontWeight: 700, fontSize: 12, color: col.stage_color || "#9ca3af" }}>
              {col.stage_label}
            </span>
            <span style={{
              background: `${col.stage_color || "#6b7280"}20`,
              color: col.stage_color || "#9ca3af",
              borderRadius: "50%", width: 20, height: 20,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700,
            }}>
              {col.count}
            </span>
          </div>
          {col.items.map((item) => (
            <KanbanCard
              key={item.id}
              item={item}
              onClick={onCardClick}
              accentColor={col.stage_color}
            />
          ))}
          {col.count === 0 && (
            <div style={{
              padding: 20, textAlign: "center", fontSize: 11,
              color: theme.text.ghost, fontStyle: "italic",
            }}>
              No items
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
