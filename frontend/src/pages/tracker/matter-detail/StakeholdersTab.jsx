import React, { useState, useCallback } from "react";
import theme from "../../../styles/theme";
import { addMatterPerson, removeMatterPerson, addMatterOrg, removeMatterOrg } from "../../../api/tracker";
import DataTable from "../../../components/shared/DataTable";
import EmptyState from "../../../components/shared/EmptyState";
import ConfirmDialog from "../../../components/shared/ConfirmDialog";

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

const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

export default function StakeholdersTab({ matterId, matter, refetch, toast, allPeople, allOrgs }) {
  const [showStakeholderAdd, setShowStakeholderAdd] = useState(false);
  const [stakeholderForm, setStakeholderForm] = useState({ person_id: "", matter_role: "", engagement_level: "", notes: "" });

  const [showOrgAdd, setShowOrgAdd] = useState(false);
  const [orgForm, setOrgForm] = useState({ organization_id: "", organization_role: "", notes: "" });

  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: "", message: "", onConfirm: null, danger: false });

  const stakeholders = matter.people || matter.stakeholders || [];
  const linkedOrgs = matter.organizations || matter.orgs || [];
  const peopleList = allPeople?.items || allPeople || [];
  const orgsList = allOrgs?.items || allOrgs || [];

  const handleAddStakeholder = useCallback(async () => {
    if (!stakeholderForm.person_id) return;
    try {
      const cleanStakeholder = Object.fromEntries(Object.entries(stakeholderForm).filter(([_, v]) => v !== ""));
      await addMatterPerson(matterId, cleanStakeholder);
      setStakeholderForm({ person_id: "", matter_role: "", engagement_level: "", notes: "" });
      setShowStakeholderAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [matterId, stakeholderForm, refetch]);

  const handleRemoveStakeholder = useCallback((mpId) => {
    setConfirmDialog({
      open: true,
      title: "Remove Stakeholder",
      message: "Remove this stakeholder from the matter?",
      danger: false,
      onConfirm: async () => {
        try {
          await removeMatterPerson(matterId, mpId);
          refetch();
        } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
      },
    });
  }, [matterId, refetch]);

  const handleAddOrg = useCallback(async () => {
    if (!orgForm.organization_id) return;
    try {
      const cleanOrg = Object.fromEntries(Object.entries(orgForm).filter(([_, v]) => v !== ""));
      await addMatterOrg(matterId, cleanOrg);
      setOrgForm({ organization_id: "", organization_role: "", notes: "" });
      setShowOrgAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [matterId, orgForm, refetch]);

  const handleRemoveOrg = useCallback((moId) => {
    setConfirmDialog({
      open: true,
      title: "Remove Organization",
      message: "Remove this organization from the matter?",
      danger: false,
      onConfirm: async () => {
        try {
          await removeMatterOrg(matterId, moId);
          refetch();
        } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
      },
    });
  }, [matterId, refetch]);

  return (
    <div>
      {/* People Section */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={sectionTitle}>People</div>
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
            <input style={{ ...inputStyle, width: 140 }}
              placeholder="Role..."
              value={stakeholderForm.matter_role}
              onChange={(e) => setStakeholderForm((p) => ({ ...p, matter_role: e.target.value }))}
            />
            <input style={{ ...inputStyle, width: 140 }}
              placeholder="Engagement..."
              value={stakeholderForm.engagement_level}
              onChange={(e) => setStakeholderForm((p) => ({ ...p, engagement_level: e.target.value }))}
            />
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

      {/* Organizations Section */}
      <div style={{ marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={sectionTitle}>Organizations</div>
          <button style={btnPrimary} onClick={() => setShowOrgAdd(!showOrgAdd)}>
            {showOrgAdd ? "Cancel" : "+ Link Organization"}
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
            <input style={{ ...inputStyle, width: 160 }}
              placeholder="Role..."
              value={orgForm.organization_role}
              onChange={(e) => setOrgForm((p) => ({ ...p, organization_role: e.target.value }))}
            />
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
