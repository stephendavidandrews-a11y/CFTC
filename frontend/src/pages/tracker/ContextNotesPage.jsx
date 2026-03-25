import React, { useState, useEffect, useCallback } from "react";
import theme from "../../styles/theme";
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

export default function ContextNotesPage() {
  useEffect(() => { document.title = "Context Notes | Command Center"; }, []);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    search: "", category: "", posture: "", sensitivity: "", durability: "",
  });
  const [expanded, setExpanded] = useState(null);

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
      const result = await listContextNotes(params);
      setData(result);
    } catch (e) {
      setError(e.message || "Failed to load context notes");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFilter = (key, val) => {
    setFilters(prev => ({ ...prev, [key]: val }));
  };

  const items = data?.items || [];

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
            Context Notes
          </h1>
          <p style={{ fontSize: 12, color: theme.text.dim, margin: "4px 0 0" }}>
            Operational intelligence, institutional knowledge, and attributed observations
          </p>
        </div>
        {data && (
          <span style={{ fontSize: 12, color: theme.text.faint }}>
            {data.total} note{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

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
          style={{
            flex: 1, minWidth: 180, padding: "6px 10px", borderRadius: 6,
            border: "1px solid " + theme.border.default,
            background: theme.bg.input, color: theme.text.primary, fontSize: 12,
          }}
        />
        <select value={filters.category} onChange={e => handleFilter("category", e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid " + theme.border.default,
            background: theme.bg.input, color: theme.text.primary, fontSize: 11 }}>
          <option value="">All categories</option>
          {Object.keys(CATEGORY_COLORS).map(c => (
            <option key={c} value={c}>{formatLabel(c)}</option>
          ))}
        </select>
        <select value={filters.posture} onChange={e => handleFilter("posture", e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid " + theme.border.default,
            background: theme.bg.input, color: theme.text.primary, fontSize: 11 }}>
          <option value="">All postures</option>
          {Object.keys(POSTURE_COLORS).map(p => (
            <option key={p} value={p}>{formatLabel(p)}</option>
          ))}
        </select>
        <select value={filters.sensitivity} onChange={e => handleFilter("sensitivity", e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid " + theme.border.default,
            background: theme.bg.input, color: theme.text.primary, fontSize: 11 }}>
          <option value="">All sensitivity</option>
          <option value="low">Low</option>
          <option value="moderate">Moderate</option>
          <option value="high">High</option>
        </select>
        <select value={filters.durability} onChange={e => handleFilter("durability", e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid " + theme.border.default,
            background: theme.bg.input, color: theme.text.primary, fontSize: 11 }}>
          <option value="">All durabilities</option>
          <option value="durable">Durable</option>
          <option value="volatile">Volatile</option>
        </select>
      </div>

      {/* Content */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: theme.text.dim }}>Loading...</div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: theme.accent.red }}>{error}</div>
      )}
      {!loading && !error && items.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: theme.text.faint }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>\u2261</div>
          <div style={{ fontSize: 14 }}>No context notes yet</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            Context notes will appear here as they are extracted from conversations.
          </div>
        </div>
      )}

      {/* Notes list */}
      {!loading && !error && items.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map(note => {
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
                  <span style={{ fontSize: 10, color: theme.text.faint }}>
                    {note.created_at?.slice(0, 10)}
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
                        \u201c{note.source_excerpt}\u201d
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
    </div>
  );
}
