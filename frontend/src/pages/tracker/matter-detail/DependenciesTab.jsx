import React, { useState, useCallback } from "react";
import theme from "../../../styles/theme";
import { addMatterDependency, removeMatterDependency } from "../../../api/tracker";
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

export default function DependenciesTab({ matterId, matter, refetch, toast, allMatters, enums }) {
  const [depForm, setDepForm] = useState({ depends_on_matter_id: "", dependency_type: "" });
  const [showDepAdd, setShowDepAdd] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: "", message: "", onConfirm: null, danger: false });

  const dependencies = matter?.dependencies || [];
  const mattersList = (allMatters?.items || allMatters || []).filter((m) => m.id !== matterId);

  const handleAddDep = useCallback(async () => {
    if (!depForm.depends_on_matter_id || !depForm.dependency_type) return;
    try {
      await addMatterDependency(matterId, depForm);
      setDepForm({ depends_on_matter_id: "", dependency_type: "" });
      setShowDepAdd(false);
      refetch();
    } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
  }, [matterId, depForm, refetch, toast]);

  const handleRemoveDep = useCallback((depId) => {
    setConfirmDialog({
      open: true,
      title: "Remove Dependency",
      message: "Remove this dependency?",
      danger: false,
      onConfirm: async () => {
        try {
          await removeMatterDependency(matterId, depId);
          refetch();
        } catch (e) { console.error(e); toast.error(e.message || "Operation failed"); }
      },
    });
  }, [matterId, refetch, toast]);

  return (
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
      <ConfirmDialog
        isOpen={confirmDialog.open}
        onClose={() => setConfirmDialog(d => ({ ...d, open: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmLabel="Remove"
        danger={confirmDialog.danger}
      />
    </div>
  );
}
