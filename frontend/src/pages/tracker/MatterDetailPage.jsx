import React, { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import {
  getMatter, addMatterUpdate, addMatterPerson, removeMatterPerson,
  addMatterOrg, removeMatterOrg, listTasks, listMeetings, listDocuments, listDecisions,
  listPeople, listOrganizations, listMatters,
  addMatterDependency, removeMatterDependency,
  getMatterTags, addMatterTag, removeMatterTag, listTags, createTag,
  getEnums, deleteMatter, getContextNotesByEntity, listContextNotes,
  listCommentTopics, createCommentTopic, updateCommentTopic, deleteCommentTopic,
  createCommentQuestion, updateCommentQuestion, deleteCommentQuestion, moveCommentQuestion,
  listMatterDirectives
} from "../../api/tracker";
import { useDrawer } from "../../contexts/DrawerContext";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import Breadcrumb from "../../components/shared/Breadcrumb";

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

function formatDate(d) {
  if (!d) return "\u2014";
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const TABS = ["Updates", "Tasks", "Stakeholders", "Organizations", "Meetings", "Documents", "Decisions", "Dependencies", "Comment Topics", "Context Notes"];

// ── Comment Topics Tab ──────────────────────────────────────────────────────

const POSITION_STATUS_COLORS = {
  open: { bg: "#2a2a2a", text: "#999" },
  research: { bg: "#1a3a5c", text: "#60a5fa" },
  draft_position: { bg: "#3b2a1a", text: "#fbbf24" },
  under_review: { bg: "#2a1a3b", text: "#c084fc" },
  final: { bg: "#1a3b2a", text: "#34d399" },
  deferred: { bg: "#2a2a2a", text: "#666" },
  not_applicable: { bg: "#2a2a2a", text: "#666" },
};

function CommentTopicsTab({ matterId }) {
  const [expandedId, setExpandedId] = React.useState(null);
  const [addingQuestion, setAddingQuestion] = React.useState(null);
  const [newQ, setNewQ] = React.useState({ question_number: "", question_text: "" });
  const { openDrawer } = useDrawer();

  const { data: topicsData, loading, error, refetch } = useApi(
    () => listCommentTopics(matterId), [matterId]
  );

  const topics = topicsData?.items || [];

  const handleDeleteTopic = async (topicId) => {
    if (!window.confirm("Delete this topic and all its questions?")) return;
    try {
      await deleteCommentTopic(topicId);
      refetch();
    } catch (err) { toast.error(err.detail || "Delete failed"); }
  };

  const handleAddQuestion = async (topicId) => {
    if (!newQ.question_number || !newQ.question_text) return;
    try {
      await createCommentQuestion(topicId, newQ);
      setNewQ({ question_number: "", question_text: "" });
      setAddingQuestion(null);
      refetch();
    } catch (err) { toast.error(err.detail || "Add failed"); }
  };

  const handleDeleteQuestion = async (qId) => {
    try {
      await deleteCommentQuestion(qId);
      refetch();
    } catch (err) { toast.error(err.detail || "Delete failed"); }
  };

  const handleMoveQuestion = async (qId, topicId) => {
    try {
      await moveCommentQuestion(qId, topicId);
      refetch();
    } catch (err) { toast.error(err.detail || "Move failed"); }
  };

  // Summary bar
  const total = topics.length;
  const statusCounts = {};
  let totalQs = 0;
  topics.forEach((t) => {
    statusCounts[t.position_status] = (statusCounts[t.position_status] || 0) + 1;
    totalQs += (t.questions || []).length;
  });

  if (loading) return <div style={{ color: theme.text.dim, padding: 24 }}>Loading comment topics...</div>;
  if (error) return <div style={{ color: theme.accent.red, padding: 24 }}>Error: {error.message}</div>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>Comment Topics</div>
        <button style={{ padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer" }}
          onClick={() => openDrawer("comment_topic", { matter_id: matterId }, refetch)}>
          + Add Topic
        </button>
      </div>

      {/* Summary bar */}
      {total > 0 && (
        <div style={{ fontSize: 12, color: theme.text.dim, marginBottom: 12 }}>
          {total} topics ({totalQs} questions): {Object.entries(statusCounts).map(([s, c]) => `${c} ${s.replace(/_/g, " ")}`).join(" \u00b7 ")}
        </div>
      )}

      {topics.length === 0 ? (
        <EmptyState icon="💬" title="No comment topics" subtitle="Add topics to track position development for this matter" />
      ) : (
        <div>
          {topics.map((topic) => {
            const isExpanded = expandedId === topic.id;
            const questions = topic.questions || [];
            const sc = POSITION_STATUS_COLORS[topic.position_status] || {};
            return (
              <div key={topic.id} style={{ background: theme.bg.card, borderRadius: 8,
                border: `1px solid ${theme.border.default}`, marginBottom: 8, overflow: "hidden" }}>
                {/* Topic row */}
                <div onClick={() => setExpandedId(isExpanded ? null : topic.id)}
                  style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                    cursor: "pointer", fontSize: 13 }}>
                  <span style={{ color: theme.text.dim, fontSize: 10 }}>{isExpanded ? "\u25bc" : "\u25b6"}</span>
                  <span style={{ flex: 1, fontWeight: 600, color: theme.text.primary }}>{topic.topic_label}</span>
                  <span style={{ color: theme.text.dim, fontSize: 12, minWidth: 50 }}>
                    {questions.length > 0 ? `${questions.length} Qs` : "\u2014"}
                  </span>
                  {topic.topic_area && <Badge bg={theme.bg.input} text={theme.text.secondary}
                    label={topic.topic_area.replace(/_/g, " ")} />}
                  <Badge bg={sc.bg || theme.bg.input} text={sc.text || theme.text.dim}
                    label={topic.position_status.replace(/_/g, " ")} />
                  {topic.priority && <span style={{ fontSize: 11, color: topic.priority === "critical" ? theme.accent.red :
                    topic.priority === "high" ? "#fbbf24" : theme.text.dim }}>{topic.priority}</span>}
                  {topic.due_date && <span style={{ fontSize: 11, color: new Date(topic.due_date) < new Date() ? theme.accent.red : theme.text.dim }}>
                    {new Date(topic.due_date).toLocaleDateString()}</span>}
                  <span style={{ fontSize: 12, color: theme.text.dim }}>{topic.assigned_to_name || ""}</span>
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <div style={{ borderTop: `1px solid ${theme.border.default}`, padding: 14 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
                      {/* Left: Questions */}
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, marginBottom: 8 }}>
                          Questions {questions.length > 0 && `(${questions.length})`}
                        </div>
                        {questions.length === 0 ? (
                          <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic" }}>
                            No numbered questions \u2014 organic topic
                          </div>
                        ) : (
                          questions.map((q) => (
                            <div key={q.id} style={{ display: "flex", gap: 8, alignItems: "flex-start",
                              padding: "6px 0", borderBottom: `1px solid ${theme.border.default}22` }}>
                              <span style={{ fontWeight: 700, fontSize: 12, color: theme.accent.blue, minWidth: 30 }}>{q.question_number}</span>
                              <span style={{ fontSize: 12, color: theme.text.secondary, flex: 1 }}>{q.question_text}</span>
                              <div style={{ display: "flex", gap: 4 }}>
                                <select onChange={(e) => { if (e.target.value) handleMoveQuestion(q.id, e.target.value); e.target.value = ""; }}
                                  style={{ fontSize: 10, background: theme.bg.input, border: `1px solid ${theme.border.default}`,
                                    borderRadius: 4, color: theme.text.dim, padding: "2px 4px" }}>
                                  <option value="">Move...</option>
                                  {topics.filter((t) => t.id !== topic.id).map((t) =>
                                    <option key={t.id} value={t.id}>{t.topic_label.slice(0, 30)}</option>)}
                                </select>
                                <button onClick={() => handleDeleteQuestion(q.id)}
                                  style={{ background: "none", border: "none", color: theme.accent.red, cursor: "pointer", fontSize: 10 }}>\u00d7</button>
                              </div>
                            </div>
                          ))
                        )}
                        {/* Add question */}
                        {addingQuestion === topic.id ? (
                          <div style={{ marginTop: 8, display: "flex", gap: 6, alignItems: "flex-end" }}>
                            <input placeholder="#" value={newQ.question_number}
                              onChange={(e) => setNewQ({ ...newQ, question_number: e.target.value })}
                              style={{ width: 40, padding: "4px 6px", fontSize: 12, background: theme.bg.input,
                                border: `1px solid ${theme.border.default}`, borderRadius: 4, color: theme.text.primary }} />
                            <input placeholder="Question text" value={newQ.question_text}
                              onChange={(e) => setNewQ({ ...newQ, question_text: e.target.value })}
                              style={{ flex: 1, padding: "4px 6px", fontSize: 12, background: theme.bg.input,
                                border: `1px solid ${theme.border.default}`, borderRadius: 4, color: theme.text.primary }} />
                            <button onClick={() => handleAddQuestion(topic.id)}
                              style={{ padding: "4px 10px", fontSize: 11, background: theme.accent.blue,
                                color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>Add</button>
                            <button onClick={() => { setAddingQuestion(null); setNewQ({ question_number: "", question_text: "" }); }}
                              style={{ padding: "4px 8px", fontSize: 11, background: theme.bg.input,
                                color: theme.text.dim, border: "none", borderRadius: 4, cursor: "pointer" }}>Cancel</button>
                          </div>
                        ) : (
                          <button onClick={() => setAddingQuestion(topic.id)}
                            style={{ marginTop: 8, background: "none", border: "none", color: theme.accent.blue,
                              cursor: "pointer", fontSize: 11 }}>+ Add Question</button>
                        )}
                      </div>

                      {/* Right: Position & metadata */}
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, marginBottom: 8 }}>Position</div>
                        {topic.position_summary ? (
                          <div style={{ fontSize: 13, color: theme.text.primary, whiteSpace: "pre-wrap",
                            background: theme.bg.input, padding: 10, borderRadius: 6, marginBottom: 8 }}>{topic.position_summary}</div>
                        ) : (
                          <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic", marginBottom: 8 }}>No position summary yet</div>
                        )}
                        {topic.notes && (
                          <div style={{ fontSize: 12, color: theme.text.dim, marginBottom: 8 }}>
                            <span style={{ fontWeight: 600 }}>Notes:</span> {topic.notes}
                          </div>
                        )}
                        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                          <button onClick={() => openDrawer("comment_topic", topic, refetch)}
                            style={{ padding: "4px 12px", fontSize: 11, background: theme.accent.blue,
                              color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>Edit Topic</button>
                          <button onClick={() => handleDeleteTopic(topic.id)}
                            style={{ padding: "4px 12px", fontSize: 11, background: theme.accent.red,
                              color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>Delete</button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Directive Linkage (compact, shown if directives exist) ──────────────────

function DirectiveLinkage({ matterId }) {
  const { data } = useApi(() => listMatterDirectives(matterId), [matterId]);
  const directives = data?.items || [];
  if (directives.length === 0) return null;
  return (
    <div style={{ marginBottom: 12, padding: "8px 12px", background: theme.bg.card,
      borderRadius: 6, border: `1px solid ${theme.border.default}` }}>
      <span style={{ fontSize: 11, color: theme.text.dim, marginRight: 8 }}>Directives:</span>
      {directives.map((d, i) => (
        <span key={d.id}>
          {i > 0 && <span style={{ color: theme.text.dim }}> \u00b7 </span>}
          <Badge bg={theme.bg.input} text={theme.text.secondary} label={d.relationship_type?.replace(/_/g, " ") || "linked"} />
          {" "}
          <a href={`/directives/${d.directive_id}`}
            style={{ fontSize: 12, color: theme.accent.blue, textDecoration: "none" }}>{d.directive_label}</a>
        </span>
      ))}
    </div>
  );
}


export default function MatterDetailPage() {
  const { id } = useParams();
  const toast = useToastContext();
  const { openDrawer } = useDrawer();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Updates");
  const [ctxNotes, setCtxNotes] = useState([]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    listContextNotes({ matter_id: id }).then(d => {
      if (!cancelled) setCtxNotes(d?.items || []);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [id]);

  const { data: matter, loading, error, refetch } = useApi(() => getMatter(id), [id]);

  // Tab data
  const { data: tasksData, refetch: refetchTasks } = useApi(() => listTasks({ matter_id: id }), [id]);
  const { data: meetingsData, refetch: refetchMeetings } = useApi(() => listMeetings({ matter_id: id }), [id]);
  const { data: docsData, refetch: refetchDocs } = useApi(() => listDocuments({ matter_id: id }), [id]);
  const { data: decisionsData, refetch: refetchDecisions } = useApi(() => listDecisions({ matter_id: id }), [id]);

  // For inline add forms
  const { data: allPeople } = useApi(() => listPeople({ limit: 500 }), []);
  const { data: allOrgs } = useApi(() => listOrganizations({ limit: 500 }), []);

  // Update form state
  const [showUpdateForm, setShowUpdateForm] = useState(false);
  const [updateType, setUpdateType] = useState("status update");
  const [updateSummary, setUpdateSummary] = useState("");
  const [savingUpdate, setSavingUpdate] = useState(false);

  // Stakeholder inline add
  const [showStakeholderAdd, setShowStakeholderAdd] = useState(false);
  const [stakeholderForm, setStakeholderForm] = useState({ person_id: "", matter_role: "", engagement_level: "", notes: "" });

  // Org inline add
  const [showOrgAdd, setShowOrgAdd] = useState(false);
  const [orgForm, setOrgForm] = useState({ organization_id: "", organization_role: "", notes: "" });

  // Dependencies
  const { data: allMatters } = useApi(() => listMatters({ limit: 500 }), []);

  React.useEffect(() => { if (matter?.title) document.title = matter?.title + " | Command Center"; }, [matter?.title]);
  const [depForm, setDepForm] = useState({ depends_on_matter_id: "", dependency_type: "" });
  const [showDepAdd, setShowDepAdd] = useState(false);

  // Tags
  const [tags, setTags] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [selectedTagId, setSelectedTagId] = useState("");
  const [showNewTag, setShowNewTag] = useState(false);
  const [newTagName, setNewTagName] = useState("");

  const handleSaveUpdate = useCallback(async () => {
    if (!updateSummary.trim()) return;
    setSavingUpdate(true);
    try {
      await addMatterUpdate(id, { update_type: updateType, summary: updateSummary });
      setUpdateSummary("");
      setShowUpdateForm(false);
      refetch();
    } catch (e) {
      console.error("Failed to save update:", e);
      toast.error("Failed to save update: " + (e.message || "Unknown error"));
    } finally {
      setSavingUpdate(false);
    }
  }, [id, updateType, updateSummary, refetch]);

  const handleAddStakeholder = useCallback(async () => {
    if (!stakeholderForm.person_id) return;
    try {
      const cleanStakeholder = Object.fromEntries(Object.entries(stakeholderForm).filter(([_, v]) => v !== ""));
      await addMatterPerson(id, cleanStakeholder);
      setStakeholderForm({ person_id: "", matter_role: "", engagement_level: "", notes: "" });
      setShowStakeholderAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, stakeholderForm, refetch]);

  const handleRemoveStakeholder = useCallback(async (mpId) => {
    if (!window.confirm("Remove this stakeholder from the matter?")) return;
    try {
      await removeMatterPerson(id, mpId);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, refetch]);

  const handleRemoveOrg = useCallback(async (moId) => {
    if (!window.confirm("Remove this organization from the matter?")) return;
    try {
      await removeMatterOrg(id, moId);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, refetch]);

  const handleAddOrg = useCallback(async () => {
    if (!orgForm.organization_id) return;
    try {
      const cleanOrg = Object.fromEntries(Object.entries(orgForm).filter(([_, v]) => v !== ""));
      await addMatterOrg(id, cleanOrg);
      setOrgForm({ organization_id: "", organization_role: "", notes: "" });
      setShowOrgAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, orgForm, refetch]);

  // Fetch tags
  useEffect(() => {
    if (!id) return;
    getMatterTags(id).then((res) => setTags(Array.isArray(res) ? res : (res?.items || res || []))).catch(() => {});
    listTags("matter").then((res) => setAllTags(res?.items || res || [])).catch(() => {});
  }, [id]);

  // Fetch enums for inline forms
  const [enums, setLoadedEnums] = useState({});
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

  // Dependencies handlers
  const handleAddDep = useCallback(async () => {
    if (!depForm.depends_on_matter_id || !depForm.dependency_type) return;
    try {
      await addMatterDependency(id, depForm);
      setDepForm({ depends_on_matter_id: "", dependency_type: "" });
      setShowDepAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, depForm, refetch]);

  const handleRemoveDep = useCallback(async (depId) => {
    if (!window.confirm("Remove this dependency?")) return;
    try {
      await removeMatterDependency(id, depId);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [id, refetch]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading matter...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
      <Breadcrumb items={[{ label: "Matters", path: "/matters" }, { label: matter?.title || 'Matter' }]} />
        <EmptyState
          icon="⚠"
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

  const tasks = tasksData?.items || tasksData || [];
  const meetings = meetingsData?.items || meetingsData || [];
  const docs = docsData?.items || docsData || [];
  const decisions = decisionsData?.items || decisionsData || [];
  const stakeholders = matter.people || matter.stakeholders || [];
  const linkedOrgs = matter.organizations || matter.orgs || [];
  const updates = matter.updates || [];
  const peopleList = allPeople?.items || allPeople || [];
  const orgsList = allOrgs?.items || allOrgs || [];
  const mattersList = (allMatters?.items || allMatters || []).filter((m) => m.id !== id);
  const dependencies = matter.dependencies || [];
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
    { label: "Next Step", value: matter.next_step },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button onClick={() => navigate("/matters")} style={{ ...btnSecondary, padding: "5px 10px", fontSize: 11 }}>
          &larr; Back
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={titleStyle}>{matter.title}</span>
            <Badge bg={st.bg} text={st.text} label={st.label || matter.status} />
            <Badge bg={pr.bg} text={pr.text} label={pr.label || matter.priority} />
          </div>
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
          onClick={async () => {
            if (!window.confirm(`Delete "${matter.title}"? This will close the matter.`)) return;
            try {
              await deleteMatter(matter.id);
              navigate("/matters");
            } catch (e) {
              toast.error(e.message || "Operation failed");
            }
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
      {(matter.problem_statement || matter.why_it_matters || matter.description || matter.pending_decision || matter.outcome_summary) && (
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
          {matter.pending_decision && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelStyle}>Pending Decision</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{matter.pending_decision}</div>
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

      {/* Tabs */}
      
      <DirectiveLinkage matterId={id} />

      <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: `1px solid ${theme.border.default}`, paddingBottom: 0 }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "10px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer",
              background: "transparent", border: "none",
              color: activeTab === tab ? theme.accent.blue : theme.text.faint,
              borderBottom: activeTab === tab ? `2px solid ${theme.accent.blue}` : "2px solid transparent",
              marginBottom: -1,
            }}
          >{tab}</button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={cardStyle}>
        {/* UPDATES TAB */}
        {activeTab === "Updates" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Updates</div>
              <button style={btnPrimary} onClick={() => setShowUpdateForm(!showUpdateForm)}>
                {showUpdateForm ? "Cancel" : "+ Add Update"}
              </button>
            </div>
            {showUpdateForm && (
              <div style={{
                background: theme.bg.input, borderRadius: 8, padding: 16,
                border: `1px solid ${theme.border.default}`, marginBottom: 16,
              }}>
                <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                  <select style={{ ...inputStyle, width: 160 }} value={updateType} onChange={(e) => setUpdateType(e.target.value)}>
                    {(enums.update_type || ["status update", "meeting readout", "document milestone", "decision made", "blocker identified", "deadline changed", "escalation", "closure note"]).map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <textarea
                  style={{ ...inputStyle, height: 80, resize: "vertical", fontFamily: theme.font.family }}
                  placeholder="Update summary..."
                  value={updateSummary}
                  onChange={(e) => setUpdateSummary(e.target.value)}
                />
                <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                  <button style={btnPrimary} onClick={handleSaveUpdate} disabled={savingUpdate}>
                    {savingUpdate ? "Saving..." : "Save Update"}
                  </button>
                </div>
              </div>
            )}
            {updates.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint }}>No updates yet</div>
            ) : (
              updates.map((u, i) => (
                <div key={u.id || i} style={{ padding: "12px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    {u.update_type && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, color: theme.accent.blue,
                        background: "rgba(59,130,246,0.12)", padding: "2px 7px", borderRadius: 3,
                      }}>{u.update_type}</span>
                    )}
                    <span style={{ fontSize: 11, color: theme.text.faint }}>{u.author || ""}</span>
                    <span style={{ fontSize: 11, color: theme.text.ghost, marginLeft: "auto" }}>{formatDate(u.created_at || u.date)}</span>
                  </div>
                  <div style={{ fontSize: 13, color: theme.text.muted, lineHeight: 1.5 }}>{u.summary}</div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TASKS TAB */}
        {activeTab === "Tasks" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Tasks</div>
              <button style={btnPrimary} onClick={() => openDrawer("task", { matter_id: id }, refetchTasks)}>
                + Add Task
              </button>
            </div>
            {tasks.length === 0 ? (
              <EmptyState title="No tasks" message="Add tasks to track work on this matter." />
            ) : (
              <DataTable
                columns={[
                  { key: "title", label: "Title" },
                  {
                    key: "status", label: "Status", width: 110,
                    render: (val) => {
                      const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                      return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
                    },
                  },
                  { key: "owner_name", label: "Assignee", width: 130 },
                  { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
                  {
                    key: "priority", label: "Priority", width: 100,
                    render: (val) => {
                      const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                      return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
                    },
                  },
                ]}
                data={tasks}
                onRowClick={(row) => openDrawer("task", row, refetchTasks)}
              />
            )}
          </div>
        )}

        {/* STAKEHOLDERS TAB */}
        {activeTab === "Stakeholders" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Stakeholders</div>
              <button style={btnPrimary} onClick={() => setShowStakeholderAdd(!showStakeholderAdd)}>
                {showStakeholderAdd ? "Cancel" : "+ Add Stakeholder"}
              </button>
            </div>
            {showStakeholderAdd && (
              <div style={{
                display: "flex", gap: 8, alignItems: "center", marginBottom: 14,
                background: theme.bg.input, padding: 12, borderRadius: 8, border: `1px solid ${theme.border.default}`,
              }}>
                <select style={{ ...inputStyle, width: 200 }}
                  value={stakeholderForm.person_id}
                  onChange={(e) => setStakeholderForm((p) => ({ ...p, person_id: e.target.value }))}
                >
                  <option value="">Select person...</option>
                  {peopleList.map((p) => <option key={p.id} value={p.id}>{p.full_name || `${p.first_name} ${p.last_name}`}</option>)}
                </select>
                <select style={{ ...inputStyle, width: 140 }}
                  value={stakeholderForm.matter_role}
                  onChange={(e) => setStakeholderForm((p) => ({ ...p, matter_role: e.target.value }))}
                >
                  <option value="">Role...</option>
                  {(enums.matter_role || []).map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <select style={{ ...inputStyle, width: 140 }}
                  value={stakeholderForm.engagement_level}
                  onChange={(e) => setStakeholderForm((p) => ({ ...p, engagement_level: e.target.value }))}
                >
                  <option value="">Engagement...</option>
                  {(enums.engagement_level || []).map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
                <input style={{ ...inputStyle, width: 180 }}
                  placeholder="Notes..."
                  value={stakeholderForm.notes}
                  onChange={(e) => setStakeholderForm((p) => ({ ...p, notes: e.target.value }))}
                />
                <button style={btnPrimary} onClick={handleAddStakeholder}>Add</button>
              </div>
            )}
            {stakeholders.length === 0 ? (
              <EmptyState title="No stakeholders" message="Link people to this matter." />
            ) : (
              <DataTable
                columns={[
                  { key: "name", label: "Name", render: (v, row) => row.full_name || row.name || `${row.first_name || ""} ${row.last_name || ""}`.trim() || "\u2014" },
                  { key: "matter_role", label: "Role", width: 130 },
                  { key: "engagement_level", label: "Engagement", width: 120 },
                  { key: "org_name", label: "Organization", width: 160 },
                  {
                    key: "_remove", label: "", width: 60, sortable: false,
                    render: (_, row) => (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRemoveStakeholder(row.id); }}
                        style={{
                          background: "transparent", border: "none", cursor: "pointer",
                          color: "#ef4444", fontSize: 11, fontWeight: 600, padding: "2px 8px",
                          borderRadius: 4, opacity: 0.7,
                        }}
                        onMouseEnter={(e) => e.target.style.opacity = "1"}
                        onMouseLeave={(e) => e.target.style.opacity = "0.7"}
                        title="Remove from matter"
                      >Remove</button>
                    ),
                  },
                ]}
                data={stakeholders}
              />
            )}
          </div>
        )}

        {/* ORGANIZATIONS TAB */}
        {activeTab === "Organizations" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Organizations</div>
              <button style={btnPrimary} onClick={() => setShowOrgAdd(!showOrgAdd)}>
                {showOrgAdd ? "Cancel" : "+ Link Org"}
              </button>
            </div>
            {showOrgAdd && (
              <div style={{
                display: "flex", gap: 8, alignItems: "center", marginBottom: 14,
                background: theme.bg.input, padding: 12, borderRadius: 8, border: `1px solid ${theme.border.default}`,
              }}>
                <select style={{ ...inputStyle, width: 220 }}
                  value={orgForm.organization_id}
                  onChange={(e) => setOrgForm((p) => ({ ...p, organization_id: e.target.value }))}
                >
                  <option value="">Select organization...</option>
                  {orgsList.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
                <select style={{ ...inputStyle, width: 160 }}
                  value={orgForm.organization_role}
                  onChange={(e) => setOrgForm((p) => ({ ...p, organization_role: e.target.value }))}
                >
                  <option value="">Role...</option>
                  {(enums.organization_role || []).map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <input style={{ ...inputStyle, width: 180 }}
                  placeholder="Notes..."
                  value={orgForm.notes}
                  onChange={(e) => setOrgForm((p) => ({ ...p, notes: e.target.value }))}
                />
                <button style={btnPrimary} onClick={handleAddOrg}>Add</button>
              </div>
            )}
            {linkedOrgs.length === 0 ? (
              <EmptyState title="No organizations" message="Link organizations to this matter." />
            ) : (
              <DataTable
                columns={[
                  { key: "name", label: "Name" },
                  { key: "organization_role", label: "Role", width: 160 },
                  {
                    key: "_remove", label: "", width: 60, sortable: false,
                    render: (_, row) => (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRemoveOrg(row.id); }}
                        style={{
                          background: "transparent", border: "none", cursor: "pointer",
                          color: "#ef4444", fontSize: 11, fontWeight: 600, padding: "2px 8px",
                          borderRadius: 4, opacity: 0.7,
                        }}
                        onMouseEnter={(e) => e.target.style.opacity = "1"}
                        onMouseLeave={(e) => e.target.style.opacity = "0.7"}
                        title="Remove from matter"
                      >Remove</button>
                    ),
                  },
                ]}
                data={linkedOrgs}
              />
            )}
          </div>
        )}

        {/* MEETINGS TAB */}
        {activeTab === "Meetings" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Meetings</div>
              <button style={btnPrimary} onClick={() => openDrawer("meeting", { matter_id: id }, refetchMeetings)}>
                + Add Meeting
              </button>
            </div>
            {meetings.length === 0 ? (
              <EmptyState title="No meetings" message="No meetings linked to this matter yet." />
            ) : (
              <DataTable
                columns={[
                  { key: "title", label: "Title" },
                  { key: "date_time_start", label: "Date", width: 140, render: (v) => formatDate(v) },
                  { key: "meeting_type", label: "Type", width: 120 },
                ]}
                data={meetings}
                onRowClick={(row) => navigate(`/meetings/${row.id}`)}
              />
            )}
          </div>
        )}

        {/* DOCUMENTS TAB */}
        {activeTab === "Documents" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Documents</div>
              <button style={btnPrimary} onClick={() => openDrawer("document", { matter_id: id }, refetchDocs)}>
                + Add Document
              </button>
            </div>
            {docs.length === 0 ? (
              <EmptyState title="No documents" message="No documents attached to this matter." />
            ) : (
              <DataTable
                columns={[
                  { key: "title", label: "Title" },
                  { key: "document_type", label: "Type", width: 130 },
                  { key: "status", label: "Status", width: 110 },
                  { key: "version_label", label: "Version", width: 80 },
                  { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
                ]}
                data={docs}
                onRowClick={(row) => openDrawer("document", row, refetchDocs)}
              />
            )}
          </div>
        )}

        {/* DECISIONS TAB */}
        {activeTab === "Decisions" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Decisions</div>
              <button style={btnPrimary} onClick={() => openDrawer("decision", { matter_id: id }, refetchDecisions)}>
                + Add Decision
              </button>
            </div>
            {decisions.length === 0 ? (
              <EmptyState title="No decisions" message="No decisions recorded for this matter." />
            ) : (
              <DataTable
                columns={[
                  { key: "title", label: "Title" },
                  {
                    key: "status", label: "Status", width: 120,
                    render: (val) => {
                      const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                      return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
                    },
                  },
                  { key: "made_at", label: "Decided", width: 130, render: (v) => formatDate(v) },
                  { key: "decision_due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
                ]}
                data={decisions}
                onRowClick={(row) => openDrawer("decision", row, refetchDecisions)}
              />
            )}
          </div>
        )}

        {/* DEPENDENCIES TAB */}
        {activeTab === "Dependencies" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={sectionTitle}>Dependencies</div>
              <button style={btnPrimary} onClick={() => setShowDepAdd(!showDepAdd)}>
                {showDepAdd ? "Cancel" : "+ Add Dependency"}
              </button>
            </div>
            {showDepAdd && (
              <div style={{
                display: "flex", gap: 8, alignItems: "center", marginBottom: 14,
                background: theme.bg.input, padding: 12, borderRadius: 8, border: `1px solid ${theme.border.default}`,
              }}>
                <select style={{ ...inputStyle, width: 280 }}
                  value={depForm.depends_on_matter_id}
                  onChange={(e) => setDepForm((p) => ({ ...p, depends_on_matter_id: e.target.value }))}
                >
                  <option value="">Select matter...</option>
                  {mattersList.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.matter_number ? `#${m.matter_number} - ` : ""}{m.title}
                    </option>
                  ))}
                </select>
                <select style={{ ...inputStyle, width: 180 }}
                  value={depForm.dependency_type}
                  onChange={(e) => setDepForm((p) => ({ ...p, dependency_type: e.target.value }))}
                >
                  <option value="">Type...</option>
                  {["legal dependency", "policy dependency", "sequencing dependency", "approval dependency", "external dependency", "shared deadline", "related risk"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <button style={btnPrimary} onClick={handleAddDep}>Add</button>
              </div>
            )}
            {dependencies.length === 0 ? (
              <EmptyState title="No dependencies" message="Add dependencies to track related matters." />
            ) : (
              <DataTable
                columns={[
                  {
                    key: "depends_on_title", label: "Related Matter",
                    render: (v, row) => row.depends_on_title || row.depends_on_matter_title || `Matter #${row.depends_on_matter_id}`,
                  },
                  { key: "dependency_type", label: "Type", width: 170 },
                  { key: "notes", label: "Notes", width: 200, render: (v) => v || "\u2014" },
                  {
                    key: "_remove", label: "", width: 60, sortable: false,
                    render: (_, row) => (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRemoveDep(row.id); }}
                        style={{
                          background: "transparent", border: "none", cursor: "pointer",
                          color: "#ef4444", fontSize: 11, fontWeight: 600, padding: "2px 8px",
                          borderRadius: 4, opacity: 0.7,
                        }}
                        onMouseEnter={(e) => e.target.style.opacity = "1"}
                        onMouseLeave={(e) => e.target.style.opacity = "0.7"}
                        title="Remove dependency"
                      >Remove</button>
                    ),
                  },
                ]}
                data={dependencies}
              />
            )}
          </div>
        )}

        
      {activeTab === "Comment Topics" && <CommentTopicsTab matterId={id} />}

      {activeTab === "Context Notes" && (
          <div style={cardStyle}>
            <div style={sectionTitle}>Context Notes ({ctxNotes.length})</div>
            {ctxNotes.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
                No context notes linked to this matter.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {ctxNotes.map((note) => {
                  const CAT_C = { people_insight: { bg: "#312e81", text: "#c4b5fd" }, institutional_knowledge: { bg: "#1e3a5f", text: "#60a5fa" }, process_note: { bg: "#0c4a6e", text: "#67e8f9" }, policy_operating_rule: { bg: "#14532d", text: "#4ade80" }, strategic_context: { bg: "#422006", text: "#fbbf24" }, culture_climate: { bg: "#431407", text: "#fb923c" }, relationship_dynamic: { bg: "#1e1b4b", text: "#a78bfa" } };
                  const POS_C = { factual: { bg: "#1e3a5f", text: "#60a5fa" }, attributed_view: { bg: "#78350f", text: "#fbbf24" }, tentative: { bg: "#1f2937", text: "#9ca3af" }, interpretive: { bg: "#1e1b4b", text: "#a78bfa" }, sensitive: { bg: "#7f1d1d", text: "#fca5a5" } };
                  const cc = CAT_C[note.category] || { bg: "#1f2937", text: "#9ca3af" };
                  const pc = POS_C[note.posture] || { bg: "#1f2937", text: "#9ca3af" };
                  return (
                    <div key={note.id} style={{ background: theme.bg.input, borderRadius: 8, border: `1px solid ${theme.border.subtle}`, padding: "12px 16px" }}>
                      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap", alignItems: "center" }}>
                        <span style={{ background: cc.bg, color: cc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          {(note.category || "").replace(/_/g, " ")}
                        </span>
                        <span style={{ background: pc.bg, color: pc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          {(note.posture || "").replace(/_/g, " ")}
                        </span>
                        {note.sensitivity && note.sensitivity !== "low" && (
                          <span style={{ background: "#7f1d1d", color: "#fca5a5", fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase" }}>
                            {note.sensitivity}
                          </span>
                        )}
                        <span style={{ flex: 1 }} />
                        <span style={{ fontSize: 10, color: theme.text.faint }}>{note.created_at?.slice(0, 10)}</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>{note.title}</div>
                      <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
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
                            <span key={i} style={{ background: "rgba(59,130,246,0.1)", color: "#93c5fd", fontSize: 10, padding: "2px 6px", borderRadius: 4, border: "1px solid rgba(59,130,246,0.2)" }}>
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
        )}

      </div>
    </div>
  );
}
