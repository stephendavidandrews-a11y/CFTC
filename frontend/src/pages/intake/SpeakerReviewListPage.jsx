import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { listConversations, getQueueCounts } from "../../api/intake";

const STATUS_TABS = [
  { key: "awaiting_speaker_review", label: "Needs Review" },
  { key: "pending", label: "Processing" },
  { key: "completed", label: "Completed" },
  { key: "error", label: "Errors" },
  { key: null, label: "All" },
];

const STATUS_STYLES = {
  awaiting_speaker_review: { bg: "#422006", text: "#fbbf24", label: "Needs Review" },
  pending: { bg: "#172554", text: "#60a5fa", label: "Processing" },
  transcribing: { bg: "#172554", text: "#60a5fa", label: "Transcribing" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
  discarded: { bg: "#1f2937", text: "#6b7280", label: "Discarded" },
  error: { bg: "#450a0a", text: "#f87171", label: "Error" },
};

const SOURCE_ICONS = { pi: "\ud83c\udf99\ufe0f", plaud: "\ud83d\udcf1", phone: "\ud83d\udcde" };

function formatDuration(seconds) {
  if (!seconds) return "--";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? m + "m " + s + "s" : s + "s";
}

function formatDate(iso) {
  if (!iso) return "--";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      " " + d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } catch (e) { return iso; }
}

export default function SpeakerReviewListPage() {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [counts, setCounts] = useState({});
  const [activeTab, setActiveTab] = useState("awaiting_speaker_review");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, qc] = await Promise.all([
        listConversations({ status: activeTab || undefined }),
        getQueueCounts(),
      ]);
      setConversations(list);
      setCounts(qc);
    } catch (err) {
      setError(err.message || "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => { load(); }, [load]);

  const needsReviewCount = counts["awaiting_speaker_review"] || 0;

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          Speaker Review
        </h1>
        <p style={{ fontSize: 13, color: theme.text.muted, margin: "6px 0 0" }}>
          Review and confirm speaker identities for recorded conversations
          {needsReviewCount > 0 && (
            <span style={{
              marginLeft: 10, background: "#422006", color: "#fbbf24",
              borderRadius: 10, padding: "2px 8px", fontSize: 11, fontWeight: 700,
            }}>
              {needsReviewCount} pending
            </span>
          )}
        </p>
      </div>

      {/* Status tabs */}
      <div style={{
        display: "flex", gap: 4, marginBottom: 20, padding: 4,
        background: theme.bg.card, borderRadius: 10, width: "fit-content",
        border: "1px solid " + theme.border.subtle,
      }}>
        {STATUS_TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          const count = tab.key ? (counts[tab.key] || 0) : Object.values(counts).reduce((a, b) => a + b, 0);
          return (
            <button
              key={tab.key ?? "all"}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: "7px 14px", borderRadius: 7, border: "none", cursor: "pointer",
                fontSize: 12, fontWeight: isActive ? 600 : 500,
                background: isActive ? "rgba(59,130,246,0.15)" : "transparent",
                color: isActive ? theme.accent.blueLight : theme.text.dim,
                transition: "all 0.15s ease",
              }}
            >
              {tab.label}
              {count > 0 && (
                <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, opacity: isActive ? 1 : 0.6 }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: "12px 16px", background: "#450a0a", border: "1px solid #7f1d1d",
          borderRadius: 8, color: "#fca5a5", fontSize: 13, marginBottom: 16,
        }}>
          {error}
          <button onClick={load} style={{
            marginLeft: 12, background: "none", border: "1px solid #7f1d1d",
            color: "#fca5a5", borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 12,
          }}>Retry</button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.dim, fontSize: 13 }}>
          Loading conversations...
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && conversations.length === 0 && (
        <div style={{
          padding: 60, textAlign: "center",
          background: theme.bg.card, borderRadius: 10, border: "1px solid " + theme.border.subtle,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>
            {activeTab === "awaiting_speaker_review" ? "\u2705" : "\ud83c\udf99\ufe0f"}
          </div>
          <div style={{ fontSize: 15, color: theme.text.muted, fontWeight: 600 }}>
            {activeTab === "awaiting_speaker_review"
              ? "No recordings need review"
              : "No conversations found"}
          </div>
          <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 6 }}>
            {activeTab === "awaiting_speaker_review"
              ? "Upload a recording or wait for the inbox watcher to pick up new files"
              : "Try a different filter"}
          </div>
        </div>
      )}

      {/* Conversation list */}
      {!loading && conversations.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {conversations.map((conv) => {
            const status = STATUS_STYLES[conv.processing_status] || STATUS_STYLES.pending;
            const isReviewable = conv.processing_status === "awaiting_speaker_review";
            return (
              <button
                key={conv.id}
                onClick={() => { if (isReviewable) navigate("/intake/speaker-review/" + conv.id); }}
                style={{
                  display: "flex", alignItems: "center", gap: 16,
                  width: "100%", textAlign: "left",
                  padding: "14px 18px", borderRadius: 10,
                  background: theme.bg.card,
                  border: "1px solid " + (isReviewable ? "rgba(251,191,36,0.2)" : theme.border.subtle),
                  cursor: isReviewable ? "pointer" : "default",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => { if (isReviewable) e.currentTarget.style.borderColor = "rgba(251,191,36,0.4)"; }}
                onMouseLeave={(e) => { if (isReviewable) e.currentTarget.style.borderColor = "rgba(251,191,36,0.2)"; }}
              >
                <span style={{ fontSize: 20, width: 32, textAlign: "center" }}>
                  {SOURCE_ICONS[conv.source] || "\ud83c\udf99\ufe0f"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 14, fontWeight: 600, color: theme.text.primary,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {conv.title || "Recording " + conv.id.slice(0, 8)}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 3 }}>
                    {formatDate(conv.created_at)}
                    {conv.duration_seconds && <span style={{ marginLeft: 12 }}>{formatDuration(conv.duration_seconds)}</span>}
                    {conv.source && <span style={{ marginLeft: 12, textTransform: "capitalize" }}>{conv.source}</span>}
                  </div>
                </div>
                <span style={{
                  background: status.bg, color: status.text,
                  borderRadius: 6, padding: "3px 10px", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap",
                }}>{status.label}</span>
                {isReviewable && <span style={{ color: theme.text.dim, fontSize: 16 }}>&rsaquo;</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
