import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { useDrawer } from "../../contexts/DrawerContext";
import { useToastContext } from "../../contexts/ToastContext";
import {
  getMeeting,
  deleteMeeting,
  listTasks,
  listDecisions,
  listPeople,
} from "../../api/tracker";
import { getMeetingIntelligence } from "../../api/ai";
import { formatDate, formatDateTime } from "../../utils/dateUtils";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import Breadcrumb from "../../components/shared/Breadcrumb";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseJSON(val) {
  if (!val) return null;
  if (Array.isArray(val)) return val;
  if (typeof val === "object") return val;
  try {
    return JSON.parse(val);
  } catch {
    return null;
  }
}

// Render a value that may be a string or a JSON object
function renderTextOrObject(val) {
  if (!val) return null;
  if (typeof val === "string") {
    try {
      const parsed = JSON.parse(val);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return renderObjectCards(parsed);
      }
      return val;
    } catch {
      return val;
    }
  }
  if (typeof val === "object" && !Array.isArray(val)) {
    return renderObjectCards(val);
  }
  return String(val);
}

function renderObjectCards(obj) {
  const entries = Object.entries(obj);
  if (!entries.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {entries.map(([key, value]) => (
        <div key={key} style={{ borderLeft: "2px solid " + theme.border.default, paddingLeft: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.dim, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>
            {key.replace(/_/g, " ")}
          </div>
          <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.6 }}>
            {typeof value === "string" ? value : typeof value === "object" ? JSON.stringify(value) : String(value)}
          </div>
        </div>
      ))}
    </div>
  );
}



function getDuration(start, end) {
  if (!start || !end) return null;
  const mins = Math.round((new Date(end) - new Date(start)) / 60000);
  if (mins <= 0) return null;
  if (mins >= 60) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  return `${mins}m`;
}

function isPast(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

function isUrl(str) {
  if (!str) return false;
  return /^https?:\/\//i.test(str.trim());
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const sectionHeaderStyle = {
  fontSize: 12,
  fontWeight: 600,
  color: theme.text.dim,
  textTransform: "uppercase",
  letterSpacing: 0.5,
  marginBottom: 12,
};

const badgeStyle = (bg, fg) => ({
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 12,
  fontSize: 12,
  fontWeight: 600,
  background: bg,
  color: fg || "#fff",
  marginRight: 6,
  marginBottom: 4,
});

const tabButtonStyle = (active) => ({
  background: "transparent",
  border: "none",
  padding: "10px 16px",
  fontSize: 14,
  cursor: "pointer",
  borderBottom: `2px solid ${active ? theme.accent.blue : "transparent"}`,
  color: active ? theme.accent.blue : theme.text.faint,
  fontFamily: theme.font.family,
  fontWeight: active ? 600 : 400,
  transition: "color 0.15s, border-color 0.15s",
});

const leftBorderCard = (color) => ({
  ...cardStyle,
  borderLeft: `3px solid ${color}`,
  padding: 16,
  marginBottom: 10,
});

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CollapsibleSection({ title, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 20 }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          cursor: "pointer",
          userSelect: "none",
          marginBottom: open ? 14 : 0,
        }}
      >
        <span
          style={{
            fontSize: 11,
            color: theme.text.dim,
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.15s",
            display: "inline-block",
          }}
        >
          &#9654;
        </span>
        <span style={{ ...sectionHeaderStyle, marginBottom: 0 }}>{title}</span>
        {badge}
      </div>
      {open && <div>{children}</div>}
    </div>
  );
}

function IssueAccordion({ items }) {
  const [openIdx, setOpenIdx] = useState(null);
  if (!items || !items.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((item, i) => {
        const isOpen = openIdx === i;
        const title =
          typeof item === "string" ? item : item.issue || item.title || item.topic || `Issue ${i + 1}`;
        const detail =
          typeof item === "string"
            ? null
            : item.detail || item.summary || item.discussion || item.description || null;
        return (
          <div key={i} style={{ ...cardStyle, padding: 12 }}>
            <div
              onClick={() => setOpenIdx(isOpen ? null : i)}
              style={{
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                userSelect: "none",
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  color: theme.text.dim,
                  transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 0.15s",
                  display: "inline-block",
                }}
              >
                &#9654;
              </span>
              <span style={{ color: theme.text.primary, fontSize: 14, fontWeight: 500 }}>{title}</span>
            </div>
            {isOpen && detail && (
              <div style={{ marginTop: 10, paddingLeft: 18, color: theme.text.muted, fontSize: 13, lineHeight: 1.6 }}>
                {detail}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const ROLE_ORDER = { decision_maker: 0, chair: 1, presenter: 2, attendee: 3, guest: 4 };

const ROLE_COLORS = {
  chair: { bg: theme.accent.purple + "22", fg: theme.accent.purple },
  decision_maker: { bg: theme.accent.yellow + "22", fg: theme.accent.yellow },
  presenter: { bg: theme.accent.blue + "22", fg: theme.accent.blue },
  attendee: { bg: theme.border.default, fg: theme.text.secondary },
  guest: { bg: theme.border.subtle, fg: theme.text.dim },
};

function ParticipantCard({ p, navigate }) {
  const roleColor = ROLE_COLORS[p.meeting_role] || ROLE_COLORS.attendee;
  const attendanceDot =
    p.attended === true || p.attended === 1
      ? theme.accent.green
      : p.attended === false || p.attended === 0
      ? theme.accent.red
      : theme.text.ghost;

  return (
    <div style={{ ...cardStyle, padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Name row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: attendanceDot,
              flexShrink: 0,
            }}
          />
          <span
            onClick={() => p.person_id && navigate(`/people/${p.person_id}`)}
            style={{
              color: theme.text.primary,
              fontWeight: 600,
              fontSize: 14,
              cursor: p.person_id ? "pointer" : "default",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {p.full_name || "Unknown"}
          </span>
        </div>
        {p.meeting_role && (
          <span style={badgeStyle(roleColor.bg, roleColor.fg)}>
            {(p.meeting_role || "").replace(/_/g, " ")}
          </span>
        )}
      </div>

      {/* Title & org */}
      {(p.person_title || p.org_name) && (
        <div style={{ color: theme.text.dim, fontSize: 12, lineHeight: 1.4 }}>
          {p.person_title}
          {p.person_title && p.org_name ? " \u00B7 " : ""}
          {p.org_name}
        </div>
      )}

      {/* Stance */}
      {p.stance_summary && (
        <div style={{ color: theme.text.dim, fontSize: 12, lineHeight: 1.4 }}>{p.stance_summary}</div>
      )}

      {/* Key contribution */}
      {p.key_contribution_summary && (
        <div style={{ color: theme.text.muted, fontSize: 12, fontStyle: "italic", lineHeight: 1.4 }}>
          {p.key_contribution_summary}
        </div>
      )}

      {/* Tags row */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {p.follow_up_expected && (
          <span style={badgeStyle(theme.accent.yellow + "22", theme.accent.yellow)}>Follow-up Expected</span>
        )}
        {p.moved_position && (
          <span style={badgeStyle(theme.accent.yellow + "22", theme.accent.yellowLight)}>Position Shifted</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Intelligence sub-panels
// ---------------------------------------------------------------------------

function SkimLayer({ intel }) {
  const decisions = parseJSON(intel.decisions_made);
  const nonDecisions = parseJSON(intel.non_decisions);
  const actionItems = parseJSON(intel.action_items_summary);
  const risks = parseJSON(intel.risks_surfaced);
  const briefing = intel.briefing_required;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Executive summary */}
      {intel.executive_summary && (
        <div style={leftBorderCard(theme.accent.blue)}>
          <div style={sectionHeaderStyle}>Executive Summary</div>
          <div style={{ color: theme.text.secondary, fontSize: 14, lineHeight: 1.7 }}>
            {intel.executive_summary}
          </div>
        </div>
      )}

      {/* Briefing required banner */}
      {briefing && (
        <div
          style={{
            background: theme.accent.yellow + "18",
            border: `1px solid ${theme.accent.yellow}44`,
            borderRadius: 8,
            padding: "12px 16px",
            color: theme.accent.yellowLight,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          Briefing Required: {typeof briefing === "string" ? briefing : "Yes"}
        </div>
      )}

      {/* Decisions made */}
      {decisions && decisions.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Decisions Made</div>
          {decisions.map((d, i) => (
            <div key={i} style={leftBorderCard(theme.accent.green)}>
              <span style={{ color: theme.text.secondary, fontSize: 13 }}>
                {typeof d === "string" ? d : d.decision || d.title || d.summary || JSON.stringify(d)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Non-decisions */}
      {nonDecisions && nonDecisions.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Non-Decisions</div>
          {nonDecisions.map((d, i) => (
            <div key={i} style={leftBorderCard(theme.accent.yellow)}>
              <div style={{ color: theme.text.secondary, fontSize: 13, fontWeight: 500 }}>
                {typeof d === "string" ? d : d.issue || d.item || d.title || d.summary || JSON.stringify(d)}
              </div>
              {typeof d === "object" && (d.why_unresolved || d.who_resolves || d.by_when || d.info_needed) && (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
                  {d.why_unresolved && <div style={{ color: theme.text.muted }}><span style={{ fontWeight: 600, color: theme.text.dim }}>Why unresolved: </span>{d.why_unresolved}</div>}
                  {d.who_resolves && <div style={{ color: theme.text.muted }}><span style={{ fontWeight: 600, color: theme.text.dim }}>Who resolves: </span>{d.who_resolves}</div>}
                  {d.by_when && <div style={{ color: theme.text.muted }}><span style={{ fontWeight: 600, color: theme.text.dim }}>By when: </span>{d.by_when}</div>}
                  {d.info_needed && <div style={{ color: theme.text.muted }}><span style={{ fontWeight: 600, color: theme.text.dim }}>Info needed: </span>{d.info_needed}</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Action items */}
      {actionItems && actionItems.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Action Items</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr>
                  {["Action", "Owner", "Due Date", "Priority"].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "8px 12px",
                        color: theme.text.dim,
                        fontWeight: 600,
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                        borderBottom: `1px solid ${theme.border.default}`,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {actionItems.map((a, i) => (
                  <tr key={i}>
                    <td style={{ padding: "8px 12px", color: theme.text.secondary }}>
                      {typeof a === "string" ? a : a.action || a.title || a.item || JSON.stringify(a)}
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.text.muted }}>
                      {typeof a === "object" ? a.owner || a.assigned_to || "\u2014" : "\u2014"}
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.text.muted }}>
                      {typeof a === "object" ? a.due_date || a.due || a.deadline || "\u2014" : "\u2014"}
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.text.muted }}>
                      {typeof a === "object" ? a.priority || "\u2014" : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Risks */}
      {risks && risks.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Risks Surfaced</div>
          {risks.map((r, i) => (
            <div key={i} style={{ ...leftBorderCard(theme.accent.red), display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: theme.text.secondary, fontSize: 13, flex: 1 }}>
                {typeof r === "string" ? r : r.risk || r.title || r.description || JSON.stringify(r)}
              </span>
              {typeof r === "object" && r.severity && (
                <span
                  style={badgeStyle(
                    r.severity === "high" ? theme.accent.red + "22" : theme.accent.yellow + "22",
                    r.severity === "high" ? theme.accent.red : theme.accent.yellow
                  )}
                >
                  {r.severity}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Closing block */}
      <ClosingBlock intel={intel} />
    </div>
  );
}

function ClosingBlock({ intel }) {
  const items = [
    { label: "Why This Mattered", value: intel.why_this_meeting_mattered, color: theme.accent.blue },
    { label: "What Changed", value: intel.what_changed, color: theme.accent.purple },
    { label: "What I Need to Do", value: intel.what_i_need_to_do, color: theme.accent.green },
    { label: "What Boss Needs to Know", value: intel.what_boss_needs_to_know, color: theme.accent.yellow, highlight: true },
    { label: "What Can Wait", value: intel.what_can_wait, color: theme.text.dim },
  ];

  const hasAny = items.some((i) => i.value);
  if (!hasAny) return null;

  return (
    <div style={{ ...cardStyle, padding: 20, marginTop: 4 }}>
      <div style={sectionHeaderStyle}>Closing Block</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {items.map(
          (item) =>
            item.value && (
              <div
                key={item.label}
                style={{
                  ...(item.highlight
                    ? {
                        background: theme.accent.yellow + "12",
                        border: `1px solid ${theme.accent.yellow}44`,
                        borderRadius: 8,
                        padding: "12px 16px",
                      }
                    : { borderLeft: `3px solid ${item.color}`, paddingLeft: 14 }),
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: item.color,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    marginBottom: 4,
                  }}
                >
                  {item.label}
                </div>
                <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.6 }}>{renderTextOrObject(item.value)}</div>
              </div>
            )
        )}
      </div>
    </div>
  );
}

function OperatingLayer({ intel }) {
  const keyIssues = parseJSON(intel.key_issues_discussed);
  const positions = parseJSON(intel.participant_positions);
  const dependencies = parseJSON(intel.dependencies_surfaced);
  const commitments = parseJSON(intel.commitments_made);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Key issues */}
      {keyIssues && keyIssues.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Key Issues Discussed</div>
          <IssueAccordion items={keyIssues} />
        </div>
      )}

      {/* Participant positions */}
      {positions && positions.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Participant Positions</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
            {positions.map((p, i) => (
              <div key={i} style={{ ...cardStyle, padding: 14 }}>
                <div style={{ fontWeight: 600, color: theme.text.primary, fontSize: 13, marginBottom: 4 }}>
                  {p.name || p.participant || p.person || `Participant ${i + 1}`}
                </div>
                {(p.position || p.stance || p.summary) && (
                  <div style={{ color: theme.text.muted, fontSize: 12, lineHeight: 1.5, marginBottom: 6 }}>
                    {p.position || p.stance || p.summary}
                  </div>
                )}
                {(p.support_level || p.support) && (
                  <span
                    style={badgeStyle(
                      theme.accent.blue + "22",
                      theme.accent.blueLight
                    )}
                  >
                    {p.support_level || p.support}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dependencies */}
      {dependencies && dependencies.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Dependencies Surfaced</div>
          <ul style={{ margin: 0, paddingLeft: 20, color: theme.text.secondary, fontSize: 13, lineHeight: 1.8 }}>
            {dependencies.map((d, i) => (
              <li key={i}>{typeof d === "string" ? d : d.dependency || d.description || JSON.stringify(d)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* What changed in matter */}
      {intel.what_changed_in_matter && (
        <div>
          <div style={sectionHeaderStyle}>What Changed in Matter</div>
          <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.7 }}>
            {renderTextOrObject(intel.what_changed_in_matter)}
          </div>
        </div>
      )}

      {/* Commitments */}
      {commitments && commitments.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Commitments Made</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr>
                  {["Who", "What", "By When"].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "8px 12px",
                        color: theme.text.dim,
                        fontWeight: 600,
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                        borderBottom: `1px solid ${theme.border.default}`,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {commitments.map((c, i) => (
                  <tr key={i}>
                    <td style={{ padding: "8px 12px", color: theme.text.secondary }}>
                      {typeof c === "string" ? c : c.who || c.person || c.owner || "\u2014"}
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.text.muted }}>
                      {typeof c === "object" ? c.what || c.commitment || c.action || "\u2014" : "\u2014"}
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.text.muted }}>
                      {typeof c === "object" ? c.by_when || c.due || c.deadline || "\u2014" : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recommended next move */}
      {intel.recommended_next_move && (
        <div>
          <div style={sectionHeaderStyle}>Recommended Next Move</div>
          <div style={leftBorderCard(theme.accent.green)}>
            <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.7 }}>
              {renderTextOrObject(intel.recommended_next_move)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RecordLayer({ intel }) {
  const materials = parseJSON(intel.materials_referenced);
  const tags = parseJSON(intel.tags);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Purpose and context */}
      {intel.purpose_and_context && (
        <div>
          <div style={sectionHeaderStyle}>Purpose and Context</div>
          <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.7 }}>
            {renderTextOrObject(intel.purpose_and_context)}
          </div>
        </div>
      )}

      {/* Materials referenced */}
      {materials && materials.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Materials Referenced</div>
          <ul style={{ margin: 0, paddingLeft: 20, color: theme.text.secondary, fontSize: 13, lineHeight: 1.8 }}>
            {materials.map((m, i) => (
              <li key={i}>{typeof m === "string" ? m : m.title || m.name || m.reference || JSON.stringify(m)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Detailed notes */}
      {intel.detailed_notes && (
        <div>
          <div style={sectionHeaderStyle}>Detailed Notes</div>
          <div
            style={{
              color: theme.text.secondary,
              fontSize: 13,
              lineHeight: 1.7,
              whiteSpace: "pre-wrap",
            }}
          >
            {renderTextOrObject(intel.detailed_notes)}
          </div>
        </div>
      )}

      {/* Tags */}
      {tags && tags.length > 0 && (
        <div>
          <div style={sectionHeaderStyle}>Tags</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {tags.map((t, i) => (
              <span key={i} style={badgeStyle(theme.border.default, theme.text.secondary)}>
                {typeof t === "string" ? t : t.tag || t.name || JSON.stringify(t)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ message }) {
  return (
    <div
      style={{
        padding: 40,
        textAlign: "center",
        color: theme.text.ghost,
        fontSize: 14,
      }}
    >
      {message || "No data available."}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function MeetingDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const { addToast } = useToastContext();

  // ---- Core data ----
  const {
    data: meeting,
    loading: meetingLoading,
    error: meetingError,
    refetch: refetchMeeting,
  } = useApi(() => getMeeting(id), [id]);

  // ---- Intelligence (may 404) ----
  const [intel, setIntel] = useState(null);
  const [intelLoading, setIntelLoading] = useState(true);

  useEffect(() => {
    setIntelLoading(true);
    getMeetingIntelligence(id)
      .then((data) => setIntel(data))
      .catch(() => setIntel(null))
      .finally(() => setIntelLoading(false));
  }, [id]);

  // ---- People lookup (for owner name) ----
  const { data: people } = useApi(() => listPeople(), []);

  // ---- Tasks from meeting source ----
  const { data: meetingTasks, refetch: refetchMeetingTasks } = useApi(
    () => listTasks({ source_id: id }),
    [id]
  );

  React.useEffect(() => { if (meeting?.title) document.title = meeting?.title + " | Command Center"; }, [meeting?.title]);

  // ---- Tasks & decisions from linked matters ----
  const [matterTasks, setMatterTasks] = useState([]);
  const [matterDecisions, setMatterDecisions] = useState([]);

  useEffect(() => {
    if (!meeting?.matters?.length) {
      setMatterTasks([]);
      setMatterDecisions([]);
      return;
    }
    const matterIds = meeting.matters.map((m) => m.id);

    Promise.all(matterIds.map((mid) => listTasks({ matter_id: mid }).catch(() => [])))
      .then((results) => setMatterTasks(results.flatMap(r => r.items || r)))
      .catch(() => setMatterTasks([]));

    Promise.all(matterIds.map((mid) => listDecisions({ matter_id: mid }).catch(() => [])))
      .then((results) => setMatterDecisions(results.flatMap(r => r.items || r)))
      .catch(() => setMatterDecisions([]));
  }, [meeting]);

  // ---- Delete confirm ----
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDelete = useCallback(async () => {
    try {
      await deleteMeeting(id);
      addToast("Meeting deleted", "success");
      navigate("/meetings");
    } catch (e) {
      addToast("Failed to delete meeting", "error");
    }
  }, [id, navigate, addToast]);

  // ---- Tabs ----
  const [activeTab, setActiveTab] = useState("matters");

  // ---- Loading / Error states ----
  if (meetingLoading) {
    return (
      <div style={{ padding: 40, color: theme.text.muted, fontFamily: theme.font.family }}>
        Loading meeting...
      </div>
    );
  }

  if (meetingError || !meeting) {
    return (
      <div style={{ padding: 40, color: theme.accent.red, fontFamily: theme.font.family }}>
        Failed to load meeting.{" "}
        <span
          onClick={() => navigate("/meetings")}
          style={{ color: theme.accent.blue, cursor: "pointer", textDecoration: "underline" }}
        >
          Back to Meetings
        </span>
      </div>
    );
  }

  // ---- Derived values ----
  const participants = [...(meeting.participants || [])].sort(
    (a, b) => (ROLE_ORDER[a.meeting_role] ?? 99) - (ROLE_ORDER[b.meeting_role] ?? 99)
  );
  const matters = meeting.matters || [];
  const duration = getDuration(meeting.date_time_start, meeting.date_time_end);
  const meetingInPast = isPast(meeting.date_time_start);

  const ownerPerson =
    meeting.assigned_to_person_id && people
      ? people.find((p) => p.id === meeting.assigned_to_person_id)
      : null;

  // ---- Render ----
  return (
    <div
      style={{
        fontFamily: theme.font.family,
        color: theme.text.primary,
        maxWidth: 1100,
        margin: "0 auto",
        padding: "24px 24px 60px",
      }}
    >
      {/* ================================================================ */}
      {/* Section 0: Action Bar                                           */}
      {/* ================================================================ */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <button
          onClick={() => navigate("/meetings")}
          style={{
            background: "none",
            border: "none",
            color: theme.accent.blue,
            cursor: "pointer",
            fontSize: 14,
            fontFamily: theme.font.family,
            padding: 0,
          }}
        >
          &larr; Back to Meetings
        </button>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => openDrawer("meeting", meeting, refetchMeeting)}
            style={{
              background: theme.accent.blue,
              color: "#fff",
              border: "none",
              borderRadius: 6,
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: theme.font.family,
            }}
          >
            Edit
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            style={{
              background: "transparent",
              color: theme.accent.red,
              border: `1px solid ${theme.accent.red}44`,
              borderRadius: 6,
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: theme.font.family,
            }}
          >
            Delete
          </button>
        </div>
      </div>

      {showDeleteConfirm && (
        <ConfirmDialog
          title="Delete Meeting"
          message={`Are you sure you want to delete "${meeting.title}"? This action cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}

      {/* ================================================================ */}
      {/* Section 1: Header Card                                          */}
      {/* ================================================================ */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        {/* Row 1: Title + badges */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 24,
              fontWeight: 700,
              color: theme.text.primary,
              lineHeight: 1.3,
            }}
          >
            {meeting.title}
          </h1>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            {meeting.meeting_type && (
              <span style={badgeStyle(theme.accent.blue + "22", theme.accent.blueLight)}>
                {meeting.meeting_type}
              </span>
            )}
            {meeting.status && <Badge status={meeting.status} />}
            {meeting.boss_attends && (
              <span style={badgeStyle(theme.accent.purple + "22", theme.accent.purple)}>Boss Present</span>
            )}
            {meeting.external_parties_attend && (
              <span style={badgeStyle(theme.accent.teal + "22", theme.accent.teal)}>External</span>
            )}
          </div>
        </div>

        {/* Row 2: Metadata grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "8px 32px",
            fontSize: 13,
            marginBottom: meeting.purpose ? 16 : 0,
          }}
        >
          {/* Left column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div>
              <span style={{ color: theme.text.dim }}>Date: </span>
              <span style={{ color: theme.text.secondary }}>{formatDateTime(meeting.date_time_start)}</span>
            </div>
            {duration && (
              <div>
                <span style={{ color: theme.text.dim }}>Duration: </span>
                <span style={{ color: theme.text.secondary }}>{duration}</span>
              </div>
            )}
            {meeting.location_or_link && (
              <div>
                <span style={{ color: theme.text.dim }}>Location: </span>
                {isUrl(meeting.location_or_link) ? (
                  <a
                    href={meeting.location_or_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: theme.accent.blue, textDecoration: "none" }}
                  >
                    {meeting.location_or_link}
                  </a>
                ) : (
                  <span style={{ color: theme.text.secondary }}>{meeting.location_or_link}</span>
                )}
              </div>
            )}
          </div>

          {/* Right column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {meeting.source && (
              <div>
                <span style={{ color: theme.text.dim }}>Source: </span>
                <span style={badgeStyle(theme.border.default, theme.text.muted)}>{meeting.source}</span>
              </div>
            )}
            {ownerPerson && (
              <div>
                <span style={{ color: theme.text.dim }}>Owner: </span>
                <span
                  onClick={() => navigate(`/people/${ownerPerson.id}`)}
                  style={{ color: theme.accent.blue, cursor: "pointer" }}
                >
                  {ownerPerson.full_name || ownerPerson.name || `Person #${ownerPerson.id}`}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Row 3: Purpose */}
        {meeting.purpose && (
          <div
            style={{
              borderLeft: `3px solid ${theme.accent.blue}`,
              paddingLeft: 14,
              marginTop: 8,
              color: theme.text.muted,
              fontSize: 13,
              lineHeight: 1.7,
              fontStyle: "italic",
            }}
          >
            {meeting.purpose}
          </div>
        )}

        {/* Conditional: Readout summary (past meetings) */}
        {meetingInPast && meeting.readout_summary && (
          <div
            style={{
              marginTop: 16,
              background: theme.accent.blue + "0a",
              border: `1px solid ${theme.accent.blue}33`,
              borderRadius: 8,
              padding: 16,
            }}
          >
            <div style={{ ...sectionHeaderStyle, color: theme.accent.blueLight }}>Readout Summary</div>
            <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.7 }}>
              {meeting.readout_summary}
            </div>
          </div>
        )}

        {/* Conditional: Prep needed (future meetings) */}
        {!meetingInPast && meeting.prep_needed && (
          <div
            style={{
              marginTop: 16,
              background: theme.accent.yellow + "12",
              border: `1px solid ${theme.accent.yellow}44`,
              borderRadius: 8,
              padding: 16,
            }}
          >
            <div style={{ ...sectionHeaderStyle, color: theme.accent.yellow }}>Preparation Needed</div>
            <div style={{ color: theme.text.secondary, fontSize: 13, lineHeight: 1.7 }}>
              {meeting.prep_needed}
            </div>
          </div>
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 2: Participants Grid                                     */}
      {/* ================================================================ */}
      <div style={{ marginBottom: 24 }}>
        <div style={sectionHeaderStyle}>
          Participants{participants.length > 0 ? ` (${participants.length})` : ""}
        </div>
        {participants.length > 0 ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 12,
            }}
          >
            {participants.map((p, i) => (
              <ParticipantCard key={p.person_id || i} p={p} navigate={navigate} />
            ))}
          </div>
        ) : (
          <EmptyState message="No participants recorded." />
        )}
      </div>

      {/* ================================================================ */}
      {/* Section 3: AI Intelligence Panel                                 */}
      {/* ================================================================ */}
      <div style={{ marginBottom: 24 }}>
        <CollapsibleSection
          title="Meeting Intelligence"
          badge={
            intel?.tier ? (
              <span
                style={badgeStyle(
                  intel.tier === "full" ? theme.accent.green + "22" : theme.accent.blue + "22",
                  intel.tier === "full" ? theme.accent.green : theme.accent.blueLight
                )}
              >
                {intel.tier}
              </span>
            ) : null
          }
          defaultOpen={true}
        >
          {intelLoading ? (
            <div style={{ padding: 20, color: theme.text.muted, fontSize: 13 }}>Loading intelligence...</div>
          ) : !intel ? (
            <EmptyState message="No AI intelligence available for this meeting." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {/* Skim layer */}
              <CollapsibleSection title="Skim" defaultOpen={true}>
                <SkimLayer intel={intel} />
              </CollapsibleSection>

              {/* Operating layer */}
              <CollapsibleSection title="Operating" defaultOpen={false}>
                <OperatingLayer intel={intel} />
              </CollapsibleSection>

              {/* Record layer */}
              <CollapsibleSection title="Record" defaultOpen={false}>
                <RecordLayer intel={intel} />
              </CollapsibleSection>
            </div>
          )}
        </CollapsibleSection>
      </div>

      {/* ================================================================ */}
      {/* Section 4: Tabbed Section                                        */}
      {/* ================================================================ */}
      <div style={{ ...cardStyle, padding: 0 }}>
        {/* Tab bar */}
        <div
          style={{
            display: "flex",
            borderBottom: `1px solid ${theme.border.default}`,
            padding: "0 8px",
          }}
        >
          {[
            { key: "matters", label: "Matters" },
            { key: "tasks", label: "Tasks" },
            { key: "decisions", label: "Decisions" },
            { key: "notes", label: "Notes & Readout" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={tabButtonStyle(activeTab === tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ padding: 24 }}>
          {/* ---- Matters tab ---- */}
          {activeTab === "matters" && (
            <>
              {matters.length > 0 ? (
                <DataTable
                  columns={[
                    {
                      key: "matter_title",
                      label: "Matter Title",
                      render: (row) => (
                        <span
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/matters/${row.id}`);
                          }}
                          style={{ color: theme.accent.blue, cursor: "pointer" }}
                        >
                          {row.matter_title || row.title || "\u2014"}
                        </span>
                      ),
                    },
                    {
                      key: "status",
                      label: "Status",
                      render: (row) => (row.status ? <Badge status={row.status} /> : "\u2014"),
                    },
                    {
                      key: "priority",
                      label: "Priority",
                      render: (row) => (row.priority ? <Badge priority={row.priority} /> : "\u2014"),
                    },
                    { key: "relationship_type", label: "Relationship" },
                    { key: "decision_summary", label: "Decision Summary" },
                  ]}
                  data={matters}
                  onRowClick={(row) => navigate(`/matters/${row.id}`)}
                />
              ) : (
                <EmptyState message="No matters linked to this meeting." />
              )}
            </>
          )}

          {/* ---- Tasks tab ---- */}
          {activeTab === "tasks" && (
            <>
              {(meetingTasks && meetingTasks.length > 0) || matterTasks.length > 0 ? (
                <>
                  {meetingTasks && meetingTasks.length > 0 && (
                    <div style={{ marginBottom: 24 }}>
                      <div style={sectionHeaderStyle}>Tasks from this Meeting</div>
                      <DataTable
                        columns={[
                          { key: "title", label: "Title" },
                          { key: "assigned_to", label: "Assigned To" },
                          {
                            key: "status",
                            label: "Status",
                            render: (row) => (row.status ? <Badge status={row.status} /> : "\u2014"),
                          },
                          {
                            key: "due_date",
                            label: "Due Date",
                            render: (row) => formatDate(row.due_date),
                          },
                          {
                            key: "priority",
                            label: "Priority",
                            render: (row) => (row.priority ? <Badge priority={row.priority} /> : "\u2014"),
                          },
                        ]}
                        data={meetingTasks}
                        onRowClick={(row) => openDrawer("task", row, refetchMeetingTasks)}
                      />
                    </div>
                  )}
                  {matterTasks.length > 0 && (
                    <div>
                      <div style={sectionHeaderStyle}>Tasks from Linked Matters</div>
                      <DataTable
                        columns={[
                          { key: "title", label: "Title" },
                          { key: "assigned_to", label: "Assigned To" },
                          {
                            key: "status",
                            label: "Status",
                            render: (row) => (row.status ? <Badge status={row.status} /> : "\u2014"),
                          },
                          {
                            key: "due_date",
                            label: "Due Date",
                            render: (row) => formatDate(row.due_date),
                          },
                          {
                            key: "priority",
                            label: "Priority",
                            render: (row) => (row.priority ? <Badge priority={row.priority} /> : "\u2014"),
                          },
                        ]}
                        data={matterTasks}
                        onRowClick={(row) => openDrawer("task", row)}
                      />
                    </div>
                  )}
                </>
              ) : (
                <EmptyState message="No tasks associated with this meeting or its matters." />
              )}
            </>
          )}

          {/* ---- Decisions tab ---- */}
          {activeTab === "decisions" && (
            <>
              {matterDecisions.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "title", label: "Title" },
                    {
                      key: "matter_title",
                      label: "Matter",
                      render: (row) => row.matter_title || row.matter_name || "\u2014",
                    },
                    {
                      key: "status",
                      label: "Status",
                      render: (row) => (row.status ? <Badge status={row.status} /> : "\u2014"),
                    },
                    { key: "decision_type", label: "Type" },
                    {
                      key: "decision_due_date",
                      label: "Due Date",
                      render: (row) => formatDate(row.decision_due_date || row.due_date),
                    },
                  ]}
                  data={matterDecisions}
                  onRowClick={(row) => openDrawer("decision", row)}
                />
              ) : (
                <EmptyState message="No decisions from linked matters." />
              )}
            </>
          )}

          {/* ---- Notes & Readout tab ---- */}
          {activeTab === "notes" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {meeting.notes && (
                <div>
                  <div style={sectionHeaderStyle}>Notes</div>
                  <div
                    style={{
                      color: theme.text.secondary,
                      fontSize: 13,
                      lineHeight: 1.7,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {meeting.notes}
                  </div>
                </div>
              )}

              {meeting.decisions_made && (
                <div>
                  <div style={sectionHeaderStyle}>Decisions Made (Manual)</div>
                  <div
                    style={{
                      color: theme.text.secondary,
                      fontSize: 13,
                      lineHeight: 1.7,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {meeting.decisions_made}
                  </div>
                </div>
              )}

              {meeting.readout_summary && (
                <div>
                  <div style={sectionHeaderStyle}>Readout Summary</div>
                  <div
                    style={{
                      color: theme.text.secondary,
                      fontSize: 13,
                      lineHeight: 1.7,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {meeting.readout_summary}
                  </div>
                </div>
              )}

              {/* Source indicators */}
              {(meeting.transcript_id || meeting.recording_id) && (
                <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                  {meeting.transcript_id && (
                    <span style={badgeStyle(theme.accent.purple + "22", theme.accent.purple)}>
                      Transcript Available
                    </span>
                  )}
                  {meeting.recording_id && (
                    <span style={badgeStyle(theme.accent.blue + "22", theme.accent.blueLight)}>
                      Recording Available
                    </span>
                  )}
                </div>
              )}

              {!meeting.notes && !meeting.decisions_made && !meeting.readout_summary && (
                <EmptyState message="No notes or readout recorded." />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
