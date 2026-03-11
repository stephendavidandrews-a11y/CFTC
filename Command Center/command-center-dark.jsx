import { useState, useEffect } from "react";

const SECTIONS = [
  { id: "summary", label: "Executive Summary", icon: "◫" },
  { id: "eo", label: "EO Tracker", icon: "⚑" },
  { id: "team", label: "Team", icon: "⊡" },
  { id: "pipeline", label: "Pipeline", icon: "▤" },
  { id: "interagency", label: "Interagency", icon: "⬡" },
  { id: "research", label: "Research", icon: "⊞" },
  { id: "comments", label: "Comments", icon: "✉" },
  { id: "intelligence", label: "Intelligence", icon: "◉" },
  { id: "reports", label: "Reports", icon: "⊟" },
];

const TEAM = [
  { name: "Sarah Chen", role: "Assistant General Counsel", gs: "GS-15", active: 3, overdue: 1 },
  { name: "Marcus Williams", role: "Senior Counsel", gs: "GS-15", active: 4, overdue: 0 },
  { name: "Jennifer Park", role: "Senior Counsel", gs: "GS-14", active: 2, overdue: 0 },
  { name: "David Thompson", role: "Attorney-Adviser", gs: "GS-14", active: 3, overdue: 1 },
  { name: "Rachel Foster", role: "Attorney-Adviser", gs: "GS-13", active: 2, overdue: 0 },
  { name: "James Liu", role: "Attorney-Adviser", gs: "GS-13", active: 1, overdue: 0 },
  { name: "Ana Martinez", role: "Attorney-Adviser", gs: "GS-13", active: 3, overdue: 2 },
  { name: "Robert Kim", role: "Attorney-Adviser", gs: "GS-12", active: 2, overdue: 0 },
  { name: "Lisa Patel", role: "Attorney-Adviser", gs: "GS-12", active: 1, overdue: 0 },
  { name: "Michael Brown", role: "Attorney-Adviser", gs: "GS-12", active: 2, overdue: 1 },
];

const EO_DATA = [
  { number: "14178", title: "Strengthening American Leadership in Digital Financial Technology", status: "in_progress", deadline: "2025-04-15", actions: 6, completed: 2 },
  { number: "14067", title: "Ensuring Responsible Development of Digital Assets", status: "superseded", deadline: null, actions: 4, completed: 4 },
  { number: "14192", title: "Unleashing Prosperity Through Deregulation", status: "in_progress", deadline: "2025-05-01", actions: 3, completed: 0 },
  { number: "14148", title: "Initial Rescissions of Harmful EOs and Actions", status: "completed", deadline: null, actions: 2, completed: 2 },
  { number: "14219", title: "Establishing the Presidential Working Group on Digital Asset Markets", status: "in_progress", deadline: "2025-07-22", actions: 8, completed: 3 },
];

const PIPELINE_DATA = [
  { title: "Event Contracts & Enumerated Activities", stage: "comment", docket: "CFTC-2024-0007", comments: 819, deadline: "2025-04-30" },
  { title: "Tokenized Collateral Framework", stage: "proposed", docket: "CFTC-2025-0002", comments: 0, deadline: "2025-06-15" },
  { title: "DeFi Safe Harbor Pilot", stage: "drafting", docket: null, comments: 0, deadline: "2025-08-01" },
  { title: "Digital Asset Clearing Amendments", stage: "proposed", docket: "CFTC-2025-0005", comments: 42, deadline: "2025-05-20" },
  { title: "Reg AT Modernization", stage: "final", docket: "CFTC-2024-0012", comments: 156, deadline: "2025-03-15" },
];

const DEADLINES = [
  { date: "2025-03-01", item: "PWG Report: Stablecoin Regulatory Framework", owner: "Interagency", status: "danger" },
  { date: "2025-03-10", item: "EO 14178 — 60-Day Regulatory Gap Analysis", owner: "S. Andrews", status: "danger" },
  { date: "2025-03-15", item: "Reg AT Modernization — Final Rule", owner: "M. Williams", status: "warning" },
  { date: "2025-04-01", item: "Comment Period Close: Event Contracts", owner: "D. Thompson", status: "ok" },
  { date: "2025-04-15", item: "EO 14178 — Proposed Token Classification Framework", owner: "S. Chen", status: "ok" },
  { date: "2025-05-01", item: "EO 14192 — Deregulation Cost-Benefit Report", owner: "J. Park", status: "ok" },
];

const LIVE_FEED = [
  { time: "2 min ago", type: "tweet", source: "@CFTCChairman", text: "Excited to announce progress on our digital assets framework. The PWG report is ahead of schedule.", icon: "𝕏" },
  { time: "18 min ago", type: "news", source: "Reuters", text: "SEC and CFTC to hold joint hearing on crypto custody rules next month", icon: "◆" },
  { time: "34 min ago", type: "fr", source: "Federal Register", text: "CFTC-2025-0005: Digital Asset Clearing Amendments — 12 new comments received", icon: "⬢" },
  { time: "1 hr ago", type: "tweet", source: "@SenLummis", text: "Bipartisan stablecoin bill moves to markup next week. Strong support from Treasury and CFTC.", icon: "𝕏" },
  { time: "1.5 hr ago", type: "news", source: "CoinDesk", text: "Kalshi seeks to expand political event contracts after favorable CFTC guidance", icon: "◆" },
  { time: "2 hr ago", type: "regulatory", source: "SEC", text: "Staff Accounting Bulletin 122 rescission — crypto custody treatment revised", icon: "⊕" },
  { time: "3 hr ago", type: "tweet", source: "@HesterPeirce", text: "Tokenized collateral is the next frontier. Looking forward to CFTC's proposed framework.", icon: "𝕏" },
  { time: "4 hr ago", type: "fr", source: "Federal Register", text: "OCC issues interpretive letter on national bank authority for stablecoin reserves", icon: "⬢" },
  { time: "5 hr ago", type: "news", source: "Bloomberg", text: "Trump crypto working group targets July deadline for comprehensive regulatory framework", icon: "◆" },
  { time: "6 hr ago", type: "regulatory", source: "Treasury", text: "FinCEN proposed rule on DeFi broker definition — comment period opens March 1", icon: "⊕" },
];

const STATUS_COLORS = {
  in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
  superseded: { bg: "#422006", text: "#fbbf24", label: "Superseded" },
  not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
};

const STAGE_COLORS = {
  drafting: { bg: "#1f2937", text: "#9ca3af", label: "Drafting", accent: "#6b7280" },
  proposed: { bg: "#172554", text: "#60a5fa", label: "Proposed Rule", accent: "#3b82f6" },
  comment: { bg: "#422006", text: "#fbbf24", label: "Comment Period", accent: "#f59e0b" },
  final: { bg: "#14532d", text: "#4ade80", label: "Final Rule", accent: "#22c55e" },
};

const FEED_COLORS = {
  tweet: { accent: "#1d9bf0", bg: "rgba(29,155,240,0.08)" },
  news: { accent: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
  fr: { accent: "#a78bfa", bg: "rgba(167,139,250,0.08)" },
  regulatory: { accent: "#34d399", bg: "rgba(52,211,153,0.08)" },
};

function Badge({ bg, text, label }) {
  return (
    <span style={{
      display: "inline-block", padding: "3px 10px", borderRadius: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
      background: bg, color: text, border: `1px solid ${text}22`,
    }}>{label}</span>
  );
}

function Pulse({ color }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 8, height: 8 }}>
      <span style={{
        position: "absolute", inset: 0, borderRadius: "50%", background: color,
        opacity: 0.4, animation: "pulse 2s ease-in-out infinite",
      }} />
      <span style={{
        position: "relative", width: 8, height: 8, borderRadius: "50%", background: color,
      }} />
      <style>{`@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 0.4; } 50% { transform: scale(2.2); opacity: 0; } }`}</style>
    </span>
  );
}

function StatCard({ value, label, accent, pulse }) {
  return (
    <div style={{
      background: "#111827", borderRadius: 10, padding: "20px 24px",
      border: "1px solid #1f2937", position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: accent || "#3b82f6" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.03em" }}>{value}</div>
        {pulse && <Pulse color={accent || "#3b82f6"} />}
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginTop: 4, fontWeight: 500 }}>{label}</div>
    </div>
  );
}

// ─── Live Feed Component ───
function LiveFeed() {
  const [items, setItems] = useState(LIVE_FEED);
  const [flash, setFlash] = useState(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setFlash(0);
      setTimeout(() => setFlash(null), 2000);
    }, 12000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
      padding: 20, height: "100%", display: "flex", flexDirection: "column",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <Pulse color="#22c55e" />
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>Live Intelligence Feed</h3>
        <span style={{ fontSize: 10, color: "#475569", marginLeft: "auto" }}>Auto-updating</span>
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {items.map((item, i) => {
          const fc = FEED_COLORS[item.type];
          const isFlash = flash === i;
          return (
            <div key={i} style={{
              padding: "12px 14px", marginBottom: 6, borderRadius: 8,
              background: isFlash ? fc.bg : "transparent",
              borderLeft: `3px solid ${isFlash ? fc.accent : "transparent"}`,
              transition: "all 0.5s ease",
              cursor: "pointer",
            }}
            onMouseEnter={e => { e.currentTarget.style.background = fc.bg; e.currentTarget.style.borderLeftColor = fc.accent; }}
            onMouseLeave={e => { if (!isFlash) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderLeftColor = "transparent"; } }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: fc.accent, fontWeight: 700 }}>{item.icon}</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: fc.accent }}>{item.source}</span>
                <span style={{ fontSize: 10, color: "#475569", marginLeft: "auto" }}>{item.time}</span>
              </div>
              <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{item.text}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Section: Executive Summary ───
function SummaryView() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", margin: 0, letterSpacing: "-0.02em" }}>
            Executive Summary
          </h2>
          <p style={{ fontSize: 13, color: "#475569", marginTop: 4 }}>
            Office of General Counsel — Regulation Division
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 13, color: "#94a3b8", fontFamily: "monospace" }}>
            {now.toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </div>
          <div style={{ fontSize: 20, color: "#f1f5f9", fontFamily: "monospace", fontWeight: 600, letterSpacing: "0.05em" }}>
            {now.toLocaleTimeString("en-US", { hour12: false })}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 28 }}>
        <StatCard value="5" label="Active Executive Orders" accent="#3b82f6" />
        <StatCard value="4" label="Overdue Items" accent="#ef4444" pulse />
        <StatCard value="5" label="Active Rulemakings" accent="#a78bfa" />
        <StatCard value="10" label="Attorneys" accent="#22c55e" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Deadlines */}
          <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>Upcoming Deadlines</h3>
              <span style={{ fontSize: 10, color: "#475569" }}>Next 90 days</span>
            </div>
            {DEADLINES.map((d, i) => {
              const color = d.status === "danger" ? "#ef4444" : d.status === "warning" ? "#f59e0b" : "#334155";
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                  borderBottom: "1px solid #1f2937", fontSize: 13, cursor: "pointer",
                }}
                onMouseEnter={e => e.currentTarget.style.background = "#0f172a"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
                  <div style={{ width: 85, color: "#64748b", fontFamily: "monospace", fontSize: 11 }}>{d.date}</div>
                  <div style={{ flex: 1, fontWeight: 500, color: "#e2e8f0" }}>{d.item}</div>
                  <div style={{ fontSize: 11, color: "#475569" }}>{d.owner}</div>
                </div>
              );
            })}
          </div>

          {/* Team */}
          <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", padding: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: "0 0 14px" }}>Team Workload</h3>
            {TEAM.slice(0, 5).map((t, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "9px 0",
                borderBottom: "1px solid #1f2937", fontSize: 13,
              }}>
                <div style={{
                  width: 30, height: 30, borderRadius: "50%",
                  background: `hsl(${i * 40 + 200}, 50%, 25%)`,
                  color: `hsl(${i * 40 + 200}, 70%, 75%)`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 600, flexShrink: 0,
                }}>
                  {t.name.split(" ").map(n => n[0]).join("")}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: "#e2e8f0", fontSize: 13 }}>{t.name}</div>
                  <div style={{ fontSize: 10, color: "#475569" }}>{t.role}</div>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span style={{
                    padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                    background: "#172554", color: "#60a5fa",
                  }}>{t.active}</span>
                  {t.overdue > 0 && (
                    <span style={{
                      padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                      background: "#450a0a", color: "#f87171",
                    }}>{t.overdue}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Feed */}
        <LiveFeed />
      </div>

      {/* Pipeline Kanban */}
      <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", padding: 20, marginTop: 20 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: "0 0 16px" }}>Rulemaking Pipeline</h3>
        <div style={{ display: "flex", gap: 14 }}>
          {["drafting", "proposed", "comment", "final"].map(stage => {
            const items = PIPELINE_DATA.filter(p => p.stage === stage);
            const s = STAGE_COLORS[stage];
            return (
              <div key={stage} style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  display: "flex", alignItems: "center", gap: 8, marginBottom: 10,
                  paddingBottom: 10, borderBottom: `2px solid ${s.accent}`,
                }}>
                  <span style={{ fontWeight: 700, fontSize: 12, color: s.text }}>{s.label}</span>
                  <span style={{
                    background: s.bg, color: s.text, borderRadius: "50%",
                    width: 20, height: 20, display: "flex", alignItems: "center",
                    justifyContent: "center", fontSize: 10, fontWeight: 700,
                  }}>{items.length}</span>
                </div>
                {items.map((p, i) => (
                  <div key={i} style={{
                    background: "#0f172a", borderRadius: 8, border: "1px solid #1e293b",
                    padding: 14, marginBottom: 8, cursor: "pointer", transition: "border-color 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = s.accent}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "#1e293b"}>
                    <div style={{ fontWeight: 600, fontSize: 12, color: "#e2e8f0", marginBottom: 4 }}>{p.title}</div>
                    {p.docket && <div style={{ fontSize: 10, color: "#475569", fontFamily: "monospace" }}>{p.docket}</div>}
                    {p.comments > 0 && <div style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>{p.comments} comments</div>}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Section: EO Tracker ───
function EOView() {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", marginBottom: 24, letterSpacing: "-0.02em" }}>
        Executive Order Tracker
      </h2>
      <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #1e293b" }}>
              {["EO #", "Title", "Status", "Deadline", "Actions", "Progress"].map(h => (
                <th key={h} style={{
                  textAlign: "left", padding: "14px 16px", fontWeight: 600,
                  color: "#475569", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em",
                  background: "#0f172a",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EO_DATA.map((eo, i) => {
              const s = STATUS_COLORS[eo.status];
              const pct = Math.round((eo.completed / eo.actions) * 100);
              return (
                <tr key={i} style={{ borderBottom: "1px solid #1e293b", cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#0f172a"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={{ padding: "14px 16px", fontWeight: 700, fontFamily: "monospace", color: "#94a3b8" }}>{eo.number}</td>
                  <td style={{ padding: "14px 16px", fontWeight: 500, color: "#e2e8f0", maxWidth: 300 }}>{eo.title}</td>
                  <td style={{ padding: "14px 16px" }}><Badge bg={s.bg} text={s.text} label={s.label} /></td>
                  <td style={{ padding: "14px 16px", color: "#64748b", fontFamily: "monospace", fontSize: 12 }}>{eo.deadline || "—"}</td>
                  <td style={{ padding: "14px 16px" }}>
                    <span style={{ fontWeight: 700, color: "#e2e8f0" }}>{eo.completed}</span>
                    <span style={{ color: "#475569" }}> / {eo.actions}</span>
                  </td>
                  <td style={{ padding: "14px 16px", width: 140 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ flex: 1, height: 5, background: "#1e293b", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{
                          width: `${pct}%`, height: "100%", borderRadius: 3,
                          background: pct === 100 ? "#22c55e" : "#3b82f6",
                          transition: "width 0.5s ease",
                        }} />
                      </div>
                      <span style={{ fontSize: 10, color: "#64748b", width: 30, textAlign: "right" }}>{pct}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Section: Team ───
function TeamView() {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", marginBottom: 24, letterSpacing: "-0.02em" }}>
        Team — Regulation Division
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
        {TEAM.map((t, i) => (
          <div key={i} style={{
            background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
            padding: 20, display: "flex", gap: 16, alignItems: "flex-start",
            cursor: "pointer", transition: "border-color 0.15s",
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = "#3b82f6"}
          onMouseLeave={e => e.currentTarget.style.borderColor = "#1f2937"}>
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: `hsl(${i * 36 + 200}, 45%, 22%)`,
              color: `hsl(${i * 36 + 200}, 65%, 72%)`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 700, flexShrink: 0,
            }}>
              {t.name.split(" ").map(n => n[0]).join("")}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, color: "#f1f5f9", fontSize: 14 }}>{t.name}</div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{t.role} · {t.gs}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <span style={{
                  padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: "#172554", color: "#60a5fa",
                }}>{t.active} active</span>
                {t.overdue > 0 && (
                  <span style={{
                    padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                    background: "#450a0a", color: "#f87171",
                  }}>{t.overdue} overdue</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Section: Pipeline ───
function PipelineView() {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", marginBottom: 24, letterSpacing: "-0.02em" }}>
        Rulemaking Pipeline
      </h2>
      <div style={{ display: "flex", gap: 16 }}>
        {["drafting", "proposed", "comment", "final"].map(stage => {
          const items = PIPELINE_DATA.filter(p => p.stage === stage);
          const s = STAGE_COLORS[stage];
          return (
            <div key={stage} style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8, marginBottom: 14,
                paddingBottom: 12, borderBottom: `2px solid ${s.accent}`,
              }}>
                <span style={{ fontWeight: 700, fontSize: 13, color: s.text }}>{s.label}</span>
                <span style={{
                  background: s.bg, color: s.text, borderRadius: "50%",
                  width: 22, height: 22, display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 11, fontWeight: 700,
                }}>{items.length}</span>
              </div>
              {items.map((p, i) => (
                <div key={i} style={{
                  background: "#111827", borderRadius: 8, border: "1px solid #1e293b",
                  padding: 16, marginBottom: 10, cursor: "pointer", transition: "all 0.15s",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = s.accent; e.currentTarget.style.boxShadow = `0 0 20px ${s.accent}15`; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "#1e293b"; e.currentTarget.style.boxShadow = "none"; }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: "#e2e8f0", marginBottom: 6 }}>{p.title}</div>
                  {p.docket && <div style={{ fontSize: 10, color: "#475569", fontFamily: "monospace", marginBottom: 4 }}>{p.docket}</div>}
                  {p.comments > 0 && <div style={{ fontSize: 10, color: "#64748b" }}>{p.comments} comments</div>}
                  {p.deadline && <div style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>Due: {p.deadline}</div>}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Section: Intelligence ───
function IntelligenceView() {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", margin: 0, letterSpacing: "-0.02em" }}>
          Intelligence
        </h2>
        <Pulse color="#22c55e" />
        <span style={{ fontSize: 11, color: "#475569" }}>Real-time</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Tweets tracked", value: "24", sub: "Last 24 hrs", accent: "#1d9bf0" },
          { label: "News articles", value: "12", sub: "Last 24 hrs", accent: "#f59e0b" },
          { label: "FR entries", value: "3", sub: "Today", accent: "#a78bfa" },
          { label: "Regulatory actions", value: "7", sub: "This week", accent: "#34d399" },
        ].map((s, i) => (
          <div key={i} style={{
            background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
            padding: "16px 20px", display: "flex", alignItems: "center", gap: 16,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `${s.accent}15`, border: `1px solid ${s.accent}30`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 18, fontWeight: 700, color: s.accent,
            }}>{s.value}</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0" }}>{s.label}</div>
              <div style={{ fontSize: 11, color: "#475569" }}>{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Tweets */}
        <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "#1d9bf0", fontSize: 16, fontWeight: 700 }}>𝕏</span>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>Tracked Accounts</h3>
          </div>
          {LIVE_FEED.filter(f => f.type === "tweet").map((f, i) => (
            <div key={i} style={{
              padding: "12px 0", borderBottom: "1px solid #1e293b", cursor: "pointer",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#1d9bf0" }}>{f.source}</span>
                <span style={{ fontSize: 10, color: "#475569" }}>{f.time}</span>
              </div>
              <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{f.text}</div>
            </div>
          ))}
        </div>

        {/* News & Regulatory */}
        <div style={{ background: "#111827", borderRadius: 10, border: "1px solid #1f2937", padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "#f59e0b", fontSize: 14 }}>◆</span>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>News & Regulatory</h3>
          </div>
          {LIVE_FEED.filter(f => f.type !== "tweet").map((f, i) => {
            const fc = FEED_COLORS[f.type];
            return (
              <div key={i} style={{
                padding: "12px 0", borderBottom: "1px solid #1e293b", cursor: "pointer",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: fc.accent, fontWeight: 700 }}>{f.icon}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: fc.accent }}>{f.source}</span>
                  <span style={{ fontSize: 10, color: "#475569", marginLeft: "auto" }}>{f.time}</span>
                </div>
                <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 }}>{f.text}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Section: Comments ───
function CommentsView() {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", marginBottom: 8, letterSpacing: "-0.02em" }}>
        Comment Analyzer
      </h2>
      <p style={{ fontSize: 13, color: "#64748b", marginBottom: 24 }}>
        Full comment analysis system — connects to the backend at cftc.stephenandrews.org
      </p>
      <div style={{
        background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
        padding: 60, textAlign: "center",
      }}>
        <div style={{ fontSize: 36, marginBottom: 16, opacity: 0.3 }}>✉</div>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#94a3b8" }}>Comment Analyzer Dashboard</div>
        <div style={{ fontSize: 12, color: "#475569", marginTop: 8, maxWidth: 400, margin: "8px auto 0" }}>
          Docket browser · Comment table · AI tiering & summarization · Briefing doc export · PDF downloads
        </div>
        <div style={{
          marginTop: 20, display: "inline-block", padding: "8px 20px", borderRadius: 6,
          background: "#1e3a5f", color: "#60a5fa", fontSize: 12, fontWeight: 600, cursor: "pointer",
        }}>Currently Live →</div>
      </div>
    </div>
  );
}

// ─── Placeholder ───
function PlaceholderView({ title, description, icon }) {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", marginBottom: 8, letterSpacing: "-0.02em" }}>{title}</h2>
      <p style={{ fontSize: 13, color: "#64748b", marginBottom: 24 }}>{description}</p>
      <div style={{
        background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
        padding: 60, textAlign: "center",
      }}>
        <div style={{ fontSize: 36, marginBottom: 16, opacity: 0.2 }}>{icon}</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#475569" }}>Coming Soon</div>
        <div style={{ fontSize: 12, color: "#334155", marginTop: 8 }}>This module will connect to your data pipeline</div>
      </div>
    </div>
  );
}

// ─── Main App ───
export default function CommandCenter() {
  const [active, setActive] = useState("summary");
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const renderSection = () => {
    switch (active) {
      case "summary": return <SummaryView />;
      case "eo": return <EOView />;
      case "team": return <TeamView />;
      case "pipeline": return <PipelineView />;
      case "comments": return <CommentsView />;
      case "intelligence": return <IntelligenceView />;
      case "interagency":
        return <PlaceholderView title="Interagency" description="Project Crypto workstreams, PWG deliverables, bilateral coordination." icon="⬡" />;
      case "research":
        return <PlaceholderView title="Research" description="Full-text search across the regulatory database. Loper Bright vulnerability scanner." icon="⊞" />;
      case "reports":
        return <PlaceholderView title="Reports" description="Weekly status generator, meeting prep builder, briefing templates." icon="⊟" />;
      default: return <SummaryView />;
    }
  };

  return (
    <div style={{
      display: "flex", height: "100vh", overflow: "hidden",
      fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
      background: "#0a0f1a",
      color: "#e2e8f0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #334155; }
      `}</style>

      {/* Sidebar */}
      <aside style={{
        width: 250, background: "#070b14",
        borderRight: "1px solid #1e293b",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        <div style={{ padding: "22px 18px 18px", borderBottom: "1px solid #1e293b" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg, #1e3a5f, #3b82f6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 700, color: "#fff",
            }}>C</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.01em" }}>
                Command Center
              </div>
              <div style={{ fontSize: 10, color: "#475569" }}>CFTC · Office of GC</div>
            </div>
          </div>
        </div>

        <nav style={{ padding: "10px 8px", flex: 1, overflowY: "auto" }}>
          {SECTIONS.map(s => {
            const isActive = active === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  width: "100%", padding: "9px 12px", borderRadius: 8,
                  background: isActive ? "rgba(59,130,246,0.12)" : "transparent",
                  color: isActive ? "#60a5fa" : "#64748b",
                  border: isActive ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
                  cursor: "pointer", fontSize: 13,
                  fontWeight: isActive ? 600 : 500, marginBottom: 2,
                  transition: "all 0.15s ease", textAlign: "left",
                }}
                onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.color = "#94a3b8"; }}}
                onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#64748b"; }}}
              >
                <span style={{ fontSize: 14, width: 20, textAlign: "center" }}>{s.icon}</span>
                <span style={{ flex: 1 }}>{s.label}</span>
                {s.id === "eo" && (
                  <span style={{
                    background: "#7f1d1d", color: "#fca5a5", borderRadius: 10,
                    padding: "1px 7px", fontSize: 9, fontWeight: 700,
                  }}>4</span>
                )}
                {s.id === "intelligence" && <Pulse color="#22c55e" />}
                {s.id === "comments" && (
                  <span style={{
                    background: "#172554", color: "#60a5fa", borderRadius: 10,
                    padding: "1px 7px", fontSize: 9, fontWeight: 700,
                  }}>819</span>
                )}
              </button>
            );
          })}
        </nav>

        <div style={{
          padding: "14px 16px", borderTop: "1px solid #1e293b", fontSize: 11,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: "linear-gradient(135deg, #1e3a5f, #2563eb)",
              color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700,
            }}>SA</div>
            <div>
              <div style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 12 }}>S. Andrews</div>
              <div style={{ color: "#475569", fontSize: 10 }}>Deputy GC, Regulation</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflow: "auto", padding: "28px 36px" }}>
        {renderSection()}
      </main>
    </div>
  );
}
