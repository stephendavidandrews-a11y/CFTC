import React, { useState, useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import Badge from "../../components/shared/Badge";
import ScoreBar from "../../components/loper/ScoreBar";
import FilterBar from "../../components/loper/FilterBar";
import InlineExpansion from "../../components/loper/InlineExpansion";
import { listRules, listGuidance } from "../../api/loper";

// ── Constants ────────────────────────────────────────────────────────

const ACTION_COLORS = {
  Rescind: { bg: "#450a0a", text: "#f87171" },
  Amend: { bg: "#422006", text: "#fbbf24" },
  Reinterpret: { bg: "#2e1065", text: "#a78bfa" },
  Defend: { bg: "#172554", text: "#60a5fa" },
  "Manual review": { bg: "#1f2937", text: "#9ca3af" },
  Deprioritize: { bg: "#1f2937", text: "#6b7280" },
  Withdraw: { bg: "#450a0a", text: "#f87171" },
  Codify: { bg: "#14532d", text: "#4ade80" },
  Narrow: { bg: "#422006", text: "#fbbf24" },
  Maintain: { bg: "#172554", text: "#60a5fa" },
};

const VALIDATION_COLORS = {
  confirmed: { bg: "#14532d", text: "#4ade80" },
  upgraded: { bg: "#052e16", text: "#22c55e" },
  downgraded: { bg: "#422006", text: "#fbbf24" },
  false_positive: { bg: "#1f2937", text: "#6b7280" },
};

// ── Page styles ──────────────────────────────────────────────────────

const headerCell = {
  padding: "10px 12px", fontSize: 11, fontWeight: 700,
  color: theme.text.faint, textTransform: "uppercase",
  letterSpacing: "0.05em", borderBottom: `1px solid ${theme.border.default}`,
  textAlign: "left", whiteSpace: "nowrap", userSelect: "none",
};

const bodyCell = {
  padding: "10px 12px", fontSize: 13, color: theme.text.secondary,
  borderBottom: `1px solid ${theme.border.subtle}`,
  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
};

function pageBtnStyle(disabled) {
  return {
    padding: "5px 10px", borderRadius: 5, fontSize: 12, fontWeight: 500,
    background: "transparent", color: disabled ? theme.text.ghost : theme.text.dim,
    border: `1px solid ${theme.border.subtle}`, cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.4 : 1,
  };
}

// ── Rule columns ─────────────────────────────────────────────────────

const RULE_COLUMNS = [
  { key: "fr_citation", label: "Citation", width: "10%", sortable: true },
  { key: "title", label: "Title", width: "22%", sortable: true },
  { key: "publication_date", label: "Date", width: "7%", sortable: true },
  { key: "composite_score", label: "Composite", width: "10%", sortable: true },
  { key: "action_category", label: "Action", width: "8%", sortable: true },
  { key: "dim1_composite", label: "Loper", width: "8%", sortable: true },
  { key: "dim2_composite", label: "Maj. Q.", width: "7%", sortable: true },
  { key: "dim4_composite", label: "Procedural", width: "8%", sortable: true },
  { key: "dim5_composite", label: "Nondel.", width: "7%", sortable: true },
  { key: "s2_validation", label: "S2 Validation", width: "8%", sortable: false },
  { key: "legal_theory_tags", label: "Theories", width: "5%", sortable: false },
];

const GUIDANCE_COLUMNS = [
  { key: "letter_number", label: "Letter #", width: "10%", sortable: false },
  { key: "title", label: "Title", width: "22%", sortable: true },
  { key: "document_type", label: "Type", width: "8%", sortable: true },
  { key: "publication_date", label: "Date", width: "7%", sortable: true },
  { key: "composite_score", label: "Composite", width: "10%", sortable: true },
  { key: "action_category", label: "Action", width: "8%", sortable: true },
  { key: "g1_composite", label: "Interp.", width: "7%", sortable: true },
  { key: "g2_composite", label: "Scope", width: "7%", sortable: true },
  { key: "g4_composite", label: "Force", width: "7%", sortable: true },
  { key: "g5_composite", label: "Deleg.", width: "7%", sortable: true },
  { key: "legal_theory_tags", label: "Theories", width: "7%", sortable: false },
];

// ── Main Component ───────────────────────────────────────────────────

export default function LoperExplorerPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Determine mode from URL
  const isGuidance = location.pathname.includes("/guidance");
  const mode = isGuidance ? "guidance" : "rules";

  // State
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [sortKey, setSortKey] = useState("composite_score");
  const [sortOrder, setSortOrder] = useState("desc");
  const [filters, setFilters] = useState({});
  const [expandedRow, setExpandedRow] = useState(null);

  // Parse initial filters from URL search params
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const initial = {};
    for (const [k, v] of params.entries()) {
      initial[k] = v;
    }
    if (Object.keys(initial).length > 0) {
      setFilters(initial);
    }
  }, []); // eslint-disable-line

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        ...filters,
        sort: sortKey,
        order: sortOrder,
        page,
        page_size: pageSize,
      };
      const result = mode === "rules"
        ? await listRules(params)
        : await listGuidance(params);
      setData(result.items || []);
      setTotal(result.total || 0);
    } catch (e) {
      setError(e.message);
      setData([]);
      setTotal(0);
    }
    setLoading(false);
  }, [mode, filters, sortKey, sortOrder, page, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Sort handler
  const handleSort = (key) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
    setPage(1);
  };

  // Filter change
  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setPage(1);
    setExpandedRow(null);
  };

  // Toggle row expansion
  const handleRowClick = (row) => {
    const key = mode === "rules" ? row.fr_citation : row.doc_id;
    setExpandedRow(expandedRow === key ? null : key);
  };

  // Computed
  const columns = mode === "rules" ? RULE_COLUMNS : GUIDANCE_COLUMNS;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Summary stats
  const stats = useMemo(() => {
    if (mode !== "rules" || data.length === 0) return null;
    const withS2 = data.filter((r) => r.s2_summary && r.s2_summary.modules_confirmed > 0);
    const avgComposite = data.reduce((s, r) => s + (r.composite_score || 0), 0) / data.length;
    return { withS2: withS2.length, avgComposite };
  }, [data, mode]);

  // ── Render cell ──────────────────────────────────────────────────

  const renderCell = (col, row) => {
    const v = row[col.key];

    switch (col.key) {
      case "fr_citation":
        return (
          <span style={{ fontFamily: theme.font.mono, fontSize: 11, color: theme.accent.blueLight }}>
            {v || "—"}
          </span>
        );

      case "title":
        return (
          <span title={v} style={{ maxWidth: 280, display: "inline-block", overflow: "hidden", textOverflow: "ellipsis" }}>
            {v ? (v.length > 65 ? v.substring(0, 65) + "..." : v) : "—"}
          </span>
        );

      case "composite_score":
        return <ScoreBar value={v} width={80} height={12} />;

      case "dim1_composite":
      case "dim2_composite":
      case "dim3_composite":
      case "dim4_composite":
      case "dim5_composite":
      case "g1_composite":
      case "g2_composite":
      case "g3_composite":
      case "g4_composite":
      case "g5_composite":
        return <ScoreBar value={v} width={60} height={10} showValue={false} />;

      case "action_category": {
        const ac = ACTION_COLORS[v] || ACTION_COLORS["Manual review"];
        return <Badge bg={ac.bg} text={ac.text} label={v || "—"} />;
      }

      case "comment_multiplier":
        return v != null ? `${v.toFixed(2)}x` : "—";

      case "publication_date":
        return v ? v.substring(0, 10) : "—";

      case "document_type":
        return <Badge bg="#172554" text={theme.accent.blueLight} label={v || "—"} />;

      case "s2_validation": {
        const summary = row.s2_summary;
        if (!summary || summary.modules_activated === 0) {
          return <span style={{ color: theme.text.ghost, fontSize: 11 }}>—</span>;
        }
        const confirmed = summary.modules_confirmed;
        const total = summary.modules_activated;
        if (confirmed > 0) {
          return (
            <Badge
              bg={VALIDATION_COLORS.confirmed.bg}
              text={VALIDATION_COLORS.confirmed.text}
              label={`${confirmed}/${total}`}
            />
          );
        }
        return (
          <Badge
            bg={VALIDATION_COLORS.downgraded.bg}
            text={VALIDATION_COLORS.downgraded.text}
            label={`0/${total}`}
          />
        );
      }

      case "legal_theory_tags": {
        const tags = v || [];
        if (tags.length === 0) return <span style={{ color: theme.text.ghost }}>—</span>;
        return (
          <span title={tags.join(", ")} style={{ fontSize: 11, color: theme.accent.purple }}>
            {tags.length} tag{tags.length !== 1 ? "s" : ""}
          </span>
        );
      }

      case "letter_number":
        return (
          <span style={{ fontFamily: theme.font.mono, fontSize: 11, color: theme.text.muted }}>
            {v || "—"}
          </span>
        );

      default:
        return v ?? "—";
    }
  };

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1600 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
            Vulnerability Explorer
          </h1>
          <p style={{ fontSize: 12, color: theme.text.dim, margin: "4px 0 0" }}>
            Browse and filter {mode === "rules" ? "385 Final Rules" : "1,117 Guidance Documents"} scored for legal vulnerability
          </p>
        </div>

        {/* Rules / Guidance toggle */}
        <div style={{ display: "flex", gap: 2, background: theme.bg.card, borderRadius: 8, border: `1px solid ${theme.border.default}`, padding: 3 }}>
          <button
            onClick={() => { navigate("/loper/rules"); setFilters({}); setPage(1); setExpandedRow(null); }}
            style={{
              padding: "6px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
              background: mode === "rules" ? "rgba(59,130,246,0.15)" : "transparent",
              color: mode === "rules" ? theme.accent.blueLight : theme.text.dim,
              border: mode === "rules" ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
            }}
          >
            Rules ({total > 0 && mode === "rules" ? total : "385"})
          </button>
          <button
            onClick={() => { navigate("/loper/guidance"); setFilters({}); setPage(1); setExpandedRow(null); }}
            style={{
              padding: "6px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
              background: mode === "guidance" ? "rgba(59,130,246,0.15)" : "transparent",
              color: mode === "guidance" ? theme.accent.blueLight : theme.text.dim,
              border: mode === "guidance" ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
            }}
          >
            Guidance ({total > 0 && mode === "guidance" ? total : "1,117"})
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar mode={mode} filters={filters} onChange={handleFilterChange} />

      {/* Summary bar */}
      {!loading && data.length > 0 && (
        <div style={{
          display: "flex", alignItems: "center", gap: 16, marginBottom: 12,
          fontSize: 12, color: theme.text.dim,
        }}>
          <span>Showing <strong style={{ color: theme.text.secondary }}>{data.length}</strong> of {total} {mode}</span>
          {stats && (
            <>
              <span style={{ color: theme.border.default }}>|</span>
              <span>Avg composite: <strong style={{ color: theme.text.secondary }}>{stats.avgComposite.toFixed(2)}</strong></span>
              <span style={{ color: theme.border.default }}>|</span>
              <span>
                <strong style={{ color: theme.accent.green }}>{stats.withS2}</strong> with S2 confirmations
              </span>
            </>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: "12px 16px", borderRadius: 8, marginBottom: 16,
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          color: theme.accent.red, fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: "60px 0", color: theme.text.faint, fontSize: 13 }}>
          Loading {mode}...
        </div>
      )}

      {/* Table */}
      {!loading && data.length > 0 && (
        <div style={{
          background: theme.bg.card, borderRadius: 10,
          border: `1px solid ${theme.border.default}`, overflow: "hidden",
        }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: theme.font.family }}>
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      style={{
                        ...headerCell,
                        width: col.width || "auto",
                        cursor: col.sortable ? "pointer" : "default",
                      }}
                      onClick={() => col.sortable && handleSort(col.key)}
                    >
                      {col.label}
                      {sortKey === col.key && (
                        <span style={{ marginLeft: 4 }}>{sortOrder === "asc" ? "▲" : "▼"}</span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row) => {
                  const rowKey = mode === "rules" ? row.fr_citation : row.doc_id;
                  const isExpanded = expandedRow === rowKey;
                  return (
                    <React.Fragment key={rowKey}>
                      <tr
                        onClick={() => handleRowClick(row)}
                        style={{
                          cursor: "pointer",
                          transition: "background 0.1s",
                          background: isExpanded ? "rgba(59,130,246,0.05)" : "transparent",
                        }}
                        onMouseEnter={(e) => {
                          if (!isExpanded) e.currentTarget.style.background = theme.bg.cardHover;
                        }}
                        onMouseLeave={(e) => {
                          if (!isExpanded) e.currentTarget.style.background = "transparent";
                        }}
                      >
                        {columns.map((col) => (
                          <td key={col.key} style={bodyCell}>
                            {renderCell(col, row)}
                          </td>
                        ))}
                      </tr>
                      {isExpanded && (
                        <InlineExpansion rule={row} mode={mode} colSpan={columns.length} />
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "12px 16px", fontSize: 12, color: theme.text.faint,
              borderTop: `1px solid ${theme.border.subtle}`,
            }}>
              <span>
                Page {page} of {totalPages} ({total} total)
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                  style={pageBtnStyle(page <= 1)}
                >
                  ‹ Prev
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let p;
                  if (totalPages <= 7) p = i + 1;
                  else if (page < 5) p = i + 1;
                  else if (page > totalPages - 4) p = totalPages - 6 + i;
                  else p = page - 3 + i;
                  return (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      style={{
                        ...pageBtnStyle(false),
                        background: p === page ? theme.accent.blue : "transparent",
                        color: p === page ? "#fff" : theme.text.faint,
                      }}
                    >
                      {p}
                    </button>
                  );
                })}
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                  style={pageBtnStyle(page >= totalPages)}
                >
                  Next ›
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && data.length === 0 && !error && (
        <div style={{
          textAlign: "center", padding: "60px 0", color: theme.text.faint, fontSize: 13,
          background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
        }}>
          No {mode} match your filters. Try adjusting or clearing filters.
        </div>
      )}
    </div>
  );
}
