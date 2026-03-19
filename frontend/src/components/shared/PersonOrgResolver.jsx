import React, { useState, useEffect } from "react";
import theme from "../../styles/theme";
import { fetchJSON } from "../../api/client";

/**
 * Shared Person/Org resolver — UI Spec Section 10A.
 *
 * Three states:
 *   1. Unresolved — search bar + "New person" / "Skip"
 *   2. Matched — name, title, org with "Change" link
 *   3. Provisional — entered name/title/org with "new" badge and "Edit" link
 *
 * Used in: speaker review, entity review, bundle review.
 */

// ── Search sub-component ─────────────────────────────────────────────────────

function TrackerSearch({ entityType = "person", onSelect, placeholder }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const endpoint = entityType === "organization"
    ? "/tracker/organizations"
    : "/tracker/people";

  const placeholderText = placeholder ||
    (entityType === "organization" ? "Search tracker organizations..." : "Search tracker people...");

  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchJSON(`${endpoint}?search=${encodeURIComponent(query)}&limit=10`);
        setResults(data.items || data || []);
      } catch { setResults([]); }
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, endpoint]);

  return (
    <div style={{ position: "relative" }}>
      <input
        type="text"
        placeholder={placeholderText}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{
          width: "100%", padding: "6px 10px", borderRadius: 6,
          border: "1px solid " + theme.border.subtle,
          background: theme.bg.card, color: theme.text.primary,
          fontSize: 12, outline: "none",
        }}
      />
      {results.length > 0 && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0,
          background: theme.bg.card, border: "1px solid " + theme.border.subtle,
          borderRadius: 6, marginTop: 2, maxHeight: 200, overflowY: "auto",
          zIndex: 100, boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
        }}>
          {results.map((item) => (
            <button
              key={item.id}
              onClick={() => { onSelect(item); setQuery(""); setResults([]); }}
              style={{
                display: "block", width: "100%", padding: "8px 10px",
                background: "transparent", border: "none", cursor: "pointer",
                textAlign: "left", color: theme.text.primary, fontSize: 12,
                borderBottom: "1px solid " + theme.border.subtle,
              }}
            >
              <div style={{ fontWeight: 600 }}>
                {entityType === "organization"
                  ? (item.name || item.short_name)
                  : item.full_name}
              </div>
              {entityType === "person" && (item.title || item.organization_name) && (
                <div style={{ fontSize: 11, color: theme.text.faint }}>
                  {[item.title, item.organization_name].filter(Boolean).join(" \u2014 ")}
                </div>
              )}
              {entityType === "organization" && item.organization_type && (
                <div style={{ fontSize: 11, color: theme.text.faint }}>
                  {item.organization_type}
                  {item.parent_name ? ` \u2014 ${item.parent_name}` : ""}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
      {loading && <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 2 }}>Searching...</div>}
    </div>
  );
}

// ── New Person Form ──────────────────────────────────────────────────────────

function NewPersonForm({ onSave, onCancel }) {
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [org, setOrg] = useState("");

  const inputStyle = {
    width: "100%", padding: "5px 8px", borderRadius: 4,
    border: "1px solid " + theme.border.subtle,
    background: theme.bg.card, color: theme.text.primary, fontSize: 12,
    outline: "none", marginBottom: 6,
  };

  return (
    <div style={{
      background: "rgba(255,255,255,0.03)", padding: 10, borderRadius: 6,
      border: "1px solid rgba(250,204,21,0.2)", marginTop: 6,
    }}>
      <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 600, marginBottom: 6 }}>
        New Person (Provisional)
      </div>
      <input placeholder="Full name *" value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} />
      <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} />
      <input placeholder="Organization" value={org} onChange={(e) => setOrg(e.target.value)} style={inputStyle} />
      <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
        <button
          onClick={() => name.trim() && onSave({
            proposed_name: name.trim(),
            proposed_title: title.trim() || null,
            proposed_org: org.trim() || null,
          })}
          disabled={!name.trim()}
          style={{
            padding: "4px 12px", borderRadius: 4, fontSize: 11, fontWeight: 600,
            background: name.trim() ? "#fbbf24" : "#374151",
            color: name.trim() ? "#000" : "#6b7280",
            border: "none", cursor: name.trim() ? "pointer" : "not-allowed",
          }}
        >
          Save
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: "4px 12px", borderRadius: 4, fontSize: 11,
            background: "transparent", color: theme.text.faint,
            border: "1px solid " + theme.border.subtle, cursor: "pointer",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── New Org Form ─────────────────────────────────────────────────────────────

function NewOrgForm({ onSave, onCancel }) {
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [orgType, setOrgType] = useState("");

  const inputStyle = {
    width: "100%", padding: "5px 8px", borderRadius: 4,
    border: "1px solid " + theme.border.subtle,
    background: theme.bg.card, color: theme.text.primary, fontSize: 12,
    outline: "none", marginBottom: 6,
  };

  return (
    <div style={{
      background: "rgba(255,255,255,0.03)", padding: 10, borderRadius: 6,
      border: "1px solid rgba(250,204,21,0.2)", marginTop: 6,
    }}>
      <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 600, marginBottom: 6 }}>
        New Organization (Provisional)
      </div>
      <input placeholder="Organization name *" value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} />
      <input placeholder="Short name / acronym" value={shortName} onChange={(e) => setShortName(e.target.value)} style={inputStyle} />
      <input placeholder="Type (e.g. Federal Agency, Law Firm)" value={orgType} onChange={(e) => setOrgType(e.target.value)} style={inputStyle} />
      <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
        <button
          onClick={() => name.trim() && onSave({
            proposed_name: name.trim(),
            short_name: shortName.trim() || null,
            organization_type: orgType.trim() || null,
          })}
          disabled={!name.trim()}
          style={{
            padding: "4px 12px", borderRadius: 4, fontSize: 11, fontWeight: 600,
            background: name.trim() ? "#fbbf24" : "#374151",
            color: name.trim() ? "#000" : "#6b7280",
            border: "none", cursor: name.trim() ? "pointer" : "not-allowed",
          }}
        >
          Save
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: "4px 12px", borderRadius: 4, fontSize: 11,
            background: "transparent", color: theme.text.faint,
            border: "1px solid " + theme.border.subtle, cursor: "pointer",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Main PersonOrgResolver ──────────────────────────────────────────────────

export default function PersonOrgResolver({
  entityType = "person",    // "person" | "organization" | "both"
  value = null,              // { tracker_person_id, tracker_org_id, proposed_name, proposed_title, proposed_org, match_source }
  onLink,                    // (trackerRecord) => void — link to existing tracker record
  onCreateNew,               // (formData) => void — create provisional person/org
  onSkip,                    // () => void — mark as skipped
  onChange,                  // () => void — reset from matched/provisional back to unresolved
  disabled = false,
  showSkip = true,
}) {
  const [showNewForm, setShowNewForm] = useState(null); // null | "person" | "organization"

  const isMatched = value && (value.tracker_person_id || value.tracker_org_id) && value.match_source !== "provisional";
  const isProvisional = value && value.match_source === "provisional";
  const isSkipped = value && value.match_source === "skipped";
  const isResolved = isMatched || isProvisional || isSkipped;

  // ── Matched state ──
  if (isMatched) {
    return (
      <div style={{
        padding: "8px 10px", borderRadius: 6,
        background: "rgba(74,222,128,0.08)", fontSize: 12,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <span style={{ color: "#4ade80", fontWeight: 600 }}>Linked: </span>
          <span style={{ color: theme.text.primary }}>
            {value.proposed_name || value.tracker_person_id || value.tracker_org_id}
          </span>
          {value.proposed_title && (
            <span style={{ color: theme.text.faint }}> \u2014 {value.proposed_title}</span>
          )}
          {value.proposed_org && (
            <span style={{ color: theme.text.faint }}>, {value.proposed_org}</span>
          )}
        </div>
        {onChange && !disabled && (
          <button onClick={onChange} style={{
            background: "none", border: "none", color: "#60a5fa",
            cursor: "pointer", fontSize: 11, textDecoration: "underline",
          }}>Change</button>
        )}
      </div>
    );
  }

  // ── Provisional state ──
  if (isProvisional) {
    return (
      <div style={{
        padding: "8px 10px", borderRadius: 6,
        background: "rgba(250,204,21,0.08)", fontSize: 12,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <span style={{
            background: "#fbbf24", color: "#000", fontSize: 9, fontWeight: 700,
            padding: "1px 5px", borderRadius: 3, marginRight: 6,
          }}>NEW</span>
          <span style={{ color: theme.text.primary, fontWeight: 600 }}>
            {value.proposed_name}
          </span>
          {value.proposed_title && (
            <span style={{ color: theme.text.faint }}> \u2014 {value.proposed_title}</span>
          )}
          {value.proposed_org && (
            <span style={{ color: theme.text.faint }}>, {value.proposed_org}</span>
          )}
        </div>
        {onChange && !disabled && (
          <button onClick={onChange} style={{
            background: "none", border: "none", color: "#60a5fa",
            cursor: "pointer", fontSize: 11, textDecoration: "underline",
          }}>Edit</button>
        )}
      </div>
    );
  }

  // ── Skipped state ──
  if (isSkipped) {
    return (
      <div style={{
        padding: "8px 10px", borderRadius: 6,
        background: "rgba(156,163,175,0.08)", fontSize: 12,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{ color: theme.text.faint }}>Skipped</span>
        {onChange && !disabled && (
          <button onClick={onChange} style={{
            background: "none", border: "none", color: "#60a5fa",
            cursor: "pointer", fontSize: 11, textDecoration: "underline",
          }}>Change</button>
        )}
      </div>
    );
  }

  // ── Unresolved state ──
  return (
    <div style={{ opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? "none" : "auto" }}>
      {/* Search */}
      {(entityType === "person" || entityType === "both") && (
        <TrackerSearch entityType="person" onSelect={onLink} />
      )}
      {entityType === "both" && <div style={{ height: 6 }} />}
      {(entityType === "organization" || entityType === "both") && (
        <TrackerSearch entityType="organization" onSelect={onLink} />
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        {(entityType === "person" || entityType === "both") && (
          <button
            onClick={() => setShowNewForm("person")}
            style={{
              padding: "5px 10px", borderRadius: 4, fontSize: 11,
              background: "rgba(250,204,21,0.1)", color: "#fbbf24",
              border: "1px solid rgba(250,204,21,0.3)", cursor: "pointer",
            }}
          >
            + New Person
          </button>
        )}
        {(entityType === "organization" || entityType === "both") && (
          <button
            onClick={() => setShowNewForm("organization")}
            style={{
              padding: "5px 10px", borderRadius: 4, fontSize: 11,
              background: "rgba(250,204,21,0.1)", color: "#fbbf24",
              border: "1px solid rgba(250,204,21,0.3)", cursor: "pointer",
            }}
          >
            + New Org
          </button>
        )}
        {showSkip && onSkip && (
          <button
            onClick={onSkip}
            style={{
              padding: "5px 10px", borderRadius: 4, fontSize: 11,
              background: "transparent", color: theme.text.faint,
              border: "1px solid " + theme.border.subtle, cursor: "pointer",
            }}
          >
            Skip
          </button>
        )}
      </div>

      {/* New person form */}
      {showNewForm === "person" && (
        <NewPersonForm
          onSave={(data) => { onCreateNew(data); setShowNewForm(null); }}
          onCancel={() => setShowNewForm(null)}
        />
      )}

      {/* New org form */}
      {showNewForm === "organization" && (
        <NewOrgForm
          onSave={(data) => { onCreateNew(data); setShowNewForm(null); }}
          onCancel={() => setShowNewForm(null)}
        />
      )}
    </div>
  );
}

export { TrackerSearch, NewPersonForm, NewOrgForm };
