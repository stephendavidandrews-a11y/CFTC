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
  getEnums, deleteMatter,
  addRegulatoryId, removeRegulatoryId
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
  const [showRegIdForm, setShowRegIdForm] = useState(false);
  const [regIdType, setRegIdType] = useState("fr_citation");
  const [regIdValue, setRegIdValue] = useState("");
  const [regIdRelationship, setRegIdRelationship] = useState("primary");

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

  const handleAddRegId = useCallback(async () => {
    if (!regIdValue.trim()) return;
    try {
      await addRegulatoryId(id, { id_type: regIdType, id_value: regIdValue.trim(), relationship: regIdRelationship });
      setRegIdValue("");
      setShowRegIdForm(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Failed to add regulatory ID"); }
  }, [id, regIdType, regIdValue, regIdRelationship, refetch]);

  const handleRemoveRegId = useCallback(async (rid) => {
    try {
      await removeRegulatoryId(id, rid);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Failed to remove regulatory ID"); }
  }, [id, refetch]);

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
    { label: "Blocker", value: matter.blocker, render: (v) => v ? <span style={{ color: "#ef5350", fontWeight: 600 }}>{v}</span> : <span style={{ color: "#888" }}>None</span> },
  ];

  const infoRight = [
    { label: "Owner", value: matter.owner_name || matter.owner },
    { label: "Client Org", value: matter.client_org_name || matter.client_org },
    { label: "Opened Date", value: formatDate(matter.opened_date || matter.created_at) },
    { label: "Work Deadline", value: formatDate(matter.work_deadline) },
    { label: "External Deadline", value: formatDate(matter.external_deadline) },
    { label: "Next Step", value: matter.next_step },
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
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
            {matter.matter_number && (
              <span style={{ fontSize: 12, color: theme.text.faint }}>#{matter.matter_number}</span>
            )}
            {matter.source && matter.source !== "manual" && (
              <Badge bg="rgba(100,181,246,0.15)" text="#64b5f6" label={matter.source} />
            )}
          </div>
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
              <div style={valStyle}>{item.render ? item.render(item.value) : (item.value || "\u2014")}</div>
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

      {/* Extension Section */}
      {(() => {
        const extBorderColor =
          matter.matter_type === "rulemaking" ? "#ce93d8" :
          matter.matter_type === "guidance" ? "#64b5f6" : "#ef5350";
        const extLabel =
          matter.matter_type === "rulemaking" ? "Rulemaking" :
          matter.matter_type === "guidance" ? "Guidance" : "Enforcement";
        const ext = matter.extension;

        if (ext) {
          // Comment period badge logic
          let commentBadge = null;
          if (matter.matter_type === "rulemaking" && matter.comment_period_status) {
            if (matter.comment_period_status === "closed") {
              commentBadge = (
                <Badge bg="rgba(136,136,136,0.15)" text="#888" label={`Comment Period Closed${matter.comment_period_closes ? ` on ${formatDate(matter.comment_period_closes)}` : ""}`} />
              );
            } else if (matter.comment_period_status === "open") {
              const days = matter.comment_period_closes
                ? Math.ceil((new Date(matter.comment_period_closes) - new Date()) / 86400000)
                : null;
              const badgeColor = days !== null && days <= 3 ? "#ef5350" : days !== null && days <= 14 ? "#ffb74d" : "#888";
              const badgeBg = days !== null && days <= 3 ? "rgba(239,83,80,0.15)" : days !== null && days <= 14 ? "rgba(255,183,77,0.15)" : "rgba(136,136,136,0.15)";
              commentBadge = (
                <Badge bg={badgeBg} text={badgeColor} label={days !== null ? `Comment Period: ${days} day${days !== 1 ? "s" : ""} left` : "Comment Period Open"} />
              );
            }
          }

          return (
            <div style={{ marginTop: 16, marginBottom: 16, borderLeft: `3px solid ${extBorderColor}`, paddingLeft: 16 }}>
              <h4 style={{ color: extBorderColor, marginBottom: 8 }}>{extLabel} Details</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 24px" }}>
                {matter.matter_type === "rulemaking" && (<>
                  {ext.rin && <div><span style={{ color: "#888" }}>RIN</span> <span style={valStyle}>{ext.rin}</span></div>}
                  {ext.regulatory_stage && <div><span style={{ color: "#888" }}>Regulatory Stage</span> <span style={valStyle}>{ext.regulatory_stage}</span></div>}
                  {ext.workflow_status && <div><span style={{ color: "#888" }}>Workflow Status</span> <span style={valStyle}>{ext.workflow_status}</span></div>}
                  {commentBadge && <div style={{ gridColumn: "1 / -1" }}>{commentBadge}</div>}
                  {ext.cfr_citation && <div><span style={{ color: "#888" }}>CFR Citation</span> <span style={valStyle}>{ext.cfr_citation}</span></div>}
                  {ext.docket_number && <div><span style={{ color: "#888" }}>Docket Number</span> <span style={valStyle}>{ext.docket_number}</span></div>}
                  {ext.fr_doc_number && <div><span style={{ color: "#888" }}>FR Doc Number</span> <span style={valStyle}>{ext.fr_doc_number}</span></div>}
                  {ext.federal_register_citation && <div><span style={{ color: "#888" }}>Federal Register Citation</span> <span style={valStyle}>{ext.federal_register_citation}</span></div>}
                  {ext.unified_agenda_priority && <div><span style={{ color: "#888" }}>Unified Agenda Priority</span> <span style={valStyle}>{ext.unified_agenda_priority}</span></div>}
                  {ext.interagency_role && <div><span style={{ color: "#888" }}>Interagency Role</span> <span style={valStyle}>{ext.interagency_role}</span></div>}
                  {ext.is_petition && <div><Badge bg="rgba(239,83,80,0.15)" text="#ef5350" label="Petition" /></div>}
                  {ext.petition_disposition && <div><span style={{ color: "#888" }}>Petition Disposition</span> <span style={valStyle}>{ext.petition_disposition}</span></div>}
                  {ext.review_trigger && <div><span style={{ color: "#888" }}>Review Trigger</span> <span style={valStyle}>{ext.review_trigger}</span></div>}
                </>)}
                {matter.matter_type === "guidance" && (<>
                  {ext.instrument_type && <div><span style={{ color: "#888" }}>Instrument Type</span> <span style={valStyle}>{ext.instrument_type}</span></div>}
                  {ext.cftc_letter_number && <div><span style={{ color: "#888" }}>CFTC Letter Number</span> <span style={valStyle}>{ext.cftc_letter_number}</span></div>}
                  {ext.workflow_status && <div><span style={{ color: "#888" }}>Workflow Status</span> <span style={valStyle}>{ext.workflow_status}</span></div>}
                  {ext.published_in_fr != null && <div><Badge bg={ext.published_in_fr ? "rgba(129,199,132,0.15)" : "rgba(136,136,136,0.15)"} text={ext.published_in_fr ? "#81c784" : "#888"} label={ext.published_in_fr ? "Published in FR" : "Not in FR"} /></div>}
                  {(ext.requestor_name || ext.requestor_org) && <div><span style={{ color: "#888" }}>Requestor</span> <span style={valStyle}>{[ext.requestor_name, ext.requestor_org].filter(Boolean).join(", ")}</span></div>}
                  {ext.requestor_counsel && <div><span style={{ color: "#888" }}>Requestor Counsel</span> <span style={valStyle}>{ext.requestor_counsel}</span></div>}
                  {ext.request_date && <div><span style={{ color: "#888" }}>Request Date</span> <span style={valStyle}>{formatDate(ext.request_date)}</span></div>}
                  {ext.issuing_office && <div><span style={{ color: "#888" }}>Issuing Office</span> <span style={valStyle}>{ext.issuing_office}</span></div>}
                  {ext.signatory && <div><span style={{ color: "#888" }}>Signatory</span> <span style={valStyle}>{ext.signatory}</span></div>}
                  {ext.staff_contact && <div><span style={{ color: "#888" }}>Staff Contact</span> <span style={valStyle}>{ext.staff_contact}</span></div>}
                  {ext.legal_question && <div style={{ gridColumn: "1 / -1" }}><span style={{ color: "#888" }}>Legal Question</span> <span style={{ ...valStyle, whiteSpace: "pre-wrap" }}>{ext.legal_question}</span></div>}
                  {ext.cea_provisions && <div><span style={{ color: "#888" }}>CEA Provisions</span> <span style={valStyle}>{ext.cea_provisions}</span></div>}
                  {ext.cfr_provisions && <div><span style={{ color: "#888" }}>CFR Provisions</span> <span style={valStyle}>{ext.cfr_provisions}</span></div>}
                  {ext.conditions_summary && <div style={{ gridColumn: "1 / -1" }}><span style={{ color: "#888" }}>Conditions Summary</span> <span style={{ ...valStyle, whiteSpace: "pre-wrap" }}>{ext.conditions_summary}</span></div>}
                  {ext.amends_matter && <div><span style={{ color: "#888" }}>Amends Matter</span> <span style={valStyle}><a href={`/matters/${ext.amends_matter}`} style={{ color: theme.accent.blue }}>{ext.amends_matter}</a></span></div>}
                  {ext.prior_letter_number && <div><span style={{ color: "#888" }}>Prior Letter Number</span> <span style={valStyle}>{ext.prior_letter_number}</span></div>}
                  {ext.issuance_date && <div><span style={{ color: "#888" }}>Issuance Date</span> <span style={valStyle}>{formatDate(ext.issuance_date)}</span></div>}
                  {ext.expiration_date && <div><span style={{ color: "#888" }}>Expiration Date</span> <span style={valStyle}>{formatDate(ext.expiration_date)}</span></div>}
                </>)}
                {matter.matter_type === "enforcement" && (<>
                  {ext.requesting_division && <div><span style={{ color: "#888" }}>Requesting Division</span> <span style={valStyle}>{ext.requesting_division}</span></div>}
                  {ext.enforcement_reference && <div><span style={{ color: "#888" }}>Enforcement Reference</span> <span style={valStyle}>{ext.enforcement_reference}</span></div>}
                  {ext.workflow_status && <div><span style={{ color: "#888" }}>Workflow Status</span> <span style={valStyle}>{ext.workflow_status}</span></div>}
                  {ext.legal_issue_type && <div><span style={{ color: "#888" }}>Legal Issue Type</span> <span style={valStyle}>{ext.legal_issue_type}</span></div>}
                  {ext.support_type && <div><span style={{ color: "#888" }}>Support Type</span> <span style={valStyle}>{ext.support_type}</span></div>}
                  {ext.litigation_stage && <div><span style={{ color: "#888" }}>Litigation Stage</span> <span style={valStyle}>{ext.litigation_stage}</span></div>}
                  {ext.court_or_forum && <div><span style={{ color: "#888" }}>Court/Forum</span> <span style={valStyle}>{ext.court_or_forum}</span></div>}
                  {ext.deadline_source && <div><span style={{ color: "#888" }}>Deadline Source</span> <span style={valStyle}>{ext.deadline_source}</span></div>}
                  {ext.privilege_flags && <div><span style={{ color: "#888" }}>Privilege Flags</span> <span style={valStyle}>{ext.privilege_flags}</span></div>}
                  {ext.confidential && <div><Badge bg="rgba(239,83,80,0.15)" text="#ef5350" label="Confidential" /></div>}
                </>)}
              </div>
            </div>
          );
        } else if (["rulemaking", "guidance", "enforcement"].includes(matter.matter_type)) {
          return (
            <div style={{ padding: "12px 16px", border: "1px dashed #555", borderRadius: 6, margin: "16px 0" }}>
              <span style={{ color: "#888" }}>No {matter.matter_type} details recorded.</span>
            </div>
          );
        }
        return null;
      })()}

      {/* Context Section */}
      {(matter.description || matter.outcome_summary) && (
        <div style={{ ...cardStyle, marginBottom: 24 }}>
          <div style={sectionTitle}>Context</div>
          {matter.description && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Description</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.description}</div>
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
      {matter.next_step && (
        <div style={{ ...cardStyle, marginBottom: 24, background: theme.bg.cardHover, borderLeft: `3px solid ${theme.accent.blue}` }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.02em" }}>Current State</div>
          <div>
            <div style={labelStyle}>Next Step</div>
            <div style={valStyle}>{matter.next_step}</div>
          </div>
        </div>
      )}

      {/* Regulatory IDs */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={sectionTitle}>Regulatory IDs</div>
          <button style={{ ...btnSecondary, padding: "4px 10px", fontSize: 11 }} onClick={() => setShowRegIdForm((v) => !v)}>
            {showRegIdForm ? "Cancel" : "+ Add"}
          </button>
        </div>
        {(matter.regulatory_ids && matter.regulatory_ids.length > 0) ? matter.regulatory_ids.map((rid) => (
          <div key={rid.id} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <Badge bg="rgba(100,181,246,0.15)" text="#64b5f6" label={rid.id_type} />
            <span style={valStyle}>{rid.id_value}</span>
            {rid.relationship && <span style={{ fontSize: 11, color: "#888" }}>({rid.relationship})</span>}
            <button
              onClick={() => handleRemoveRegId(rid.id)}
              style={{ background: "transparent", border: "none", cursor: "pointer", color: "#ef5350", fontSize: 14, padding: "0 4px", lineHeight: 1, opacity: 0.7 }}
              title="Remove"
            >&#128465;</button>
          </div>
        )) : (
          <div style={{ color: "#888", fontSize: 12 }}>No regulatory IDs linked.</div>
        )}
        {showRegIdForm && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
            <select style={{ ...inputStyle, width: 140, padding: "4px 8px", fontSize: 12 }} value={regIdType} onChange={(e) => setRegIdType(e.target.value)}>
              <option value="fr_citation">FR Citation</option>
              <option value="rin">RIN</option>
              <option value="cfr_part">CFR Part</option>
              <option value="docket_number">Docket Number</option>
              <option value="stage1_doc_id">Stage 1 Doc ID</option>
              <option value="letter_number">Letter Number</option>
            </select>
            <input
              style={{ ...inputStyle, width: 180, padding: "4px 8px", fontSize: 12 }}
              placeholder="ID value..."
              value={regIdValue}
              onChange={(e) => setRegIdValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddRegId()}
            />
            <select style={{ ...inputStyle, width: 120, padding: "4px 8px", fontSize: 12 }} value={regIdRelationship} onChange={(e) => setRegIdRelationship(e.target.value)}>
              <option value="primary">Primary</option>
              <option value="related">Related</option>
              <option value="under_review">Under Review</option>
              <option value="amends">Amends</option>
              <option value="supersedes">Supersedes</option>
            </select>
            <button style={{ ...btnPrimary, padding: "4px 10px", fontSize: 11 }} onClick={handleAddRegId}>Save</button>
          </div>
        )}
      </div>

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
