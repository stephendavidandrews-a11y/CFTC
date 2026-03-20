import React, { useState, useEffect } from "react";
import theme from "../../styles/theme";
import { fetchJSON } from "../../api/client";
import { getEnum, listOrganizations, listPeople } from "../../api/tracker";

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

// ── New Person Form (full fields matching PersonDrawer) ──────────────────────

function NewPersonForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    title: "",
    organization_id: "",
    email: "",
    phone: "",
    relationship_category: "",
    relationship_lane: "",
    include_in_team_workload: false,
    manager_person_id: "",
  });
  const [enums, setEnums] = useState({ relationship_category: [], relationship_lane: [] });
  const [orgs, setOrgs] = useState([]);
  const [people, setPeople] = useState([]);

  useEffect(() => {
    Promise.all([
      getEnum("relationship_category").catch(() => []),
      getEnum("relationship_lane").catch(() => []),
      listOrganizations({ limit: 200 }).catch(() => ({ items: [] })),
      listPeople({ limit: 200, is_active: true }).catch(() => ({ items: [] })),
    ]).then(([relCat, relLane, orgData, pplData]) => {
      setEnums({ relationship_category: relCat, relationship_lane: relLane });
      setOrgs(orgData.items || orgData || []);
      setPeople(pplData.items || pplData || []);
    });
  }, []);

  const handleChange = (field, val) => {
    const updated = { ...form, [field]: val };
    // Auto-set include_in_team_workload for direct/indirect reports
    if (field === "relationship_category" && (val === "Direct report" || val === "Indirect report")) {
      updated.include_in_team_workload = true;
    }
    setForm(updated);
  };

  const canSave = form.first_name.trim() || form.last_name.trim();

  const handleSave = () => {
    if (!canSave) return;
    const fullName = `${form.first_name.trim()} ${form.last_name.trim()}`.trim();
    const orgObj = orgs.find((o) => o.id === form.organization_id);
    onSave({
      proposed_name: fullName,
      proposed_title: form.title.trim() || null,
      proposed_org: orgObj ? (orgObj.short_name || orgObj.name) : null,
      proposed_org_id: form.organization_id || null,
      // Extra fields for direct tracker creation
      first_name: form.first_name.trim() || null,
      last_name: form.last_name.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      relationship_category: form.relationship_category || null,
      relationship_lane: form.relationship_lane || null,
      include_in_team_workload: form.include_in_team_workload ? 1 : 0,
      manager_person_id: form.manager_person_id || null,
    });
  };

  const inputStyle = {
    width: "100%", padding: "5px 8px", borderRadius: 4,
    border: "1px solid " + theme.border.subtle,
    background: theme.bg.card, color: theme.text.primary, fontSize: 12,
    outline: "none",
  };

  const selectStyle = {
    ...inputStyle,
    cursor: "pointer",
    appearance: "auto",
  };

  const labelStyle = {
    fontSize: 10, color: theme.text.faint, fontWeight: 600,
    marginBottom: 2, marginTop: 8, textTransform: "uppercase",
    letterSpacing: "0.03em",
  };

  const rowStyle = {
    display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
  };

  return (
    <div style={{
      background: "rgba(255,255,255,0.03)", padding: 12, borderRadius: 6,
      border: "1px solid rgba(250,204,21,0.2)", marginTop: 6,
      maxHeight: 420, overflowY: "auto",
    }}>
      <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 600, marginBottom: 4 }}>
        New Person (Provisional)
      </div>

      {/* Name row */}
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>First Name *</div>
          <input
            placeholder="First name"
            value={form.first_name}
            onChange={(e) => handleChange("first_name", e.target.value)}
            style={inputStyle}
          />
        </div>
        <div>
          <div style={labelStyle}>Last Name *</div>
          <input
            placeholder="Last name"
            value={form.last_name}
            onChange={(e) => handleChange("last_name", e.target.value)}
            style={inputStyle}
          />
        </div>
      </div>

      {/* Title */}
      <div style={labelStyle}>Title</div>
      <input
        placeholder="e.g. Senior Counsel"
        value={form.title}
        onChange={(e) => handleChange("title", e.target.value)}
        style={inputStyle}
      />

      {/* Organization dropdown */}
      <div style={labelStyle}>Organization</div>
      <select
        value={form.organization_id}
        onChange={(e) => handleChange("organization_id", e.target.value)}
        style={selectStyle}
      >
        <option value="">Select organization...</option>
        {orgs.map((o) => (
          <option key={o.id} value={o.id}>
            {o.short_name || o.name}
          </option>
        ))}
      </select>

      {/* Contact row */}
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>Email</div>
          <input
            placeholder="email@example.com"
            value={form.email}
            onChange={(e) => handleChange("email", e.target.value)}
            style={inputStyle}
          />
        </div>
        <div>
          <div style={labelStyle}>Phone</div>
          <input
            placeholder="(555) 123-4567"
            value={form.phone}
            onChange={(e) => handleChange("phone", e.target.value)}
            style={inputStyle}
          />
        </div>
      </div>

      {/* Relationship category dropdown */}
      <div style={labelStyle}>Relationship Category</div>
      <select
        value={form.relationship_category}
        onChange={(e) => handleChange("relationship_category", e.target.value)}
        style={selectStyle}
      >
        <option value="">Select category...</option>
        {enums.relationship_category.map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>

      {/* Relationship lane dropdown */}
      <div style={labelStyle}>Relationship Lane</div>
      <select
        value={form.relationship_lane}
        onChange={(e) => handleChange("relationship_lane", e.target.value)}
        style={selectStyle}
      >
        <option value="">Select lane...</option>
        {enums.relationship_lane.map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>

      {/* Manager dropdown */}
      <div style={labelStyle}>Reports To</div>
      <select
        value={form.manager_person_id}
        onChange={(e) => handleChange("manager_person_id", e.target.value)}
        style={selectStyle}
      >
        <option value="">No manager</option>
        {people.map((p) => (
          <option key={p.id} value={p.id}>
            {p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim()}
          </option>
        ))}
      </select>

      {/* Team workload checkbox */}
      <label style={{
        display: "flex", alignItems: "center", gap: 6,
        marginTop: 10, fontSize: 11, color: theme.text.muted, cursor: "pointer",
      }}>
        <input
          type="checkbox"
          checked={form.include_in_team_workload}
          onChange={(e) => handleChange("include_in_team_workload", e.target.checked)}
        />
        Include in team workload
      </label>

      {/* Save / Cancel */}
      <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
        <button
          onClick={handleSave}
          disabled={!canSave}
          style={{
            padding: "5px 14px", borderRadius: 4, fontSize: 11, fontWeight: 600,
            background: canSave ? "#fbbf24" : "#374151",
            color: canSave ? "#000" : "#6b7280",
            border: "none", cursor: canSave ? "pointer" : "not-allowed",
          }}
        >
          Create Person
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: "5px 14px", borderRadius: 4, fontSize: 11,
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
            <span style={{ color: theme.text.faint }}> {"\u2014"} {value.proposed_title}</span>
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
            <span style={{ color: theme.text.faint }}> {"\u2014"} {value.proposed_title}</span>
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
