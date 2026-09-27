import React, { useState } from "react";
import theme from "../../styles/theme";
import { btnPrimary, btnSecondary, inputStyle } from "../../styles/pageStyles";
import Modal from "../shared/Modal";
import {
  uploadContactSheet,
  confirmEnrichmentMapping,
  getEnrichmentPreflight,
  startEnrichmentJob,
} from "../../api/ai";
import ColumnMappingStep from "./ColumnMappingStep";
import PreflightPanel from "./PreflightPanel";

/**
 * Three-step upload: pick a file, confirm the column mapping, review the cost.
 *
 * Nothing reaches Hunter until the operator clears the final step, so backing
 * out at any point costs nothing.
 */

const STEP_FILE = "file";
const STEP_MAPPING = "mapping";
const STEP_PREFLIGHT = "preflight";

const SOURCE_SPREADSHEET = "spreadsheet";
const SOURCE_LINKEDIN = "linkedin_export";

const labelStyle = {
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: 0.5,
  color: theme.text.dim,
  marginBottom: 6,
  display: "block",
};

const stepDotStyle = (active, done) => ({
  width: 22,
  height: 22,
  borderRadius: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 11,
  fontWeight: 700,
  background: done ? theme.accent.green : active ? theme.accent.blue : theme.bg.input,
  color: done || active ? "#fff" : theme.text.faint,
  border: `1px solid ${done ? theme.accent.green : active ? theme.accent.blue : theme.border.default}`,
});

export default function UploadContactsModal({ open, onClose, onComplete, config }) {
  const [step, setStep] = useState(STEP_FILE);
  const [file, setFile] = useState(null);
  const [sourceType, setSourceType] = useState(SOURCE_SPREADSHEET);
  const [enrichProfile, setEnrichProfile] = useState(
    !!config?.enrich_profile_default
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [upload, setUpload] = useState(null);
  const [mapping, setMapping] = useState({});
  const [preflight, setPreflight] = useState(null);

  function reset() {
    setStep(STEP_FILE);
    setFile(null);
    setUpload(null);
    setMapping({});
    setPreflight(null);
    setError(null);
    setBusy(false);
  }

  function handleClose() {
    reset();
    onClose?.();
  }

  async function handleUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadContactSheet(file, { sourceType, enrichProfile });
      setUpload(result);
      setMapping(result.proposed_mapping || {});
      setStep(STEP_MAPPING);
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmMapping() {
    setBusy(true);
    setError(null);
    try {
      await confirmEnrichmentMapping(upload.job_id, mapping);
      const pf = await getEnrichmentPreflight(upload.job_id);
      setPreflight(pf);
      setStep(STEP_PREFLIGHT);
    } catch (err) {
      const detail = err.detail;
      if (detail && detail.mapping_problems) {
        setError(detail.mapping_problems.join("; "));
      } else {
        setError(err.message || "Could not confirm the mapping");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleStart({ acknowledgeEgress, creditCap }) {
    setBusy(true);
    setError(null);
    try {
      await startEnrichmentJob(upload.job_id, { acknowledgeEgress, creditCap });
      const jobId = upload.job_id;
      reset();
      onComplete?.(jobId);
    } catch (err) {
      setError(err.message || "Could not start the job");
      setBusy(false);
    }
  }

  const steps = [
    { key: STEP_FILE, label: "File" },
    { key: STEP_MAPPING, label: "Columns" },
    { key: STEP_PREFLIGHT, label: "Cost" },
  ];
  const currentIndex = steps.findIndex((s) => s.key === step);

  return (
    <Modal isOpen={open} onClose={handleClose} title="Upload contacts" width={820}>
      <div style={{ display: "flex", gap: 18, alignItems: "center", marginBottom: 20 }}>
        {steps.map((s, i) => (
          <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={stepDotStyle(i === currentIndex, i < currentIndex)}>
              {i < currentIndex ? "✓" : i + 1}
            </div>
            <span
              style={{
                fontSize: 12,
                fontWeight: i === currentIndex ? 600 : 400,
                color: i <= currentIndex ? theme.text.secondary : theme.text.faint,
              }}
            >
              {s.label}
            </span>
            {i < steps.length - 1 && (
              <span style={{ color: theme.text.ghost, marginLeft: 8 }}>{"→"}</span>
            )}
          </div>
        ))}
      </div>

      {error && (
        <div
          style={{
            background: "#3f1d1d",
            border: `1px solid ${theme.accent.red}`,
            borderRadius: 6,
            padding: "10px 12px",
            fontSize: 12,
            color: theme.accent.redLight,
            marginBottom: 16,
          }}
        >
          {error}
        </div>
      )}

      {step === STEP_FILE && (
        <div>
          <label style={labelStyle}>Contact sheet</label>
          <input
            type="file"
            accept=".csv,.tsv,.xlsx,.xlsm"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            style={{ ...inputStyle, minWidth: "100%", padding: 10, marginBottom: 18 }}
          />

          <label style={labelStyle}>Source</label>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
            <RadioRow
              checked={sourceType === SOURCE_SPREADSHEET}
              onChange={() => setSourceType(SOURCE_SPREADSHEET)}
              title="Generic spreadsheet"
              detail="Any headers. You confirm how the columns map in the next step."
            />
            <RadioRow
              checked={sourceType === SOURCE_LINKEDIN}
              onChange={() => setSourceType(SOURCE_LINKEDIN)}
              title="LinkedIn connections export"
              detail="Settings, Data Privacy, Get a copy of your data, Connections. Known headers, so no mapping needed."
            />
          </div>

          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={enrichProfile}
              onChange={(e) => setEnrichProfile(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span style={{ fontSize: 12, color: theme.text.secondary }}>
              Also fetch LinkedIn URL and job title
              <span style={{ display: "block", color: theme.text.dim, fontSize: 11, marginTop: 2 }}>
                Costs one extra Hunter credit per contact found.
              </span>
            </span>
          </label>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 24 }}>
            <button onClick={handleClose} style={btnSecondary}>
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || busy}
              style={{ ...btnPrimary, opacity: !file || busy ? 0.5 : 1 }}
            >
              {busy ? "Reading..." : "Continue"}
            </button>
          </div>
        </div>
      )}

      {step === STEP_MAPPING && upload && (
        <ColumnMappingStep
          upload={upload}
          mapping={mapping}
          onChange={setMapping}
          onBack={() => setStep(STEP_FILE)}
          onConfirm={handleConfirmMapping}
          busy={busy}
        />
      )}

      {step === STEP_PREFLIGHT && preflight && (
        <PreflightPanel
          preflight={preflight}
          onBack={() => setStep(STEP_MAPPING)}
          onStart={handleStart}
          busy={busy}
        />
      )}
    </Modal>
  );
}

function RadioRow({ checked, onChange, title, detail }) {
  return (
    <label
      style={{
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
        cursor: "pointer",
        padding: "10px 12px",
        borderRadius: 6,
        background: checked ? theme.bg.cardHover : "transparent",
        border: `1px solid ${checked ? theme.border.active : theme.border.default}`,
      }}
    >
      <input type="radio" checked={checked} onChange={onChange} style={{ marginTop: 3 }} />
      <span style={{ fontSize: 12, color: theme.text.secondary }}>
        {title}
        <span style={{ display: "block", color: theme.text.dim, fontSize: 11, marginTop: 2 }}>
          {detail}
        </span>
      </span>
    </label>
  );
}
