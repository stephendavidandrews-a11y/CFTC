import React, { useState } from "react";
import theme from "../../styles/theme";
import { btnPrimary, btnSecondary, inputStyle } from "../../styles/pageStyles";

/**
 * What this job will cost, before a single credit is spent.
 *
 * The egress acknowledgement is deliberate friction: running this sends contact
 * names to Hunter.io, a third-party service, and the operator should say so
 * explicitly rather than discover it afterwards.
 */

const SKIP_LABELS = {
  "skipped: email_in_sheet": "already have an email in the sheet",
  "skipped: already_verified": "already have a verified email on file",
  "skipped: no_domain": "no domain to search",
  "skipped: incomplete_name": "missing a first or last name",
  "skipped: free_email": "only a personal webmail address",
};

function statRow(label, value, color) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
      <span style={{ fontSize: 12, color: theme.text.muted }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: color || theme.text.primary }}>
        {value}
      </span>
    </div>
  );
}

export default function PreflightPanel({ preflight, onBack, onStart, busy }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [creditCap, setCreditCap] = useState(
    preflight.credits_estimated || preflight.default_credit_cap || 100
  );

  const requireAck = preflight.require_egress_acknowledgement;
  const canStart =
    (!requireAck || acknowledged) && !busy && Number(creditCap) > 0;

  const insufficient = preflight.sufficient_credits === false;

  return (
    <div>
      <div
        style={{
          border: `1px solid ${theme.border.default}`,
          borderRadius: 8,
          padding: "12px 16px",
          marginBottom: 14,
        }}
      >
        {statRow("Rows in file", preflight.row_count)}
        {statRow("Will be looked up", preflight.to_lookup, theme.accent.blueLight)}
        {statRow("Skipped, nothing to find", preflight.skipped, theme.text.dim)}
        <div style={{ height: 1, background: theme.border.subtle, margin: "8px 0" }} />
        {statRow(
          "Hunter credits this will cost",
          preflight.credits_estimated,
          theme.accent.yellowLight
        )}
        {preflight.credit_balance !== null &&
          preflight.credit_balance !== undefined &&
          statRow(
            "Credits available on your account",
            preflight.credit_balance,
            insufficient ? theme.accent.red : theme.accent.greenLight
          )}
        {preflight.balance_error && (
          <div style={{ fontSize: 11, color: theme.accent.yellowLight, paddingTop: 4 }}>
            Could not read your Hunter balance: {preflight.balance_error}
          </div>
        )}
      </div>

      {Object.keys(preflight.skip_reasons || {}).length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: 0.5,
              color: theme.text.dim,
              marginBottom: 6,
            }}
          >
            Why rows were skipped
          </div>
          {Object.entries(preflight.skip_reasons).map(([reason, count]) => (
            <div key={reason} style={{ fontSize: 11, color: theme.text.muted, padding: "2px 0" }}>
              {count} {SKIP_LABELS[reason] || reason}
            </div>
          ))}
        </div>
      )}

      {insufficient && (
        <div
          style={{
            background: "#3f1d1d",
            border: `1px solid ${theme.accent.red}`,
            borderRadius: 6,
            padding: "10px 12px",
            fontSize: 11,
            color: theme.accent.redLight,
            marginBottom: 14,
          }}
        >
          Your Hunter balance is below what this job needs. It will run until the
          credits run out and then pause, so nothing is lost, but it will not finish.
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <label
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 0.5,
            color: theme.text.dim,
            marginBottom: 6,
            display: "block",
          }}
        >
          Stop after this many credits
        </label>
        <input
          type="number"
          min={1}
          value={creditCap}
          onChange={(e) => setCreditCap(e.target.value)}
          style={{ ...inputStyle, width: 140 }}
        />
        <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 4 }}>
          A hard ceiling. The job pauses when it is reached and you can resume
          with a higher cap.
        </div>
      </div>

      {requireAck && (
        <label
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            cursor: "pointer",
            background: theme.bg.cardHover,
            border: `1px solid ${acknowledged ? theme.accent.green : theme.border.default}`,
            borderRadius: 6,
            padding: "12px 14px",
            marginBottom: 18,
          }}
        >
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            style={{ marginTop: 3 }}
          />
          <span style={{ fontSize: 12, color: theme.text.secondary }}>
            I understand this sends contact names and their employer domains to
            Hunter.io, a third-party service.
            <span
              style={{ display: "block", color: theme.text.dim, fontSize: 11, marginTop: 3 }}
            >
              Only first name, last name, and domain are sent. Matter
              associations, relationship data, and notes never leave the tracker.
            </span>
          </span>
        </label>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <button onClick={onBack} style={btnSecondary} disabled={busy}>
          Back
        </button>
        <button
          onClick={() =>
            onStart({ acknowledgeEgress: acknowledged, creditCap: Number(creditCap) })
          }
          disabled={!canStart}
          style={{ ...btnPrimary, opacity: canStart ? 1 : 0.5 }}
        >
          {busy
            ? "Running..."
            : `Look up ${preflight.to_lookup} contact${preflight.to_lookup === 1 ? "" : "s"}`}
        </button>
      </div>
    </div>
  );
}
