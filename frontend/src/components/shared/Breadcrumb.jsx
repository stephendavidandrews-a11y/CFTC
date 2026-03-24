import React from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";

export default function Breadcrumb({ items = [] }) {
  const navigate = useNavigate();

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      marginBottom: 16, fontSize: 13,
    }}>
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <React.Fragment key={i}>
            {i > 0 && <span style={{ color: theme.text.ghost }}>/</span>}
            {isLast ? (
              <span style={{ color: theme.text.muted, fontWeight: 500 }}>{item.label}</span>
            ) : (
              <span
                onClick={() => navigate(item.path)}
                style={{
                  color: theme.text.dim, cursor: "pointer",
                  transition: "color 0.15s",
                }}
                onMouseEnter={(e) => e.target.style.color = theme.accent.blueLight}
                onMouseLeave={(e) => e.target.style.color = theme.text.dim}
              >
                {item.label}
              </span>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
