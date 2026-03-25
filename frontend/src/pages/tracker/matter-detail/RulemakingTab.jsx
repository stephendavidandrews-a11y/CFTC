import React from "react";
import theme from "../../../styles/theme";
import { useToastContext } from "../../../contexts/ToastContext";
import useApi from "../../../hooks/useApi";
import {
  listCommentTopics, deleteCommentTopic,
  createCommentQuestion, deleteCommentQuestion, moveCommentQuestion,
  listMatterDirectives
} from "../../../api/tracker";
import { useDrawer } from "../../../contexts/DrawerContext";
import Badge from "../../../components/shared/Badge";
import EmptyState from "../../../components/shared/EmptyState";
import ConfirmDialog from "../../../components/shared/ConfirmDialog";

const POSITION_STATUS_COLORS = {
  open: { bg: "#2a2a2a", text: "#999" },
  research: { bg: "#1a3a5c", text: "#60a5fa" },
  draft_position: { bg: "#3b2a1a", text: "#fbbf24" },
  under_review: { bg: "#2a1a3b", text: "#c084fc" },
  final: { bg: "#1a3b2a", text: "#34d399" },
  deferred: { bg: "#2a2a2a", text: "#666" },
  not_applicable: { bg: "#2a2a2a", text: "#666" },
};

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
          {i > 0 && <span style={{ color: theme.text.dim }}> &middot; </span>}
          <Badge bg={theme.bg.input} text={theme.text.secondary} label={d.relationship_type?.replace(/_/g, " ") || "linked"} />
          {" "}
          <a href={`/directives/${d.directive_id}`}
            style={{ fontSize: 12, color: theme.accent.blue, textDecoration: "none" }}>{d.directive_label}</a>
        </span>
      ))}
    </div>
  );
}

export default function RulemakingTab({ matterId }) {
  const toast = useToastContext();
  const [confirmDialog, setConfirmDialog] = React.useState({ open: false, title: "", message: "", onConfirm: null, danger: false });
  const [expandedId, setExpandedId] = React.useState(null);
  const [addingQuestion, setAddingQuestion] = React.useState(null);
  const [newQ, setNewQ] = React.useState({ question_number: "", question_text: "" });
  const { openDrawer } = useDrawer();

  const { data: topicsData, loading, error, refetch } = useApi(
    () => listCommentTopics(matterId), [matterId]
  );

  const topics = topicsData?.items || [];

  const handleDeleteTopic = (topicId) => {
    setConfirmDialog({
      open: true,
      title: "Delete Topic",
      message: "Delete this topic and all its questions? This cannot be undone.",
      danger: true,
      onConfirm: async () => {
        try {
          await deleteCommentTopic(topicId);
          refetch();
        } catch (err) { toast.error(err.detail || "Delete failed"); }
      },
    });
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
      <DirectiveLinkage matterId={matterId} />

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
        <EmptyState icon="\u{1F4AC}" title="No comment topics" subtitle="Add topics to track position development for this matter" />
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
                                  style={{ background: "none", border: "none", color: theme.accent.red, cursor: "pointer", fontSize: 10 }}>&times;</button>
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
      <ConfirmDialog
        isOpen={confirmDialog.open}
        onClose={() => setConfirmDialog(d => ({ ...d, open: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmLabel="Delete"
        danger={confirmDialog.danger}
      />
    </div>
  );
}
