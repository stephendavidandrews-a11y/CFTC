import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { fetchJSON } from "../../api/client";

const TAG_COLORS = {
  BOSS: { bg: "#7f1d1d", text: "#fca5a5" },
  DEADLINE: { bg: "#78350f", text: "#fbbf24" },
  BLOCKED: { bg: "#450a0a", text: "#f87171" },
  OVERDUE: { bg: "#431407", text: "#fb923c" },
  REVIEW: { bg: "#1e3a5f", text: "#60a5fa" },
};

function Badge({ bg, text, label }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4,
      fontSize: 10, fontWeight: 600, background: bg, color: text,
      textTransform: "uppercase", letterSpacing: "0.04em",
    }}>{label}</span>
  );
}

function Section({ title, icon, count, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{
      background: theme.bg.card, border: `1px solid ${theme.border.default}`,
      borderRadius: 8, marginBottom: 16, overflow: "hidden",
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "12px 16px", borderBottom: open ? `1px solid ${theme.border.default}` : "none",
          cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center",
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
          <span style={{ fontSize: 15, fontWeight: 600, color: theme.text.primary }}>{title}</span>
          {count != null && (
            <span style={{ fontSize: 12, color: theme.text.faint, fontWeight: 400 }}>({count})</span>
          )}
        </div>
        <span style={{ color: theme.text.faint, fontSize: 12 }}>{open ? "\u25B2" : "\u25BC"}</span>
      </div>
      {open && <div style={{ padding: 16 }}>{children}</div>}
    </div>
  );
}

function EmptyLine({ message }) {
  return <div style={{ color: theme.text.faint, fontSize: 13, fontStyle: "italic", padding: "8px 0" }}>{message}</div>;
}

function EvidenceBlock({ text, attribution }) {
  return (
    <blockquote style={{
      margin: "8px 0", padding: "8px 12px", borderLeft: `3px solid ${theme.accent.blue}`,
      background: "rgba(59,130,246,0.05)", fontSize: 13, color: theme.text.muted,
      borderRadius: "0 4px 4px 0",
    }}>
      {text}
      {attribution && (
        <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 4 }}>{"\u2014"} {attribution}</div>
      )}
    </blockquote>
  );
}

export default function DailyBriefPage() {
  const navigate = useNavigate();
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));
  const [generating, setGenerating] = useState(false);
  const [briefList, setBriefList] = useState([]);

  const fetchBrief = useCallback(async (dateStr) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJSON(`/ai/api/intelligence/briefs/by-date/daily/${dateStr}`);
      if (result.error) {
        setBrief(null);
      } else {
        const content = typeof result.content === "string" ? JSON.parse(result.content) : result.content;
        setBrief({ ...result, content });
      }
    } catch (e) {
      setError(e.message);
      setBrief(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchList = useCallback(async () => {
    try {
      const result = await fetchJSON("/ai/api/intelligence/briefs?brief_type=daily&limit=30");
      setBriefList(result.items || []);
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchBrief(selectedDate);
    fetchList();
  }, [selectedDate, fetchBrief, fetchList]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await fetchJSON("/ai/api/intelligence/generate?brief_type=daily", { method: "POST" });
      await fetchBrief(new Date().toISOString().slice(0, 10));
      await fetchList();
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const data = brief?.content || {};
  const hasData = brief && !brief.error;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 900, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, color: theme.text.primary }}>Daily Brief</h1>
          <div style={{ fontSize: 13, color: theme.text.faint, marginTop: 4 }}>
            Command and control: what needs attention today
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{
              background: theme.bg.input, border: `1px solid ${theme.border.default}`,
              borderRadius: 6, padding: "6px 10px", color: theme.text.primary,
              fontSize: 13,
            }}
          />
          <button
            onClick={handleGenerate}
            disabled={generating}
            style={{
              background: theme.accent.blue, color: "#fff", border: "none",
              borderRadius: 6, padding: "7px 14px", fontSize: 13, fontWeight: 500,
              cursor: generating ? "wait" : "pointer", opacity: generating ? 0.6 : 1,
            }}
          >
            {generating ? "Generating..." : "Generate Now"}
          </button>
        </div>
      </div>

      {/* Date chips for recent briefs */}
      {briefList.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
          {briefList.slice(0, 10).map((b) => (
            <button
              key={b.id}
              onClick={() => setSelectedDate(b.brief_date)}
              style={{
                background: b.brief_date === selectedDate ? theme.accent.blue : theme.bg.input,
                color: b.brief_date === selectedDate ? "#fff" : theme.text.muted,
                border: `1px solid ${b.brief_date === selectedDate ? theme.accent.blue : theme.border.default}`,
                borderRadius: 4, padding: "3px 10px", fontSize: 11, cursor: "pointer",
              }}
            >
              {b.brief_date}
            </button>
          ))}
        </div>
      )}

      {loading && <div style={{ color: theme.text.faint, padding: 40, textAlign: "center" }}>Loading...</div>}
      {error && <div style={{ color: "#f87171", padding: 16 }}>{error}</div>}

      {!loading && !hasData && (
        <div style={{
          background: theme.bg.card, border: `1px solid ${theme.border.default}`,
          borderRadius: 8, padding: 40, textAlign: "center",
        }}>
          <div style={{ fontSize: 15, color: theme.text.muted, marginBottom: 12 }}>
            No brief for {selectedDate}
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            style={{
              background: theme.accent.blue, color: "#fff", border: "none",
              borderRadius: 6, padding: "8px 16px", fontSize: 13, cursor: "pointer",
            }}
          >
            Generate Daily Brief
          </button>
        </div>
      )}

      {!loading && hasData && (
        <>
          {/* Brief date header */}
          <div style={{
            textAlign: "center", padding: "8px 0 20px",
            fontSize: 18, fontWeight: 600, color: theme.text.primary,
          }}>
            {data.date_display || selectedDate}
          </div>

          {/* Section 1: What Changed */}
          <Section title="What Changed" icon={"\uD83D\uDD04"} count={data.what_changed?.length || 0}>
            {(data.what_changed || []).length > 0 ? (
              data.what_changed.map((c, i) => (
                <div key={i} style={{
                  padding: "6px 0", borderBottom: `1px solid ${theme.border.default}`,
                  fontSize: 13, display: "flex", justifyContent: "space-between",
                }}>
                  <div>
                    <span style={{ color: theme.text.faint, fontSize: 11, marginRight: 8 }}>{c.entity_type}</span>
                    {c.summary}
                  </div>
                  <span style={{ color: theme.text.faint, fontSize: 11 }}>{(c.timestamp || "").slice(0, 16)}</span>
                </div>
              ))
            ) : (
              <EmptyLine message="No changes since last brief." />
            )}
          </Section>

          {/* Section 2: Action List */}
          <Section title="Action List" icon={"\uD83D\uDCCB"} count={data.action_list?.length || 0}>
            {(data.action_list || []).length > 0 ? (
              data.action_list.map((a, i) => {
                const tc = TAG_COLORS[a.tag] || { bg: "#1f2937", text: "#9ca3af" };
                return (
                  <div key={i} style={{
                    padding: "8px 0", borderBottom: `1px solid ${theme.border.default}`,
                    cursor: a.entity_type && a.entity_id ? "pointer" : "default",
                  }}
                  onClick={() => {
                    if (a.entity_type === "matter") navigate(`/matters/${a.entity_id}`);
                    else if (a.entity_type === "decision") navigate(`/decisions`);
                    else if (a.entity_type === "communication") navigate(`/review/communications`);
                  }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Badge bg={tc.bg} text={tc.text} label={a.tag} />
                      <span style={{ fontSize: 14, fontWeight: 500 }}>{a.title}</span>
                      {a.matter && (
                        <span style={{ fontSize: 12, color: theme.text.muted }}>{a.matter}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 4, marginLeft: 60 }}>
                      {a.detail}
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyLine message="No action items today." />
            )}
          </Section>

          {/* Section 3: Meetings */}
          <Section title={"Today\u2019s Meetings"} icon={"\uD83D\uDCC5"} count={data.meetings?.length || 0}>
            {(data.meetings || []).length > 0 ? (
              data.meetings.map((m, i) => (
                <div key={i} style={{
                  padding: "10px 0", borderBottom: `1px solid ${theme.border.default}`,
                  cursor: m.id ? "pointer" : "default",
                }}
                onClick={() => m.id && navigate(`/meetings/${m.id}`)}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 500 }}>{m.title}</span>
                    {m.has_external && (
                      <Badge bg="#78350f" text="#fbbf24" label="EXTERNAL" />
                    )}
                    {m.prep_needed && (
                      <Badge bg="#1e3a5f" text="#60a5fa" label="PREP" />
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 2 }}>
                    {[
                      m.start_time ? m.start_time.slice(0, 5) : null,
                      m.meeting_type,
                      m.location,
                    ].filter(Boolean).join(" \u2022 ")}
                  </div>
                  {m.participants?.length > 0 && (
                    <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 2 }}>
                      {m.participants.map((p) => p.full_name || p.name || "").filter(Boolean).join(", ")}
                    </div>
                  )}
                  {m.linked_matters?.length > 0 && (
                    <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>
                      Matters: {m.linked_matters.map((mat) => mat.title || "").join(", ")}
                    </div>
                  )}
                  {m.prep_narrative && (
                    <EvidenceBlock text={m.prep_narrative} />
                  )}
                </div>
              ))
            ) : (
              <EmptyLine message="No meetings today." />
            )}
          </Section>

          {/* Section 4: Follow-Ups */}
          <Section title="Follow-Ups Due" icon={"\uD83D\uDCDE"} count={data.followups?.length || 0}>
            {(data.followups || []).length > 0 ? (
              data.followups.map((f, i) => {
                const isOverdue = f.next_date <= new Date().toISOString().slice(0, 10);
                return (
                  <div key={i} style={{
                    padding: "6px 0", borderBottom: `1px solid ${theme.border.default}`,
                    cursor: f.person_id ? "pointer" : "default",
                  }}
                  onClick={() => f.person_id && navigate(`/people/${f.person_id}`)}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontWeight: 500, fontSize: 13 }}>{f.name}</span>
                      {f.organization && (
                        <span style={{ fontSize: 12, color: theme.text.muted }}>{f.organization}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 2 }}>
                      <span style={{ color: isOverdue ? "#f87171" : "#f97316" }}>{f.next_date}</span>
                      {f.interaction_type && <span> {"\u2022"} {f.interaction_type}</span>}
                      {f.purpose && <span> {"\u2022"} {f.purpose}</span>}
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyLine message="No follow-ups due in the next 3 days." />
            )}
          </Section>

          {/* Section 5: Team Pulse */}
          <Section title="Team Pulse" icon={"\uD83D\uDC65"} defaultOpen={true}>
            {(() => {
              const pulse = data.team_pulse || {};
              const overdueCount = pulse.overdue_count || 0;
              const byAssignee = pulse.overdue_by_assignee || {};
              const overloaded = pulse.overloaded_people || [];
              const hasIssues = overdueCount > 0 || overloaded.length > 0;

              return hasIssues ? (
                <div>
                  {overdueCount > 0 && (
                    <div style={{ fontSize: 13, padding: "4px 0" }}>
                      <span style={{ color: "#f87171" }}>{overdueCount} overdue tasks</span>:{" "}
                      {Object.entries(byAssignee).map(([name, count]) => `${name} (${count})`).join(", ")}
                    </div>
                  )}
                  {overloaded.length > 0 && (
                    <div style={{ fontSize: 13, padding: "4px 0" }}>
                      <span style={{ color: "#f97316" }}>Overloaded</span>:{" "}
                      {overloaded.map((p) => `${p.name} (${p.task_count})`).join(", ")}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 13, color: "#22c55e" }}>No team execution risks today.</div>
              );
            })()}
          </Section>

          {/* Footer */}
          <div style={{
            textAlign: "center", padding: "16px 0", fontSize: 11, color: theme.text.faint,
          }}>
            Generated {brief.created_at?.slice(0, 19)} {brief.model_used ? `\u2022 Model: ${brief.model_used}` : ""}
          </div>
        </>
      )}
    </div>
  );
}
