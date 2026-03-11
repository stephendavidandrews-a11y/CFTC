import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Pulse from "../shared/Pulse";
import theme from "../../styles/theme";

const SECTIONS = [
  { path: "/", label: "Executive Summary", icon: "\u25eb" },
  { path: "/eo", label: "EO Tracker", icon: "\u2691" },
  { path: "/team", label: "Team", icon: "\u22a1" },
  { path: "/pipeline", label: "Pipeline", icon: "\u25a4" },
  { path: "/regulatory", label: "Reg Actions", icon: "\u25c7" },
  { path: "/work", label: "Work Mgmt", icon: "\u2630" },
  { path: "/work/tasks", label: "My Tasks", icon: "\u2611" },
  { path: "/interagency", label: "Interagency", icon: "\u2b21" },
  { path: "/research", label: "Research", icon: "\u229e" },
  { path: "/comments", label: "Comments", icon: "\u2709" },
  { path: "/intelligence", label: "Intelligence", icon: "\u25c9" },
  { path: "/reports", label: "Reports", icon: "\u229f" },
  { separator: true },
  { path: "/loper", label: "Loper Bright", icon: "\u2696" },
  { separator: true, label: "Personal" },
  { path: "/network/", label: "Network", icon: "\u{1F310}", external: true },
];

export default function Sidebar({ badgeCounts = {}, isMobile = false, onNavigate }) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleClick = (path) => {
    navigate(path);
    if (onNavigate) onNavigate();
  };

  return (
    <aside style={{
      width: isMobile ? 270 : theme.sidebar.width,
      height: "100%",
      background: theme.bg.sidebar,
      borderRight: `1px solid ${theme.border.subtle}`,
      display: "flex", flexDirection: "column", flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "22px 18px 18px", borderBottom: `1px solid ${theme.border.subtle}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #1e3a5f, #3b82f6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 700, color: "#fff",
          }}>C</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, letterSpacing: "-0.01em" }}>
              Command Center
            </div>
            <div style={{ fontSize: 10, color: theme.text.faint }}>CFTC · Office of GC</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ padding: "10px 8px", flex: 1, overflowY: "auto" }}>
        {SECTIONS.map((s, idx) => {
          if (s.separator) {
            return (
              <div key={`sep-${idx}`} style={{ margin: "8px 12px" }}>
                <div style={{ height: 1, background: theme.border.subtle }} />
                {s.label && (
                  <div style={{
                    fontSize: 9, fontWeight: 700, color: theme.text.faint,
                    textTransform: "uppercase", letterSpacing: "0.08em",
                    marginTop: 10, marginBottom: 2, paddingLeft: 4,
                  }}>{s.label}</div>
                )}
              </div>
            );
          }
          const isActive = location.pathname === s.path ||
            (s.path !== "/" && location.pathname.startsWith(s.path));

          const handleItemClick = s.external
            ? () => { window.location.href = s.path; }
            : () => handleClick(s.path);

          return (
            <button
              key={s.path}
              onClick={handleItemClick}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                width: "100%", padding: "9px 12px", borderRadius: 8,
                background: isActive ? "rgba(59,130,246,0.12)" : "transparent",
                color: isActive ? theme.accent.blueLight : theme.text.dim,
                border: isActive ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
                cursor: "pointer", fontSize: 13,
                fontWeight: isActive ? 600 : 500, marginBottom: 2,
                transition: "all 0.15s ease", textAlign: "left",
              }}
            >
              <span style={{ fontSize: 14, width: 20, textAlign: "center" }}>{s.icon}</span>
              <span style={{ flex: 1 }}>{s.label}</span>
              {badgeCounts[s.path] && (
                <span style={{
                  background: s.path === "/eo" ? "#7f1d1d" : "#172554",
                  color: s.path === "/eo" ? "#fca5a5" : theme.accent.blueLight,
                  borderRadius: 10, padding: "1px 7px", fontSize: 9, fontWeight: 700,
                }}>{badgeCounts[s.path]}</span>
              )}
              {s.path === "/intelligence" && <Pulse color={theme.accent.green} />}
            </button>
          );
        })}
      </nav>

      {/* User */}
      <div style={{ padding: "14px 16px", borderTop: `1px solid ${theme.border.subtle}`, fontSize: 11 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: "linear-gradient(135deg, #1e3a5f, #2563eb)",
            color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, fontWeight: 700,
          }}>SA</div>
          <div>
            <div style={{ color: theme.text.secondary, fontWeight: 600, fontSize: 12 }}>S. Andrews</div>
            <div style={{ color: theme.text.faint, fontSize: 10 }}>Deputy GC, Regulation</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
