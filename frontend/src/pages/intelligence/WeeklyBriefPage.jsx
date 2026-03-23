import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { fetchJSON } from "../../api/client";

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

function ScoreCircle({ score, label, size = 48 }) {
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#f97316" : "#ef4444";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: size, fontWeight: 700, color }}>{score}%</div>
      <div style={{ fontSize: 12, color: theme.text.muted }}>{label}</div>
    </div>
  );
}

function MatterRow({ m, onClick }) {
  const dl = m.nearest_deadline || "no deadline";
  const owner = m.next_step_owner || "no owner";
  return (
    <div style={{
      padding: "6px 0", borderBottom: `1px solid ${theme.border.default}`,
      fontSize: 13, cursor: onClick ? "pointer" : "default",
    }} onClick={onClick}>
      <span style={{ fontWeight: 500 }}>{m.title}</span>
      <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 2 }}>
        {m.status} {"\u2022"} {dl} {"\u2022"} {owner}
      </div>
    </div>
  );
}

export default function WeeklyBriefPage() {
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
      const result = await fetchJSON(`/ai/api/intelligence/briefs/by-date/weekly/${dateStr}`);
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
      const result = await fetchJSON("/ai/api/intelligence/briefs?brief_type=weekly&limit=20");
      setBriefList(result.items || []);
    } catch (e) { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchBrief(selectedDate);
    fetchList();
  }, [selectedDate, fetchBrief, fetchList]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await fetchJSON("/ai/api/intelligence/generate?brief_type=weekly", { method: "POST" });
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, color: theme.text.primary }}>Weekly Brief</h1>
          <div style={{ fontSize: 13, color: theme.text.faint, marginTop: 4 }}>
            Management and strategic steering
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)}
            style={{ background: theme.bg.input, border: `1px solid ${theme.border.default}`, borderRadius: 6, padding: "6px 10px", color: theme.text.primary, fontSize: 13 }} />
          <button onClick={handleGenerate} disabled={generating}
            style={{ background: theme.accent.blue, color: "#fff", border: "none", borderRadius: 6, padding: "7px 14px", fontSize: 13, fontWeight: 500, cursor: generating ? "wait" : "pointer", opacity: generating ? 0.6 : 1 }}>
            {generating ? "Generating..." : "Generate Now"}
          </button>
        </div>
      </div>

      {briefList.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
          {briefList.slice(0, 10).map((b) => (
            <button key={b.id} onClick={() => setSelectedDate(b.brief_date)}
              style={{ background: b.brief_date === selectedDate ? theme.accent.blue : theme.bg.input, color: b.brief_date === selectedDate ? "#fff" : theme.text.muted, border: `1px solid ${b.brief_date === selectedDate ? theme.accent.blue : theme.border.default}`, borderRadius: 4, padding: "3px 10px", fontSize: 11, cursor: "pointer" }}>
              {b.brief_date}
            </button>
          ))}
        </div>
      )}

      {loading && <div style={{ color: theme.text.faint, padding: 40, textAlign: "center" }}>Loading...</div>}
      {error && <div style={{ color: "#f87171", padding: 16 }}>{error}</div>}

      {!loading && !hasData && (
        <div style={{ background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, padding: 40, textAlign: "center" }}>
          <div style={{ fontSize: 15, color: theme.text.muted, marginBottom: 12 }}>No weekly brief for {selectedDate}</div>
          <button onClick={handleGenerate} disabled={generating}
            style={{ background: theme.accent.blue, color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", fontSize: 13, cursor: "pointer" }}>
            Generate Weekly Brief
          </button>
        </div>
      )}

      {!loading && hasData && (
        <>
          <div style={{ textAlign: "center", padding: "8px 0 20px", fontSize: 18, fontWeight: 600, color: theme.text.primary }}>
            {data.date_display || selectedDate}
          </div>

          {/* Calibration */}
          <Section title="What I Got Wrong" icon={"\uD83C\uDFAF"}>
            {data.calibration?.has_data ? (
              <div>
                <ScoreCircle score={data.calibration.score} label="Signal Quality" />
                <div style={{ display: "flex", justifyContent: "center", gap: 24, marginTop: 16, fontSize: 13 }}>
                  <div><span style={{ color: "#ef4444", fontWeight: 600 }}>{data.calibration.materialized}</span> materialized</div>
                  <div><span style={{ color: "#22c55e", fontWeight: 600 }}>{data.calibration.resolved}</span> resolved</div>
                  <div><span style={{ color: theme.text.muted, fontWeight: 600 }}>{data.calibration.still_open}</span> still open</div>
                  <div><span style={{ color: "#f97316", fontWeight: 600 }}>{data.calibration.wrong}</span> wrong</div>
                </div>
              </div>
            ) : (
              <EmptyLine message={data.calibration?.message || "No calibration data."} />
            )}
          </Section>

          {/* Executive Summary */}
          <Section title="Executive Summary" icon={"\uD83D\uDCDD"}>
            {data.executive_summary ? (
              <div style={{ fontSize: 14, lineHeight: 1.6, color: theme.text.primary }}>{data.executive_summary}</div>
            ) : (
              <EmptyLine message="Executive summary not generated." />
            )}
          </Section>

          {/* Portfolio Health */}
          <Section title="Portfolio Health" icon={"\uD83D\uDCCA"} count={data.portfolio?.total_active}>
            {[
              { key: "critical", label: "Critical This Week", color: "#ef4444" },
              { key: "important", label: "Important This Month", color: "#f97316" },
              { key: "strategic", label: "Strategic / Slow Burn", color: theme.accent.blue },
              { key: "monitoring", label: "Monitoring", color: theme.text.faint },
            ].map(({ key, label, color }) => {
              const items = data.portfolio?.[key] || [];
              if (!items.length) return null;
              return (
                <div key={key} style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                    {label} ({items.length})
                  </div>
                  {items.map((m, i) => (
                    <MatterRow key={i} m={m} onClick={() => navigate(`/matters/${m.id}`)} />
                  ))}
                </div>
              );
            })}
            {!data.portfolio?.total_active && <EmptyLine message="No active matters." />}
          </Section>

          {/* Decision Docket */}
          <Section title="Decision Docket" icon={"\u2696\uFE0F"} count={data.decisions?.length}>
            {(data.decisions || []).length > 0 ? data.decisions.map((d, i) => (
              <div key={i} style={{ padding: "6px 0", borderBottom: `1px solid ${theme.border.default}`, fontSize: 13 }}>
                <span style={{ fontWeight: 500 }}>{d.title}</span>
                <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 2 }}>
                  {d.matter_title} {"\u2022"} {d.decision_owner || "unassigned"} {"\u2022"} Due: {d.due_date || "no date"} {"\u2022"} {d.status}
                </div>
              </div>
            )) : <EmptyLine message="No open decisions." />}
          </Section>

          {/* Team View */}
          <Section title="Team Management" icon={"\uD83D\uDC65"}>
            {(data.team?.workload || []).length > 0 ? (
              <div>
                {data.team.workload.sort((a, b) => (b.overdue || 0) - (a.overdue || 0)).map((w, i) => (
                  <div key={i} style={{ padding: "4px 0", fontSize: 13 }}>
                    <span style={{ fontWeight: 500 }}>{w.name}</span>
                    {" \u2014 "}{w.open_tasks} tasks, {w.open_matters} matters
                    {w.overdue > 0 && <span style={{ color: "#ef4444", fontSize: 11 }}> ({w.overdue} overdue)</span>}
                  </div>
                ))}
                {(data.team.drifting_matters || []).length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#f97316", marginBottom: 4 }}>Drifting Matters</div>
                    {data.team.drifting_matters.map((dm, i) => (
                      <div key={i} style={{ fontSize: 12, color: theme.text.muted, padding: "2px 0" }}>
                        {dm.title} {"\u2014"} {dm.days_stale}d stale {"\u2014"} {dm.owner}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : <EmptyLine message="No team data." />}
          </Section>

          {/* Stakeholders */}
          <Section title="Stakeholders" icon={"\uD83E\uDD1D"}>
            {(data.stakeholders?.touchpoints_due || []).length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: theme.accent.blue, marginBottom: 6 }}>Touchpoints Due</div>
                {data.stakeholders.touchpoints_due.map((tp, i) => (
                  <div key={i} style={{ padding: "4px 0", fontSize: 13, borderBottom: `1px solid ${theme.border.default}`, cursor: "pointer" }}
                    onClick={() => tp.person_id && navigate(`/people/${tp.person_id}`)}>
                    <span style={{ fontWeight: 500 }}>{tp.name}</span>
                    <span style={{ color: theme.text.muted, fontSize: 12, marginLeft: 6 }}>{tp.organization}</span>
                    <div style={{ fontSize: 11, color: theme.text.muted }}>{tp.next_date} {"\u2022"} {tp.purpose}</div>
                  </div>
                ))}
              </div>
            )}
            {(data.stakeholders?.neglected || []).length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#f97316", marginBottom: 6 }}>Neglected Relationships</div>
                {data.stakeholders.neglected.map((n, i) => (
                  <div key={i} style={{ fontSize: 12, color: theme.text.muted, padding: "2px 0" }}>
                    {n.name} ({n.category}) {"\u2014"} {n.days_since} days since last contact
                  </div>
                ))}
              </div>
            )}
            {!(data.stakeholders?.touchpoints_due?.length) && !(data.stakeholders?.neglected?.length) && (
              <EmptyLine message="No stakeholder actions needed." />
            )}
          </Section>

          {/* Deadlines */}
          <Section title="Deadlines & Horizon" icon={"\uD83D\uDCC6"}>
            {[
              { key: "two_weeks", label: "Next 2 Weeks" },
              { key: "thirty_days", label: "Next 30 Days" },
              { key: "ninety_days", label: "Next 90 Days" },
            ].map(({ key, label }) => {
              const items = data.deadlines?.[key] || [];
              if (!items.length) return null;
              return (
                <div key={key} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.accent.blue, marginBottom: 4 }}>{label} ({items.length})</div>
                  {items.map((item, i) => (
                    <div key={i} style={{ fontSize: 12, color: theme.text.muted, padding: "2px 0" }}>
                      {item.date} {"\u2022"} {item.deadline_type} {"\u2022"} {item.matter_title} {"\u2022"} {item.owner}
                    </div>
                  ))}
                </div>
              );
            })}
            {!data.deadlines?.two_weeks?.length && !data.deadlines?.thirty_days?.length && !data.deadlines?.ninety_days?.length && (
              <EmptyLine message="No upcoming deadlines." />
            )}
          </Section>

          {/* Documents */}
          <Section title="Documents Pipeline" icon={"\uD83D\uDCC4"}>
            {Object.keys(data.documents || {}).length > 0 ? (
              Object.entries(data.documents).map(([status, items]) => (
                <div key={status} style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.muted, marginBottom: 3 }}>{status} ({items.length})</div>
                  {items.map((d, i) => (
                    <div key={i} style={{ fontSize: 12, color: theme.text.muted, padding: "2px 0" }}>{d.title}</div>
                  ))}
                </div>
              ))
            ) : <EmptyLine message="No documents tracked." />}
          </Section>

          {/* Risks */}
          <Section title="Risk Register" icon={"\u26A0\uFE0F"} count={data.risks?.high_sensitivity?.length}>
            {(data.risks?.high_sensitivity || []).length > 0 ? data.risks.high_sensitivity.map((r, i) => (
              <div key={i} style={{ padding: "4px 0", fontSize: 13, borderBottom: `1px solid ${theme.border.default}` }}>
                <span style={{ fontWeight: 500 }}>{r.title}</span>
                <div style={{ fontSize: 11, color: theme.text.muted }}>{r.sensitivity} {"\u2022"} {r.status} {"\u2022"} Boss: {r.boss_involvement || "none"}</div>
              </div>
            )) : <EmptyLine message="No high-sensitivity items." />}
          </Section>

          {/* Data Hygiene */}
          <Section title="Data Hygiene" icon={"\uD83E\uDDF9"}>
            <ScoreCircle score={data.hygiene?.score || 0} label="Tracker Health" size={48} />
            {(data.hygiene?.checks || []).length > 0 && (
              <div style={{ marginTop: 16 }}>
                {data.hygiene.checks.sort((a, b) => a.pct - b.pct).map((c, i) => {
                  const barColor = c.pct >= 80 ? "#22c55e" : c.pct >= 50 ? "#f97316" : "#ef4444";
                  const field = (c.field || "").replace(".", " \u2192 ");
                  return (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 12 }}>
                      <span style={{ width: 180, color: theme.text.muted }}>{field}</span>
                      <div style={{ flex: 1, height: 6, background: theme.border.default, borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${c.pct}%`, height: "100%", background: barColor, borderRadius: 3 }} />
                      </div>
                      <span style={{ width: 60, textAlign: "right", color: theme.text.muted }}>{c.count}/{c.total}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>

          <div style={{ textAlign: "center", padding: "16px 0", fontSize: 11, color: theme.text.faint }}>
            Generated {brief.created_at?.slice(0, 19)} {brief.model_used ? `\u2022 Model: ${brief.model_used}` : ""}
          </div>
        </>
      )}
    </div>
  );
}
