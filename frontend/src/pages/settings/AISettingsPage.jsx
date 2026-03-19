/**
 * AISettingsPage — Phase 8 Settings UI for the CFTC AI Layer.
 *
 * Five collapsible accordion sections covering user identity, trust
 * configuration, routing/extraction policy, proactive intelligence,
 * model configuration, and change history.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import theme from "../../styles/theme";
import {
  getAIConfig,
  updateAIConfigSection,
  getConfigAudit,
  getConfigStats,
  getAIHealth,
} from "../../api/ai";
import { useToastContext } from "../../contexts/ToastContext";

// ── Label Maps ──────────────────────────────────────────────────────────────

const ACTION_LABELS = {
  task: "Tasks",
  matter_update: "Matter Updates",
  decision: "Decisions",
  status_change: "Status Changes",
  meeting_record: "Meeting Records",
  stakeholder_addition: "Stakeholder Additions",
  new_matter: "New Matters",
  new_person: "New People",
  new_organization: "New Organizations",
  follow_up: "Follow-ups",
  document: "Documents",
};

const MODE_LABELS = {
  review_required: "Review Required",
  auto_if_confident: "Auto if Confident",
  always_auto: "Always Auto-commit",
};

const EXTRACTION_LABELS = {
  propose_tasks: "Tasks",
  propose_decisions: "Decisions",
  propose_matter_updates: "Matter Updates",
  propose_meeting_records: "Meeting Records",
  propose_new_matters: "New Matters",
  propose_stakeholders: "Stakeholders",
  propose_follow_ups: "Follow-ups",
  propose_new_people: "New People",
  propose_new_organizations: "New Organizations",
  propose_status_changes: "Status Changes",
  propose_documents: "Documents",
  capture_stance_data: "Stance / Position Data",
  capture_intelligence_notes: "Intelligence Notes",
};

const SENSITIVITY_LABELS = {
  flag_enforcement_sensitive: "Enforcement Sensitive",
  flag_congressional_sensitive: "Congressional Sensitive",
  flag_deliberative: "Deliberative Process",
};

const THRESHOLD_OPTIONS = ["low", "moderate", "high"];
const WEEKDAY_OPTIONS = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

// ── Shared Style Helpers ────────────────────────────────────────────────────

const cardStyle = {
  background: theme.bg.card,
  borderRadius: theme.card.radius,
  border: `1px solid ${theme.border.subtle}`,
  marginBottom: 16,
  overflow: "hidden",
};

const inputStyle = {
  background: theme.bg.input,
  border: `1px solid ${theme.border.subtle}`,
  borderRadius: 6,
  color: theme.text.secondary,
  padding: "8px 12px",
  fontSize: 14,
  fontFamily: theme.font.family,
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
  transition: "border-color 0.15s",
};

const selectStyle = {
  ...inputStyle,
  cursor: "pointer",
  appearance: "none",
  WebkitAppearance: "none",
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2394a3b8' d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 10px center",
  paddingRight: 30,
};

const labelStyle = {
  color: theme.text.muted,
  fontSize: 13,
  marginBottom: 4,
  display: "block",
};

const descriptionStyle = {
  color: theme.text.dim,
  fontSize: 13,
  fontStyle: "italic",
  marginBottom: 16,
  lineHeight: 1.4,
};

const sectionHeaderStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "14px 20px",
  cursor: "pointer",
  userSelect: "none",
};

const sectionTitleStyle = {
  color: theme.text.primary,
  fontSize: 16,
  fontWeight: 600,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const sectionBodyStyle = (expanded) => ({
  maxHeight: expanded ? 5000 : 0,
  overflow: "hidden",
  transition: "max-height 0.35s ease",
});

const saveButtonStyle = (dirty, saving) => ({
  background: dirty ? theme.accent.blue : theme.border.default,
  color: dirty ? "#fff" : theme.text.dim,
  border: "none",
  borderRadius: 6,
  padding: "8px 20px",
  fontSize: 14,
  fontFamily: theme.font.family,
  fontWeight: 500,
  cursor: dirty && !saving ? "pointer" : "default",
  opacity: saving ? 0.7 : 1,
  transition: "background 0.15s, opacity 0.15s",
  display: "flex",
  alignItems: "center",
  gap: 8,
});

const errorTextStyle = {
  color: theme.accent.red,
  fontSize: 13,
  marginTop: 4,
};

const subHeadingStyle = {
  color: theme.text.muted,
  fontSize: 13,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 12,
  marginTop: 20,
};

// ── Reusable Components ─────────────────────────────────────────────────────

function DirtyDot() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: theme.accent.yellow,
        flexShrink: 0,
      }}
      title="Unsaved changes"
    />
  );
}

function ChevronIcon({ expanded }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      style={{
        transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
        transition: "transform 0.2s ease",
        flexShrink: 0,
      }}
    >
      <path
        d="M4 6l4 4 4-4"
        stroke={theme.text.muted}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Spinner() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        border: `2px solid ${theme.text.dim}`,
        borderTopColor: "transparent",
        borderRadius: "50%",
        animation: "ai-settings-spin 0.6s linear infinite",
      }}
    />
  );
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{
        width: 40,
        height: 22,
        borderRadius: 11,
        border: "none",
        background: checked ? theme.accent.blue : theme.border.default,
        position: "relative",
        cursor: disabled ? "default" : "pointer",
        transition: "background 0.2s",
        padding: 0,
        flexShrink: 0,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <span
        style={{
          display: "block",
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "#fff",
          position: "absolute",
          top: 3,
          left: checked ? 21 : 3,
          transition: "left 0.2s",
        }}
      />
    </button>
  );
}

function FieldRow({ label, children, description }) {
  return (
    <div style={{ marginBottom: 14 }}>
      {label && <label style={labelStyle}>{label}</label>}
      {children}
      {description && (
        <div style={{ color: theme.text.dim, fontSize: 12, marginTop: 2 }}>
          {description}
        </div>
      )}
    </div>
  );
}

function ToggleRow({ label, checked, onChange, disabled }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 0",
      }}
    >
      <span style={{ color: theme.text.secondary, fontSize: 14 }}>
        {label}
      </span>
      <Toggle checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}

function LoadingSkeleton() {
  const bar = (w) => ({
    height: 14,
    width: w,
    background: theme.border.default,
    borderRadius: 4,
    marginBottom: 10,
    animation: "ai-settings-pulse 1.5s ease-in-out infinite",
  });
  return (
    <div style={{ padding: 24 }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ ...cardStyle, padding: 20 }}>
          <div style={bar("40%")} />
          <div style={bar("80%")} />
          <div style={bar("60%")} />
        </div>
      ))}
    </div>
  );
}

// ── Accordion Section Wrapper ───────────────────────────────────────────────

function Section({
  title,
  description,
  expanded,
  onToggle,
  dirty,
  saving,
  onSave,
  children,
  hideFooter,
}) {
  return (
    <div style={cardStyle}>
      <div style={sectionHeaderStyle} onClick={onToggle}>
        <div style={sectionTitleStyle}>
          <ChevronIcon expanded={expanded} />
          {title}
          {dirty && <DirtyDot />}
        </div>
      </div>
      <div style={sectionBodyStyle(expanded)}>
        <div style={{ padding: "0 20px 20px" }}>
          {description && <p style={descriptionStyle}>{description}</p>}
          {children}
          {!hideFooter && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
              <button
                style={saveButtonStyle(dirty, saving)}
                disabled={!dirty || saving}
                onClick={(e) => {
                  e.stopPropagation();
                  onSave();
                }}
              >
                {saving && <Spinner />}
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Error Boundary ──────────────────────────────────────────────────────────

class SettingsErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: theme.text.muted,
          }}
        >
          <h2 style={{ color: theme.accent.red, marginBottom: 12 }}>
            Settings Error
          </h2>
          <p>Something went wrong loading the settings page.</p>
          <p style={{ fontSize: 13, color: theme.text.dim, marginTop: 8 }}>
            {this.state.error?.message}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              ...saveButtonStyle(true, false),
              display: "inline-flex",
              marginTop: 20,
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Main Page Component ─────────────────────────────────────────────────────

function AISettingsPageInner() {
  const toast = useToastContext();

  // ── State ───────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Config sections (mirrors backend structure)
  const [userConfig, setUserConfig] = useState(null);
  const [routingPolicy, setRoutingPolicy] = useState(null);
  const [extractionPolicy, setExtractionPolicy] = useState(null);
  const [sensitivityPolicy, setSensitivityPolicy] = useState(null);
  const [trustConfig, setTrustConfig] = useState(null);
  const [modelConfig, setModelConfig] = useState(null);
  const [proactiveConfig, setProactiveConfig] = useState(null);

  // Snapshots for dirty detection
  const [snapshots, setSnapshots] = useState({});

  // Supplementary data
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState(null);
  const [audit, setAudit] = useState([]);

  // Section UI state
  const [expanded, setExpanded] = useState({
    user: false,
    trust: true,
    routing: false,
    proactive: false,
    model: false,
    history: false,
  });
  const [saving, setSaving] = useState({});

  // Ref for beforeunload
  const dirtyRef = useRef(false);

  // ── Data Loading ────────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const [configRes, statsRes, healthRes, auditRes] = await Promise.allSettled([
        getAIConfig(),
        getConfigStats(),
        getAIHealth(),
        getConfigAudit(),
      ]);

      if (configRes.status === "rejected") {
        throw configRes.reason;
      }

      const cfg = configRes.value;
      setUserConfig(cfg.user_config || {});
      setRoutingPolicy(cfg.routing_policy || {});
      setExtractionPolicy(cfg.extraction_policy || {});
      setSensitivityPolicy(cfg.sensitivity_policy || {});
      setTrustConfig(cfg.trust_config || {});
      setModelConfig(cfg.model_config || {});
      setProactiveConfig(cfg.proactive_config || {});

      setSnapshots({
        user_config: JSON.stringify(cfg.user_config || {}),
        routing_policy: JSON.stringify(cfg.routing_policy || {}),
        extraction_policy: JSON.stringify(cfg.extraction_policy || {}),
        sensitivity_policy: JSON.stringify(cfg.sensitivity_policy || {}),
        trust_config: JSON.stringify(cfg.trust_config || {}),
        model_config: JSON.stringify(cfg.model_config || {}),
        proactive_config: JSON.stringify(cfg.proactive_config || {}),
      });

      // Expand user section if name is empty
      if (!cfg.user_config?.name) {
        setExpanded((prev) => ({ ...prev, user: true }));
      }

      if (statsRes.status === "fulfilled") setStats(statsRes.value || {});
      if (healthRes.status === "fulfilled") setHealth(healthRes.value || null);
      if (auditRes.status === "fulfilled") setAudit(auditRes.value || []);
    } catch (err) {
      setLoadError(err.message || "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Dirty Detection ─────────────────────────────────────────────────────

  const isDirty = (sectionName, currentValue) => {
    if (!snapshots[sectionName]) return false;
    return JSON.stringify(currentValue) !== snapshots[sectionName];
  };

  const dirtyUser = isDirty("user_config", userConfig);
  const dirtyRouting = isDirty("routing_policy", routingPolicy);
  const dirtyExtraction = isDirty("extraction_policy", extractionPolicy);
  const dirtySensitivity = isDirty("sensitivity_policy", sensitivityPolicy);
  const dirtyTrust = isDirty("trust_config", trustConfig);
  const dirtyModel = isDirty("model_config", modelConfig);
  const dirtyProactive = isDirty("proactive_config", proactiveConfig);

  const dirtyRoutingSection = dirtyRouting || dirtyExtraction || dirtySensitivity;
  const anyDirty = dirtyUser || dirtyRoutingSection || dirtyTrust || dirtyModel || dirtyProactive;

  useEffect(() => {
    dirtyRef.current = anyDirty;
  }, [anyDirty]);

  useEffect(() => {
    const handler = (e) => {
      if (dirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // ── Save Helpers ────────────────────────────────────────────────────────

  const saveSection = async (sectionKey, sectionName, data) => {
    setSaving((prev) => ({ ...prev, [sectionKey]: true }));
    try {
      await updateAIConfigSection(sectionName, data);
      setSnapshots((prev) => ({
        ...prev,
        [sectionName]: JSON.stringify(data),
      }));
      toast.success(`${sectionKey.charAt(0).toUpperCase() + sectionKey.slice(1)} settings saved`);
    } catch (err) {
      toast.error(err.message || `Failed to save ${sectionKey}`);
    } finally {
      setSaving((prev) => ({ ...prev, [sectionKey]: false }));
    }
  };

  const saveUser = () => saveSection("user", "user_config", userConfig);
  const saveTrust = () => saveSection("trust", "trust_config", trustConfig);
  const saveModel = () => saveSection("model", "model_config", modelConfig);
  const saveProactive = () =>
    saveSection("proactive", "proactive_config", proactiveConfig);

  // Routing section saves multiple backend sections
  const saveRouting = async () => {
    setSaving((prev) => ({ ...prev, routing: true }));
    try {
      const promises = [];
      if (dirtyRouting) promises.push(updateAIConfigSection("routing_policy", routingPolicy));
      if (dirtyExtraction) promises.push(updateAIConfigSection("extraction_policy", extractionPolicy));
      if (dirtySensitivity) promises.push(updateAIConfigSection("sensitivity_policy", sensitivityPolicy));
      await Promise.all(promises);

      setSnapshots((prev) => ({
        ...prev,
        ...(dirtyRouting ? { routing_policy: JSON.stringify(routingPolicy) } : {}),
        ...(dirtyExtraction ? { extraction_policy: JSON.stringify(extractionPolicy) } : {}),
        ...(dirtySensitivity ? { sensitivity_policy: JSON.stringify(sensitivityPolicy) } : {}),
      }));

      toast.success("Routing & extraction settings saved");
    } catch (err) {
      toast.error(err.message || "Failed to save routing settings");
    } finally {
      setSaving((prev) => ({ ...prev, routing: false }));
    }
  };

  // ── Section Toggle ──────────────────────────────────────────────────────

  const toggle = (key) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  // ── Refresh audit after any save ────────────────────────────────────────

  const refreshAudit = useCallback(async () => {
    try {
      const res = await getConfigAudit();
      setAudit(res || []);
    } catch {
      /* silent */
    }
  }, []);

  // Refresh audit when any save completes
  const prevSaving = useRef(saving);
  useEffect(() => {
    const wasSaving = Object.values(prevSaving.current).some(Boolean);
    const nowSaving = Object.values(saving).some(Boolean);
    if (wasSaving && !nowSaving) {
      refreshAudit();
    }
    prevSaving.current = saving;
  }, [saving, refreshAudit]);

  // ── Trust suggestion logic ──────────────────────────────────────────────

  const getSuggestion = (actionKey) => {
    const s = stats[actionKey];
    if (!s || s.total < 20) return null;
    if (s.acceptance_rate >= 0.9 && s.edit_rate <= 0.1) {
      return "Consider auto-commit at 0.85";
    }
    return null;
  };

  // ── Render ──────────────────────────────────────────────────────────────

  if (loading) return <LoadingSkeleton />;

  if (loadError) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <h2 style={{ color: theme.accent.red, marginBottom: 12 }}>
          Failed to Load Settings
        </h2>
        <p style={{ color: theme.text.muted }}>{loadError}</p>
        <button
          onClick={loadData}
          style={{ ...saveButtonStyle(true, false), display: "inline-flex", marginTop: 16 }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px 32px", maxWidth: 960, margin: "0 auto" }}>
      {/* Keyframe injection */}
      <style>{`
        @keyframes ai-settings-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes ai-settings-pulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.8; }
        }
      `}</style>

      <h1
        style={{
          color: theme.text.primary,
          fontSize: 24,
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        AI Settings
      </h1>
      <p style={{ color: theme.text.dim, fontSize: 14, marginBottom: 24 }}>
        Configure the AI operations layer for communication processing,
        intelligence extraction, and trust policies.
      </p>

      {/* ── Section 1: User Identity ─────────────────────────────── */}
      <Section
        title="User Identity"
        description="Your identity used for pipeline processing. Email addresses are used to identify emails you sent."
        expanded={expanded.user}
        onToggle={() => toggle("user")}
        dirty={dirtyUser}
        saving={saving.user}
        onSave={saveUser}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="Name">
            <input
              style={inputStyle}
              value={userConfig?.name || ""}
              placeholder="Your full name"
              onFocus={(e) => (e.target.style.borderColor = theme.border.active)}
              onBlur={(e) => (e.target.style.borderColor = theme.border.subtle)}
              onChange={(e) =>
                setUserConfig((prev) => ({ ...prev, name: e.target.value }))
              }
            />
          </FieldRow>
          <FieldRow label="Title">
            <input
              style={inputStyle}
              value={userConfig?.title || ""}
              placeholder="Your title / role"
              onFocus={(e) => (e.target.style.borderColor = theme.border.active)}
              onBlur={(e) => (e.target.style.borderColor = theme.border.subtle)}
              onChange={(e) =>
                setUserConfig((prev) => ({ ...prev, title: e.target.value }))
              }
            />
          </FieldRow>
        </div>
        <FieldRow
          label="Email Addresses"
          description="Comma-separated list of your email addresses"
        >
          <input
            style={inputStyle}
            value={
              Array.isArray(userConfig?.email_addresses)
                ? userConfig.email_addresses.join(", ")
                : ""
            }
            placeholder="user@example.com, alias@example.com"
            onFocus={(e) => (e.target.style.borderColor = theme.border.active)}
            onBlur={(e) => (e.target.style.borderColor = theme.border.subtle)}
            onChange={(e) =>
              setUserConfig((prev) => ({
                ...prev,
                email_addresses: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }))
            }
          />
        </FieldRow>
        <FieldRow label="Tracker Person ID" description="Optional. Links to your tracker profile.">
          <input
            style={{ ...inputStyle, maxWidth: 300 }}
            value={userConfig?.tracker_person_id || ""}
            placeholder="e.g. person-abc123"
            onFocus={(e) => (e.target.style.borderColor = theme.border.active)}
            onBlur={(e) => (e.target.style.borderColor = theme.border.subtle)}
            onChange={(e) =>
              setUserConfig((prev) => ({
                ...prev,
                tracker_person_id: e.target.value || null,
              }))
            }
          />
        </FieldRow>
      </Section>

      {/* ── Section 2: Trust Configuration ───────────────────────── */}
      <Section
        title="Trust Configuration"
        description="Control which proposal types require human review before committing to the tracker."
        expanded={expanded.trust}
        onToggle={() => toggle("trust")}
        dirty={dirtyTrust}
        saving={saving.trust}
        onSave={saveTrust}
      >
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 14,
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: `1px solid ${theme.border.subtle}`,
                }}
              >
                {[
                  "Action Type",
                  "Mode",
                  "Threshold",
                  "Acceptance",
                  "Edit Rate",
                  "Suggestion",
                ].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "8px 10px",
                      color: theme.text.dim,
                      fontWeight: 500,
                      fontSize: 12,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(ACTION_LABELS).map((key) => {
                const entry = trustConfig?.[key] || {
                  mode: "review_required",
                  auto_commit_threshold: null,
                };
                const s = stats[key];
                const suggestion = getSuggestion(key);

                return (
                  <tr
                    key={key}
                    style={{
                      borderBottom: `1px solid ${theme.border.subtle}`,
                    }}
                  >
                    <td
                      style={{
                        padding: "10px 10px",
                        color: theme.text.secondary,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {ACTION_LABELS[key]}
                    </td>
                    <td style={{ padding: "10px 10px" }}>
                      <select
                        style={{ ...selectStyle, width: "auto", minWidth: 170 }}
                        value={entry.mode}
                        onChange={(e) =>
                          setTrustConfig((prev) => ({
                            ...prev,
                            [key]: {
                              ...prev[key],
                              mode: e.target.value,
                              auto_commit_threshold:
                                e.target.value === "auto_if_confident"
                                  ? prev[key]?.auto_commit_threshold ?? 0.85
                                  : null,
                            },
                          }))
                        }
                      >
                        {Object.entries(MODE_LABELS).map(([v, l]) => (
                          <option key={v} value={v}>
                            {l}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: "10px 10px" }}>
                      <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.05"
                        disabled={entry.mode !== "auto_if_confident"}
                        style={{
                          ...inputStyle,
                          width: 80,
                          opacity: entry.mode !== "auto_if_confident" ? 0.4 : 1,
                        }}
                        value={
                          entry.auto_commit_threshold != null
                            ? entry.auto_commit_threshold
                            : ""
                        }
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          setTrustConfig((prev) => ({
                            ...prev,
                            [key]: {
                              ...prev[key],
                              auto_commit_threshold:
                                isNaN(val)
                                  ? null
                                  : Math.max(0, Math.min(1, val)),
                            },
                          }));
                        }}
                      />
                    </td>
                    <td
                      style={{
                        padding: "10px 10px",
                        color: theme.text.muted,
                        fontFamily: theme.font.mono,
                        fontSize: 13,
                      }}
                    >
                      {s
                        ? `${(s.acceptance_rate * 100).toFixed(0)}% (${s.approved}/${s.total})`
                        : "\u2014"}
                    </td>
                    <td
                      style={{
                        padding: "10px 10px",
                        color: theme.text.muted,
                        fontFamily: theme.font.mono,
                        fontSize: 13,
                      }}
                    >
                      {s
                        ? `${(s.edit_rate * 100).toFixed(0)}%`
                        : "\u2014"}
                    </td>
                    <td style={{ padding: "10px 10px" }}>
                      {suggestion ? (
                        <span
                          style={{
                            color: theme.accent.green,
                            fontSize: 13,
                          }}
                        >
                          {suggestion}
                        </span>
                      ) : (
                        <span style={{ color: theme.text.ghost }}>
                          {"\u2014"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── Section 3: Routing & Extraction Policy ───────────────── */}
      <Section
        title="Routing & Extraction Policy"
        description="Configure how communications are analyzed and what types of intelligence are extracted."
        expanded={expanded.routing}
        onToggle={() => toggle("routing")}
        dirty={dirtyRoutingSection}
        saving={saving.routing}
        onSave={saveRouting}
      >
        {/* Routing sub-section */}
        <div style={subHeadingStyle}>Routing</div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="New Matter Threshold">
            <select
              style={selectStyle}
              value={routingPolicy?.new_matter_threshold || "low"}
              onChange={(e) =>
                setRoutingPolicy((prev) => ({
                  ...prev,
                  new_matter_threshold: e.target.value,
                }))
              }
            >
              {THRESHOLD_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Match Confidence Minimum">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={routingPolicy?.match_confidence_minimum ?? 0.5}
                onChange={(e) =>
                  setRoutingPolicy((prev) => ({
                    ...prev,
                    match_confidence_minimum: parseFloat(e.target.value),
                  }))
                }
                style={{ flex: 1, accentColor: theme.accent.blue }}
              />
              <span
                style={{
                  color: theme.text.secondary,
                  fontFamily: theme.font.mono,
                  fontSize: 13,
                  minWidth: 36,
                  textAlign: "right",
                }}
              >
                {(routingPolicy?.match_confidence_minimum ?? 0.5).toFixed(2)}
              </span>
            </div>
          </FieldRow>

          <FieldRow label="Max New Matters per Communication">
            <input
              type="number"
              min="1"
              max="10"
              step="1"
              style={{ ...inputStyle, width: 100 }}
              value={routingPolicy?.max_new_matters_per_communication ?? 3}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val > 0) {
                  setRoutingPolicy((prev) => ({
                    ...prev,
                    max_new_matters_per_communication: val,
                  }));
                }
              }}
            />
          </FieldRow>
        </div>

        <ToggleRow
          label="Multi-matter routing enabled"
          checked={routingPolicy?.multi_matter_enabled ?? true}
          onChange={(v) =>
            setRoutingPolicy((prev) => ({ ...prev, multi_matter_enabled: v }))
          }
        />
        <ToggleRow
          label="Standalone items enabled"
          checked={routingPolicy?.standalone_items_enabled ?? true}
          onChange={(v) =>
            setRoutingPolicy((prev) => ({
              ...prev,
              standalone_items_enabled: v,
            }))
          }
        />

        {/* Extraction sub-section */}
        <div style={subHeadingStyle}>Extraction Types</div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0 24px",
          }}
        >
          {Object.entries(EXTRACTION_LABELS).map(([key, label]) => (
            <ToggleRow
              key={key}
              label={label}
              checked={extractionPolicy?.[key] ?? false}
              onChange={(v) =>
                setExtractionPolicy((prev) => ({ ...prev, [key]: v }))
              }
            />
          ))}
        </div>

        {/* Sensitivity sub-section */}
        <div style={subHeadingStyle}>Sensitivity Flags</div>

        {Object.entries(SENSITIVITY_LABELS).map(([key, label]) => (
          <ToggleRow
            key={key}
            label={label}
            checked={sensitivityPolicy?.[key] ?? false}
            onChange={(v) =>
              setSensitivityPolicy((prev) => ({ ...prev, [key]: v }))
            }
          />
        ))}
      </Section>

      {/* ── Section 4: Proactive Intelligence ────────────────────── */}
      <Section
        title="Proactive Intelligence"
        description="Configure automated intelligence generation and alerting behavior."
        expanded={expanded.proactive}
        onToggle={() => toggle("proactive")}
        dirty={dirtyProactive}
        saving={saving.proactive}
        onSave={saveProactive}
      >
        {/* Daily Digest */}
        <div style={subHeadingStyle}>Daily Digest</div>
        <ToggleRow
          label="Enabled"
          checked={proactiveConfig?.daily_digest?.enabled ?? false}
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              daily_digest: { ...prev.daily_digest, enabled: v },
            }))
          }
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="Schedule Time">
            <input
              type="time"
              style={inputStyle}
              value={proactiveConfig?.daily_digest?.schedule_time || "06:00"}
              onChange={(e) =>
                setProactiveConfig((prev) => ({
                  ...prev,
                  daily_digest: {
                    ...prev.daily_digest,
                    schedule_time: e.target.value,
                  },
                }))
              }
            />
          </FieldRow>
        </div>
        <ToggleRow
          label="Email digest"
          checked={proactiveConfig?.daily_digest?.email_digest ?? false}
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              daily_digest: { ...prev.daily_digest, email_digest: v },
            }))
          }
        />

        {/* Weekly Brief */}
        <div style={subHeadingStyle}>Weekly Brief</div>
        <ToggleRow
          label="Enabled"
          checked={proactiveConfig?.weekly_brief?.enabled ?? false}
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              weekly_brief: { ...prev.weekly_brief, enabled: v },
            }))
          }
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="Day of Week">
            <select
              style={selectStyle}
              value={proactiveConfig?.weekly_brief?.schedule_day || "sunday"}
              onChange={(e) =>
                setProactiveConfig((prev) => ({
                  ...prev,
                  weekly_brief: {
                    ...prev.weekly_brief,
                    schedule_day: e.target.value,
                  },
                }))
              }
            >
              {WEEKDAY_OPTIONS.map((d) => (
                <option key={d} value={d}>
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </option>
              ))}
            </select>
          </FieldRow>
          <FieldRow label="Schedule Time">
            <input
              type="time"
              style={inputStyle}
              value={proactiveConfig?.weekly_brief?.schedule_time || "20:00"}
              onChange={(e) =>
                setProactiveConfig((prev) => ({
                  ...prev,
                  weekly_brief: {
                    ...prev.weekly_brief,
                    schedule_time: e.target.value,
                  },
                }))
              }
            />
          </FieldRow>
        </div>
        <ToggleRow
          label="Auto boss brief"
          checked={proactiveConfig?.weekly_brief?.auto_boss_brief ?? false}
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              weekly_brief: { ...prev.weekly_brief, auto_boss_brief: v },
            }))
          }
        />

        {/* Real-time Alerts */}
        <div style={subHeadingStyle}>Real-time Alerts</div>
        <ToggleRow
          label="Enabled"
          checked={proactiveConfig?.realtime_alerts?.enabled ?? false}
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              realtime_alerts: { ...prev.realtime_alerts, enabled: v },
            }))
          }
        />
        <FieldRow label="Check Interval (minutes)">
          <input
            type="number"
            min="5"
            max="1440"
            step="5"
            style={{ ...inputStyle, width: 120 }}
            value={
              proactiveConfig?.realtime_alerts?.check_interval_minutes ?? 60
            }
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val) && val >= 5) {
                setProactiveConfig((prev) => ({
                  ...prev,
                  realtime_alerts: {
                    ...prev.realtime_alerts,
                    check_interval_minutes: val,
                  },
                }));
              }
            }}
          />
        </FieldRow>

        {/* Deadline Thresholds */}
        <div style={subHeadingStyle}>Deadline Thresholds</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="Critical (days)">
            <input
              type="number"
              min="1"
              step="1"
              style={{ ...inputStyle, width: 100 }}
              value={
                proactiveConfig?.deadline_thresholds?.critical_days ?? 3
              }
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val >= 1) {
                  setProactiveConfig((prev) => ({
                    ...prev,
                    deadline_thresholds: {
                      ...prev.deadline_thresholds,
                      critical_days: val,
                    },
                  }));
                }
              }}
            />
          </FieldRow>
          <FieldRow label="Warning (days)">
            <input
              type="number"
              min="1"
              step="1"
              style={{ ...inputStyle, width: 100 }}
              value={
                proactiveConfig?.deadline_thresholds?.warning_days ?? 7
              }
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val >= 1) {
                  setProactiveConfig((prev) => ({
                    ...prev,
                    deadline_thresholds: {
                      ...prev.deadline_thresholds,
                      warning_days: val,
                    },
                  }));
                }
              }}
            />
          </FieldRow>
        </div>

        {/* Follow-up Thresholds */}
        <div style={subHeadingStyle}>Follow-up Thresholds</div>
        <ToggleRow
          label="Overdue alert"
          checked={
            proactiveConfig?.followup_thresholds?.overdue_alert ?? true
          }
          onChange={(v) =>
            setProactiveConfig((prev) => ({
              ...prev,
              followup_thresholds: {
                ...prev.followup_thresholds,
                overdue_alert: v,
              },
            }))
          }
        />
        <FieldRow label="Upcoming (days)">
          <input
            type="number"
            min="1"
            step="1"
            style={{ ...inputStyle, width: 100 }}
            value={
              proactiveConfig?.followup_thresholds?.upcoming_days ?? 3
            }
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val) && val >= 1) {
                setProactiveConfig((prev) => ({
                  ...prev,
                  followup_thresholds: {
                    ...prev.followup_thresholds,
                    upcoming_days: val,
                  },
                }));
              }
            }}
          />
        </FieldRow>

        {/* Workload Thresholds */}
        <div style={subHeadingStyle}>Workload Thresholds</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <FieldRow label="Multiplier">
            <input
              type="number"
              min="1"
              max="10"
              step="0.1"
              style={{ ...inputStyle, width: 100 }}
              value={
                proactiveConfig?.workload_thresholds?.multiplier ?? 2.0
              }
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val >= 1) {
                  setProactiveConfig((prev) => ({
                    ...prev,
                    workload_thresholds: {
                      ...prev.workload_thresholds,
                      multiplier: val,
                    },
                  }));
                }
              }}
            />
          </FieldRow>
          <FieldRow label="Max Matters Flag">
            <input
              type="number"
              min="1"
              step="1"
              style={{ ...inputStyle, width: 100 }}
              value={
                proactiveConfig?.workload_thresholds?.max_matters_flag ?? 5
              }
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val >= 1) {
                  setProactiveConfig((prev) => ({
                    ...prev,
                    workload_thresholds: {
                      ...prev.workload_thresholds,
                      max_matters_flag: val,
                    },
                  }));
                }
              }}
            />
          </FieldRow>
        </div>

        {/* Snooze Options */}
        <div style={subHeadingStyle}>Snooze Options (days)</div>
        <FieldRow description="Comma-separated list of snooze durations in days">
          <input
            style={{ ...inputStyle, width: 250 }}
            value={
              Array.isArray(proactiveConfig?.snooze_options_days)
                ? proactiveConfig.snooze_options_days.join(", ")
                : ""
            }
            placeholder="3, 7, 14, 30"
            onFocus={(e) => (e.target.style.borderColor = theme.border.active)}
            onBlur={(e) => (e.target.style.borderColor = theme.border.subtle)}
            onChange={(e) => {
              const vals = e.target.value
                .split(",")
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !isNaN(n) && n > 0);
              setProactiveConfig((prev) => ({
                ...prev,
                snooze_options_days: vals,
              }));
            }}
          />
        </FieldRow>
      </Section>

      {/* ── Section 5: Model Configuration ───────────────────────── */}
      <Section
        title="Model Configuration"
        description="AI model configuration and budget controls. Model selections are display-only."
        expanded={expanded.model}
        onToggle={() => toggle("model")}
        dirty={dirtyModel}
        saving={saving.model}
        onSave={saveModel}
      >
        {/* Models (display-only) */}
        <div style={subHeadingStyle}>Models</div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 12,
            marginBottom: 16,
          }}
        >
          {[
            {
              label: "Primary Extraction",
              value: modelConfig?.primary_extraction_model,
            },
            {
              label: "Escalation",
              value: modelConfig?.escalation_model,
            },
            { label: "Haiku (Fast)", value: modelConfig?.haiku_model },
          ].map((m) => (
            <div
              key={m.label}
              style={{
                background: theme.bg.input,
                border: `1px solid ${theme.border.subtle}`,
                borderRadius: 8,
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  color: theme.text.dim,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  marginBottom: 4,
                }}
              >
                {m.label}
              </div>
              <div
                style={{
                  color: theme.text.secondary,
                  fontSize: 13,
                  fontFamily: theme.font.mono,
                  wordBreak: "break-all",
                }}
              >
                {m.value || "\u2014"}
              </div>
            </div>
          ))}
        </div>

        {/* Budget */}
        <div style={subHeadingStyle}>Budget</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <FieldRow label="Daily Budget (USD)">
            <input
              type="number"
              min="0.01"
              step="0.50"
              style={{ ...inputStyle, width: 120 }}
              value={modelConfig?.daily_budget_usd ?? 10}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val > 0) {
                  setModelConfig((prev) => ({
                    ...prev,
                    daily_budget_usd: val,
                  }));
                }
              }}
            />
          </FieldRow>
          <FieldRow label="Warning Threshold (0-1)">
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              style={{ ...inputStyle, width: 120 }}
              value={modelConfig?.budget_warning_threshold ?? 0.8}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val >= 0 && val <= 1) {
                  setModelConfig((prev) => ({
                    ...prev,
                    budget_warning_threshold: val,
                  }));
                }
              }}
            />
          </FieldRow>
          <FieldRow label="Today's Spend">
            {health ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 6,
                  paddingTop: 8,
                }}
              >
                <span
                  style={{
                    color:
                      health.spend?.today_usd >=
                      (health.spend?.daily_budget_usd || 10) *
                        (modelConfig?.budget_warning_threshold ?? 0.8)
                        ? theme.accent.yellow
                        : theme.accent.green,
                    fontFamily: theme.font.mono,
                    fontSize: 18,
                    fontWeight: 600,
                  }}
                >
                  ${(health.spend?.today_usd ?? 0).toFixed(2)}
                </span>
                <span style={{ color: theme.text.dim, fontSize: 13 }}>
                  / ${(health.spend?.daily_budget_usd ?? 10).toFixed(2)}
                </span>
                {health.spend?.paused && (
                  <span
                    style={{
                      color: theme.accent.red,
                      fontSize: 12,
                      fontWeight: 600,
                      marginLeft: 8,
                    }}
                  >
                    PAUSED
                  </span>
                )}
              </div>
            ) : (
              <span style={{ color: theme.text.dim, fontSize: 13, paddingTop: 8, display: "block" }}>
                Unavailable
              </span>
            )}
          </FieldRow>
        </div>

        {/* Opus Retry Triggers */}
        <div style={subHeadingStyle}>Opus Escalation Triggers</div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0 24px",
          }}
        >
          {modelConfig?.opus_retry_triggers &&
            Object.entries(modelConfig.opus_retry_triggers).map(
              ([key, val]) => (
                <ToggleRow
                  key={key}
                  label={key
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (c) => c.toUpperCase())}
                  checked={val}
                  onChange={(v) =>
                    setModelConfig((prev) => ({
                      ...prev,
                      opus_retry_triggers: {
                        ...prev.opus_retry_triggers,
                        [key]: v,
                      },
                    }))
                  }
                />
              )
            )}
        </div>

        {/* Prompt Versions (display-only) */}
        <div style={subHeadingStyle}>Active Prompt Versions</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {modelConfig?.active_prompt_versions &&
            Object.entries(modelConfig.active_prompt_versions).map(
              ([key, ver]) => (
                <div
                  key={key}
                  style={{
                    background: theme.bg.input,
                    border: `1px solid ${theme.border.subtle}`,
                    borderRadius: 6,
                    padding: "6px 12px",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <span style={{ color: theme.text.muted, fontSize: 13 }}>
                    {key}
                  </span>
                  <span
                    style={{
                      color: theme.text.secondary,
                      fontFamily: theme.font.mono,
                      fontSize: 13,
                    }}
                  >
                    {ver}
                  </span>
                </div>
              )
            )}
        </div>
      </Section>

      {/* ── Section 6: Change History ────────────────────────────── */}
      <Section
        title="Change History"
        description="Recent configuration changes."
        expanded={expanded.history}
        onToggle={() => toggle("history")}
        dirty={false}
        saving={false}
        onSave={() => {}}
        hideFooter
      >
        {audit.length === 0 ? (
          <p style={{ color: theme.text.dim, fontSize: 14 }}>
            No configuration changes recorded yet.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 13,
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  {["Time", "Section", "Field", "Old Value", "New Value"].map(
                    (h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: "left",
                          padding: "8px 10px",
                          color: theme.text.dim,
                          fontWeight: 500,
                          fontSize: 11,
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {audit.slice(0, 50).map((entry, idx) => (
                  <tr
                    key={entry.id || idx}
                    style={{
                      borderBottom: `1px solid ${theme.border.subtle}`,
                    }}
                  >
                    <td
                      style={{
                        padding: "8px 10px",
                        color: theme.text.muted,
                        whiteSpace: "nowrap",
                        fontFamily: theme.font.mono,
                        fontSize: 12,
                      }}
                    >
                      {entry.created_at || "\u2014"}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        color: theme.text.secondary,
                      }}
                    >
                      {entry.section}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        color: theme.text.secondary,
                        fontFamily: theme.font.mono,
                      }}
                    >
                      {entry.field}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        color: theme.accent.red,
                        fontFamily: theme.font.mono,
                        maxWidth: 200,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={entry.old_value}
                    >
                      {entry.old_value || "\u2014"}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        color: theme.accent.green,
                        fontFamily: theme.font.mono,
                        maxWidth: 200,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={entry.new_value}
                    >
                      {entry.new_value || "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}

// ── Exported Component (wrapped in error boundary) ──────────────────────────

export default function AISettingsPage() {
  return (
    <SettingsErrorBoundary>
      <AISettingsPageInner />
    </SettingsErrorBoundary>
  );
}
