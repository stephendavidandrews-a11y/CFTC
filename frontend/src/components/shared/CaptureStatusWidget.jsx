/**
 * Compact capture status widget for the dashboard.
 * Shows live ReSpeaker Pi state: recording/idle/offline/error,
 * audio level, Wi-Fi, and key health metrics.
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";

const STATE_COLORS = {
  recording: { bg: "#052e16", text: "#22c55e", label: "Recording" },
  idle:      { bg: "#172554", text: "#3b82f6", label: "Idle" },
  offline:   { bg: "#1c1917", text: "#78716c", label: "Offline" },
  error:     { bg: "#450a0a", text: "#ef4444", label: "Error" },
};

function formatAge(receivedAt) {
  if (!receivedAt) return "—";
  const age = (Date.now() - new Date(receivedAt).getTime()) / 1000;
  if (age < 60) return `${Math.round(age)}s ago`;
  if (age < 3600) return `${Math.round(age / 60)}m ago`;
  return `${Math.round(age / 3600)}h ago`;
}

function signalBars(rssi) {
  if (rssi == null) return "—";
  if (rssi >= -50) return "████ Excellent";
  if (rssi >= -60) return "███░ Good";
  if (rssi >= -70) return "██░░ Fair";
  return "█░░░ Weak";
}

function audioBar(db) {
  if (db == null || db <= -100) return null;
  // Map -80dB..0dB to 0..100%
  const pct = Math.max(0, Math.min(100, ((db + 80) / 80) * 100));
  const color = db > -30 ? theme.accent.green : db > -50 ? theme.accent.yellow : theme.text.faint;
  return { pct, color };
}

export default function CaptureStatusWidget({ status, connected }) {
  const navigate = useNavigate();
  const state = status?.state || "offline";
  const sc = STATE_COLORS[state] || STATE_COLORS.offline;

  const bar = audioBar(status?.audio_level_db);

  return (
    <div
      onClick={() => navigate("/capture")}
      style={{
        background: theme.bg.card,
        borderRadius: 10,
        border: `1px solid ${theme.border.default}`,
        padding: "16px 20px",
        cursor: "pointer",
        position: "relative",
        overflow: "hidden",
        transition: "border-color 0.2s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = theme.accent.blue)}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = theme.border.default)}
    >
      {/* Left accent bar */}
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: sc.text }} />

      {/* Header: state + WS indicator */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Pulsing dot for recording */}
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: sc.text,
            animation: state === "recording" ? "pulse 2s infinite" : "none",
            boxShadow: state === "recording" ? `0 0 6px ${sc.text}` : "none",
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: sc.text }}>{sc.label}</span>
        </div>
        <span style={{
          fontSize: 10, color: connected ? theme.text.faint : theme.accent.yellow,
          fontWeight: 500,
        }}>
          {connected ? "Live" : "Reconnecting…"}
        </span>
      </div>

      {/* Audio level bar */}
      {bar && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 10, color: theme.text.faint, marginBottom: 3 }}>Audio</div>
          <div style={{
            height: 4, borderRadius: 2, background: theme.bg.input,
            overflow: "hidden",
          }}>
            <div style={{
              height: "100%", width: `${bar.pct}%`,
              background: bar.color, borderRadius: 2,
              transition: "width 0.3s ease",
            }} />
          </div>
          <div style={{ fontSize: 9, color: theme.text.ghost, marginTop: 2 }}>
            {status.audio_level_db?.toFixed(1)} dB
          </div>
        </div>
      )}

      {/* Metrics row */}
      <div style={{ display: "flex", gap: 16, fontSize: 11, color: theme.text.muted }}>
        <div>
          <span style={{ color: theme.text.faint }}>WiFi </span>
          {status?.wifi_rssi != null ? `${status.wifi_rssi} dBm` : "—"}
        </div>
        <div>
          <span style={{ color: theme.text.faint }}>CPU </span>
          {status?.cpu_temp_c != null ? `${status.cpu_temp_c.toFixed(0)}°C` : "—"}
        </div>
        <div>
          <span style={{ color: theme.text.faint }}>Disk </span>
          {status?.disk_used_pct != null ? `${status.disk_used_pct.toFixed(0)}%` : "—"}
        </div>
      </div>

      {/* Last heartbeat age */}
      <div style={{ fontSize: 10, color: theme.text.ghost, marginTop: 8 }}>
        Last heartbeat: {formatAge(status?.received_at)}
        {status?.silence_seconds > 0 && state !== "offline" && (
          <span> · silence {status.silence_seconds}s</span>
        )}
      </div>

      {/* CSS animation for recording pulse */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
