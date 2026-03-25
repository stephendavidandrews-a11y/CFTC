import React, { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import useTabState from "../../hooks/useTabState";
import {
  getMatter,
  listPeople, listOrganizations, listMatters,
  getMatterTags, addMatterTag, removeMatterTag, listTags, createTag,
  getEnums, deleteMatter
} from "../../api/tracker";
import { useDrawer } from "../../contexts/DrawerContext";
import Badge from "../../components/shared/Badge";
import Breadcrumb from "../../components/shared/Breadcrumb";
import EmptyState from "../../components/shared/EmptyState";
import { formatDate } from "../../utils/dateUtils";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import ActivityTab from "./matter-detail/ActivityTab";
import WorkTab from "./matter-detail/WorkTab";
import StakeholdersTab from "./matter-detail/StakeholdersTab";
import IntelligenceTab from "./matter-detail/IntelligenceTab";
import DependenciesTab from "./matter-detail/DependenciesTab";
import RulemakingTab from "./matter-detail/RulemakingTab";

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

const inputStyle = {
  background: theme.bg.input,
  border: `1px solid ${theme.border.default}`,
  borderRadius: 6,
  padding: "7px 12px",
  fontSize: 13,
  color: theme.text.secondary,
  outline: "none",
  width: "100%",
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

const labelStyle = { fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em" };
const valStyle = { fontSize: 13, color: theme.text.secondary, marginTop: 2 };


export default function MatterDetailPage() {
  const { id } = useParams();
  const toast = useToastContext();
  const { openDrawer } = useDrawer();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useTabState("Activity");
  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: "", message: "", onConfirm: null, danger: false });

  const { data: matter, loading, error, refetch } = useApi(() => getMatter(id), [id]);

  const { data: allPeople } = useApi(() => listPeople({ limit: 500 }), []);
  const { data: allOrgs } = useApi(() => listOrganizations({ limit: 500 }), []);
  const { data: allMatters } = useApi(() => listMatters({ limit: 500 }), []);

  const [tags, setTags] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [selectedTagId, setSelectedTagId] = useState("");
  const [showNewTag, setShowNewTag] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [enums, setLoadedEnums] = useState({});

  React.useEffect(() => { if (matter?.title) document.title = matter?.title + " | Command Center"; }, [matter?.title]);

  useEffect(() => {
    if (!id) return;
    getMatterTags(id).then((res) => setTags(Array.isArray(res) ? res : (res?.items || res || []))).catch(() => {});
    listTags("matter").then((res) => setAllTags(res?.items || res || [])).catch(() => {});
  }, [id]);

  useEffect(() => {
    getEnums().then((data) => setLoadedEnums(data || {})).catch(() => {});
  }, []);

  const handleAddTag = useCallback(async () => {
    if (!selectedTagId) return;
    try {
      await addMatterTag(id, selectedTagId);
      const updated = await getMatterTags(id);
      setTags(Array.isArray(updated) ? updated : (updated?.items || updated || []));
      setSelectedTagId("");
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, selectedTagId]);

  const handleRemoveTag = useCallback(async (tagId) => {
    try {
      await removeMatterTag(id, tagId);
      const updated = await getMatterTags(id);
      setTags(Array.isArray(updated) ? updated : (updated?.items || updated || []));
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id]);

  const handleCreateTag = useCallback(async () => {
    if (!newTagName.trim()) return;
    try {
      const newTag = await createTag({ name: newTagName.trim(), tag_type: "matter" });
      setAllTags((prev) => [...prev, newTag]);
      setNewTagName("");
      setShowNewTag(false);
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [newTagName]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading matter...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <Breadcrumb items={[{ label: "Matters", path: "/matters" }, { label: matter?.title || "Matter" }]} />
        <EmptyState
          icon="&#9888;"
          title="Matter not found"
          message="This matter may have been archived or deleted, or the ID may be invalid."
          actionLabel="Go to Matters"
          onAction={() => navigate("/matters")}
        />
      </div>
    );
  }
  if (!matter) return null;

  const st = theme.status[matter.status] || { bg: theme.bg.input, text: theme.text.faint, label: matter.status };
  const pr = theme.priority[matter.priority] || { bg: theme.bg.input, text: theme.text.faint, label: matter.priority };

  const assignedTagIds = new Set((tags || []).map((t) => t.id || t.tag_id));
  const availableTags = (allTags || []).filter((t) => !assignedTagIds.has(t.id));

  const infoLeft = [
    { label: "Type", value: matter.matter_type },
    { label: "Status", value: matter.status },
    { label: "Priority", value: matter.priority },
    { label: "Sensitivity", value: matter.sensitivity },
    { label: "Boss Involvement", value: matter.boss_involvement_level },
    { label: "RIN", value: matter.rin },
    { label: "Regulatory Stage", value: matter.regulatory_stage },
    { label: "Risk Level", value: matter.risk_level },
  ];

  const infoRight = [
    { label: "Owner", value: matter.owner_name || matter.owner },
    { label: "Supervisor", value: matter.supervisor_name || matter.supervisor },
    { label: "Client Org", value: matter.client_org_name || matter.client_org },
    { label: "Requesting Org", value: matter.requesting_org_name || matter.requesting_org },
    { label: "Reviewing Org", value: matter.reviewing_org_name || matter.reviewing_org },
    { label: "Opened Date", value: formatDate(matter.opened_date || matter.created_at) },
    { label: "Revisit Date", value: formatDate(matter.revisit_date) },
    { label: "Work Deadline", value: formatDate(matter.work_deadline) },
    { label: "External Deadline", value: formatDate(matter.external_deadline) },
    { label: "Decision Deadline", value: formatDate(matter.decision_deadline) },
  ];

  const tabs = [
    { key: "Activity", label: "Activity" },
    { key: "Work", label: "Work" },
    { key: "Stakeholders", label: "Stakeholders" },
    { key: "Intelligence", label: "Intelligence" },
    { key: "Dependencies", label: "Dependencies" },
    ...(matter?.matter_type === "rulemaking" ? [{ key: "Rulemaking", label: "Rulemaking" }] : []),
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 20 }}>
        <button onClick={() => navigate("/matters")} style={{ ...btnSecondary, padding: "5px 10px", fontSize: 11, marginTop: 4 }}>
          &larr; Back
        </button>
        <div style={{ flex: 1 }}>
          {/* Status + Priority badges above title */}
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            {matter.status && <Badge bg={st.bg} text={st.text} label={st.label || matter.status} />}
            {matter.priority && <Badge bg={pr.bg} text={pr.text} label={pr.label || matter.priority} />}
          </div>
          {/* Title */}
          <h1 style={titleStyle}>{matter.title}</h1>
          {matter.matter_number && (
            <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 2 }}>#{matter.matter_number}</div>
          )}
        </div>
        <button style={btnPrimary} onClick={() => openDrawer("matter", matter, refetch)}>
          Edit
        </button>
        <button
          style={{
            padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: "rgba(239,68,68,0.1)", color: "#f87171",
            border: "1px solid rgba(239,68,68,0.25)", cursor: "pointer",
          }}
          onClick={() => {
            setConfirmDialog({
              open: true,
              title: "Delete Matter",
              message: `Delete "${matter.title}"? This will close the matter.`,
              danger: true,
              onConfirm: async () => {
                try {
                  await deleteMatter(matter.id);
                  navigate("/matters");
                } catch (e) {
                  toast.error(e.message || "Operation failed");
                }
              },
            });
          }}
        >
          Delete
        </button>
      </div>

      {/* Info Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={cardStyle}>
          {infoLeft.map((item) => (
            <div key={item.label} style={{ marginBottom: 12 }}>
              <div style={labelStyle}>{item.label}</div>
              <div style={valStyle}>{item.value || "\u2014"}</div>
            </div>
          ))}
        </div>
        <div style={cardStyle}>
          {infoRight.map((item) => (
            <div key={item.label} style={{ marginBottom: 12 }}>
              <div style={labelStyle}>{item.label}</div>
              <div style={valStyle}>{item.value || "\u2014"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Context Section */}
      {(matter.problem_statement || matter.why_it_matters || matter.description || matter.outcome_summary) && (
        <div style={{ ...cardStyle, marginBottom: 24 }}>
          <div style={sectionTitle}>Context</div>
          {matter.description && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Description</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.description}</div>
            </div>
          )}
          {matter.problem_statement && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Problem Statement</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.problem_statement}</div>
            </div>
          )}
          {matter.why_it_matters && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Why It Matters</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.why_it_matters}</div>
            </div>
          )}
          {matter.outcome_summary && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Outcome Summary</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.outcome_summary}</div>
            </div>
          )}
        </div>
      )}

      {/* Current State Card */}
      {(matter.next_step || matter.pending_decision) && (
        <div style={{ ...cardStyle, marginBottom: 24, background: theme.bg.cardHover, borderLeft: `3px solid ${theme.accent.blue}` }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.02em" }}>Current State</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {matter.next_step && (
              <div>
                <div style={labelStyle}>Next Step</div>
                <div style={valStyle}>{matter.next_step}</div>
              </div>
            )}
            {matter.next_step_owner_name && (
              <div>
                <div style={labelStyle}>Next Step Owner</div>
                <div style={valStyle}>{matter.next_step_owner_name}</div>
              </div>
            )}
            {matter.pending_decision && (
              <div style={{ gridColumn: "1 / -1" }}>
                <div style={labelStyle}>Pending Decision</div>
                <div style={{ ...valStyle, whiteSpace: "pre-wrap" }}>{matter.pending_decision}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Rulemaking Details */}
      {matter.matter_type === "rulemaking" && (matter.federal_register_citation || matter.unified_agenda_priority || matter.docket_number) && (
        <div style={{ ...cardStyle, marginBottom: 24 }}>
          <div style={sectionTitle}>Rulemaking Details</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <div><div style={labelStyle}>FR Citation</div><div style={valStyle}>{matter.federal_register_citation || "\u2014"}</div></div>
            <div><div style={labelStyle}>Unified Agenda Priority</div><div style={valStyle}>{matter.unified_agenda_priority || "\u2014"}</div></div>
            <div><div style={labelStyle}>Docket Number</div><div style={valStyle}>{matter.docket_number || "\u2014"}</div></div>
          </div>
        </div>
      )}

      {/* Tags */}
      <div style={{ ...cardStyle, marginBottom: 24, padding: "14px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div style={{ ...labelStyle, marginBottom: 0 }}>Tags</div>
          {(tags || []).map((t) => (
            <span key={t.id || t.tag_id} style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              background: "rgba(59,130,246,0.12)", color: theme.accent.blue,
              fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 12,
            }}>
              {t.name || t.tag_name}
              <button
                onClick={() => handleRemoveTag(t.id || t.tag_id)}
                style={{
                  background: "transparent", border: "none", cursor: "pointer",
                  color: theme.accent.blue, fontSize: 13, padding: "0 2px", lineHeight: 1, opacity: 0.7,
                }}
                title="Remove tag"
              >&times;</button>
            </span>
          ))}
          {!showNewTag && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <select style={{ ...inputStyle, width: 160, padding: "4px 8px", fontSize: 12 }}
                value={selectedTagId} onChange={(e) => setSelectedTagId(e.target.value)}>
                <option value="">Add tag...</option>
                {availableTags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {selectedTagId && (
                <button style={{ ...btnPrimary, padding: "4px 10px", fontSize: 11 }} onClick={handleAddTag}>Add</button>
              )}
              <button
                onClick={() => setShowNewTag(true)}
                style={{ ...btnSecondary, padding: "4px 10px", fontSize: 11 }}
              >New Tag</button>
            </div>
          )}
          {showNewTag && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                style={{ ...inputStyle, width: 140, padding: "4px 8px", fontSize: 12 }}
                placeholder="Tag name..."
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateTag()}
              />
              <button style={{ ...btnPrimary, padding: "4px 10px", fontSize: 11 }} onClick={handleCreateTag}>Create</button>
              <button style={{ ...btnSecondary, padding: "4px 10px", fontSize: 11 }} onClick={() => { setShowNewTag(false); setNewTagName(""); }}>Cancel</button>
            </div>
          )}
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: `1px solid ${theme.border.default}`, paddingBottom: 0, flexWrap: "wrap" }}>
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "10px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer",
              background: "transparent", border: "none",
              color: activeTab === tab.key ? theme.accent.blue : theme.text.faint,
              borderBottom: activeTab === tab.key ? `2px solid ${theme.accent.blue}` : "2px solid transparent",
              marginBottom: -1,
            }}
          >{tab.label}</button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={cardStyle}>
        {activeTab === "Activity" && <ActivityTab matterId={id} matter={matter} refetch={refetch} toast={toast} enums={enums} />}
        {activeTab === "Work" && <WorkTab matterId={id} activeTab={activeTab} />}
        {activeTab === "Stakeholders" && <StakeholdersTab matterId={id} matter={matter} refetch={refetch} toast={toast} allPeople={allPeople} allOrgs={allOrgs} />}
        {activeTab === "Intelligence" && <IntelligenceTab matterId={id} activeTab={activeTab} />}
        {activeTab === "Dependencies" && <DependenciesTab matterId={id} matter={matter} refetch={refetch} toast={toast} allMatters={allMatters} enums={enums} />}
        {activeTab === "Rulemaking" && <RulemakingTab matterId={id} />}
      </div>

      <ConfirmDialog
        isOpen={confirmDialog.open}
        onClose={() => setConfirmDialog(d => ({ ...d, open: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmLabel={confirmDialog.danger ? "Delete" : "Remove"}
        danger={confirmDialog.danger}
      />
    </div>
  );
}
