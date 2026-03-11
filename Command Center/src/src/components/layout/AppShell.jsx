import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import theme from "../../styles/theme";
import { useApi } from "../../hooks/useApi";
import { getExecutiveSummary } from "../../api/pipeline";

export default function AppShell() {
  const { data: summary } = useApi(() => getExecutiveSummary(), []);

  const badgeCounts = {};
  if (summary) {
    if (summary.active_rulemakings) badgeCounts["/pipeline"] = summary.active_rulemakings;
    if (summary.active_reg_actions) badgeCounts["/regulatory"] = summary.active_reg_actions;
    if (summary.total_overdue_deadlines) badgeCounts["/eo"] = summary.total_overdue_deadlines;
  }

  return (
    <div style={{
      display: "flex", height: "100vh", overflow: "hidden",
      fontFamily: theme.font.family, background: theme.bg.app, color: theme.text.secondary,
    }}>
      <Sidebar badgeCounts={badgeCounts} />
      <main style={{ flex: 1, overflow: "auto", padding: "28px 36px" }}>
        <Outlet />
      </main>
    </div>
  );
}
