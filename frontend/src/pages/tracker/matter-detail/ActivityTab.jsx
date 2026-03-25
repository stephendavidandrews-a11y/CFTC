import React, { useState, useCallback } from "react";
import theme from "../../../styles/theme";
import { addMatterUpdate } from "../../../api/tracker";
import Badge from "../../../components/shared/Badge";
import { formatDate } from "../../../utils/dateUtils";

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

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

export default function ActivityTab({ matterId, matter, refetch, toast, enums }) {
  const [showUpdateForm, setShowUpdateForm] = useState(false);
  const [updateType, setUpdateType] = useState("status update");
  const [updateSummary, setUpdateSummary] = useState("");
  const [savingUpdate, setSavingUpdate] = useState(false);

  const updates = matter?.updates || [];

  const handleSaveUpdate = useCallback(async () => {
    if (!updateSummary.trim()) return;
    setSavingUpdate(true);
    try {
      await addMatterUpdate(matterId, { update_type: updateType, summary: updateSummary });
      setUpdateSummary("");
      setShowUpdateForm(false);
      refetch();
    } catch (e) {
      console.error("Failed to save update:", e);
      toast.error("Failed to save update: " + (e.message || "Unknown error"));
    } finally {
      setSavingUpdate(false);
    }
  }, [matterId, updateType, updateSummary, refetch, toast]);

  return (
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
              {(enums?.update_type || ["status update", "meeting readout", "document milestone", "decision made", "blocker identified", "deadline changed", "escalation", "closure note"]).map((t) => (
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
  );
}
