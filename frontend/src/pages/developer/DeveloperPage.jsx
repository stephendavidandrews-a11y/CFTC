import React, { useMemo } from "react";
import { Tabs } from "../../components/radix/StyledTabs";
import theme from "../../styles/theme";
import manifest from "../../data/schema-manifest.json";

/* ═══════════════════════════════════════════════════════════════════════
   CFTC Command Center — Developer Console
   /developer — Auto-generated schema reference, ERD, and system docs.
   Data sourced from schema-manifest.json (build-time generated).
   Run:  python3 scripts/generate-schema-manifest.py
   ═══════════════════════════════════════════════════════════════════════ */

const SCHEMA = manifest.tables;
const RELATIONSHIPS = manifest.relationships;
const ENUMS = manifest.enums;
const SERVICES_META = manifest.services;
const GENERATED_AT = manifest.generated_at;

// ── Tab definitions ──────────────────────────────────────────────────
const TABS = [
  { key: "schema", label: "Schema & ERD" },
  { key: "api", label: "API Reference" },
  { key: "enums", label: "Enums & Lookups" },
  { key: "services", label: "Services" },
];

// ── Colors for services ──────────────────────────────────────────────
const SVC = {
  tracker: { color: "#3b82f6", bg: "rgba(59,130,246,0.08)",  border: "rgba(59,130,246,0.25)", label: "Tracker" },
  ai:      { color: "#a855f7", bg: "rgba(168,85,247,0.08)",  border: "rgba(168,85,247,0.25)", label: "AI" },
};

// ── Field type badge colors ──────────────────────────────────────────
const TYPE_COLORS = {
  PK:   { bg: "#422006", text: "#fbbf24" },
  FK:   { bg: "#172554", text: "#60a5fa" },
  ENUM: { bg: "#1e1b4b", text: "#a78bfa" },
  IDX:  { bg: "#0c4a6e", text: "#38bdf8" },
  TS:   { bg: "#14532d", text: "#4ade80" },
  BOOL: { bg: "#1f2937", text: "#94a3b8" },
  JSON: { bg: "#1f2937", text: "#d4d4d8" },
};

// ── API REFERENCE (static — not in schema files) ─────────────────────
const API_ENDPOINTS = [
  // ── Tracker: Dashboard ──
  { method: "GET",    path: "/tracker/dashboard",            desc: "Dashboard overview — counts, deadlines, recent activity" },
  { method: "GET",    path: "/tracker/dashboard/stats",      desc: "Table row counts for all entities" },
  // ── Tracker: Matters ──
  { method: "GET",    path: "/tracker/matters",              desc: "List matters (filters: status, priority, type, assigned_to, search)" },
  { method: "POST",   path: "/tracker/matters",              desc: "Create a new matter" },
  { method: "GET",    path: "/tracker/matters/:id",          desc: "Matter detail with people, orgs, tasks" },
  { method: "PUT",    path: "/tracker/matters/:id",          desc: "Update matter fields" },
  { method: "DELETE", path: "/tracker/matters/:id",          desc: "Delete matter (cascades)" },
  { method: "POST",   path: "/tracker/matters/:id/people",   desc: "Add person to matter" },
  { method: "DELETE", path: "/tracker/matters/:id/people/:pid", desc: "Remove person from matter" },
  { method: "POST",   path: "/tracker/matters/:id/orgs",     desc: "Add org to matter" },
  { method: "POST",   path: "/tracker/matters/:id/updates",  desc: "Add timeline update" },
  // ── Tracker: Tasks ──
  { method: "GET",    path: "/tracker/tasks",                desc: "List tasks (filters: status, priority, matter_id, assigned_to)" },
  { method: "POST",   path: "/tracker/tasks",                desc: "Create task" },
  { method: "GET",    path: "/tracker/tasks/:id",            desc: "Task detail" },
  { method: "PUT",    path: "/tracker/tasks/:id",            desc: "Update task" },
  { method: "DELETE", path: "/tracker/tasks/:id",            desc: "Delete task" },
  // ── Tracker: People ──
  { method: "GET",    path: "/tracker/people",               desc: "List people (filters: person_type, org, search)" },
  { method: "POST",   path: "/tracker/people",               desc: "Create person" },
  { method: "GET",    path: "/tracker/people/:id",           desc: "Person detail with matters, tasks, meetings" },
  { method: "PUT",    path: "/tracker/people/:id",           desc: "Update person" },
  // ── Tracker: Organizations ──
  { method: "GET",    path: "/tracker/organizations",        desc: "List organizations" },
  { method: "POST",   path: "/tracker/organizations",        desc: "Create organization" },
  { method: "GET",    path: "/tracker/organizations/:id",    desc: "Org detail with people, matters" },
  { method: "PUT",    path: "/tracker/organizations/:id",    desc: "Update org" },
  // ── Tracker: Meetings ──
  { method: "GET",    path: "/tracker/meetings",             desc: "List meetings (filters: date range, meeting_type)" },
  { method: "POST",   path: "/tracker/meetings",             desc: "Create meeting" },
  { method: "GET",    path: "/tracker/meetings/:id",         desc: "Meeting detail with participants, matters" },
  { method: "PUT",    path: "/tracker/meetings/:id",         desc: "Update meeting" },
  // ── Tracker: Documents & Decisions ──
  { method: "GET",    path: "/tracker/documents",            desc: "List documents (filters: matter_id, doc_type, status)" },
  { method: "POST",   path: "/tracker/documents",            desc: "Create/upload document" },
  { method: "GET",    path: "/tracker/decisions",            desc: "List decisions" },
  { method: "POST",   path: "/tracker/decisions",            desc: "Create decision" },
  // ── Tracker: Lookups ──
  { method: "GET",    path: "/tracker/lookups/enums/:name",  desc: "Enum values for dropdown fields" },
  { method: "GET",    path: "/tracker/lookups/enums",        desc: "All enum values (full dict)" },
  // ── AI: Communications ──
  { method: "GET",    path: "/ai/api/communications",                        desc: "List communications (filters: status, source_type, search)" },
  { method: "GET",    path: "/ai/api/communications/:id",                    desc: "Communication detail with transcript, participants, entities" },
  { method: "GET",    path: "/ai/api/communications/:id/transcript",         desc: "Full transcript for communication" },
  { method: "GET",    path: "/ai/api/communications/:id/audio",              desc: "Audio file(s) for communication" },
  { method: "GET",    path: "/ai/api/communications/:id/messages",           desc: "Email messages for communication" },
  { method: "GET",    path: "/ai/api/communications/:id/artifacts",          desc: "Attachments/artifacts for communication" },
  { method: "POST",   path: "/ai/api/communications/audio-upload",           desc: "Ingest audio file for processing" },
  { method: "POST",   path: "/ai/api/communications/email-upload",           desc: "Ingest email for processing" },
  { method: "DELETE", path: "/ai/api/communications/:id",                    desc: "Delete communication and all related data" },
  { method: "POST",   path: "/ai/api/communications/:id/archive",            desc: "Archive a completed communication" },
  { method: "POST",   path: "/ai/api/communications/:id/unarchive",          desc: "Unarchive a communication" },
  { method: "POST",   path: "/ai/api/communications/:id/retry",              desc: "Retry failed processing" },
  // ── AI: Bundle Review ──
  { method: "POST",   path: "/ai/api/bundle-review/:id/create-bundle",       desc: "Create new review bundle for communication" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/edit-bundle",         desc: "Edit bundle routing (target matter, type)" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/merge-bundles",       desc: "Merge two bundles into one" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/accept-bundle",       desc: "Accept bundle for writeback" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/reject-bundle",       desc: "Reject bundle" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/accept-all",          desc: "Accept all proposed bundles" },
  // ── AI: Item Review ──
  { method: "POST",   path: "/ai/api/bundle-review/:id/add-item",            desc: "Add new item to a bundle" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/edit-item",           desc: "Edit item proposed data" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/move-item",           desc: "Move item between bundles" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/accept-item",         desc: "Accept individual item" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/reject-item",         desc: "Reject individual item" },
  { method: "POST",   path: "/ai/api/bundle-review/:id/restore-item",        desc: "Restore rejected item to proposed" },
  // ── AI: Entity Review ──
  { method: "POST",   path: "/ai/api/entity-review/:id/confirm-entity",      desc: "Confirm person/org entity mention" },
  { method: "POST",   path: "/ai/api/entity-review/:id/link-entity",         desc: "Link entity to tracker person/org" },
  { method: "POST",   path: "/ai/api/entity-review/:id/edit-entity",         desc: "Edit entity proposed data" },
  { method: "POST",   path: "/ai/api/entity-review/:id/merge-entities",      desc: "Merge duplicate entities" },
  { method: "POST",   path: "/ai/api/entity-review/:id/reject-entity",       desc: "Reject entity mention" },
  // ── AI: Participant Review ──
  { method: "POST",   path: "/ai/api/participant-review/:id/link-speaker",    desc: "Map speaker label to tracker person" },
  { method: "POST",   path: "/ai/api/participant-review/:id/merge-speakers",  desc: "Merge two speaker labels" },
  { method: "POST",   path: "/ai/api/participant-review/:id/unlink-speaker",  desc: "Unlink speaker from person" },
  { method: "POST",   path: "/ai/api/participant-review/:id/skip-speaker",    desc: "Skip speaker mapping" },
  { method: "POST",   path: "/ai/api/participant-review/:id/reject-match",    desc: "Reject voiceprint match suggestion" },
  // ── AI: Speaker Review ──
  { method: "GET",    path: "/ai/api/speaker-review/profiles/list",           desc: "List all voice profiles" },
  { method: "GET",    path: "/ai/api/speaker-review/profiles/:person_id",     desc: "Voice profile for person" },
  { method: "POST",   path: "/ai/api/speaker-review/profiles/:person_id/activate",   desc: "Activate voice profile" },
  { method: "POST",   path: "/ai/api/speaker-review/profiles/:person_id/deactivate", desc: "Deactivate voice profile" },
  // ── AI: Intelligence ──
  { method: "POST",   path: "/ai/api/intelligence/generate",                 desc: "Generate intelligence brief (daily/weekly)" },
  { method: "GET",    path: "/ai/api/intelligence/briefs",                    desc: "List intelligence briefs" },
  { method: "GET",    path: "/ai/api/intelligence/briefs/:id",               desc: "Brief detail" },
  { method: "GET",    path: "/ai/api/intelligence/briefs/by-date/:type/:date", desc: "Briefs by type and date" },
  // ── AI: Meeting Intelligence ──
  { method: "GET",    path: "/ai/api/meeting-intelligence/:meeting_id",       desc: "Meeting intelligence for a tracker meeting" },
  // ── AI: Events, Config, Telemetry, Health ──
  { method: "GET",    path: "/ai/api/events/stream",                          desc: "SSE stream for real-time pipeline events" },
  { method: "PUT",    path: "/ai/api/config/:section",                        desc: "Update AI policy/config section" },
  { method: "GET",    path: "/ai/api/telemetry/summary",                      desc: "LLM usage and cost summary" },
  { method: "POST",   path: "/ai/api/telemetry/page-visit",                   desc: "Track page visit analytics" },
  { method: "GET",    path: "/ai/api/health",                                 desc: "AI service health check" },
  // ── Tracker: Context Notes (missing from original) ──
  { method: "GET",    path: "/tracker/context-notes",                          desc: "List context notes (filters: entity, category, stale)" },
  { method: "POST",   path: "/tracker/context-notes",                          desc: "Create context note" },
  { method: "GET",    path: "/tracker/context-notes/:id",                      desc: "Context note detail with entity links" },
  { method: "PUT",    path: "/tracker/context-notes/:id",                      desc: "Update context note" },
  { method: "DELETE", path: "/tracker/context-notes/:id",                      desc: "Delete context note" },
  { method: "POST",   path: "/tracker/context-notes/:id/links",               desc: "Add entity link to note" },
  { method: "DELETE", path: "/tracker/context-notes/:id/links/:link_id",      desc: "Remove entity link from note" },
  { method: "GET",    path: "/tracker/context-notes/by-entity/:type/:id",     desc: "Notes linked to a specific entity" },
  // ── Tracker: Batch (missing from original) ──
  { method: "POST",   path: "/tracker/batch",                                  desc: "Atomic batch write (insert/update/delete with idempotency)" },
  // ── Tracker: Schema Version (missing from original) ──
  { method: "GET",    path: "/tracker/schema-version/version",                 desc: "Current schema version" },
  { method: "GET",    path: "/tracker/schema-version/tables/:name/columns",    desc: "Column metadata for a table (dynamic UI)" },
];


// ═══════════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════

function TagBadge({ tag }) {
  const c = TYPE_COLORS[tag] || { bg: "#1f2937", text: "#94a3b8" };
  return (
    <span style={{
      display: "inline-block", fontSize: 9, fontWeight: 700, fontFamily: theme.font.mono,
      padding: "1px 5px", borderRadius: 3, background: c.bg, color: c.text,
      letterSpacing: "0.03em", lineHeight: "16px",
    }}>{tag}</span>
  );
}

function ServiceBadge({ service }) {
  const s = SVC[service];
  if (!s) return null;
  return (
    <span style={{
      display: "inline-block", fontSize: 9, fontWeight: 700,
      padding: "2px 7px", borderRadius: 4, background: s.bg, color: s.color,
      border: `1px solid ${s.border}`, letterSpacing: "0.04em",
    }}>{s.label}</span>
  );
}

function MethodBadge({ method }) {
  const colors = {
    GET:    { bg: "#14532d", text: "#4ade80" },
    POST:   { bg: "#172554", text: "#60a5fa" },
    PUT:    { bg: "#422006", text: "#fbbf24" },
    PATCH:  { bg: "#3b1f06", text: "#fb923c" },
    DELETE: { bg: "#450a0a", text: "#f87171" },
  };
  const c = colors[method] || colors.GET;
  return (
    <span style={{
      display: "inline-block", fontSize: 10, fontWeight: 700, fontFamily: theme.font.mono,
      padding: "2px 8px", borderRadius: 4, background: c.bg, color: c.text,
      minWidth: 52, textAlign: "center",
    }}>{method}</span>
  );
}


// ── Table Card (ERD node) ────────────────────────────────────────────

function TableCard({ table, isExpanded, onToggle, relCount }) {
  const svc = SVC[table.service] || SVC.tracker;
  const pkFields = table.fields.filter(f => f.tags.includes("PK"));
  const fkFields = table.fields.filter(f => f.tags.includes("FK"));
  const enumFields = table.fields.filter(f => f.tags.includes("ENUM"));

  return (
    <div style={{
      background: theme.bg.card,
      border: `1px solid ${isExpanded ? svc.border : theme.border.default}`,
      borderRadius: 8, overflow: "hidden",
      transition: "border-color 0.15s ease",
    }}>
      <div onClick={onToggle} style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 16px", cursor: "pointer",
        borderBottom: isExpanded ? `1px solid ${theme.border.subtle}` : "none",
        background: isExpanded ? "rgba(255,255,255,0.02)" : "transparent",
      }}>
        <span style={{
          fontSize: 11, color: theme.text.faint, width: 16, textAlign: "center",
          transition: "transform 0.15s ease",
          transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
        }}>{"\u25b8"}</span>
        <span style={{
          fontFamily: theme.font.mono, fontSize: 13, fontWeight: 700,
          color: svc.color, flex: 1,
        }}>{table.name}</span>
        <span style={{ fontSize: 10, color: theme.text.faint, marginRight: 6 }}>
          {table.fields.length} cols
        </span>
        {relCount > 0 && (
          <span style={{ fontSize: 10, color: theme.text.faint }}>
            {relCount} rel{relCount !== 1 ? "s" : ""}
          </span>
        )}
        <ServiceBadge service={table.service} />
      </div>

      {isExpanded && (
        <div style={{ padding: "10px 16px 0 42px" }}>
          <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
            {pkFields.length > 0 && <span style={{ fontSize: 10, color: "#fbbf24" }}>{"\u25cf"} {pkFields.length} PK</span>}
            {fkFields.length > 0 && <span style={{ fontSize: 10, color: "#60a5fa" }}>{"\u25cf"} {fkFields.length} FK</span>}
            {enumFields.length > 0 && <span style={{ fontSize: 10, color: "#a78bfa" }}>{"\u25cf"} {enumFields.length} ENUM</span>}
          </div>
        </div>
      )}

      {isExpanded && (
        <div style={{ padding: "0 16px 12px 16px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${theme.border.subtle}` }}>
                {["Field", "Type", "Tags", "Note"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "6px 8px", color: theme.text.faint, fontSize: 10, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.fields.map((f, i) => (
                <tr key={f.name} style={{
                  borderBottom: i < table.fields.length - 1 ? `1px solid ${theme.border.subtle}` : "none",
                  background: f.tags.includes("PK") ? "rgba(251,191,36,0.03)" : f.tags.includes("FK") ? "rgba(96,165,250,0.03)" : "transparent",
                }}>
                  <td style={{ padding: "5px 8px", fontFamily: theme.font.mono, color: f.tags.includes("PK") ? "#fbbf24" : f.tags.includes("FK") ? "#60a5fa" : theme.text.secondary, fontWeight: f.tags.includes("PK") ? 700 : 400 }}>
                    {f.name}
                  </td>
                  <td style={{ padding: "5px 8px", fontFamily: theme.font.mono, color: theme.text.dim, fontSize: 11 }}>
                    {f.type}
                  </td>
                  <td style={{ padding: "5px 8px" }}>
                    <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                      {f.tags.map(t => <TagBadge key={t} tag={t} />)}
                    </div>
                  </td>
                  <td style={{ padding: "5px 8px", color: theme.text.dim, fontSize: 11, maxWidth: 320 }}>
                    {f.note || ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ── Relationship Diagram ─────────────────────────────────────────────

function RelationshipDiagram({ relationships, filter }) {
  const tableServiceMap = useMemo(() => {
    const m = {};
    SCHEMA.forEach(t => { m[t.name] = t.service; });
    return m;
  }, []);

  const filtered = filter === "all"
    ? relationships
    : relationships.filter(r => tableServiceMap[r.from] === filter || tableServiceMap[r.to] === filter);

  return (
    <div style={{ fontFamily: theme.font.mono, fontSize: 11 }}>
      {filtered.map((r, i) => {
        const fromColor = SVC[tableServiceMap[r.from]]?.color || theme.text.muted;
        const toColor = SVC[tableServiceMap[r.to]]?.color || theme.text.muted;
        return (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "5px 12px", borderBottom: `1px solid ${theme.border.subtle}`,
          }}>
            <span style={{ color: fromColor, fontWeight: 600, minWidth: 260 }}>
              {r.from}<span style={{ color: theme.text.dim, fontWeight: 400 }}>.{r.fromField}</span>
            </span>
            <span style={{ color: theme.text.faint, fontSize: 12 }}>{"\u2192"}</span>
            <span style={{ color: toColor, fontWeight: 600, minWidth: 220 }}>
              {r.to}<span style={{ color: theme.text.dim, fontWeight: 400 }}>.{r.toField}</span>
            </span>
            <span style={{ color: theme.text.faint, fontSize: 10, fontFamily: theme.font.family }}>
              {r.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// TAB PANELS
// ═══════════════════════════════════════════════════════════════════════

function SchemaTab() {
  const [expandedTables, setExpandedTables] = useState(new Set(["matters"]));
  const [serviceFilter, setServiceFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [view, setView] = useState("tables");

  const toggleTable = (name) => {
    setExpandedTables(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const expandAll = () => setExpandedTables(new Set(SCHEMA.map(t => t.name)));
  const collapseAll = () => setExpandedTables(new Set());

  const filtered = useMemo(() => {
    return SCHEMA.filter(t => {
      if (serviceFilter !== "all" && t.service !== serviceFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return t.name.includes(q) || t.fields.some(f => f.name.includes(q));
      }
      return true;
    });
  }, [serviceFilter, search]);

  const relCountMap = useMemo(() => {
    const m = {};
    RELATIONSHIPS.forEach(r => { m[r.from] = (m[r.from] || 0) + 1; });
    return m;
  }, []);

  // Dynamic grouping: tracker tables into core/junction/rulemaking/support/system; intake gets its own groups
  const groups = useMemo(() => {
    const trackerCore = ["organizations", "people", "matters", "tasks", "meetings", "documents", "decisions"];
    const trackerJunction = ["matter_people", "matter_organizations", "meeting_participants", "meeting_matters", "matter_tags", "document_reviewers", "task_dependencies", "matter_dependencies"];
    const trackerRulemaking = ["rulemaking_publication_status", "rulemaking_comment_periods", "rulemaking_cba_tracking"];
    const trackerSupport = ["matter_updates", "task_updates", "document_files", "tags", "context_notes", "context_note_links", "person_profiles"];
    const trackerSystem = ["system_events", "sync_state", "idempotency_keys"];

    const intakePipeline = ["conversations", "audio_files", "transcripts"];
    const intakeSpeakers = ["voice_samples", "speaker_voice_profiles", "speaker_mappings"];

    const groups = [];
    const addGroup = (label, tables) => { if (tables.length) groups.push({ label, tables }); };

    if (serviceFilter === "all" || serviceFilter === "tracker") {
      addGroup("Core Entities", filtered.filter(t => t.service === "tracker" && trackerCore.includes(t.name)));
      addGroup("Junction Tables", filtered.filter(t => t.service === "tracker" && trackerJunction.includes(t.name)));
      addGroup("Rulemaking Extensions", filtered.filter(t => t.service === "tracker" && trackerRulemaking.includes(t.name)));
      addGroup("Support Tables", filtered.filter(t => t.service === "tracker" && trackerSupport.includes(t.name)));
      addGroup("System Tables", filtered.filter(t => t.service === "tracker" && trackerSystem.includes(t.name)));
      // Catch any tracker table not in the above
      const allTrackerKnown = new Set([...trackerCore, ...trackerJunction, ...trackerRulemaking, ...trackerSupport, ...trackerSystem]);
      addGroup("Tracker (Other)", filtered.filter(t => t.service === "tracker" && !allTrackerKnown.has(t.name)));
    }
    if (serviceFilter === "all" || serviceFilter === "ai") {
      const aiPipeline = ["communications", "audio_files", "communication_participants", "transcripts", "communication_entities", "communication_messages", "communication_artifacts"];
      const aiVoice = ["voice_samples", "speaker_voice_profiles", "voiceprint_match_log"];
      const aiExtraction = ["ai_extractions", "review_bundles", "review_bundle_items", "tracker_writebacks"];
      const aiIntelligence = ["digests", "intelligence_briefs", "meeting_intelligence"];
      const aiSystem = ["config_audit_log", "alert_actions", "llm_usage", "commit_batches", "review_action_log"];

      addGroup("AI — Pipeline & Comms", filtered.filter(t => t.service === "ai" && aiPipeline.includes(t.name)));
      addGroup("AI — Voice Intelligence", filtered.filter(t => t.service === "ai" && aiVoice.includes(t.name)));
      addGroup("AI — Extraction & Review", filtered.filter(t => t.service === "ai" && aiExtraction.includes(t.name)));
      addGroup("AI — Intelligence & Reporting", filtered.filter(t => t.service === "ai" && aiIntelligence.includes(t.name)));
      addGroup("AI — System & Audit", filtered.filter(t => t.service === "ai" && aiSystem.includes(t.name)));
      const allAiKnown = new Set([...aiPipeline, ...aiVoice, ...aiExtraction, ...aiIntelligence, ...aiSystem]);
      addGroup("AI (Other)", filtered.filter(t => t.service === "ai" && !allAiKnown.has(t.name)));
    }
    if (serviceFilter === "all" || serviceFilter === "intake") {
      addGroup("Intake — Pipeline & Transcripts", filtered.filter(t => t.service === "intake" && intakePipeline.includes(t.name)));
      addGroup("Intake — Speaker Identity", filtered.filter(t => t.service === "intake" && intakeSpeakers.includes(t.name)));
      // Catch any intake table not in the above
      const allIntakeKnown = new Set([...intakePipeline, ...intakeSpeakers]);
      addGroup("Intake (Other)", filtered.filter(t => t.service === "intake" && !allIntakeKnown.has(t.name)));
    }
    return groups;
  }, [filtered, serviceFilter]);

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        padding: "14px 0", borderBottom: `1px solid ${theme.border.subtle}`, marginBottom: 16,
      }}>
        <div style={{ display: "flex", background: theme.bg.input, borderRadius: 6, border: `1px solid ${theme.border.default}`, overflow: "hidden" }}>
          {["tables", "relationships"].map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding: "6px 14px", fontSize: 11, fontWeight: 600, border: "none", cursor: "pointer",
              background: view === v ? "rgba(59,130,246,0.15)" : "transparent",
              color: view === v ? theme.accent.blueLight : theme.text.dim,
            }}>{v === "tables" ? "Tables" : "Relationships"}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[{ key: "all", label: "All", color: theme.text.muted }].concat(
            Object.entries(SVC).map(([k, v]) => ({ key: k, label: v.label, color: v.color }))
          ).map(s => (
            <button key={s.key} onClick={() => setServiceFilter(s.key)} style={{
              padding: "5px 10px", fontSize: 10, fontWeight: 600, border: "none", cursor: "pointer",
              borderRadius: 4, letterSpacing: "0.03em",
              background: serviceFilter === s.key ? (SVC[s.key]?.bg || "rgba(255,255,255,0.08)") : "transparent",
              color: serviceFilter === s.key ? s.color : theme.text.dim,
            }}>{s.label}</button>
          ))}
        </div>
        <input
          placeholder="Search tables or fields..."
          value={search} onChange={e => setSearch(e.target.value)}
          style={{
            background: theme.bg.input, border: `1px solid ${theme.border.default}`, borderRadius: 6,
            padding: "6px 12px", color: theme.text.secondary, fontSize: 12,
            fontFamily: theme.font.mono, outline: "none", width: 220,
          }}
        />
        {view === "tables" && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button onClick={expandAll} style={{ padding: "5px 10px", fontSize: 10, fontWeight: 600, border: `1px solid ${theme.border.default}`, borderRadius: 4, background: "transparent", color: theme.text.dim, cursor: "pointer" }}>Expand all</button>
            <button onClick={collapseAll} style={{ padding: "5px 10px", fontSize: 10, fontWeight: 600, border: `1px solid ${theme.border.default}`, borderRadius: 4, background: "transparent", color: theme.text.dim, cursor: "pointer" }}>Collapse all</button>
          </div>
        )}
      </div>

      {/* Summary strip */}
      <div style={{
        display: "flex", gap: 24, marginBottom: 20, padding: "10px 16px",
        background: "rgba(255,255,255,0.02)", borderRadius: 6, border: `1px solid ${theme.border.subtle}`,
        flexWrap: "wrap", alignItems: "center",
      }}>
        <span style={{ fontSize: 11, color: theme.text.muted }}><strong style={{ color: theme.text.primary }}>{filtered.length}</strong> tables</span>
        <span style={{ fontSize: 11, color: theme.text.muted }}><strong style={{ color: theme.text.primary }}>{filtered.reduce((n, t) => n + t.fields.length, 0)}</strong> columns</span>
        <span style={{ fontSize: 11, color: theme.text.muted }}><strong style={{ color: theme.text.primary }}>{RELATIONSHIPS.length}</strong> relationships</span>
        {Object.entries(SVC).map(([k, v]) => (
          <span key={k} style={{ fontSize: 11, color: v.color }}>{v.label}: {SCHEMA.filter(t => t.service === k).length}</span>
        ))}
        <span style={{ fontSize: 10, color: theme.text.ghost, marginLeft: "auto", fontFamily: theme.font.mono }}>
          generated {GENERATED_AT ? new Date(GENERATED_AT).toLocaleDateString() : "unknown"}
        </span>
      </div>

      {/* Content */}
      {view === "tables" ? (
        <div>
          {groups.map(g => (
            <div key={g.label} style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.08em", padding: "0 4px 8px" }}>
                {g.label} ({g.tables.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {g.tables.map(t => (
                  <TableCard key={t.name} table={t} isExpanded={expandedTables.has(t.name)} onToggle={() => toggleTable(t.name)} relCount={relCountMap[t.name] || 0} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: `1px solid ${theme.border.subtle}`, display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>Foreign Key Relationships</span>
            <span style={{ fontSize: 10, color: theme.text.faint }}>{RELATIONSHIPS.length} total</span>
          </div>
          <RelationshipDiagram relationships={RELATIONSHIPS} filter={serviceFilter} />
        </div>
      )}
    </div>
  );
}


function EnumsTab() {
  const enumKeys = Object.keys(ENUMS);
  const [selected, setSelected] = useState(enumKeys[0] || "");

  return (
    <div style={{ display: "flex", gap: 20, minHeight: 500 }}>
      <div style={{ width: 240, flexShrink: 0, background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, overflow: "auto" }}>
        <div style={{ padding: "10px 14px", borderBottom: `1px solid ${theme.border.subtle}`, fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Enum Fields ({enumKeys.length})
        </div>
        {enumKeys.map(k => (
          <button key={k} onClick={() => setSelected(k)} style={{
            display: "block", width: "100%", textAlign: "left", padding: "8px 14px", fontSize: 12, fontFamily: theme.font.mono,
            border: "none", cursor: "pointer",
            background: selected === k ? "rgba(59,130,246,0.1)" : "transparent",
            color: selected === k ? theme.accent.blueLight : theme.text.dim,
            fontWeight: selected === k ? 600 : 400,
          }}>{k}</button>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {selected && ENUMS[selected] && (
          <div style={{ background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${theme.border.subtle}`, display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontFamily: theme.font.mono, fontSize: 14, fontWeight: 700, color: theme.accent.purple }}>{selected}</span>
              <span style={{ fontSize: 10, color: theme.text.faint }}>{ENUMS[selected].length} values</span>
            </div>
            <div style={{ padding: "12px 16px" }}>
              {ENUMS[selected].map((v, i) => (
                <div key={v} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 8px", borderBottom: i < ENUMS[selected].length - 1 ? `1px solid ${theme.border.subtle}` : "none" }}>
                  <span style={{ width: 20, height: 20, borderRadius: 4, background: "rgba(167,139,250,0.1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: theme.accent.purple, fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                  <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.secondary }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


function ApiTab() {
  const [methodFilter, setMethodFilter] = useState("all");
  const [serviceFilter, setServiceFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = API_ENDPOINTS.filter(e => {
    if (methodFilter !== "all" && e.method !== methodFilter) return false;
    if (serviceFilter !== "all") {
      if (serviceFilter === "tracker" && !e.path.startsWith("/tracker/")) return false;
      if (serviceFilter === "ai" && !e.path.startsWith("/ai/")) return false;
      if (serviceFilter === "intake" && !e.path.startsWith("/intake/")) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      return e.path.toLowerCase().includes(q) || e.desc.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", padding: "14px 0", borderBottom: `1px solid ${theme.border.subtle}`, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 4 }}>
          {["all", "GET", "POST", "PUT", "PATCH", "DELETE"].map(m => (
            <button key={m} onClick={() => setMethodFilter(m)} style={{
              padding: "5px 10px", fontSize: 10, fontWeight: 600, border: "none", borderRadius: 4, cursor: "pointer",
              background: methodFilter === m ? "rgba(255,255,255,0.08)" : "transparent",
              color: methodFilter === m ? theme.text.primary : theme.text.dim,
            }}>{m}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[{ key: "all", label: "All", color: theme.text.muted }].concat(
            Object.entries(SVC).map(([k, v]) => ({ key: k, label: v.label, color: v.color }))
          ).map(s => (
            <button key={s.key} onClick={() => setServiceFilter(s.key)} style={{
              padding: "5px 10px", fontSize: 10, fontWeight: 600, border: "none", borderRadius: 4, cursor: "pointer",
              background: serviceFilter === s.key ? (SVC[s.key]?.bg || "rgba(255,255,255,0.08)") : "transparent",
              color: serviceFilter === s.key ? s.color : theme.text.dim,
            }}>{s.label}</button>
          ))}
        </div>
        <input placeholder="Search endpoints..." value={search} onChange={e => setSearch(e.target.value)}
          style={{ background: theme.bg.input, border: `1px solid ${theme.border.default}`, borderRadius: 6, padding: "6px 12px", color: theme.text.secondary, fontSize: 12, fontFamily: theme.font.mono, outline: "none", width: 260 }} />
        <span style={{ fontSize: 11, color: theme.text.faint, marginLeft: "auto" }}>{filtered.length} endpoint{filtered.length !== 1 ? "s" : ""}</span>
      </div>
      <div style={{ background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, overflow: "hidden" }}>
        {filtered.map((e, i) => {
          const svcKey = e.path.startsWith("/ai/") ? "ai" : e.path.startsWith("/intake/") ? "intake" : "tracker";
          const svc = SVC[svcKey];
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 16px", borderBottom: i < filtered.length - 1 ? `1px solid ${theme.border.subtle}` : "none" }}>
              <MethodBadge method={e.method} />
              <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: svc.color, minWidth: 380 }}>{e.path}</span>
              <span style={{ fontSize: 11, color: theme.text.dim, flex: 1 }}>{e.desc}</span>
              <ServiceBadge service={svcKey} />
            </div>
          );
        })}
      </div>
    </div>
  );
}


function ServicesTab() {
  const serviceList = Object.entries(SERVICES_META).map(([key, meta]) => ({ key, ...meta }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ background: theme.bg.card, border: `1px solid ${theme.border.default}`, borderRadius: 8, padding: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 12 }}>System Architecture</div>
        <div style={{
          fontFamily: theme.font.mono, fontSize: 11, color: theme.text.muted,
          lineHeight: 2, whiteSpace: "pre", overflowX: "auto",
          padding: 16, background: theme.bg.app, borderRadius: 6, border: `1px solid ${theme.border.subtle}`,
        }}>
{`\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  cftc.stephenandrews.org (Cloudflare Tunnel \u2192 Mac Mini)               \u2502
\u2502                                                                           \u2502
\u2502  \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510  \u2502
\u2502  \u2502  nginx (port 80)  \u2014 SPA + reverse proxy                          \u2502  \u2502
\u2502  \u2502                                                                   \u2502  \u2502
\u2502  \u2502  /tracker/*     \u2192 Tracker API    :8004   (SQLite: tracker.db)    \u2502  \u2502
\u2502  \u2502  /ai/*          \u2192 AI Layer       :8006   (SQLite: ai.db)         \u2502  \u2502
\u2502  \u2502  /intake/api/*  \u2192 Intake API     :8005   (SQLite: intake.db)     \u2502  \u2502
\u2502  \u2502  /*             \u2192 React SPA      (index.html fallback)           \u2502  \u2502
\u2502  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518  \u2502
\u2502                                                                           \u2502
\u2502  Auth: HTTP Basic  \u00b7  DB: SQLite + WAL  \u00b7  Infra: launchd (Mac Mini)         \u2502
\u2502                                                                           \u2502
\u2502  All services run native on Mac Mini via launchd              \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518

\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
\u2502  cftctools.stephenandrews.org (separate service)                  \u2502
\u2502                                                                           \u2502
\u2502  Analysis, Loper Bright, Pipeline, Work (legacy apps)                    \u2502
\u2502  Shares localhost network for tracker bridge                    \u2502
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518`}
        </div>
      </div>
      {serviceList.map(s => {
        const svc = SVC[s.key] || SVC.tracker;
        return (
          <div key={s.key} style={{ background: theme.bg.card, border: `1px solid ${svc.border}`, borderRadius: 8, padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: svc.color }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: svc.color }}>{svc.label} Service</span>
              <span style={{ fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono }}>:{s.port}</span>
            </div>
            <div style={{ display: "flex", gap: 20, fontSize: 11, color: theme.text.dim }}>
              <span>Database: <strong style={{ color: theme.text.secondary }}>{s.db}</strong></span>
              <span>Tables: <strong style={{ color: theme.text.secondary }}>{s.tables}</strong></span>
              <span>Stack: <strong style={{ color: theme.text.secondary }}>{s.tech}</strong></span>
            </div>
          </div>
        );
      })}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════

export default function DeveloperPage() {

  return (
    <div style={{
      padding: "24px 32px", maxWidth: 1200, margin: "0 auto",
      fontFamily: theme.font.family, color: theme.text.primary,
    }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: "linear-gradient(135deg, #1e3a5f, #3b82f6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 12, fontWeight: 700, color: "#fff",
          }}>D</div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: "-0.02em" }}>
            Developer Console
          </h1>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "3px 8px", borderRadius: 4,
            background: "rgba(245,158,11,0.12)", color: "#f59e0b",
            border: "1px solid rgba(245,158,11,0.25)",
          }}>INTERNAL</span>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "3px 8px", borderRadius: 4,
            background: "rgba(34,197,94,0.08)", color: "#22c55e",
            border: "1px solid rgba(34,197,94,0.2)",
          }}>AUTO-GENERATED</span>
        </div>
        <p style={{ fontSize: 12, color: theme.text.dim, margin: 0 }}>
          System data model, API reference, and service architecture. Schema data auto-generated from source files at build time.
        </p>
      </div>

      {/* Tabs */}
      <Tabs.Root defaultValue="schema">
        <Tabs.List>
          {TABS.map(t => (
            <Tabs.Trigger key={t.key} value={t.key} style={{ padding: "10px 20px", fontSize: 12 }}>
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="schema"><SchemaTab /></Tabs.Content>
        <Tabs.Content value="api"><ApiTab /></Tabs.Content>
        <Tabs.Content value="enums"><EnumsTab /></Tabs.Content>
        <Tabs.Content value="services"><ServicesTab /></Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
