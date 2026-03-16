import React, { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import {
  getMatter, addMatterUpdate, addMatterPerson, removeMatterPerson,
  addMatterOrg, removeMatterOrg, listTasks, listMeetings, listDocuments, listDecisions,
  listPeople, listOrganizations,
} from "../../api/tracker";
import { useDrawer } from "../../contexts/DrawerContext";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";

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
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const TABS = ["Updates", "Tasks", "Stakeholders", "Organizations", "Meetings", "Documents", "Decisions"];

export default function MatterDetailPage() {
  const { id } = useParams();
  const { openDrawer } = useDrawer();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Updates");

  const { data: matter, loading, error, refetch } = useApi(() => getMatter(id), [id]);

  // Tab data
  const { data: tasksData, refetch: refetchTasks } = useApi(() => listTasks({ matter_id: id }), [id]);
  const { data: meetingsData } = useApi(() => listMeetings({ matter_id: id }), [id]);
  const { data: docsData, refetch: refetchDocs } = useApi(() => listDocuments({ matter_id: id }), [id]);
  const { data: decisionsData, refetch: refetchDecisions } = useApi(() => listDecisions({ matter_id: id }), [id]);

  // For inline add forms
  const { data: allPeople } = useApi(() => listPeople({ limit: 500 }), []);
  const { data: allOrgs } = useApi(() => listOrganizations({ limit: 500 }), []);

  // Update form state
  const [showUpdateForm, setShowUpdateForm] = useState(false);
  const [updateType, setUpdateType] = useState("note");
  const [updateSummary, setUpdateSummary] = useState("");
  const [savingUpdate, setSavingUpdate] = useState(false);

  // Stakeholder inline add
  const [showStakeholderAdd, setShowStakeholderAdd] = useState(false);
  const [stakeholderForm, setStakeholderForm] = useState({ person_id: "", matter_role: "", engagement_level: "" });

  // Org inline add
  const [showOrgAdd, setShowOrgAdd] = useState(false);
  const [orgForm, setOrgForm] = useState({ organization_id: "", organization_role: "" });

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
    } finally {
      setSavingUpdate(false);
    }
  }, [id, updateType, updateSummary, refetch]);

  const handleAddStakeholder = useCallback(async () => {
    if (!stakeholderForm.person_id) return;
    try {
      await addMatterPerson(id, stakeholderForm);
      setStakeholderForm({ person_id: "", matter_role: "", engagement_level: "" });
      setShowStakeholderAdd(false);
      refetch();
    } catch (e) { console.error(e); }
  }, [id, stakeholderForm, refetch]);

  const handleRemoveStakeholder = useCallback(async (mpId) => {
    if (!window.confirm("Remove this stakeholder from the matter?")) return;
    try {
      await removeMatterPerson(id, mpId);
      refetch();
    } catch (e) { console.error(e); }
  }, [id, refetch]);

  const handleRemoveOrg = useCallback(async (moId) => {
    if (!window.confirm("Remove this organization from the matter?")) return;
    try {
      await removeMatterOrg(id, moId);
      refetch();
    } catch (e) { console.error(e); }
  }, [id, refetch]);

  const handleAddOrg = useCallback(async () => {
    if (!orgForm.organization_id) return;
    try {
      await addMatterOrg(id, orgForm);
      setOrgForm({ organization_id: "", organization_role: "" });
      setShowOrgAdd(false);
      refetch();
    } catch (e) { console.error(e); }
  }, [id, orgForm, refetch]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading matter...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
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

  const infoLeft = [
    { label: "Type", value: matter.matter_type },
    { label: "Status", value: matter.status },
    { label: "Priority", value: matter.priority },
    { label: "Sensitivity", value: matter.sensitivity },
    { label: "Boss Involvement", value: matter.boss_involvement_level },
    { label: "RIN", value: matter.rin },
    { label: "Regulatory Stage", value: matter.regulatory_stage },
  ];

  const infoRight = [
    { label: "Owner", value: matter.owner_name || matter.owner },
    { label: "Supervisor", value: matter.supervisor_name || matter.supervisor },
    { label: "Client Org", value: matter.client_org_name || matter.client_org },
    { label: "Reviewing Org", value: matter.reviewing_org_name || matter.reviewing_org },
    { label: "Opened Date", value: formatDate(matter.opened_date || matter.created_at) },
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

      {/* Tabs */}
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
                    {["note", "status_change", "decision", "meeting", "deadline", "escalation", "external"].map((t) => (
                      <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
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
              <button style={btnPrimary} onClick={() => openDrawer("task", { matter_id: parseInt(id) }, refetchTasks)}>
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
                  {["lead", "reviewer", "advisor", "stakeholder", "approver", "observer"].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <select style={{ ...inputStyle, width: 140 }}
                  value={stakeholderForm.engagement_level}
                  onChange={(e) => setStakeholderForm((p) => ({ ...p, engagement_level: e.target.value }))}
                >
                  <option value="">Engagement...</option>
                  {["high", "medium", "low"].map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
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
                  {["client", "reviewing", "collaborating", "regulated", "external"].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
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
            <div style={sectionTitle}>Meetings</div>
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
      </div>
    </div>
  );
}
