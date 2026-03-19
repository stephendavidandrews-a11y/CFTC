import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import theme from "../../styles/theme";

const SECTIONS = [
  // -- Operations --
  { separator: true, label: "Operations" },
  { path: "/", label: "Dashboard", icon: "\u25eb" },
  { path: "/matters", label: "Matters", icon: "\u25a4" },
  { path: "/people", label: "People", icon: "\u22a1" },
  { path: "/organizations", label: "Organizations", icon: "\u2b21" },
  { path: "/tasks", label: "Tasks", icon: "\u2611" },
  { path: "/team-workload", label: "Team Workload", icon: "\u2630" },
  { path: "/meetings", label: "Meetings", icon: "\u229e" },
  { path: "/decisions", label: "Decisions", icon: "\u2696" },
  { path: "/documents", label: "Documents", icon: "\u2b1a" },

  // -- AI Review --
  { separator: true, label: "AI Review" },
  { path: "/review/communications", label: "Communications", icon: "◎" },
  { path: "/review/speakers", label: "Speaker Review", icon: "\u25ce" },
  { path: "/review/entities", label: "Entity Review", icon: "\u22a1" },
  { path: "/review/bundles", label: "Bundle Review", icon: "\u25a4" },
  { path: "/review/commit", label: "Ready to Commit", icon: "\u2611" },

  // -- Intelligence --
  { separator: true, label: "Intelligence" },
  { path: "/intelligence/digests", label: "Digests", icon: "\u25eb" },
  { path: "/intelligence/briefs", label: "Briefs", icon: "\u229e" },

  // -- Settings --
  { separator: true, label: "Settings" },
  { path: "/settings/ai", label: "AI Configuration", icon: "\u2699" },

  // -- Tools --
  { separator: true, label: "Tools" },
  { path: "https://cftctools.stephenandrews.org", label: "CFTC Tools", icon: "\u2b21", external: true },

  // -- Developer --
  { separator: true, label: "Developer" },
  { path: "/developer", label: "Dev Console", icon: "\u2699" },
];

export default function Sidebar({ isMobile = false, onNavigate }) {
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
      borderRight: "1px solid " + theme.border.subtle,
      display: "flex", flexDirection: "column", flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "22px 18px 18px", borderBottom: "1px solid " + theme.border.subtle }}>
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
            <div style={{ fontSize: 10, color: theme.text.faint }}>CFTC &middot; Office of GC</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ padding: "10px 8px", flex: 1, overflowY: "auto" }}>
        {SECTIONS.map((s, idx) => {
          if (s.separator) {
            return (
              <div key={"sep-" + idx} style={{ margin: "8px 12px" }}>
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

          const isActive = s.path.includes("?")
            ? (location.pathname + location.search) === s.path
            : location.pathname === s.path ||
              (s.path !== "/" && location.pathname.startsWith(s.path));

          const handleItemClick = s.external
            ? () => { window.open(s.path, "_blank"); }
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
              {s.external && (
                <span style={{ fontSize: 10, color: theme.text.faint, opacity: 0.6 }}>&nearr;</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* User */}
      <div style={{ padding: "14px 16px", borderTop: "1px solid " + theme.border.subtle, fontSize: 11 }}>
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
