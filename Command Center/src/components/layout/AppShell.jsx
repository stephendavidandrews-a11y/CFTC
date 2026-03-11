import React, { useState, useCallback } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import theme from "../../styles/theme";
import { useApi } from "../../hooks/useApi";
import { getExecutiveSummary } from "../../api/pipeline";
import useMediaQuery from "../../hooks/useMediaQuery";

export default function AppShell() {
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const { data: summary } = useApi(() => getExecutiveSummary(), []);

  const badgeCounts = {};
  if (summary) {
    if (summary.active_rulemakings) badgeCounts["/pipeline"] = summary.active_rulemakings;
    if (summary.active_reg_actions) badgeCounts["/regulatory"] = summary.active_reg_actions;
    if (summary.total_overdue_deadlines) badgeCounts["/eo"] = summary.total_overdue_deadlines;
  }

  // Close sidebar on navigation (mobile)
  const handleNavigation = useCallback(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  // Close sidebar when route changes
  React.useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [location.pathname, isMobile]);

  return (
    <div style={{
      display: "flex", height: "100vh", overflow: "hidden",
      fontFamily: theme.font.family, background: theme.bg.app, color: theme.text.secondary,
    }}>
      {/* Mobile top bar */}
      {isMobile && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
          height: 52,
          background: theme.bg.sidebar,
          borderBottom: `1px solid ${theme.border.subtle}`,
          display: "flex", alignItems: "center", padding: "0 16px",
          gap: 12,
        }}>
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: theme.text.secondary, fontSize: 22, padding: "4px 6px",
              lineHeight: 1,
            }}
            aria-label="Toggle menu"
          >
            {sidebarOpen ? "\u2715" : "\u2630"}
          </button>
          <div style={{
            width: 26, height: 26, borderRadius: 6,
            background: "linear-gradient(135deg, #1e3a5f, #3b82f6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, fontWeight: 700, color: "#fff",
          }}>C</div>
          <span style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary }}>
            Command Center
          </span>
        </div>
      )}

      {/* Overlay backdrop (mobile only) */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: "fixed", inset: 0, zIndex: 199,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(2px)",
          }}
        />
      )}

      {/* Sidebar — on mobile, fixed slide-out overlay */}
      <div style={{
        ...(isMobile ? {
          position: "fixed",
          top: 0, left: 0, bottom: 0,
          width: 270,
          zIndex: 200,
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)",
          boxShadow: sidebarOpen ? "4px 0 24px rgba(0,0,0,0.5)" : "none",
        } : {}),
      }}>
        <Sidebar
          badgeCounts={badgeCounts}
          isMobile={isMobile}
          onNavigate={handleNavigation}
        />
      </div>

      {/* Main content — more padding on desktop, tight on mobile */}
      <main style={{
        flex: 1,
        overflow: "auto",
        padding: isMobile ? "68px 16px 24px" : "28px 36px",
      }}>
        <Outlet />
      </main>
    </div>
  );
}
