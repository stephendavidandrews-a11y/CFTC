import React, { useState, useCallback } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import theme from "../../styles/theme";
import useMediaQuery from "../../hooks/useMediaQuery";
import { DrawerProvider, useDrawer } from "../../contexts/DrawerContext";
import { OwnerProvider } from "../../contexts/OwnerContext";
import MatterDrawer from "../tracker/MatterDrawer";
import TaskDrawer from "../tracker/TaskDrawer";
import PersonDrawer from "../tracker/PersonDrawer";
import MeetingDrawer from "../tracker/MeetingDrawer";
import OrganizationDrawer from "../tracker/OrganizationDrawer";
import DecisionDrawer from "../tracker/DecisionDrawer";
import DocumentDrawer from "../tracker/DocumentDrawer";

function DrawerRenderer() {
  const { drawer, closeDrawer } = useDrawer();

  const handleSaved = () => {
    if (drawer.onSaved) drawer.onSaved();
  };

  const type = drawer.type;
  const data = drawer.data;

  return (
    <>
      <MatterDrawer
        isOpen={type === "matter"}
        onClose={closeDrawer}
        matter={type === "matter" && data?.id ? data : null}
        onSaved={handleSaved}
      />
      <TaskDrawer
        isOpen={type === "task"}
        onClose={closeDrawer}
        task={type === "task" && data?.id ? data : null}
        matterId={type === "task" && data?.matter_id && !data?.id ? data.matter_id : null}
        onSaved={handleSaved}
      />
      <PersonDrawer
        isOpen={type === "person"}
        onClose={closeDrawer}
        person={type === "person" && data?.id ? data : null}
        onSaved={handleSaved}
      />
      <MeetingDrawer
        isOpen={type === "meeting"}
        onClose={closeDrawer}
        meeting={type === "meeting" && data?.id ? data : null}
        onSaved={handleSaved}
      />
      <OrganizationDrawer
        isOpen={type === "organization"}
        onClose={closeDrawer}
        organization={type === "organization" && data?.id ? data : null}
        onSaved={handleSaved}
      />
      <DecisionDrawer
        isOpen={type === "decision"}
        onClose={closeDrawer}
        decision={type === "decision" && data?.id ? data : null}
        matterId={type === "decision" && data?.matter_id && !data?.id ? data.matter_id : null}
        onSaved={handleSaved}
      />
      <DocumentDrawer
        isOpen={type === "document"}
        onClose={closeDrawer}
        document={type === "document" && data?.id ? data : null}
        matterId={type === "document" && data?.matter_id && !data?.id ? data.matter_id : null}
        onSaved={handleSaved}
      />
    </>
  );
}

export default function AppShell() {
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const handleNavigation = useCallback(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  React.useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [location.pathname, isMobile]);

  return (
    <OwnerProvider>
    <DrawerProvider>
      <div style={{
        display: "flex", height: "100vh", overflow: "hidden",
        fontFamily: theme.font.family, background: theme.bg.app, color: theme.text.secondary,
      }}>
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
            isMobile={isMobile}
            onNavigate={handleNavigation}
          />
        </div>

        <main style={{
          flex: 1,
          overflow: "auto",
          padding: isMobile ? "68px 16px 24px" : "28px 36px",
        }}>
          <Outlet />
        </main>

        <DrawerRenderer />
      </div>
    </DrawerProvider>
    </OwnerProvider>
  );
}
