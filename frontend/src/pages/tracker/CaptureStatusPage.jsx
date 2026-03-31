/**
 * Full capture monitoring page — /capture
 * Shows live ReSpeaker Pi status, 24h timeline, health metrics, and session info.
 */
import React, { useState, useEffect, useMemo } from "react";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, cardStyle } from "../../styles/pageStyles";
import useCaptureStatus from "../../hooks/useCaptureStatus";
import useApi from "../../hooks/useApi";
import { getCaptureTimeline, executeCaptureAction, getCaptureActionLog, getCaptureAlerts } from "../../api/tracker";
import { useToastContext } from "../../contexts/ToastContext";

const STATE_COLORS = {
  recording: { bg: "#052e16", text: "#22c55e", label: "Recording" },
  idle:      { bg: "#172554", text: "#3b82f6", label: "Idle" },
  stopped:   { bg: "#1c1917", text: "#a8a29e", label: "Stopped" },
  offline:   { bg: "#1c1917", text: "#78716c", label: "Offline" },
  error:     { bg: "#450a0a", text: "#ef4444", label: "Error" },
};

function formatAge(ts) {
  if (!ts) return "\u2014";
  const sec = (Date.now() - new Date(ts).getTime()) / 1000;
  if (sec < 60) return Math.round(sec) + "s ago";
  if (sec < 3600) return Math.round(sec / 60) + "m ago";
  return Math.round(sec / 3600) + "h ago";
}

function formatDuration(sec) {
  if (sec == null) return "\u2014";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  if (h > 0) return h + "h " + m + "m";
  if (m > 0) return m + "m " + s + "s";
  return s + "s";
}

function formatUptime(sec) {
  if (sec == null) return "\u2014";
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return d + "d " + h + "h";
  if (h > 0) return h + "h " + m + "m";
  return m + "m";
}

/* -- Timeline bar: 24h horizontal chart -- */
function TimelineBar({ intervals }) {
  if (!intervals || intervals.length === 0) {
    return <div style={{ color: theme.text.faint, fontSize: 12, padding: 12 }}>No timeline data</div>;
  }

  const now = Date.now();
  const span = 24 * 3600 * 1000;
  const start = now - span;

  // Merge adjacent same-state intervals
  const merged = [];
  for (const iv of intervals) {
    const from = Math.max(new Date(iv.from).getTime(), start);
    const to = Math.min(new Date(iv.to).getTime(), now);
    if (to <= from) continue;
    const last = merged[merged.length - 1];
    if (last && last.state === iv.state && Math.abs(from - last.toMs) < 60000) {
      last.toMs = to;
    } else {
      merged.push({ state: iv.state, fromMs: from, toMs: to });
    }
  }

  return (
    <div style={{ position: "relative", height: 32, borderRadius: 6, overflow: "hidden", background: theme.bg.input }}>
      {merged.map((seg, i) => {
        const left = ((seg.fromMs - start) / span) * 100;
        const width = ((seg.toMs - seg.fromMs) / span) * 100;
        const sc = STATE_COLORS[seg.state] || STATE_COLORS.offline;
        return (
          <div
            key={i}
            title={sc.label + ": " + new Date(seg.fromMs).toLocaleTimeString() + " \u2013 " + new Date(seg.toMs).toLocaleTimeString()}
            style={{
              position: "absolute", top: 0, bottom: 0,
              left: left + "%", width: Math.max(width, 0.3) + "%",
              background: sc.text, opacity: 0.7,
            }}
          />
        );
      })}
      {/* Time gridlines */}
      {[0, 6, 12, 18, 24].map((h) => (
        <div
          key={h}
          style={{
            position: "absolute", top: 0, bottom: 0,
            left: (h / 24) * 100 + "%",
            borderLeft: "1px solid rgba(255,255,255,0.08)",
          }}
        />
      ))}
    </div>
  );
}

function TimelineLabels() {
  const now = new Date();
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: theme.text.ghost, marginTop: 4 }}>
      {[24, 18, 12, 6, 0].map((hoursAgo) => {
        const t = new Date(now.getTime() - hoursAgo * 3600 * 1000);
        return <span key={hoursAgo}>{t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>;
      })}
    </div>
  );
}

/* -- Summary stats from intervals -- */
function computeStats(intervals) {
  if (!intervals || intervals.length === 0) return { recording: 0, idle: 0, offline: 0, total: 0 };
  const now = Date.now();
  const span = 24 * 3600 * 1000;
  const start = now - span;
  const totals = { recording: 0, idle: 0, offline: 0, error: 0 };
  for (const iv of intervals) {
    const from = Math.max(new Date(iv.from).getTime(), start);
    const to = Math.min(new Date(iv.to).getTime(), now);
    if (to > from) totals[iv.state] = (totals[iv.state] || 0) + (to - from) / 1000;
  }
  return { ...totals, total: (now - start) / 1000 };
}

/* -- Metric cell -- */
function MetricCell({ label, value, unit, color }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 10, color: theme.text.faint, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || theme.text.secondary }}>{value != null ? value : "\u2014"}</div>
      {unit && <div style={{ fontSize: 10, color: theme.text.ghost }}>{unit}</div>}
    </div>
  );
}

/* -- Audio level bar (wide) -- */
function AudioBar({ db }) {
  if (db == null || db <= -100) return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
  const pct = Math.max(0, Math.min(100, ((db + 80) / 80) * 100));
  const color = db > -30 ? theme.accent.green : db > -50 ? theme.accent.yellow : theme.text.faint;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: theme.bg.input, overflow: "hidden" }}>
        <div style={{ height: "100%", width: pct + "%", background: color, borderRadius: 3, transition: "width 0.3s" }} />
      </div>
      <span style={{ fontSize: 11, color: theme.text.muted, minWidth: 55 }}>{db != null ? db.toFixed(1) + " dB" : "\u2014"}</span>
    </div>
  );
}

/* -- Legend -- */
function Legend() {
  return (
    <div style={{ display: "flex", gap: 16, fontSize: 11 }}>
      {Object.entries(STATE_COLORS).map(([key, sc]) => (
        <div key={key} style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 10, height: 10, borderRadius: 3, background: sc.text, opacity: 0.7 }} />
          <span style={{ color: theme.text.muted }}>{sc.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ================================================================ */
export default function CaptureStatusPage() {
  useEffect(() => { document.title = "Capture Status | Command Center"; }, []);

  const toast = useToastContext();
  const { status, thresholds, connectionState, connected } = useCaptureStatus();
  const { data: timeline, loading: timelineLoading } = useApi(
    () => getCaptureTimeline(24), [], { refetchOnFocus: true }
  );

  // Auto-refresh age display every 5s
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(id);
  }, []);

  // Management actions state
  const [actionPending, setActionPending] = useState(null);
  const [actionResult, setActionResult] = useState(null);
  const [actionLog, setActionLog] = useState([]);
  const [logLoading, setLogLoading] = useState(false);

  // Load action log and alerts on mount
  const [alerts, setAlerts] = useState([]);
  useEffect(() => {
    setLogLoading(true);
    getCaptureActionLog(10).then(data => {
      setActionLog(data.actions || []);
    }).catch((err) => {
      console.error(err);
      setActionLog([]);
      toast.error(err.message || "Failed to load capture action log");
    }).finally(() => setLogLoading(false));
    getCaptureAlerts().then(data => setAlerts(data.alerts || [])).catch((err) => {
      console.error(err);
      setAlerts([]);
      toast.error(err.message || "Failed to load capture alerts");
    });
  }, [toast]);

  // Refresh alerts when WS broadcasts alert changes
  useEffect(() => {
    if (status && (status.type === "alert_opened" || status.type === "alert_resolved")) {
      getCaptureAlerts().then(data => setAlerts(data.alerts || [])).catch((err) => {
        console.error(err);
        toast.error(err.message || "Failed to refresh capture alerts");
      });
    }
  }, [status, toast]);

  const runAction = async (action, force) => {
    setActionPending(action);
    setActionResult(null);
    try {
      const result = await executeCaptureAction(action, force);
      setActionResult(result);
      // Refresh log
      getCaptureActionLog(10).then(data => setActionLog(data.actions || [])).catch((err) => {
        console.error(err);
        toast.error(err.message || "Failed to refresh capture action log");
      });
    } catch (err) {
      const detail = err.detail || err.message || "Request failed";
      setActionResult({ action, status: "error", error: detail, httpStatus: err.status });
    } finally {
      setActionPending(null);
    }
  };

  const state = status?.state || "offline";
  const sc = STATE_COLORS[state] || STATE_COLORS.offline;
  const stats = useMemo(() => computeStats(timeline?.intervals), [timeline]);

  return (
    <div style={{ padding: "28px 32px", maxWidth: 900 }}>
      {/* Header */}
      <div style={{ ...titleStyle, display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <span>Capture Status</span>
        <span style={{
          fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 4,
          color: connected ? theme.accent.green : theme.accent.yellow,
          background: connected ? "rgba(34,197,94,0.1)" : "rgba(234,179,8,0.1)",
        }}>
          {connectionState === "connected" ? "Live" : connectionState === "connecting" ? "Connecting\u2026" : "Disconnected"}
        </span>
      </div>
      <div style={subtitleStyle}>ReSpeaker Pi 5 &middot; Office Capture System</div>

      {/* == Active Alerts == */}
      {alerts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {alerts.map(alert => (
            <div key={alert.id} style={{
              padding: "10px 14px", borderRadius: 6, marginBottom: 6,
              background: alert.severity === "critical" ? "rgba(239,68,68,0.08)" : "rgba(234,179,8,0.08)",
              border: "1px solid " + (alert.severity === "critical" ? "rgba(239,68,68,0.25)" : "rgba(234,179,8,0.25)"),
              display: "flex", alignItems: "center", gap: 10,
            }}>
              <span style={{
                fontSize: 16,
                color: alert.severity === "critical" ? theme.accent.red : theme.accent.yellow,
              }}>{alert.severity === "critical" ? "\u26a0" : "\u26a0"}</span>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 12, fontWeight: 600,
                  color: alert.severity === "critical" ? theme.accent.red : theme.accent.yellow,
                }}>{alert.message}</div>
                {alert.detail && (
                  <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 2 }}>{alert.detail}</div>
                )}
              </div>
              <div style={{ fontSize: 10, color: theme.text.ghost }}>
                {alert.opened_at ? new Date(alert.opened_at).toLocaleTimeString() : ""}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* == Live Status Card == */}
      <div style={{
        ...cardStyle,
        position: "relative", overflow: "hidden", marginBottom: 20,
        borderLeft: "4px solid " + sc.text,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 12, height: 12, borderRadius: "50%",
              background: sc.text,
              animation: state === "recording" ? "pulse 2s infinite" : "none",
              boxShadow: state === "recording" ? "0 0 8px " + sc.text : "none",
            }} />
            <span style={{ fontSize: 22, fontWeight: 700, color: sc.text }}>{sc.label}</span>
          </div>
          <div style={{ textAlign: "right", fontSize: 11, color: theme.text.faint }}>
            <div>Session: {status?.session_id ? status.session_id.slice(0, 8) : "\u2014"}</div>
            <div>Seq: {status?.seq != null ? status.seq : "\u2014"}</div>
          </div>
        </div>

        {/* Audio level */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: theme.text.faint, marginBottom: 4 }}>Audio Level</div>
          <AudioBar db={status?.audio_level_db} />
        </div>

        {/* Metrics grid */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12,
          padding: "14px 0", borderTop: "1px solid " + theme.border.subtle,
        }}>
          <MetricCell label="WiFi" value={status?.wifi_rssi != null ? status.wifi_rssi : null} unit="dBm"
            color={status?.wifi_rssi > -60 ? theme.accent.green : status?.wifi_rssi > -70 ? theme.accent.yellow : theme.accent.red} />
          <MetricCell label="CPU Temp" value={status?.cpu_temp_c != null ? status.cpu_temp_c.toFixed(0) : null} unit="°C"
            color={status?.cpu_temp_c > 70 ? theme.accent.red : status?.cpu_temp_c > 55 ? theme.accent.yellow : theme.text.secondary} />
          <MetricCell label="Disk" value={status?.disk_used_pct != null ? status.disk_used_pct.toFixed(0) : null} unit="%"
            color={status?.disk_used_pct > 85 ? theme.accent.red : status?.disk_used_pct > 70 ? theme.accent.yellow : theme.text.secondary} />
          <MetricCell label="Memory" value={status?.memory_used_pct != null ? status.memory_used_pct.toFixed(0) : null} unit="%"
            color={status?.memory_used_pct > 85 ? theme.accent.red : theme.text.secondary} />
          <MetricCell label="Uptime" value={formatUptime(status?.uptime_seconds)} />
        </div>

        {/* Bottom row */}
        <div style={{
          display: "flex", gap: 20, fontSize: 11, color: theme.text.muted,
          paddingTop: 10, borderTop: "1px solid " + theme.border.subtle,
        }}>
          <div>Silence: <span style={{ color: status?.silence_seconds > 30 ? theme.accent.yellow : theme.text.secondary }}>
            {status?.silence_seconds != null ? status.silence_seconds + "s" : "\u2014"}
          </span></div>
          <div>SSID: {status?.wifi_ssid || "\u2014"}</div>
          <div>Last heartbeat: {formatAge(status?.received_at)}</div>
          {status?.segment_open ? (
            <div>Segment: open ({formatDuration(status?.segment_duration_seconds)})</div>
          ) : (
            <div>Segment: closed</div>
          )}
        </div>
      </div>

      {/* == 24h Timeline == */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: theme.text.secondary }}>24-Hour Timeline</div>
          <Legend />
        </div>
        {timelineLoading ? (
          <div style={{ color: theme.text.faint, fontSize: 12, padding: 12 }}>Loading&hellip;</div>
        ) : (
          <>
            <TimelineBar intervals={timeline?.intervals} />
            <TimelineLabels />
          </>
        )}

        {/* Summary stats */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
          marginTop: 16, paddingTop: 14, borderTop: "1px solid " + theme.border.subtle,
        }}>
          <MetricCell label="Recording" value={formatDuration(stats.recording)} color={STATE_COLORS.recording.text} />
          <MetricCell label="Idle" value={formatDuration(stats.idle)} color={STATE_COLORS.idle.text} />
          <MetricCell label="Offline" value={formatDuration(stats.offline)} color={STATE_COLORS.offline.text} />
          <MetricCell label="Availability"
            value={stats.total > 0 ? Math.round(((stats.recording + stats.idle) / stats.total) * 100) + "%" : "\u2014"}
            color={theme.accent.green} />
        </div>
      </div>

      {/* == Management Actions == */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 12 }}>Management Actions</div>

        {/* Capture toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16, padding: "12px 16px", borderRadius: 8, background: (state === "recording" || state === "idle") ? "rgba(34,197,94,0.06)" : "rgba(120,113,108,0.08)", border: "1px solid " + ((state === "recording" || state === "idle") ? "rgba(34,197,94,0.15)" : "rgba(120,113,108,0.2)") }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.secondary }}>
              {state === "recording" || state === "idle" ? "Capture Active" : "Capture Stopped"}
            </div>
            <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>
              {state === "recording" || state === "idle" ? "ReSpeaker mic is live. Audio is being monitored and recorded." : "ReSpeaker mic is off. No audio is being recorded."}
            </div>
          </div>
          <button
            disabled={!!actionPending}
            onClick={() => {
              const action = (state === "recording" || state === "idle") ? "stop-capture" : "start-capture";
              if (state === "recording") {
                if (!window.confirm("Capture is currently recording. Stop anyway? (may lose in-progress segment)")) return;
                runAction(action, true);
              } else {
                runAction(action, false);
              }
            }}
            style={{
              padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 700,
              background: (state === "recording" || state === "idle") ? "#dc2626" : theme.accent.green,
              color: "#fff",
              border: "none",
              cursor: actionPending ? "not-allowed" : "pointer",
              opacity: actionPending ? 0.6 : 1,
              transition: "all 0.2s",
              minWidth: 100,
            }}
          >
            {actionPending === "start-capture" || actionPending === "stop-capture" ? "Working..." : (state === "recording" || state === "idle") ? "Stop" : "Start"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
          {[
            { key: "diagnose", label: "Diagnose", desc: "Gather Pi diagnostics" },
            { key: "restart-heartbeat", label: "Restart Heartbeat", desc: "Restart heartbeat daemon" },
            { key: "restart-capture", label: "Restart Capture", desc: "Restart audio capture" },
          ].map(act => (
            <button
              key={act.key}
              disabled={!!actionPending}
              onClick={() => {
                if (act.key === "restart-capture" && state === "recording") {
                  if (!window.confirm("Capture is recording. Restart anyway? (may lose in-progress segment)")) return;
                  runAction(act.key, true);
                } else {
                  runAction(act.key, false);
                }
              }}
              style={{
                padding: "8px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: actionPending === act.key ? theme.accent.yellow : theme.bg.input,
                color: actionPending === act.key ? "#000" : theme.text.secondary,
                border: "1px solid " + theme.border.default,
                cursor: actionPending ? "not-allowed" : "pointer",
                opacity: actionPending && actionPending !== act.key ? 0.5 : 1,
                transition: "all 0.2s",
              }}
              title={act.desc}
            >
              {actionPending === act.key ? "Running…" : act.label}
            </button>
          ))}
        </div>

        {/* Action result */}
        {actionResult && (
          <div style={{
            padding: "10px 14px", borderRadius: 6, fontSize: 12,
            background: actionResult.status === "success" ? "rgba(34,197,94,0.08)" :
                        actionResult.status === "error" && actionResult.httpStatus === 429 ? "rgba(234,179,8,0.08)" :
                        "rgba(239,68,68,0.08)",
            border: "1px solid " + (actionResult.status === "success" ? "rgba(34,197,94,0.2)" :
                        actionResult.status === "error" && actionResult.httpStatus === 429 ? "rgba(234,179,8,0.2)" :
                        "rgba(239,68,68,0.2)"),
            marginBottom: 8,
          }}>
            <div style={{ fontWeight: 600, marginBottom: 4,
              color: actionResult.status === "success" ? theme.accent.green :
                     actionResult.status === "error" && actionResult.httpStatus === 429 ? theme.accent.yellow :
                     theme.accent.red,
            }}>
              {actionResult.status === "success" ? "Success" :
               actionResult.status === "error" && actionResult.httpStatus === 429 ? "Cooldown" :
               "Failed"}
              {actionResult.result && actionResult.result.duration_ms != null &&
                " (" + actionResult.result.duration_ms + "ms)"}
            </div>
            {actionResult.error && (
              <div style={{ color: theme.text.muted }}>{actionResult.error}</div>
            )}
            {actionResult.result && actionResult.result.stdout && (
              <pre style={{
                fontSize: 10, color: theme.text.dim, marginTop: 6,
                whiteSpace: "pre-wrap", wordBreak: "break-all",
                maxHeight: 200, overflow: "auto",
                background: theme.bg.input, padding: 8, borderRadius: 4,
              }}>{actionResult.result.stdout}</pre>
            )}
            {actionResult.result && actionResult.result.stderr && (
              <div style={{ fontSize: 10, color: theme.accent.red, marginTop: 4 }}>
                {actionResult.result.stderr}
              </div>
            )}
          </div>
        )}
      </div>

      {/* == Action Log == */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 12 }}>Action Log</div>
        {logLoading ? (
          <div style={{ color: theme.text.faint, fontSize: 12 }}>Loading…</div>
        ) : actionLog.length === 0 ? (
          <div style={{ color: theme.text.faint, fontSize: 12 }}>No actions recorded</div>
        ) : (
          <div style={{ fontSize: 11 }}>
            {actionLog.map(entry => (
              <div key={entry.id} style={{
                display: "flex", gap: 12, padding: "6px 0",
                borderBottom: "1px solid " + theme.border.subtle,
                alignItems: "center",
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                  background: entry.status === "success" ? theme.accent.green : theme.accent.red,
                }} />
                <span style={{ color: theme.text.secondary, fontWeight: 600, minWidth: 120 }}>{entry.action}</span>
                <span style={{ color: theme.text.muted, flex: 1 }}>
                  {entry.result_summary ? entry.result_summary.slice(0, 60) : "—"}
                </span>
                <span style={{ color: theme.text.ghost, fontSize: 10, minWidth: 50, textAlign: "right" }}>
                  {entry.duration_ms != null ? entry.duration_ms + "ms" : ""}
                </span>
                <span style={{ color: theme.text.ghost, fontSize: 10, minWidth: 80, textAlign: "right" }}>
                  {entry.requested_at ? new Date(entry.requested_at).toLocaleTimeString() : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* == Thresholds Card == */}
      {thresholds && (
        <div style={{ ...cardStyle, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 12 }}>Thresholds</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, fontSize: 12 }}>
            <div>
              <div style={{ color: theme.text.faint, marginBottom: 2 }}>Stale Warning</div>
              <div style={{ color: theme.text.secondary }}>{thresholds.stale_warning_s}s</div>
            </div>
            <div>
              <div style={{ color: theme.text.faint, marginBottom: 2 }}>Offline Threshold</div>
              <div style={{ color: theme.text.secondary }}>{thresholds.offline_threshold_s}s</div>
            </div>
            <div>
              <div style={{ color: theme.text.faint, marginBottom: 2 }}>Silence Timeout</div>
              <div style={{ color: theme.text.secondary }}>{thresholds.silence_timeout_s}s</div>
            </div>
          </div>
        </div>
      )}

      {/* CSS animation */}
      <style>{"\n        @keyframes pulse {\n          0%, 100% { opacity: 1; }\n          50% { opacity: 0.4; }\n        }\n      "}</style>
    </div>
  );
}
