import React, { useState, useRef, useCallback } from "react";
import theme from "../../styles/theme";
import Modal from "./Modal";

const ACCEPTED_EXTENSIONS = [
  ".wav", ".flac", ".mp3", ".m4a", ".mp4",
  ".aac", ".ogg", ".opus", ".wma", ".webm",
];
const ACCEPT_STRING = ACCEPTED_EXTENSIONS.join(",");
const MAX_SIZE_MB = 200;

/**
 * Audio upload modal with file picker, optional title, and sensitivity flags.
 *
 * Props:
 *   isOpen, onClose, onUpload(file, title, sensitivityFlags) => Promise
 */
export default function UploadAudioModal({ isOpen, onClose, onUpload }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [flags, setFlags] = useState({
    enforcement_sensitive: false,
    congressional_sensitive: false,
    deliberative: false,
  });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const reset = useCallback(() => {
    setFile(null);
    setTitle("");
    setFlags({ enforcement_sensitive: false, congressional_sensitive: false, deliberative: false });
    setError(null);
    setUploading(false);
    setDragOver(false);
  }, []);

  const handleClose = () => {
    if (uploading) return;
    reset();
    onClose();
  };

  const validateFile = (f) => {
    if (!f) return "No file selected.";
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return `Unsupported format: ${ext}. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File too large (${(f.size / 1024 / 1024).toFixed(1)} MB). Maximum: ${MAX_SIZE_MB} MB.`;
    }
    if (f.size === 0) return "File is empty.";
    return null;
  };

  const selectFile = (f) => {
    const err = validateFile(f);
    if (err) {
      setError(err);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) selectFile(f);
  };

  const handleSubmit = async () => {
    if (!file || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const activeFlags = Object.entries(flags)
        .filter(([, v]) => v)
        .map(([k]) => k);
      const flagStr = activeFlags.length > 0 ? activeFlags.join(",") : null;
      await onUpload(file, title || null, flagStr);
      reset();
      onClose();
    } catch (err) {
      setError(err?.message || "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  const fileSizeMB = file ? (file.size / 1024 / 1024).toFixed(1) : null;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Upload Audio" width={480}>
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? theme.accent.blue : theme.border.default}`,
          borderRadius: 10,
          padding: file ? "16px 20px" : "32px 20px",
          textAlign: "center",
          cursor: "pointer",
          background: dragOver ? "rgba(59,130,246,0.06)" : theme.bg.input,
          transition: "all 0.15s ease",
          marginBottom: 16,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_STRING}
          style={{ display: "none" }}
          onChange={(e) => { if (e.target.files?.[0]) selectFile(e.target.files[0]); }}
        />
        {file ? (
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: "rgba(59,130,246,0.12)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16, color: theme.accent.blueLight, flexShrink: 0,
            }}>{"\u266B"}</div>
            <div style={{ flex: 1, textAlign: "left", minWidth: 0 }}>
              <div style={{
                fontSize: 13, fontWeight: 600, color: theme.text.primary,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>{file.name}</div>
              <div style={{ fontSize: 11, color: theme.text.dim }}>{fileSizeMB} MB</div>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null); setTitle(""); setError(null); }}
              style={{
                background: "transparent", border: "none", color: theme.text.faint,
                fontSize: 14, cursor: "pointer", padding: 4,
              }}
            >{"\u2715"}</button>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 24, color: theme.text.ghost, marginBottom: 8 }}>{"\u2191"}</div>
            <div style={{ fontSize: 13, color: theme.text.muted, marginBottom: 4 }}>
              Drop an audio file here or click to browse
            </div>
            <div style={{ fontSize: 11, color: theme.text.faint }}>
              WAV, FLAC, MP3, M4A, AAC, OGG, OPUS, WMA, WebM &middot; Up to {MAX_SIZE_MB} MB
            </div>
          </>
        )}
      </div>

      {/* Title field */}
      <div style={{ marginBottom: 16 }}>
        <label style={{
          display: "block", fontSize: 11, fontWeight: 700, color: theme.text.faint,
          textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6,
        }}>Title (optional)</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Auto-filled from filename"
          style={{
            width: "100%", padding: "9px 12px", borderRadius: 7,
            background: theme.bg.input, color: theme.text.secondary,
            border: `1px solid ${theme.border.default}`,
            fontSize: 13, fontFamily: theme.font.family,
            outline: "none", boxSizing: "border-box",
          }}
        />
      </div>

      {/* Sensitivity flags */}
      <div style={{ marginBottom: 20 }}>
        <label style={{
          display: "block", fontSize: 11, fontWeight: 700, color: theme.text.faint,
          textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8,
        }}>Sensitivity flags</label>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {[
            { key: "enforcement_sensitive", label: "Enforcement Sensitive" },
            { key: "congressional_sensitive", label: "Congressional Sensitive" },
            { key: "deliberative", label: "Deliberative" },
          ].map(({ key, label }) => (
            <label key={key} style={{
              display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
              fontSize: 13, color: flags[key] ? theme.text.secondary : theme.text.dim,
            }}>
              <input
                type="checkbox"
                checked={flags[key]}
                onChange={() => setFlags((f) => ({ ...f, [key]: !f[key] }))}
                style={{ accentColor: theme.accent.blue }}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          fontSize: 12, color: theme.accent.red, marginBottom: 14,
          background: "rgba(239,68,68,0.08)", padding: "8px 12px",
          borderRadius: 6, border: "1px solid rgba(239,68,68,0.2)",
        }}>
          {error}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button
          onClick={handleClose}
          disabled={uploading}
          style={{
            padding: "9px 18px", borderRadius: 7, fontSize: 13, fontWeight: 600,
            background: theme.bg.input, color: theme.text.muted,
            border: `1px solid ${theme.border.default}`, cursor: "pointer",
            opacity: uploading ? 0.5 : 1,
          }}
        >Cancel</button>
        <button
          onClick={handleSubmit}
          disabled={!file || uploading}
          style={{
            padding: "9px 22px", borderRadius: 7, fontSize: 13, fontWeight: 600,
            background: !file || uploading ? "#1e3a5f" : "#1e40af",
            color: "#fff", border: "none", cursor: !file || uploading ? "default" : "pointer",
            opacity: !file || uploading ? 0.5 : 1,
          }}
        >{uploading ? "Uploading..." : "Upload & Process"}</button>
      </div>
    </Modal>
  );
}
