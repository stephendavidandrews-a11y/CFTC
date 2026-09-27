import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import {
  titleStyle,
  subtitleStyle,
  btnPrimary,
  btnSecondary,
  inputStyle,
} from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { useToastContext } from "../../contexts/ToastContext";
import {
  getEnrichmentJob,
  listEnrichmentRows,
  updateEnrichmentRow,
  bulkAcceptEnrichment,
  commitEnrichmentJob,
  undoEnrichmentJob,
  resumeEnrichmentJob,
  enrichmentExportUrl,
} from "../../api/ai";
import Badge from "../../components/shared/Badge";
import ConfidenceIndicator from "../../components/shared/ConfidenceIndicator";
import EmptyState from "../../components/shared/EmptyState";
import ConfirmDialog from "../../components/shared/ConfirmDialog";

/**
 * Review what Hunter found, row by row, before anything is written.
 *
 * The left of each row is what the operator's spreadsheet said; the right is
 * what Hunter proposes. Rows the auto-accept rule pre-approved are grouped so
 * they can be taken in one click; everything else needs a decision.
 */

const TABS = [
  { key: "auto_accepted", label: "Ready to accept" },
  { key: "pending", label: "Needs review" },
  { key: "accepted", label: "Accepted" },
  { key: "rejected", label: "Rejected" },
  { key: "committed", label: "Saved" },
  { key: "", label: "All" },
];

const REVIEW_STYLES = {
  auto_accepted: { bg: "#14532d", text: "#4ade80", label: "Ready" },
  pending: { bg: "#422006", text: "#fbbf24", label: "Needs review" },
  accepted: { bg: "#172554", text: "#60a5fa", label: "Accepted" },
  edited: { bg: "#172554", text: "#60a5fa", label: "Edited" },
  rejected: { bg: "#3f1d1d", text: "#f87171", label: "Rejected" },
  committed: { bg: "#14532d", text: "#4ade80", label: "Saved" },
  skipped: { bg: "#1f2937", text: "#9ca3af", label: "Skipped" },
};

/** Why a row is not auto-acceptable, in words the operator can act on. */
const REASON_LABELS = {
  would_overwrite_existing_email:
    "This contact already has a different email on file. Accepting replaces it.",
  ambiguous_person_match:
    "More than one existing contact could be this person. Check before saving.",
  below_auto_accept_threshold: "Hunter is less than confident in this address.",
  below_reject_threshold: "Hunter has low confidence. Probably a guess.",
  no_score: "Hunter returned no confidence score.",
  undeliverable: "This address bounced verification.",
  verification_risky: "Verification came back risky.",
  verification_unknown: "Verification was inconclusive.",
  would_change_existing_values: "This would change values already on the record.",
  not_found: "Hunter found no address for this person.",
  lookup_error: "The lookup failed.",
  "skipped: no_domain": "No domain to search. Supply one to look this person up.",
  "skipped: email_in_sheet": "Your sheet already had an email for this row.",
  "skipped: already_verified": "This contact already has a verified email.",
  "skipped: incomplete_name": "Needs both a first and last name.",
  "skipped: free_email": "Only a personal webmail address, which Hunter cannot search.",
  "skipped: lookup": "Queued for lookup.",
};

const VERIFICATION_STYLES = {
  deliverable: { bg: "#14532d", text: "#4ade80", label: "Deliverable" },
  risky: { bg: "#422006", text: "#fbbf24", label: "Risky" },
  undeliverable: { bg: "#3f1d1d", text: "#f87171", label: "Undeliverable" },
  unknown: { bg: "#1f2937", text: "#9ca3af", label: "Unknown" },
};

const cellLabel = {
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: 0.5,
  color: theme.text.dim,
};

const dash = "—";

export default function EnrichmentReviewPage() {
  const { id: jobId } = useParams();
  const navigate = useNavigate();
  const toast = useToastContext();
  const [tab, setTab] = useState("auto_accepted");
  const [busy, setBusy] = useState(false);
  const [confirmCommit, setConfirmCommit] = useState(false);
  const [confirmUndo, setConfirmUndo] = useState(false);

  const {
    data: job,
    loading: jobLoading,
    error: jobError,
    refetch: refetchJob,
  } = useApi(() => getEnrichmentJob(jobId), [jobId]);

  const {
    data: rowsData,
    loading: rowsLoading,
    refetch: refetchRows,
  } = useApi(
    () => listEnrichmentRows(jobId, { review_status: tab || undefined, limit: 500 }),
    [jobId, tab]
  );

  const { lastEvent } = useAIEvents(ENRICHMENT_EVENTS);

  const refreshAll = useCallback(() => {
    refetchJob().catch(() => {});
    refetchRows().catch(() => {});
  }, [refetchJob, refetchRows]);

  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.data?.job_id !== jobId) return;
    refreshAll();
  }, [lastEvent, jobId, refreshAll]);

  const rows = rowsData?.items || [];
  const counts = job?.review_counts || {};

  async function rowAction(rowId, payload, successMessage) {
    setBusy(true);
    try {
      await updateEnrichmentRow(rowId, payload);
      refreshAll();
      if (successMessage) toast?.success?.(successMessage);
    } catch (err) {
      toast?.error?.(err.message || "Could not update the row");
    } finally {
      setBusy(false);
    }
  }

  async function handleBulkAccept() {
    setBusy(true);
    try {
      const result = await bulkAcceptEnrichment(jobId);
      toast?.success?.(`Accepted ${result.accepted} contacts`);
      refreshAll();
    } catch (err) {
      toast?.error?.(err.message || "Bulk accept failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCommit() {
    setConfirmCommit(false);
    setBusy(true);
    try {
      const result = await commitEnrichmentJob(jobId);
      toast?.success?.(`Saved ${result.committed} contacts to the tracker`);
      refreshAll();
    } catch (err) {
      toast?.error?.(err.message || "Commit failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleUndo() {
    setConfirmUndo(false);
    setBusy(true);
    try {
      const result = await undoEnrichmentJob(jobId);
      toast?.success?.(`Reversed ${result.reversed} writes`);
      refreshAll();
    } catch (err) {
      toast?.error?.(err.message || "Undo failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleResume() {
    setBusy(true);
    try {
      await resumeEnrichmentJob(jobId, (job?.credit_cap || 0) + 500);
      toast?.success?.("Resumed");
      refreshAll();
    } catch (err) {
      toast?.error?.(err.message || "Could not resume");
    } finally {
      setBusy(false);
    }
  }

  if (jobLoading && !job) {
    return <div style={{ color: theme.text.muted, fontSize: 13 }}>Loading...</div>;
  }
  if (jobError) {
    return (
      <div style={{ color: theme.accent.redLight, fontSize: 13 }}>
        {jobError.message}
      </div>
    );
  }

  const acceptedCount =
    (counts.accepted || 0) + (counts.edited || 0) + (counts.auto_accepted || 0);
  const hasCommitted = (counts.committed || 0) > 0;

  return (
    <div>
      <button
        onClick={() => navigate("/enrichment")}
        style={{
          background: "none",
          border: "none",
          color: theme.text.dim,
          fontSize: 12,
          cursor: "pointer",
          padding: 0,
          marginBottom: 10,
        }}
      >
        {"←"} All enrichment jobs
      </button>

      <div
        style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}
      >
        <div>
          <h1 style={titleStyle}>{job.original_filename}</h1>
          <p style={subtitleStyle}>
            {job.row_count} rows {"·"} {job.rows_found || 0} found {"·"}{" "}
            {job.credits_spent || 0} credits spent
            {job.credit_cap ? ` of ${job.credit_cap}` : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <a
            href={enrichmentExportUrl(jobId)}
            style={{
              ...btnSecondary,
              textDecoration: "none",
              display: "inline-block",
            }}
          >
            Download filled sheet
          </a>
          {job.status === "paused" && (
            <button onClick={handleResume} disabled={busy} style={btnSecondary}>
              Resume
            </button>
          )}
          {counts.auto_accepted > 0 && (
            <button onClick={handleBulkAccept} disabled={busy} style={btnSecondary}>
              Accept all {counts.auto_accepted} ready
            </button>
          )}
          {acceptedCount > 0 && (
            <button
              onClick={() => setConfirmCommit(true)}
              disabled={busy}
              style={btnPrimary}
            >
              Save {acceptedCount} to tracker
            </button>
          )}
          {hasCommitted && (
            <button onClick={() => setConfirmUndo(true)} disabled={busy} style={btnSecondary}>
              Undo
            </button>
          )}
        </div>
      </div>

      {job.status === "paused" && (
        <div
          style={{
            background: "#422006",
            border: `1px solid ${theme.accent.yellow}`,
            borderRadius: 6,
            padding: "10px 14px",
            fontSize: 12,
            color: theme.accent.yellowLight,
            marginBottom: 16,
          }}
        >
          Paused at the credit cap. Nothing was lost {"—"} resume to continue
          from where it stopped.
        </div>
      )}

      {job.status === "failed" && job.error_message && (
        <div
          style={{
            background: "#3f1d1d",
            border: `1px solid ${theme.accent.red}`,
            borderRadius: 6,
            padding: "10px 14px",
            fontSize: 12,
            color: theme.accent.redLight,
            marginBottom: 16,
          }}
        >
          {job.error_message}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: 4,
          borderBottom: `1px solid ${theme.border.default}`,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        {TABS.map((t) => {
          const count = t.key ? counts[t.key] : job.row_count;
          const active = tab === t.key;
          return (
            <button
              key={t.key || "all"}
              onClick={() => setTab(t.key)}
              style={{
                background: "none",
                border: "none",
                borderBottom: `2px solid ${active ? theme.accent.blue : "transparent"}`,
                color: active ? theme.text.primary : theme.text.dim,
                fontSize: 12,
                fontWeight: active ? 600 : 400,
                padding: "8px 12px",
                cursor: "pointer",
              }}
            >
              {t.label}
              {count ? (
                <span style={{ color: theme.text.faint }}> ({count})</span>
              ) : null}
            </button>
          );
        })}
      </div>

      {rowsLoading && rows.length === 0 ? (
        <div style={{ color: theme.text.muted, fontSize: 13 }}>Loading rows...</div>
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing here" message="No rows in this category." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {rows.map((row) => (
            <RowCard key={row.id} row={row} busy={busy} onAction={rowAction} />
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmCommit}
        onClose={() => setConfirmCommit(false)}
        onConfirm={handleCommit}
        title="Save to tracker"
        message={`This writes ${acceptedCount} contacts into your people records. You can undo it afterwards.`}
        confirmLabel="Save"
      />
      <ConfirmDialog
        isOpen={confirmUndo}
        onClose={() => setConfirmUndo(false)}
        onConfirm={handleUndo}
        title="Undo these writes"
        message="Contacts created by this job are deactivated, and updated fields are restored to their previous values."
        confirmLabel="Undo"
        danger
      />
    </div>
  );
}

function RowCard({ row, busy, onAction }) {
  const [editing, setEditing] = useState(false);
  const [emailDraft, setEmailDraft] = useState(row.hunter_email || "");
  const [domainDraft, setDomainDraft] = useState("");

  const review = REVIEW_STYLES[row.review_status] || {
    bg: "#1f2937",
    text: "#9ca3af",
    label: row.review_status,
  };
  const proposed = row.edited_data || row.proposed_data || {};
  const reason = REASON_LABELS[row.error_detail] || row.error_detail;
  const needsDomain = row.error_detail === "skipped: no_domain";
  const isOverwrite = row.error_detail === "would_overwrite_existing_email";
  const decided = ["committed", "rejected"].includes(row.review_status);

  return (
    <div
      style={{
        background: theme.bg.card,
        border: `1px solid ${isOverwrite ? theme.accent.yellow : theme.border.default}`,
        borderRadius: 10,
        padding: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.primary }}>
            {row.full_name || dash}
          </div>
          <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>
            Row {row.row_number}
            {row.org_name_raw ? ` · ${row.org_name_raw}` : ""}
            {row.domain ? ` · ${row.domain}` : ""}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {row.from_cache ? (
            <span style={{ fontSize: 10, color: theme.text.faint }}>cached</span>
          ) : null}
          <Badge bg={review.bg} text={review.text} label={review.label} />
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: reason || needsDomain ? 12 : 0,
        }}
      >
        <div>
          <div style={cellLabel}>From your sheet</div>
          <div style={{ fontSize: 12, color: theme.text.secondary, marginTop: 4 }}>
            {row.email_raw || <span style={{ color: theme.text.ghost }}>no email</span>}
          </div>
          {row.title_raw && (
            <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>
              {row.title_raw}
            </div>
          )}
          {row.matched_person_id && (
            <div style={{ fontSize: 11, color: theme.accent.blueLight, marginTop: 4 }}>
              matches an existing contact
              {row.match_confidence
                ? ` (${Math.round(row.match_confidence * 100)}% name match)`
                : ""}
              {row.match_ambiguous ? " · ambiguous" : ""}
            </div>
          )}
        </div>

        <div>
          <div style={cellLabel}>Hunter proposes</div>
          {row.hunter_email ? (
            <>
              <div
                style={{
                  fontSize: 12,
                  color: theme.text.primary,
                  fontWeight: 600,
                  marginTop: 4,
                  wordBreak: "break-all",
                }}
              >
                {proposed.email || row.hunter_email}
              </div>
              <div
                style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 5 }}
              >
                {row.hunter_score != null && (
                  <ConfidenceIndicator
                    score={row.hunter_score / 100}
                    size="bar"
                    showLabel
                    width={50}
                  />
                )}
                {row.hunter_verification && (
                  <Badge
                    bg={(VERIFICATION_STYLES[row.hunter_verification] || {}).bg || "#1f2937"}
                    text={
                      (VERIFICATION_STYLES[row.hunter_verification] || {}).text || "#9ca3af"
                    }
                    label={
                      (VERIFICATION_STYLES[row.hunter_verification] || {}).label ||
                      row.hunter_verification
                    }
                  />
                )}
              </div>
              {row.hunter_position && (
                <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 4 }}>
                  {row.hunter_position}
                </div>
              )}
              {row.hunter_linkedin_url && (
                <a
                  href={row.hunter_linkedin_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: 11,
                    color: theme.accent.blueLight,
                    marginTop: 3,
                    display: "inline-block",
                  }}
                >
                  LinkedIn profile
                </a>
              )}
            </>
          ) : (
            <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 4 }}>
              nothing found
            </div>
          )}
        </div>
      </div>

      {reason && (
        <div
          style={{
            fontSize: 11,
            color: isOverwrite ? theme.accent.yellowLight : theme.text.muted,
            background: isOverwrite ? "#422006" : theme.bg.cardHover,
            borderRadius: 6,
            padding: "7px 10px",
            marginBottom: 10,
          }}
        >
          {reason}
        </div>
      )}

      {needsDomain && !decided && (
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input
            placeholder="employer domain, e.g. cftc.gov"
            value={domainDraft}
            onChange={(e) => setDomainDraft(e.target.value)}
            style={{ ...inputStyle, flex: 1 }}
          />
          <button
            onClick={() =>
              onAction(
                row.id,
                { action: "set_domain", domain: domainDraft },
                "Domain set, row queued for lookup"
              )
            }
            disabled={busy || !domainDraft.trim()}
            style={{ ...btnSecondary, opacity: busy || !domainDraft.trim() ? 0.5 : 1 }}
          >
            Queue lookup
          </button>
        </div>
      )}

      {editing && (
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input
            value={emailDraft}
            onChange={(e) => setEmailDraft(e.target.value)}
            style={{ ...inputStyle, flex: 1 }}
          />
          <button
            onClick={() => {
              onAction(
                row.id,
                { action: "edit", data: { email: emailDraft.trim() } },
                "Saved your correction"
              );
              setEditing(false);
            }}
            disabled={busy || !emailDraft.trim()}
            style={{ ...btnSecondary, opacity: busy || !emailDraft.trim() ? 0.5 : 1 }}
          >
            Save
          </button>
          <button onClick={() => setEditing(false)} style={btnSecondary}>
            Cancel
          </button>
        </div>
      )}

      {!decided && (
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          {!editing && (
            <button
              onClick={() => {
                setEmailDraft(proposed.email || row.hunter_email || "");
                setEditing(true);
              }}
              disabled={busy}
              style={btnSecondary}
            >
              Edit email
            </button>
          )}
          <button
            onClick={() => onAction(row.id, { action: "reject" })}
            disabled={busy}
            style={btnSecondary}
          >
            Reject
          </button>
          {row.write_action !== "none" && (
            <button
              onClick={() => onAction(row.id, { action: "accept" })}
              disabled={busy}
              style={{ ...btnPrimary, padding: "8px 14px", fontSize: 12 }}
            >
              {isOverwrite ? "Replace email" : "Accept"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
