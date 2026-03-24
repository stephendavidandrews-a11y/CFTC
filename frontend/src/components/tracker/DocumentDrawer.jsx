import React from "react";
import DrawerShell from "./DrawerShell";
import {
  createDocument,
  updateDocument,
  uploadDocumentFile,
  getEnum,
  listPeople,
  listMatters,
  getDocument,
} from "../../api/tracker";
import { validate } from "../../utils/validation";

const INPUT_STYLE = {
  width: "100%",
  padding: "8px 12px",
  borderRadius: 6,
  border: "1px solid #1f2937",
  background: "#0f172a",
  color: "#f1f5f9",
  fontSize: 13,
  boxSizing: "border-box",
};
const LABEL_STYLE = { display: "block", fontSize: 12, fontWeight: 600, color: "#94a3b8", marginBottom: 4 };
const SAVE_BTN = { background: "#1e40af", color: "#fff", padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const CANCEL_BTN = { background: "transparent", color: "#64748b", padding: "8px 20px", borderRadius: 8, fontSize: 13, border: "1px solid #1f2937", cursor: "pointer" };

const FILE_AREA_STYLE = {
  border: "1px dashed #334155",
  borderRadius: 6,
  background: "#0f172a",
  padding: "12px 14px",
  textAlign: "center",
  cursor: "pointer",
  marginBottom: 14,
};

const EMPTY = {
  title: "",
  document_type: "",
  matter_id: "",
  status: "",
  assigned_to_person_id: "",
  version_label: "",
  due_date: "",
  summary: "",
  notes: "",
  final_location: "",
  is_finalized: 0,
  is_sent: 0,
  sent_at: "",
};

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export default function DocumentDrawer({ isOpen, onClose, document: doc, matterId, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [etag, setEtag] = React.useState(null);
  const [file, setFile] = React.useState(null);
  const fileInputRef = React.useRef(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      getEnum("document_type").catch(() => []),
      getEnum("document_status").catch(() => []),
      listPeople({ limit: 100 }).catch(() => ({ items: [] })),
      listMatters({ limit: 200 }).catch(() => ({ items: [] })),
    ]).then(([docType, docStatus, ppl, matterList]) => {
      setEnums({ document_type: docType, document_status: docStatus });
      setPeople(ppl.items || ppl || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (doc) {
      setForm({
        title: doc.title || "",
        document_type: doc.document_type || "",
        matter_id: doc.matter_id || "",
        status: doc.status || "",
        assigned_to_person_id: doc.assigned_to_person_id || "",
        version_label: doc.version_label || "",
        due_date: doc.due_date || "",
        summary: doc.summary || "",
        notes: doc.notes || "",
        final_location: doc.final_location || "",
        is_finalized: doc.is_finalized || 0,
        is_sent: doc.is_sent || 0,
        sent_at: doc.sent_at ? doc.sent_at.slice(0, 16) : "",
      });
    } else {
      setEtag(null);
      setForm({ ...EMPTY, matter_id: matterId || "" });
    }
    setFile(null);
    setError(null);
    setFieldErrors({});
  }, [doc, matterId, isOpen]);

  // Fetch full detail on edit to prevent data loss and capture ETag
  React.useEffect(() => {
    if (doc && doc.id) {
      getDocument(doc.id).then(d => {
        setEtag(d._etag || null);
        setForm({
          title: d.title || "",
          document_type: d.document_type || "",
          matter_id: d.matter_id || "",
          status: d.status || "",
          assigned_to_person_id: d.assigned_to_person_id || "",
          version_label: d.version_label || "",
          due_date: (d.due_date || "").slice(0, 10),
          summary: d.summary || "",
          notes: d.notes || "",
          final_location: d.final_location || "",
          is_finalized: d.is_finalized || 0,
          is_sent: d.is_sent || 0,
          sent_at: d.sent_at ? d.sent_at.slice(0, 16) : "",
        });
      }).catch(() => {});
    }
  }, [doc, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const setCheck = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.checked ? 1 : 0 }));

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected || null);
  };

  const handleSave = async () => {
    setError(null);
    setFieldErrors({});
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      payload.is_finalized = form.is_finalized ? 1 : 0;
      payload.is_sent = form.is_sent ? 1 : 0;
      if (!doc?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const v = validate("document", payload);
      if (!v.valid) { setFieldErrors(v.errors); setError(Object.values(v.errors).join(", ")); setSaving(false); return; }

      let docId;
      if (doc?.id) {
        await updateDocument(doc.id, payload, etag);
        docId = doc.id;
      } else {
        const created = await createDocument(payload);
        docId = created.id;
      }

      // Upload file if selected
      if (file && docId) {
        const formData = new FormData();
        formData.append("file", file);
        await uploadDocumentFile(docId, formData);
      }

      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      if (err.status === 409 && !err.fieldErrors) {
        setError("This record was modified by someone else. Please close, reopen to load the latest version, and review before saving again.");
        setSaving(false);
        return;
      }
      if (err.fieldErrors && Object.keys(err.fieldErrors).length) {
        setFieldErrors(err.fieldErrors);
        setError(Object.entries(err.fieldErrors).map(([k, v]) => `${k}: ${v}`).join("; "));
      } else {
        setFieldErrors({});
        setError(err.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const renderSelect = (label, field, options) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <select style={INPUT_STYLE} value={form[field]} onChange={set(field)}>
        <option value="">--</option>
        {(Array.isArray(options) ? options : []).map((v) => (
          <option key={typeof v === "object" ? v.value : v} value={typeof v === "object" ? v.value : v}>
            {typeof v === "object" ? v.label || v.value : v}
          </option>
        ))}
      </select>
    </div>
  );

  const renderInput = (label, field, type = "text", extra = {}) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <input style={INPUT_STYLE} type={type} value={form[field]} onChange={set(field)} {...extra} />
    </div>
  );

  const personOpts = people.map((p) => ({ value: p.id, label: ((p.first_name || "") + " " + (p.last_name || "")).trim() || p.full_name || ("Person #" + p.id) }));
  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || ("Matter #" + m.id) }));

  const isEdit = !!doc?.id;
  const existingFiles = doc?.files || [];

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={isEdit ? "Edit Document" : "New Document"}>
      {renderInput("Title *", "title", "text", { required: true })}
      {renderSelect("Document Type *", "document_type", enums.document_type)}
      {renderSelect("Matter", "matter_id", matterOpts)}
      {renderSelect("Status", "status", enums.document_status)}
      {renderSelect("Assigned To", "assigned_to_person_id", personOpts)}
      {renderInput("Version Label", "version_label")}
      {renderInput("Due Date", "due_date", "date")}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Summary</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.summary} onChange={set("summary")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Notes</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.notes} onChange={set("notes")} />
      </div>

      {renderInput("Final Location", "final_location")}
      <div style={{ display: "flex", gap: 20, marginBottom: 14 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#e2e8f0", cursor: "pointer" }}>
          <input type="checkbox" checked={!!form.is_finalized} onChange={setCheck("is_finalized")} style={{ accentColor: "#1e40af" }} />
          Finalized
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#e2e8f0", cursor: "pointer" }}>
          <input type="checkbox" checked={!!form.is_sent} onChange={setCheck("is_sent")} style={{ accentColor: "#1e40af" }} />
          Sent
        </label>
      </div>
      {!!form.is_sent && renderInput("Sent At", "sent_at", "datetime-local")}

      {/* File Upload */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>File</label>
        {existingFiles.length > 0 && !file && (
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6, padding: "6px 10px", background: "#1e293b", borderRadius: 6 }}>
            Current: {existingFiles.map((f) => f.original_filename || f.filename || "file").join(", ")}
          </div>
        )}
        <div
          style={FILE_AREA_STYLE}
          onClick={() => fileInputRef.current && fileInputRef.current.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileChange}
            style={{ display: "none" }}
          />
          {file ? (
            <div style={{ color: "#e2e8f0", fontSize: 12 }}>
              <div style={{ fontWeight: 600 }}>{file.name}</div>
              <div style={{ color: "#64748b", marginTop: 2 }}>{formatFileSize(file.size)}</div>
            </div>
          ) : (
            <div style={{ color: "#64748b", fontSize: 12 }}>
              Click to choose a file{existingFiles.length > 0 ? " (replaces current)" : ""}
            </div>
          )}
        </div>
        {file && (
          <button
            onClick={() => { setFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
            style={{ background: "none", border: "none", color: "#ef4444", fontSize: 11, cursor: "pointer", padding: 0 }}
          >
            Remove selected file
          </button>
        )}
      </div>

      {error && <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 16, borderTop: "1px solid #1f2937", marginTop: 10 }}>
        <button style={CANCEL_BTN} onClick={onClose}>Cancel</button>
        <button style={{ ...SAVE_BTN, opacity: saving ? 0.6 : 1 }} onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : (document ? "Save Changes" : "Create Document")}
        </button>
      </div>
    </DrawerShell>
  );
}
