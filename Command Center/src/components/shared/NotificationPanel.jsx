import React, { useState, useEffect, useRef } from "react";
import theme from "../../styles/theme";
import { useApi } from "../../hooks/useApi";
import { getNotifications, markNotificationRead } from "../../api/pipeline";

const SEVERITY_ICONS = {
  info: { icon: "i", bg: "#172554", color: theme.accent.blueLight },
  warning: { icon: "!", bg: "#422006", color: theme.accent.yellowLight },
  error: { icon: "×", bg: "#450a0a", color: theme.accent.redLight },
  success: { icon: "✓", bg: "#14532d", color: theme.accent.greenLight },
};

export default function NotificationPanel({ isOpen, onClose, onCountChange }) {
  const panelRef = useRef(null);
  const [markingRead, setMarkingRead] = useState({});
  const { data: notifications, refetch } = useApi(
    () => (isOpen ? getNotifications() : Promise.resolve([])),
    [isOpen]
  );

  const items = notifications || [];

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  const handleMarkRead = async (id) => {
    setMarkingRead((prev) => ({ ...prev, [id]: true }));
    try {
      await markNotificationRead(id);
      refetch();
      if (onCountChange) onCountChange();
    } catch { /* ignore */ }
    setMarkingRead((prev) => ({ ...prev, [id]: false }));
  };

  const handleMarkAllRead = async () => {
    const unread = items.filter((n) => !n.is_read);
    for (const n of unread) {
      try { await markNotificationRead(n.id); } catch { /* ignore */ }
    }
    refetch();
    if (onCountChange) onCountChange();
  };

  if (!isOpen) return null;

  const unreadCount = items.filter((n) => !n.is_read).length;

  return (
    <div
      ref={panelRef}
      style={{
        position: "absolute", top: "100%", right: 0, marginTop: 8,
        width: 380, maxHeight: 480, overflowY: "auto",
        background: "#111827", borderRadius: 10,
        border: `1px solid ${theme.border.default}`,
        boxShadow: "0 16px 48px rgba(0,0,0,0.5)",
        zIndex: 1100,
      }}
    >
      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "14px 16px", borderBottom: `1px solid ${theme.border.default}`,
      }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary }}>
          Notifications {unreadCount > 0 && `(${unreadCount})`}
        </span>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllRead}
            style={{
              background: "transparent", border: "none", color: theme.accent.blueLight,
              fontSize: 11, fontWeight: 600, cursor: "pointer",
            }}
          >Mark all read</button>
        )}
      </div>

      {/* List */}
      {items.length === 0 ? (
        <div style={{ padding: "30px 16px", textAlign: "center", color: theme.text.faint, fontSize: 12 }}>
          No notifications
        </div>
      ) : (
        items.slice(0, 50).map((n) => {
          const sev = SEVERITY_ICONS[n.severity] || SEVERITY_ICONS.info;
          return (
            <div
              key={n.id}
              onClick={() => !n.is_read && handleMarkRead(n.id)}
              style={{
                display: "flex", gap: 12, padding: "12px 16px",
                borderBottom: `1px solid ${theme.border.subtle}`,
                background: n.is_read ? "transparent" : "rgba(59,130,246,0.04)",
                cursor: n.is_read ? "default" : "pointer",
                opacity: markingRead[n.id] ? 0.5 : 1,
              }}
            >
              <div style={{
                width: 26, height: 26, borderRadius: 6, flexShrink: 0,
                background: sev.bg, color: sev.color,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 700,
              }}>{sev.icon}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 12, color: n.is_read ? theme.text.dim : theme.text.secondary,
                  fontWeight: n.is_read ? 400 : 500, lineHeight: 1.4,
                }}>{n.message}</div>
                <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 3 }}>
                  {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                </div>
              </div>
              {!n.is_read && (
                <div style={{
                  width: 8, height: 8, borderRadius: "50%", background: theme.accent.blue,
                  flexShrink: 0, marginTop: 4,
                }} />
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
