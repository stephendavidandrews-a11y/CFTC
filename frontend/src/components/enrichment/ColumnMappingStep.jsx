import React, { useMemo } from "react";
import theme from "../../styles/theme";
import { btnPrimary, btnSecondary } from "../../styles/pageStyles";

/**
 * Confirm how the sheet's columns map onto the fields Hunter needs.
 *
 * The proposed mapping is a heuristic guess (or the LinkedIn preset), and is
 * always shown for confirmation rather than applied silently.
 */

const CANONICAL_FIELDS = [
  { value: "", label: "(ignore)" },
  { value: "first_name", label: "First name" },
  { value: "last_name", label: "Last name" },
  { value: "full_name", label: "Full name" },
  { value: "org_name", label: "Organization" },
  { value: "domain", label: "Domain" },
  { value: "title", label: "Job title" },
  { value: "email", label: "Email" },
  { value: "linkedin_url", label: "LinkedIn URL" },
];

const selectStyle = {
  background: theme.bg.input,
  border: `1px solid ${theme.border.default}`,
  borderRadius: 6,
  padding: "6px 10px",
  fontSize: 12,
  color: theme.text.secondary,
  outline: "none",
  width: "100%",
};

/** Mirrors validate_mapping in services/ai/app/enrichment/parsing.py. */
function validate(mapping) {
  const fields = Object.values(mapping).filter(Boolean);
  const problems = [];

  const counts = {};
  fields.forEach((f) => {
    counts[f] = (counts[f] || 0) + 1;
  });
  const dupes = Object.keys(counts).filter((f) => counts[f] > 1);
  if (dupes.length) {
    problems.push(`Two columns are mapped to the same field: ${dupes.join(", ")}`);
  }

  const hasName =
    fields.includes("full_name") ||
    (fields.includes("first_name") && fields.includes("last_name"));
  if (!hasName) {
    problems.push(
      "Map a name: either 'Full name', or both 'First name' and 'Last name'"
    );
  }

  const hasDomainSource = ["domain", "org_name", "email"].some((f) =>
    fields.includes(f)
  );
  if (!hasDomainSource) {
    problems.push("Map a domain source: 'Domain', 'Organization', or 'Email'");
  }
  return problems;
}

export default function ColumnMappingStep({
  upload,
  mapping,
  onChange,
  onBack,
  onConfirm,
  busy,
}) {
  const headers = upload.headers || [];
  const preview = upload.preview || [];
  const problems = useMemo(() => validate(mapping), [mapping]);

  function setField(header, field) {
    const next = { ...mapping };
    if (field) {
      next[header] = field;
    } else {
      delete next[header];
    }
    onChange(next);
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: theme.text.muted, marginBottom: 4 }}>
        {upload.row_count} rows from <strong>{upload.original_filename || "your file"}</strong>
        {upload.source_type === "linkedin_export" && (
          <span style={{ color: theme.accent.blueLight }}>
            {" "}
            {"·"} detected as a LinkedIn export
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 16 }}>
        Check the mapping below. Nothing is sent to Hunter yet.
      </div>

      {upload.duplicate_of && (
        <div
          style={{
            background: "#422006",
            border: `1px solid ${theme.accent.yellow}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 11,
            color: theme.accent.yellowLight,
            marginBottom: 14,
          }}
        >
          This exact file was uploaded before. Cached results mean a re-run is
          nearly free, so this is safe to continue.
        </div>
      )}

      <div
        style={{
          border: `1px solid ${theme.border.default}`,
          borderRadius: 8,
          overflow: "hidden",
          marginBottom: 14,
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: theme.bg.cardHover }}>
              <th style={thStyle}>Column in your file</th>
              <th style={thStyle}>Maps to</th>
              <th style={thStyle}>First value</th>
            </tr>
          </thead>
          <tbody>
            {headers.map((header) => (
              <tr key={header} style={{ borderTop: `1px solid ${theme.border.subtle}` }}>
                <td style={{ ...tdStyle, color: theme.text.primary, fontWeight: 600 }}>
                  {header}
                </td>
                <td style={{ ...tdStyle, width: 190 }}>
                  <select
                    value={mapping[header] || ""}
                    onChange={(e) => setField(header, e.target.value)}
                    style={selectStyle}
                  >
                    {CANONICAL_FIELDS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={{ ...tdStyle, color: theme.text.dim }}>
                  {preview[0]?.[header] || <span style={{ color: theme.text.ghost }}>{"—"}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {problems.length > 0 && (
        <ul
          style={{
            margin: "0 0 14px",
            paddingLeft: 18,
            fontSize: 11,
            color: theme.accent.yellowLight,
          }}
        >
          {problems.map((p) => (
            <li key={p} style={{ marginBottom: 3 }}>
              {p}
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <button onClick={onBack} style={btnSecondary} disabled={busy}>
          Back
        </button>
        <button
          onClick={onConfirm}
          disabled={busy || problems.length > 0}
          style={{ ...btnPrimary, opacity: busy || problems.length > 0 ? 0.5 : 1 }}
        >
          {busy ? "Matching..." : "Confirm columns"}
        </button>
      </div>
    </div>
  );
}

const thStyle = {
  textAlign: "left",
  padding: "8px 12px",
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: 0.5,
  color: theme.text.dim,
  fontWeight: 600,
};

const tdStyle = { padding: "8px 12px", verticalAlign: "middle" };
