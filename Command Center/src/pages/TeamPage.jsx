import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../styles/theme";
import Modal from "../components/shared/Modal";
import Badge from "../components/shared/Badge";
import { useApi } from "../hooks/useApi";
import { useToastContext } from "../contexts/ToastContext";
import { listTeam, getTeamDashboard, getMemberWorkload, createTeamMember, updateTeamMember, deleteTeamMember } from "../api/pipeline";

const inputStyle = {
  width: "100%", padding: "8px 12px", borderRadius: 6,
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  color: theme.text.secondary, fontSize: 13, outline: "none",
  fontFamily: theme.font.family,
};

const CAPACITY_COLORS = {
  available: { bg: "#052e16", text: "#4ade80" },
  stretched: { bg: "#422006", text: "#fbbf24" },
  at_capacity: { bg: "#431407", text: "#fb923c" },
  overloaded: { bg: "#450a0a", text: "#f87171" },
  on_leave: { bg: "#1e1b4b", text: "#a78bfa" },
};

const WORKING_STYLES = ["detail_oriented", "big_picture", "balanced", "methodical", "creative"];
const COMM_PREFS = ["email", "slack", "in_person", "phone"];
const CAPACITY_LEVELS = ["available", "stretched", "at_capacity", "overloaded", "on_leave"];

const EMPTY_FORM = {
  name: "", role: "Attorney-Adviser", gs_level: "GS-13",
  email: "", division: "", specializations: "", max_concurrent: 5,
  background_summary: "", working_style: "balanced", communication_preference: "email",
  current_capacity: "available", strengths: "", growth_areas: "", personal_context: "",
};

export default function TeamPage() {
  const navigate = useNavigate();
  const toast = useToastContext();
  const { data: team, refetch: refetchTeam } = useApi(() => listTeam(), []);
  const { data: dashboard } = useApi(() => getTeamDashboard(), []);
  const [showAdd, setShowAdd] = useState(false);
  const [showEdit, setShowEdit] = useState(null); // member object or null
  const [expandedId, setExpandedId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Workload for expanded member
  const { data: workload } = useApi(
    () => (expandedId ? getMemberWorkload(expandedId) : Promise.resolve(null)),
    [expandedId]
  );

  const handleAdd = async () => {
    setSaving(true);
    try {
      await createTeamMember({
        name: form.name,
        role: form.role,
        gs_level: form.gs_level,
        email: form.email || undefined,
        division: form.division || undefined,
        specializations: form.specializations ? form.specializations.split(",").map((s) => s.trim()) : undefined,
        max_concurrent: Number(form.max_concurrent) || 5,
        background_summary: form.background_summary || undefined,
        working_style: form.working_style || undefined,
        communication_preference: form.communication_preference || undefined,
        current_capacity: form.current_capacity || undefined,
        strengths: form.strengths ? form.strengths.split(",").map((s) => s.trim()) : undefined,
        growth_areas: form.growth_areas ? form.growth_areas.split(",").map((s) => s.trim()) : undefined,
        personal_context: form.personal_context || undefined,
      });
      setShowAdd(false);
      setForm({ ...EMPTY_FORM });
      toast.success("Team member added");
      refetchTeam();
    } catch (err) {
      toast.error("Failed to add member: " + (err.message || "Unknown error"));
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async () => {
    if (!showEdit) return;
    setSaving(true);
    try {
      await updateTeamMember(showEdit.id, {
        name: editForm.name,
        role: editForm.role,
        gs_level: editForm.gs_level,
        email: editForm.email || undefined,
        division: editForm.division || undefined,
        specializations: editForm.specializations ? editForm.specializations.split(",").map((s) => s.trim()) : undefined,
        max_concurrent: Number(editForm.max_concurrent) || 5,
        background_summary: editForm.background_summary || undefined,
        working_style: editForm.working_style || undefined,
        communication_preference: editForm.communication_preference || undefined,
        current_capacity: editForm.current_capacity || undefined,
        strengths: editForm.strengths ? editForm.strengths.split(",").map((s) => s.trim()) : undefined,
        growth_areas: editForm.growth_areas ? editForm.growth_areas.split(",").map((s) => s.trim()) : undefined,
        personal_context: editForm.personal_context || undefined,
      });
      setShowEdit(null);
      toast.success("Team member updated");
      refetchTeam();
    } catch (err) {
      toast.error("Failed to update member: " + (err.message || "Unknown error"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (member) => {
    if (!window.confirm(`Remove ${member.name} from the team? They will be marked inactive.`)) return;
    try {
      await deleteTeamMember(member.id);
      toast.success(`${member.name} removed`);
      setShowEdit(null);
      setExpandedId(null);
      refetchTeam();
    } catch (err) {
      toast.error("Failed to remove member: " + (err.message || "Unknown error"));
    }
  };

  const openEdit = (member) => {
    setEditForm({
      name: member.name || "",
      role: member.role || "Attorney-Adviser",
      gs_level: member.gs_level || "GS-13",
      email: member.email || "",
      division: member.division || "",
      specializations: Array.isArray(member.specializations) ? member.specializations.join(", ") : (member.specializations || ""),
      max_concurrent: member.max_concurrent || 5,
      background_summary: member.background_summary || "",
      working_style: member.working_style || "balanced",
      communication_preference: member.communication_preference || "email",
      current_capacity: member.current_capacity || "available",
      strengths: Array.isArray(member.strengths) ? member.strengths.join(", ") : (member.strengths || ""),
      growth_areas: Array.isArray(member.growth_areas) ? member.growth_areas.join(", ") : (member.growth_areas || ""),
      personal_context: member.personal_context || "",
    });
    setShowEdit(member);
  };

  const members = team || [];
  const dashMembers = dashboard?.members || [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0, letterSpacing: "-0.02em" }}>
            Team — Regulation Division
          </h2>
          <p style={{ fontSize: 13, color: theme.text.faint, marginTop: 4 }}>
            {members.length} members
            {dashboard ? ` · ${dashboard.total_active_items} active items · ${dashboard.total_overdue} overdue` : ""}
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          style={{
            padding: "8px 16px", borderRadius: 6, border: "none",
            background: theme.accent.blue, color: "#fff",
            fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
        >+ Add Member</button>
      </div>

      {/* Capacity overview bar */}
      {dashMembers.length > 0 && (
        <div style={{
          background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
          padding: "16px 20px", marginBottom: 20,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            Team Capacity
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {dashMembers.map((d, i) => {
              const member = members.find((m) => m.id === d.id);
              const max = member?.max_concurrent || d.max_concurrent || 5;
              const active = d.active_items || 0;
              const pct = Math.min((active / max) * 100, 100);
              const color = pct >= 90 ? theme.accent.red : pct >= 70 ? theme.accent.yellow : theme.accent.green;
              return (
                <div key={d.id} style={{ flex: "1 1 120px", minWidth: 100 }}>
                  <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {member?.name || d.name}
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "#1f2937", overflow: "hidden" }}>
                    <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color, transition: "width 0.3s" }} />
                  </div>
                  <div style={{ fontSize: 9, color: theme.text.faint, marginTop: 2 }}>
                    {active}/{max}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Member cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
        {members.map((t, i) => {
          const dash = dashMembers.find((d) => d.id === t.id) || {};
          const isExpanded = expandedId === t.id;
          return (
            <div key={t.id} style={{ gridColumn: isExpanded ? "1 / -1" : undefined }}>
              <div
                onClick={() => setExpandedId(isExpanded ? null : t.id)}
                style={{
                  background: theme.bg.card, borderRadius: 10, border: `1px solid ${isExpanded ? theme.border.active : theme.border.default}`,
                  padding: 20, display: "flex", gap: 16, alignItems: "flex-start",
                  cursor: "pointer", transition: "border-color 0.15s",
                }}
              >
                <div style={{
                  width: 44, height: 44, borderRadius: 10,
                  background: `hsl(${i * 36 + 200}, 45%, 22%)`,
                  color: `hsl(${i * 36 + 200}, 65%, 72%)`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 14, fontWeight: 700, flexShrink: 0,
                }}>
                  {t.name.split(" ").map((n) => n[0]).join("")}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, color: theme.text.primary, fontSize: 14 }}>{t.name}</div>
                  <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 2 }}>
                    {t.role} · {t.gs_level || ""}
                    {t.email ? ` · ${t.email}` : ""}
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                    {t.current_capacity && (
                      <span style={{
                        padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: (CAPACITY_COLORS[t.current_capacity] || CAPACITY_COLORS.available).bg,
                        color: (CAPACITY_COLORS[t.current_capacity] || CAPACITY_COLORS.available).text,
                      }}>{(t.current_capacity || "available").replace(/_/g, " ")}</span>
                    )}
                    <span style={{
                      padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                      background: "#172554", color: theme.accent.blueLight,
                    }}>{dash.active_items || 0} active</span>
                    {(dash.overdue_deadlines || 0) > 0 && (
                      <span style={{
                        padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: "#450a0a", color: theme.accent.redLight,
                      }}>{dash.overdue_deadlines} overdue</span>
                    )}
                    <span style={{
                      padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                      background: "#1f2937", color: theme.text.muted,
                    }}>{dash.capacity_remaining ?? (t.max_concurrent || 5)} capacity</span>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); openEdit(t); }}
                  style={{
                    padding: "5px 12px", borderRadius: 5, border: `1px solid ${theme.border.default}`,
                    background: "transparent", color: theme.text.dim, fontSize: 11,
                    fontWeight: 600, cursor: "pointer",
                  }}
                >Edit</button>
              </div>

              {/* Expanded workload detail */}
              {isExpanded && (
                <div style={{
                  background: theme.bg.cardHover, borderRadius: "0 0 10px 10px",
                  border: `1px solid ${theme.border.active}`, borderTop: "none",
                  padding: 20,
                }}>
                  {/* Profile section */}
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 10 }}>
                      Profile
                    </div>
                    {t.background_summary && (
                      <div style={{ fontSize: 12, color: theme.text.secondary, marginBottom: 10, lineHeight: 1.5 }}>
                        {t.background_summary}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                      {t.working_style && (
                        <span style={{ padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: "#172554", color: "#60a5fa" }}>
                          {t.working_style.replace(/_/g, " ")}
                        </span>
                      )}
                      {t.communication_preference && (
                        <span style={{ padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: "#1e1b4b", color: "#a78bfa" }}>
                          prefers {t.communication_preference.replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                    {Array.isArray(t.strengths) && t.strengths.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontSize: 10, fontWeight: 600, color: theme.text.faint }}>STRENGTHS: </span>
                        {t.strengths.map((s, i) => (
                          <span key={i} style={{ padding: "2px 8px", borderRadius: 4, fontSize: 10, background: "#052e16", color: "#4ade80", marginRight: 4 }}>{s}</span>
                        ))}
                      </div>
                    )}
                    {Array.isArray(t.growth_areas) && t.growth_areas.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontSize: 10, fontWeight: 600, color: theme.text.faint }}>GROWTH AREAS: </span>
                        {t.growth_areas.map((g, i) => (
                          <span key={i} style={{ padding: "2px 8px", borderRadius: 4, fontSize: 10, background: "#422006", color: "#fbbf24", marginRight: 4 }}>{g}</span>
                        ))}
                      </div>
                    )}
                    {t.personal_context && (
                      <div style={{ fontSize: 11, color: theme.text.dim, fontStyle: "italic", marginTop: 6 }}>
                        {t.personal_context}
                      </div>
                    )}
                  </div>

                  {!workload ? (
                    <div style={{ color: theme.text.dim, fontSize: 12 }}>Loading workload...</div>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                      {/* Active items */}
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 10 }}>
                          Active Items ({workload.items?.length || 0})
                        </div>
                        {(workload.items || []).length === 0 ? (
                          <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic" }}>No active items</div>
                        ) : (
                          (workload.items || []).map((item) => (
                            <div
                              key={item.id}
                              onClick={() => {
                                const path = item.module === "regulatory_action" ? "regulatory" : "pipeline";
                                navigate(`/${path}/${item.id}`);
                              }}
                              style={{
                                padding: "8px 12px", marginBottom: 4, borderRadius: 6,
                                background: theme.bg.card, border: `1px solid ${theme.border.default}`,
                                cursor: "pointer", fontSize: 12, color: theme.text.secondary,
                                transition: "border-color 0.15s",
                              }}
                            >
                              <div style={{ fontWeight: 600 }}>{item.title || item.short_title}</div>
                              <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 2 }}>
                                {item.current_stage || "—"} · {item.item_type || ""}
                              </div>
                            </div>
                          ))
                        )}
                      </div>

                      {/* Deadlines */}
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 10 }}>
                          Upcoming Deadlines
                        </div>
                        {(workload.overdue_deadlines || 0) > 0 && (
                          <div style={{ marginBottom: 8 }}>
                            <div style={{
                              padding: "6px 10px", borderRadius: 4,
                              background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
                              fontSize: 11, fontWeight: 600, color: theme.accent.redLight,
                            }}>
                              {workload.overdue_deadlines} overdue deadline{workload.overdue_deadlines !== 1 ? "s" : ""}
                            </div>
                          </div>
                        )}
                        {(workload.upcoming_deadlines || []).length === 0 && !workload.overdue_deadlines ? (
                          <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic" }}>No deadlines</div>
                        ) : (
                          (workload.upcoming_deadlines || []).map((dl, i) => (
                            <div key={i} style={{
                              padding: "6px 10px", marginBottom: 3, borderRadius: 4,
                              background: theme.bg.card, border: `1px solid ${theme.border.default}`,
                              fontSize: 11, color: theme.text.dim,
                            }}>
                              {dl.title} — {dl.due_date}
                            </div>
                          ))
                        )}

                        {/* Capacity bar */}
                        <div style={{ marginTop: 16 }}>
                          <div style={{ fontSize: 10, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>CAPACITY</div>
                          {(() => {
                            const max = t.max_concurrent || 5;
                            const active = workload.items?.length || 0;
                            const pct = Math.min((active / max) * 100, 100);
                            const color = pct >= 90 ? theme.accent.red : pct >= 70 ? theme.accent.yellow : theme.accent.green;
                            return (
                              <div>
                                <div style={{ height: 8, borderRadius: 4, background: "#1f2937", overflow: "hidden" }}>
                                  <div style={{ width: `${pct}%`, height: "100%", borderRadius: 4, background: color }} />
                                </div>
                                <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 3 }}>
                                  {active} of {max} slots used ({Math.round(pct)}%)
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Add Member Modal */}
      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add Team Member" width={560}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Name *</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={inputStyle} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Role</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                <option>Assistant General Counsel</option>
                <option>Senior Counsel</option>
                <option>Attorney-Adviser</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>GS Level</label>
              <select value={form.gs_level} onChange={(e) => setForm({ ...form, gs_level: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {["GS-15", "GS-14", "GS-13", "GS-12", "GS-11"].map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Email</label>
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="email@cftc.gov" style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Division</label>
              <input value={form.division} onChange={(e) => setForm({ ...form, division: e.target.value })} placeholder="e.g., Regulation" style={inputStyle} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Specializations</label>
              <input value={form.specializations} onChange={(e) => setForm({ ...form, specializations: e.target.value })} placeholder="Comma-separated, e.g., DCMs, Clearing, SDRs" style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Max Concurrent</label>
              <input type="number" value={form.max_concurrent} onChange={(e) => setForm({ ...form, max_concurrent: e.target.value })} min={1} max={20} style={{ ...inputStyle, width: 80 }} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Background Summary</label>
            <textarea value={form.background_summary} onChange={(e) => setForm({ ...form, background_summary: e.target.value })} placeholder="Brief professional background" style={{ ...inputStyle, minHeight: 50, resize: "vertical" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Working Style</label>
              <select value={form.working_style} onChange={(e) => setForm({ ...form, working_style: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {WORKING_STYLES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Communication</label>
              <select value={form.communication_preference} onChange={(e) => setForm({ ...form, communication_preference: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {COMM_PREFS.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Capacity</label>
              <select value={form.current_capacity} onChange={(e) => setForm({ ...form, current_capacity: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {CAPACITY_LEVELS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Strengths</label>
              <input value={form.strengths} onChange={(e) => setForm({ ...form, strengths: e.target.value })} placeholder="Comma-separated" style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Growth Areas</label>
              <input value={form.growth_areas} onChange={(e) => setForm({ ...form, growth_areas: e.target.value })} placeholder="Comma-separated" style={inputStyle} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Personal Context</label>
            <input value={form.personal_context} onChange={(e) => setForm({ ...form, personal_context: e.target.value })} placeholder="e.g., prefers morning meetings" style={inputStyle} />
          </div>
          <button
            onClick={handleAdd}
            disabled={!form.name || saving}
            style={{
              padding: "10px 20px", borderRadius: 6, border: "none",
              background: form.name && !saving ? theme.accent.blue : "#1f2937",
              color: form.name && !saving ? "#fff" : theme.text.dim,
              fontSize: 13, fontWeight: 600,
              cursor: form.name && !saving ? "pointer" : "not-allowed",
            }}
          >{saving ? "Adding..." : "Add Member"}</button>
        </div>
      </Modal>

      {/* Edit Member Modal */}
      <Modal isOpen={!!showEdit} onClose={() => setShowEdit(null)} title="Edit Team Member" width={560}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Name *</label>
            <input value={editForm.name || ""} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} style={inputStyle} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Role</label>
              <select value={editForm.role || ""} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                <option>Assistant General Counsel</option>
                <option>Senior Counsel</option>
                <option>Attorney-Adviser</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>GS Level</label>
              <select value={editForm.gs_level || ""} onChange={(e) => setEditForm({ ...editForm, gs_level: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {["GS-15", "GS-14", "GS-13", "GS-12", "GS-11"].map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Email</label>
              <input value={editForm.email || ""} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Division</label>
              <input value={editForm.division || ""} onChange={(e) => setEditForm({ ...editForm, division: e.target.value })} style={inputStyle} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Specializations</label>
              <input value={editForm.specializations || ""} onChange={(e) => setEditForm({ ...editForm, specializations: e.target.value })} placeholder="Comma-separated" style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Max Concurrent</label>
              <input type="number" value={editForm.max_concurrent || 5} onChange={(e) => setEditForm({ ...editForm, max_concurrent: e.target.value })} min={1} max={20} style={{ ...inputStyle, width: 80 }} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Background Summary</label>
            <textarea value={editForm.background_summary || ""} onChange={(e) => setEditForm({ ...editForm, background_summary: e.target.value })} placeholder="Brief professional background" style={{ ...inputStyle, minHeight: 50, resize: "vertical" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Working Style</label>
              <select value={editForm.working_style || "balanced"} onChange={(e) => setEditForm({ ...editForm, working_style: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {WORKING_STYLES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Communication</label>
              <select value={editForm.communication_preference || "email"} onChange={(e) => setEditForm({ ...editForm, communication_preference: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {COMM_PREFS.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Capacity</label>
              <select value={editForm.current_capacity || "available"} onChange={(e) => setEditForm({ ...editForm, current_capacity: e.target.value })} style={{ ...inputStyle, cursor: "pointer" }}>
                {CAPACITY_LEVELS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Strengths</label>
              <input value={editForm.strengths || ""} onChange={(e) => setEditForm({ ...editForm, strengths: e.target.value })} placeholder="Comma-separated" style={inputStyle} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Growth Areas</label>
              <input value={editForm.growth_areas || ""} onChange={(e) => setEditForm({ ...editForm, growth_areas: e.target.value })} placeholder="Comma-separated" style={inputStyle} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Personal Context</label>
            <input value={editForm.personal_context || ""} onChange={(e) => setEditForm({ ...editForm, personal_context: e.target.value })} placeholder="e.g., prefers morning meetings" style={inputStyle} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button
              onClick={() => handleDelete(showEdit)}
              style={{
                padding: "10px 20px", borderRadius: 6, border: `1px solid rgba(239,68,68,0.3)`,
                background: "transparent", color: theme.accent.red,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >Remove</button>
            <button
              onClick={handleEdit}
              disabled={!editForm.name || saving}
              style={{
                padding: "10px 20px", borderRadius: 6, border: "none",
                background: editForm.name && !saving ? theme.accent.blue : "#1f2937",
                color: editForm.name && !saving ? "#fff" : theme.text.dim,
                fontSize: 13, fontWeight: 600,
                cursor: editForm.name && !saving ? "pointer" : "not-allowed",
              }}
            >{saving ? "Saving..." : "Save Changes"}</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
