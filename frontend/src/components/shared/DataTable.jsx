import React, { useState, useMemo } from "react";
import theme from "../../styles/theme";

/**
 * Sortable, paginated data table.
 *
 * Props:
 *  columns: [{ key, label, width?, render?, sortable? }]
 *  data: array of row objects
 *  onRowClick: (row) => void
 *  pageSize: number (default 25)
 *  emptyMessage: string
 */
export default function DataTable({
  columns = [],
  data = [],
  onRowClick,
  pageSize = 25,
  emptyMessage = "No data available",
}) {
  const [sortKey, setSortKey] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return sortAsc ? av - bv : bv - av;
      const sa = String(av).toLowerCase(), sb = String(bv).toLowerCase();
      return sortAsc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  }, [data, sortKey, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const paged = sorted.slice(safePage * pageSize, (safePage + 1) * pageSize);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const headerCell = {
    padding: "10px 14px", fontSize: 11, fontWeight: 700,
    color: theme.text.faint, textTransform: "uppercase",
    letterSpacing: "0.05em", borderBottom: `1px solid ${theme.border.default}`,
    textAlign: "left", whiteSpace: "nowrap", userSelect: "none",
  };

  const bodyCell = {
    padding: "11px 14px", fontSize: 13, color: theme.text.secondary,
    borderBottom: `1px solid ${theme.border.subtle}`,
  };

  if (!data.length) {
    return (
      <div style={{
        textAlign: "center", padding: "40px 0", color: theme.text.faint, fontSize: 13,
      }}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table style={{
          width: "100%", borderCollapse: "collapse", fontFamily: theme.font.family,
        }}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={{
                    ...headerCell,
                    width: col.width || "auto",
                    cursor: col.sortable !== false ? "pointer" : "default",
                  }}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span style={{ marginLeft: 4 }}>{sortAsc ? "\u25b2" : "\u25bc"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, i) => (
              <tr
                key={row.id || i}
                onClick={() => onRowClick && onRowClick(row)}
                style={{
                  cursor: onRowClick ? "pointer" : "default",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = theme.bg.cardHover}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                {columns.map((col) => (
                  <td key={col.key} style={bodyCell}>
                    {col.render ? col.render(row[col.key], row) : (row[col.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 0", fontSize: 12, color: theme.text.faint,
        }}>
          <span>
            Showing {safePage * pageSize + 1}–{Math.min((safePage + 1) * pageSize, sorted.length)} of {sorted.length}
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              disabled={safePage === 0}
              onClick={() => setPage(safePage - 1)}
              style={pageBtnStyle(safePage === 0)}
            >
              ‹ Prev
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p;
              if (totalPages <= 7) {
                p = i;
              } else if (safePage < 4) {
                p = i;
              } else if (safePage > totalPages - 5) {
                p = totalPages - 7 + i;
              } else {
                p = safePage - 3 + i;
              }
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  style={{
                    ...pageBtnStyle(false),
                    background: p === safePage ? theme.accent.blue : "transparent",
                    color: p === safePage ? "#fff" : theme.text.faint,
                  }}
                >
                  {p + 1}
                </button>
              );
            })}
            <button
              disabled={safePage >= totalPages - 1}
              onClick={() => setPage(safePage + 1)}
              style={pageBtnStyle(safePage >= totalPages - 1)}
            >
              Next ›
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function pageBtnStyle(disabled) {
  return {
    padding: "5px 10px", borderRadius: 5, fontSize: 12, fontWeight: 500,
    background: "transparent", color: disabled ? theme.text.ghost : theme.text.dim,
    border: `1px solid ${theme.border.subtle}`, cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.4 : 1,
  };
}
