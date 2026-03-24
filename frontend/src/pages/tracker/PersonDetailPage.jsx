import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import { getPerson, deletePerson, getPersonProfile, getContextNotesByEntity } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import { useDrawer } from "../../contexts/DrawerContext";
import EmptyState from "../../components/shared/EmptyState";
import Breadcrumb from "../../components/shared/Breadcrumb";

/* ── Styles ──────────────────────────────────────────────────── */

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 20,
};

const sidebarCardStyle = {
  ...cardStyle,
  background: theme.bg.input,
};

const sectionLabel = {
  fontSize: 11,
  fontWeight: 700,
  color: theme.text.faint,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 12,
};

const fieldLabel = {
  fontSize: 12,
  fontWeight: 600,
  color: theme.text.secondary,
};

const fieldValue = {
  fontSize: 13,
  color: theme.text.muted,
  marginTop: 1,
};

const btnPrimary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};

const btnSecondary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: "transparent", color: theme.text.muted,
  border: `1px solid ${theme.border.default}`, cursor: "pointer",
};

/* ── Badge color maps ────────────────────────────────────────── */

const CATEGORY_COLORS = {
  "Boss":                 { bg: "#3b1f6e", text: "#a78bfa" },
  "Leadership":           { bg: "#3b1f6e", text: "#a78bfa" },
  "Direct report":        { bg: "#1e3a5f", text: "#60a5fa" },
  "OGC peer":             { bg: "#1a4731", text: "#34d399" },
  "Internal client":      { bg: "#1a4731", text: "#34d399" },
  "Commissioner office":  { bg: "#3b1f6e", text: "#a78bfa" },
  "Partner agency":       { bg: "#1a3a4a", text: "#38bdf8" },
  "Hill":                 { bg: "#4a3728", text: "#fbbf24" },
  "Outside party":        { bg: "#3a2a3a", text: "#c084fc" },
};

const LANE_COLORS = {
  "Decision-maker": { bg: "#4a2020", text: "#f87171" },
  "Recommender":    { bg: "#4a3728", text: "#fbbf24" },
  "Drafter":        { bg: "#1e3a5f", text: "#60a5fa" },
  "Blocker":        { bg: "#4a2020", text: "#f87171" },
  "Influencer":     { bg: "#3b1f6e", text: "#a78bfa" },
  "FYI only":       { bg: "#2a2a2a", text: "#9ca3af" },
};

const STATUS_COLORS = {
  "not started":    { bg: "#2a2a2a", text: "#9ca3af" },
  "in progress":    { bg: "#1e3a5f", text: "#60a5fa" },
  "needs review":   { bg: "#4a3728", text: "#fbbf24" },
  "blocked":        { bg: "#4a2020", text: "#f87171" },
  "waiting":        { bg: "#3b1f6e", text: "#a78bfa" },
  "completed":      { bg: "#1a4731", text: "#34d399" },
  "done":           { bg: "#1a4731", text: "#34d399" },
};

const ENGAGEMENT_COLORS = {
  "Core":       { bg: "#1e3a5f", text: "#60a5fa" },
  "Consulted":  { bg: "#3b1f6e", text: "#a78bfa" },
  "Informed":   { bg: "#2a2a2a", text: "#9ca3af" },
  "FYI":        { bg: "#2a2a2a", text: "#9ca3af" },
};

/* ── Helpers ─────────────────────────────────────────────────── */

function SmallBadge({ label, colorMap }) {
  const c = colorMap?.[label] || { bg: theme.bg.input, text: theme.text.faint };
  return (
    <span style={{
      background: c.bg, color: c.text,
      padding: "2px 8px", borderRadius: 10,
      fontSize: 11, fontWeight: 500, whiteSpace: "nowrap",
    }}>
      {label || "\u2014"}
    </span>
  );
}

function timeAgo(d) {
  if (!d) return "\u2014";
  const now = new Date();
  const then = new Date(d);
  const diffDays = Math.floor((now - then) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 14) return "1 week ago";
  return `${Math.floor(diffDays / 7)} weeks ago`;
}

function nextNeededLabel(d) {
  if (!d) return "\u2014";
  const now = new Date();
  const then = new Date(d);
  const diffDays = Math.floor((then - now) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "Overdue";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays <= 7) return "This week";
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDate(d) {
  if (!d) return "\u2014";
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/* ── Component ───────────────────────────────────────────────── */

export default function PersonDetailPage() {
  const { id } = useParams();
  const toast = useToastContext();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: person, loading, error, refetch } = useApi(() => getPerson(id), [id]);

  React.useEffect(() => { if (person) document.title = (person?.full_name || ((person?.first_name || "") + " " + (person?.last_name || "")).trim()) + " | Command Center"; }, [person]);

  const [profile, setProfile] = useState(null);
  const [contextNotes, setContextNotes] = useState([]);

  useEffect(() => {
    if (!person?.id) return;
    let cancelled = false;
    getPersonProfile(person.id).then(d => { if (!cancelled) setProfile(d); }).catch(() => {});
    getContextNotesByEntity("person", person.id).then(d => { if (!cancelled) setContextNotes(d?.items || []); }).catch(() => {});
    return () => { cancelled = true; };
  }, [person]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deletePerson(id, person?._etag);
      navigate("/people");
    } catch (err) {
      if (err.status === 409) {
        toast.warning("This person was modified. Please refresh before deleting.");
      } else {
        toast.error("Failed to delete: " + (err.message || String(err)));
      }
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading person...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
      <Breadcrumb items={[{ label: "People", path: "/people" }, { label: person?.full_name || person?.first_name || 'Person' }]} />
        <EmptyState
          icon="⚠"
          title="Person not found"
          message="This person may have been archived or deleted, or the ID may be invalid."
          actionLabel="Go to People"
          onAction={() => navigate("/people")}
        />
      </div>
    );
  }
  if (!person) return null;

  const fullName = person.full_name || `${person.first_name || ""} ${person.last_name || ""}`.trim();
  const tasks = person.tasks || [];
  const personMatters = person.matters || [];
  const personMeetings = person.meetings || [];

  const nextLabel = nextNeededLabel(person.next_interaction_needed_date);
  const nextIsUrgent = nextLabel === "Overdue" || nextLabel === "Today" || nextLabel === "Tomorrow";

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1500 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <button onClick={() => navigate("/people")} style={{ ...btnSecondary, padding: "5px 10px", fontSize: 11 }}>
          &larr; People
        </button>
      </div>

      <div style={{
        ...cardStyle,
        marginBottom: 24,
        padding: "20px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary }}>{fullName}</span>
            {person.is_active === false || person.is_active === 0 ? (
              <Badge bg="rgba(239,68,68,0.12)" text="#ef4444" label="Inactive" />
            ) : null}
          </div>
          <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 13, color: theme.text.muted }}>
            {person.title && <span>{person.title}</span>}
            {person.title && person.org_name && <span style={{ color: theme.text.faint }}>&#8226;</span>}
            {person.org_name && (
              <span
                style={{ color: theme.accent.blueLight, cursor: "pointer" }}
                onClick={() => person.organization_id && navigate(`/organizations/${person.organization_id}`)}
              >
                {person.org_short_name || person.org_name}
              </span>
            )}
            {(person.title || person.org_name) && person.relationship_category && (
              <span style={{ color: theme.text.faint }}>&#8226;</span>
            )}
            {person.relationship_category && (
              <SmallBadge label={person.relationship_category} colorMap={CATEGORY_COLORS} />
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button style={{ ...btnSecondary, color: "#ef4444", borderColor: "#7f1d1d" }} onClick={() => setShowDeleteConfirm(true)}>
            Delete
          </button>
          <button style={btnPrimary} onClick={() => openDrawer("person", person, refetch)}>
            Edit Person
          </button>
        </div>
      </div>

      {/* Two-column layout: sidebar + main */}
      <div style={{ display: "grid", gridTemplateColumns: "360px minmax(0, 1fr)", gap: 24 }}>
        {/* ── Sidebar ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Relationship panel */}
          <div style={sidebarCardStyle}>
            <div style={sectionLabel}>Relationship</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <RelField label="Relationship owner" value={person.relationship_owner_name || "You"} />
              <RelField label="Last interaction" value={timeAgo(person.last_interaction_date)} />
              <RelField
                label="Next interaction needed"
                value={nextLabel}
                valueStyle={nextIsUrgent ? { color: theme.accent.yellowLight, fontWeight: 600 } : undefined}
              />
              {person.next_interaction_type && (
                <RelField label="Next interaction type" value={person.next_interaction_type} />
              )}
              {person.next_interaction_purpose && (
                <RelField label="Next interaction purpose" value={person.next_interaction_purpose} />
              )}
              <div style={{ height: 1, background: theme.border.subtle, margin: "2px 0" }} />
              <RelField label="Email" value={person.email} />
              <RelField label="Phone" value={person.phone} />
              <RelField label="Assistant" value={
                person.assistant_name
                  ? `${person.assistant_name}${person.assistant_contact ? ` (${person.assistant_contact})` : ""}`
                  : null
              } />
              {person.manager_name && <RelField label="Manager" value={person.manager_name} />}
            </div>
          </div>

          {/* Substantive Areas */}
          {person.substantive_areas && (
            <div style={sidebarCardStyle}>
              <div style={sectionLabel}>Substantive Areas</div>
              <div style={{ fontSize: 13, color: theme.text.muted, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {person.substantive_areas}
              </div>
            </div>
          )}

          {/* Interaction Timing cards */}
          {/* Profile */}
          {profile && (() => {
            const pf = [
              ["Birthday", profile.birthday],
              ["Spouse", profile.spouse_name],
              ["Children", profile.children_count != null ? String(profile.children_count) : null],
              ["Children Names", (() => { try { const a = typeof profile.children_names === "string" ? JSON.parse(profile.children_names) : profile.children_names; return Array.isArray(a) && a.length ? a.join(", ") : null; } catch { return profile.children_names; } })()],
              ["Hometown", profile.hometown],
              ["Current City", profile.current_city],
              ["Education", profile.education_summary],
              ["Prior Roles", profile.prior_roles_summary],
              ["Interests", (() => { try { const a = typeof profile.interests === "string" ? JSON.parse(profile.interests) : profile.interests; return Array.isArray(a) && a.length ? a.join(", ") : null; } catch { return profile.interests; } })()],
              ["Scheduling", profile.scheduling_notes],
              ["Relationship Prefs", profile.relationship_preferences],
              ["Leadership", profile.leadership_notes],
            ].filter(([, v]) => v != null && v !== "");
            if (pf.length === 0) return null;
            return (
              <div style={sidebarCardStyle}>
                <div style={sectionLabel}>Profile</div>
                {pf.map(([label, val]) => (
                  <div key={label} style={{ marginBottom: 6 }}>
                    <div style={fieldLabel}>{label}</div>
                    <div style={fieldValue}>{val}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={sidebarCardStyle}>
              <div style={{ fontSize: 10, fontWeight: 600, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Last interaction
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary, marginTop: 4 }}>
                {timeAgo(person.last_interaction_date)}
              </div>
            </div>
            <div style={sidebarCardStyle}>
              <div style={{ fontSize: 10, fontWeight: 600, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Next needed
              </div>
              <div style={{
                fontSize: 16, fontWeight: 600, marginTop: 4,
                color: nextIsUrgent ? theme.accent.yellowLight : theme.text.primary,
              }}>
                {nextLabel}
              </div>
            </div>
          </div>
        </div>

        {/* ── Main content ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Active Matters */}
          <div style={cardStyle}>
            <div style={sectionLabel}>Active Matters ({personMatters.length})</div>
            {personMatters.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
                No active matters linked to this person.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {personMatters.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => navigate(`/matters/${m.id}`)}
                    style={{
                      background: theme.bg.input,
                      borderRadius: 8,
                      border: `1px solid ${theme.border.subtle}`,
                      padding: "12px 16px",
                      cursor: "pointer",
                      transition: "border-color 0.15s",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = theme.accent.blue}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = theme.border.subtle}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: theme.accent.blueLight }}>
                        {m.title}
                      </span>
                      {m.matter_number && (
                        <span style={{ fontSize: 11, color: theme.text.faint }}>{m.matter_number}</span>
                      )}
                    </div>
                    <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                      {m.matter_role && <SmallBadge label={m.matter_role} colorMap={LANE_COLORS} />}
                      {m.engagement_level && <SmallBadge label={m.engagement_level} colorMap={ENGAGEMENT_COLORS} />}
                      {m.status && <SmallBadge label={m.status} colorMap={STATUS_COLORS} />}
                      {m.priority && (
                        <span style={{ fontSize: 11, color: theme.text.faint }}>
                          {m.priority}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Assigned Tasks */}
          <div style={cardStyle}>
            <div style={sectionLabel}>Assigned Tasks ({tasks.length})</div>
            {tasks.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
                No open tasks assigned to this person.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {tasks.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => openDrawer("task", t, refetch)}
                    style={{
                      background: theme.bg.input,
                      borderRadius: 8,
                      border: `1px solid ${theme.border.subtle}`,
                      padding: "12px 16px",
                      cursor: "pointer",
                      transition: "border-color 0.15s",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = theme.accent.blue}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = theme.border.subtle}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>
                        {t.title}
                      </span>
                    </div>
                    <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                      {t.matter_title && (
                        <span style={{ fontSize: 11, color: theme.text.muted }}>{t.matter_title}</span>
                      )}
                      {t.matter_title && t.status && <span style={{ color: theme.text.faint }}>&#8226;</span>}
                      {t.status && <SmallBadge label={t.status} colorMap={STATUS_COLORS} />}
                      {t.due_date && (
                        <>
                          <span style={{ color: theme.text.faint }}>&#8226;</span>
                          <span style={{
                            fontSize: 11,
                            color: new Date(t.due_date) < new Date() ? "#f87171" : theme.text.muted,
                            fontWeight: new Date(t.due_date) < new Date() ? 600 : 400,
                          }}>
                            Due {formatDate(t.due_date)}
                          </span>
                        </>
                      )}
                      {(t.waiting_on_person_name || t.waiting_on_description) && (
                        <>
                          <span style={{ color: theme.text.faint }}>&#8226;</span>
                          <span style={{ fontSize: 11, color: "#a78bfa" }}>
                            Waiting on: {t.waiting_on_person_name || t.waiting_on_description}
                          </span>
                        </>
                      )}
                    </div>
                    {t.expected_output && (
                      <div style={{ marginTop: 6, fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>
                        {t.expected_output}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Meetings */}
          <div style={cardStyle}>
            <div style={sectionLabel}>Recent Meetings ({personMeetings.length})</div>
            {personMeetings.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
                No meetings found.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {personMeetings.map((mtg) => (
                  <div
                    key={mtg.id}
                    onClick={() => openDrawer("meeting", mtg, refetch)}
                    style={{
                      background: theme.bg.input,
                      borderRadius: 8,
                      border: `1px solid ${theme.border.subtle}`,
                      padding: "12px 16px",
                      cursor: "pointer",
                      transition: "border-color 0.15s",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = theme.accent.blue}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = theme.border.subtle}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>
                      {mtg.title}
                    </div>
                    <div style={{ marginTop: 4, display: "flex", gap: 6, alignItems: "center", fontSize: 11, color: theme.text.muted }}>
                      <span>{formatDate(mtg.date_time_start)}</span>
                      {mtg.meeting_type && (
                        <>
                          <span style={{ color: theme.text.faint }}>&#8226;</span>
                          <span>{mtg.meeting_type}</span>
                        </>
                      )}
                      {mtg.meeting_role && (
                        <>
                          <span style={{ color: theme.text.faint }}>&#8226;</span>
                          <span>{mtg.meeting_role}</span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Context Notes */}
          <div style={cardStyle}>
            <div style={sectionLabel}>Context Notes ({contextNotes.length})</div>
            {contextNotes.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
                No context notes linked to this person.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {contextNotes.map((note) => {
                  const CAT_C = { people_insight: { bg: "#312e81", text: "#c4b5fd" }, institutional_knowledge: { bg: "#1e3a5f", text: "#60a5fa" }, process_note: { bg: "#0c4a6e", text: "#67e8f9" }, policy_operating_rule: { bg: "#14532d", text: "#4ade80" }, strategic_context: { bg: "#422006", text: "#fbbf24" }, culture_climate: { bg: "#431407", text: "#fb923c" }, relationship_dynamic: { bg: "#1e1b4b", text: "#a78bfa" } };
                  const POS_C = { factual: { bg: "#1e3a5f", text: "#60a5fa" }, attributed_view: { bg: "#78350f", text: "#fbbf24" }, tentative: { bg: "#1f2937", text: "#9ca3af" }, interpretive: { bg: "#1e1b4b", text: "#a78bfa" }, sensitive: { bg: "#7f1d1d", text: "#fca5a5" } };
                  const cc = CAT_C[note.category] || { bg: "#1f2937", text: "#9ca3af" };
                  const pc = POS_C[note.posture] || { bg: "#1f2937", text: "#9ca3af" };
                  return (
                    <div key={note.id} style={{ background: theme.bg.input, borderRadius: 8, border: `1px solid ${theme.border.subtle}`, padding: "12px 16px" }}>
                      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
                        <span style={{ background: cc.bg, color: cc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          {(note.category || "").replace(/_/g, " ")}
                        </span>
                        <span style={{ background: pc.bg, color: pc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          {(note.posture || "").replace(/_/g, " ")}
                        </span>
                        <span style={{ flex: 1 }} />
                        <span style={{ fontSize: 10, color: theme.text.faint }}>{note.created_at?.slice(0, 10)}</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>{note.title}</div>
                      <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                        {note.body}
                      </div>
                      {note.speaker_attribution && (
                        <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 6, fontStyle: "italic" }}>
                          — {note.speaker_attribution}
                        </div>
                      )}
                      {note.links && note.links.length > 0 && (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                          {note.links.map((lnk, i) => (
                            <span key={i} style={{ background: "rgba(59,130,246,0.1)", color: theme.accent.blueLight, fontSize: 10, padding: "2px 6px", borderRadius: 4, border: "1px solid rgba(59,130,246,0.2)" }}>
                              {lnk.entity_name || lnk.entity_type} ({lnk.relationship_role})
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1000,
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={() => !deleting && setShowDeleteConfirm(false)}>
          <div style={{
            background: theme.bg.card, borderRadius: 12,
            border: `1px solid ${theme.border.default}`,
            padding: 28, maxWidth: 400, width: "90%",
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 16, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
              Delete Person
            </div>
            <div style={{ fontSize: 13, color: theme.text.muted, marginBottom: 20 }}>
              Are you sure you want to delete <strong style={{ color: theme.text.secondary }}>{fullName}</strong>?
              This will deactivate the person record.
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button style={btnSecondary} onClick={() => setShowDeleteConfirm(false)} disabled={deleting}>
                Cancel
              </button>
              <button
                style={{ ...btnPrimary, background: "#991b1b", opacity: deleting ? 0.6 : 1 }}
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Sidebar field row ───────────────────────────────────────── */

function RelField({ label, value, valueStyle }) {
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>{label}</div>
      <div style={{ fontSize: 13, color: theme.text.muted, marginTop: 1, ...valueStyle }}>
        {value || "\u2014"}
      </div>
    </div>
  );
}
