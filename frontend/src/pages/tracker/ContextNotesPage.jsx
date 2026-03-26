import React, { useState, useEffect, useCallback } from "react";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, inputStyle } from "../../styles/pageStyles";
import { timeAgo } from "../../utils/dateUtils";
import { listContextNotes, deleteContextNote } from "../../api/tracker";

const CATEGORY_COLORS = {
  people_insight: { bg: "#312e81", text: "#c4b5fd" },
  institutional_knowledge: { bg: "#1e3a5f", text: "#60a5fa" },
  process_note: { bg: "#0c4a6e", text: "#67e8f9" },
  policy_operating_rule: { bg: "#14532d", text: "#4ade80" },
  strategic_context: { bg: "#422006", text: "#fbbf24" },
  culture_climate: { bg: "#431407", text: "#fb923c" },
  relationship_dynamic: { bg: "#1e1b4b", text: "#a78bfa" },
};

const POSTURE_COLORS = {
  factual: { bg: "#1e3a5f", text: "#60a5fa" },
  attributed_view: { bg: "#78350f", text: "#fbbf24" },
  tentative: { bg: "#1f2937", text: "#9ca3af" },
  interpretive: { bg: "#1e1b4b", text: "#a78bfa" },
  sensitive: { bg: "#7f1d1d", text: "#fca5a5" },
};

function Badge({ bg, text, label }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4,
      fontSize: 10, fontWeight: 600, background: bg, color: text,
      textTransform: "uppercase", letterSpacing: "0.04em",
    }}>{label}</span>
  );
}

function formatLabel(s) {
  return (s || "").replace(/_/g, " ");
}

const SAVED_VIEWS = [
  { label: "All Notes", filter: () => true },
  { label: "High Sensitivity", filter: (n) => n.sensitivity === "high" || n.sensitivity === "moderate" },
  { label: "Stale / Expiring", filter: (n) => n.stale_after && new Date(n.stale_after) <= new Date() },
  { label: "Recent", filter: (n) => {
    const d = new Date(n.created_at);
    return d >= new Date(Date.now() - 7 * 86400000);
  }},
];

export default function ContextNotesPage() {
  useEffect(() => { document.title = "Context Notes | Command Center"; }, []);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    search: "", category: "", posture: "", sensitivity: "", durability: "",
  });
  const [expanded, setExpanded] = useState(null);
  const [sortBy, setSortBy] = useState("created_at_desc");
  const [activeView, setActiveView] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filters.search) params.search = filters.search;
      if (filters.category) params.category = filters.category;
      if (filters.posture) params.posture = filters.posture;
      if (filters.sensitivity) params.sensitivity = filters.sensitivity;
      if (filters.durability) params.durability = filters.durability;
      params.limit = 200;
      const [field, dir] = sortBy.includes("_asc")
        ? [sortBy.replace("_asc", ""), "asc"]
        : sortBy.includes("_desc")
          ? [sortBy.replace("_desc", ""), "desc"]
          : [sortBy, "asc"];
      params.sort_by = field;
      params.sort_dir = dir;
      const result = await listContextNotes(params);
      setData(result);
    } catch (e) {
      setError(e.message || "Failed to load context notes");
    } finally {
      setLoading(false);
    }
  }, [filters, sortBy]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFilter = (key, val) => {
    setFilters(prev => ({ ...prev, [key]: val }));
  };

  const items = data?.items || [];
  const filtered = items.filter(SAVED_VIEWS[activeView].filter);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={titleStyle}>Context Notes</div>
      <div style={subtitleStyle}>Operational intelligence, institutional knowledge, and attributed observations</div>

      {/* Filters */}
      <div style={{
        display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap",
        padding: "12px 16px", background: theme.bg.card, borderRadius: 8,
        border: "1px solid " + theme.border.subtle,
      }}>
        <input
          type="text"
          placeholder="Search notes..."
          value={filters.search}
          onChange={e => handleFilter("search", e.target.value)}
          style={{ ...inputStyle, flex: 1, minWidth: 180 }}
        />
        <select value={filters.category} onChange={e => handleFilter("category", e.target.value)}
          style={{ ...inputStyle, minWidth: 0, flex: "none" }}>
          <option value="">All categories</option>
          {Object.keys(CATEGORY_COLORS).map(c => (
            <option key={c} value={c}>{formatLabel(c)}</option>
          ))}
        </select>
        <select value={filters.posture} onChange={e => handleFilter("posture", e.target.value)}
          style={{ ...inputStyle, minWidth: 0, flex: "none" }}>
          <option value="">All postures</option>
          {Object.keys(POSTURE_COLORS).map(p => (
            <option key={p} value={p}>{formatLabel(p)}</option>
          ))}
        </select>
        <select value={filters.sensitivity} onChange={e => handleFilter("sensitivity", e.target.value)}
          style={{ ...inputStyle, minWidth: 0, flex: "none" }}>
          <option value="">All sensitivity</option>
          <option value="low">Low</option>
          <option value="moderate">Moderate</option>
          <option value="high">High</option>
        </select>
        <select value={filters.durability} onChange={e => handleFilter("durability", e.target.value)}
          style={{ ...inputStyle, minWidth: 0, flex: "none" }}>
          <option value="">All durabilities</option>
          <option value="durable">Durable</option>
          <option value="volatile">Volatile</option>
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}
          style={{ ...inputStyle, minWidth: 0, flex: "none" }}>
          <option value="created_at_desc">Newest first</option>
          <option value="created_at_asc">Oldest first</option>
          <option value="sensitivity">By sensitivity</option>
          <option value="category">By category</option>
        </select>
      </div>

      {/* Saved view pills */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {SAVED_VIEWS.map((view, i) => (
          <div
            key={view.label}
            onClick={() => setActiveView(i)}
            style={{
              padding: "5px 14px", borderRadius: 20, fontSize: 12,
              cursor: "pointer", userSelect: "none",
              background: i === activeView ? "#1e3a5f" : theme.bg.input,
              color: i === activeView ? theme.accent.blueLight : theme.text.muted,
              border: `1px solid ${i === activeView ? theme.accent.blue : theme.border.default}`,
              fontWeight: i === activeView ? 600 : 400,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            {view.label}
          </div>
        ))}
      </div>

      {/* Content */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: theme.text.dim }}>Loading...</div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: theme.accent.red }}>{error}</div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: theme.text.faint }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>{"\u2261"}</div>
          <div style={{ fontSize: 14 }}>No context notes yet</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            Context notes will appear here as they are extracted from conversations.
          </div>
        </div>
      )}

      {/* Notes list */}
      {!loading && !error && filtered.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filtered.map(note => {
            const catColor = CATEGORY_COLORS[note.category] || CATEGORY_COLORS.institutional_knowledge;
            const posColor = POSTURE_COLORS[note.posture] || POSTURE_COLORS.factual;
            const isExpanded = expanded === note.id;
            const isStale = note.stale_after && new Date(note.stale_after) <= new Date();

            return (
              <div
                key={note.id}
                onClick={() => setExpanded(isExpanded ? null : note.id)}
                style={{
                  background: theme.bg.card,
                  border: "1px solid " + theme.border.subtle,
                  borderRadius: 8,
                  padding: "12px 16px",
                  cursor: "pointer",
                  transition: "border-color 0.15s",
                }}
              >
                {/* Header row */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <Badge bg={catColor.bg} text={catColor.text} label={formatLabel(note.category)} />
                  <Badge bg={posColor.bg} text={posColor.text} label={formatLabel(note.posture)} />
                  {note.sensitivity !== "low" && (
                    <Badge bg="#7f1d1d" text="#fca5a5" label={note.sensitivity} />
                  )}
                  {isStale && (
                    <Badge bg="#78350f" text="#fbbf24" label="stale" />
                  )}
                  <span style={{ flex: 1 }} />
                  {note.speaker_attribution && (
                    <span style={{ fontSize: 10, color: theme.text.muted, fontStyle: "italic" }}>
                      {note.speaker_attribution}
                    </span>
                  )}
                  {note.ai_confidence != null && (
                    <span style={{ fontSize: 10, color: theme.text.faint }}>
                      {(note.ai_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  <span style={{ fontSize: 10, color: theme.text.faint }}>
                    {timeAgo(note.created_at)}
                  </span>
                </div>

                {/* Title */}
                <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>
                  {note.title}
                </div>

                {/* Body preview */}
                {!isExpanded && (
                  <div style={{
                    fontSize: 12, color: theme.text.dim, lineHeight: 1.5,
                    overflow: "hidden", textOverflow: "ellipsis",
                    display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                  }}>
                    {note.body}
                  </div>
                )}

                {/* Expanded detail */}
                {isExpanded && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: theme.text.secondary, lineHeight: 1.6, marginBottom: 12 }}>
                      {note.body}
                    </div>

                    {note.speaker_attribution && (
                      <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 6 }}>
                        <strong>Speaker:</strong> {note.speaker_attribution}
                      </div>
                    )}

                    {note.source_excerpt && (
                      <div style={{
                        borderLeft: "3px solid " + theme.accent.blue,
                        paddingLeft: 12, marginBottom: 8,
                        fontStyle: "italic", fontSize: 12, color: theme.text.muted, lineHeight: 1.6,
                      }}>
                        {"\u201c"}{note.source_excerpt}{"\u201d"}
                      </div>
                    )}

                    {/* Linked entities */}
                    {note.links && note.links.length > 0 && (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                        {note.links.map((link, i) => (
                          <span key={i} style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            padding: "2px 8px", borderRadius: 4, fontSize: 10,
                            background: "rgba(59,130,246,0.1)", color: theme.accent.blueLight,
                            border: "1px solid rgba(59,130,246,0.2)",
                          }}>
                            <span style={{ textTransform: "capitalize" }}>{link.entity_type}</span>
                            {link.entity_name && <span>· {link.entity_name}</span>}
                            <span style={{ color: theme.text.faint }}>({link.relationship_role})</span>
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Metadata */}
                    <div style={{
                      display: "flex", gap: 16, marginTop: 10, fontSize: 10, color: theme.text.faint,
                    }}>
                      <span>Durability: {note.durability}</span>
                      <span>Source: {note.source}</span>
                      {note.ai_confidence != null && <span>Confidence: {(note.ai_confidence * 100).toFixed(0)}%</span>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Footer count */}
      {!loading && !error && filtered.length > 0 && (
        <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 8 }}>
          Showing {filtered.length} of {data?.total || 0} notes
        </div>
      )}
    </div>
  );
}
