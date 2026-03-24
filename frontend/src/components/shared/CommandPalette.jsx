import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { listMatters, listPeople, listOrganizations } from "../../api/tracker";

const PAGES = [
  { label: "Dashboard", path: "/", type: "page" },
  { label: "Matters", path: "/matters", type: "page" },
  { label: "People", path: "/people", type: "page" },
  { label: "Organizations", path: "/organizations", type: "page" },
  { label: "Tasks", path: "/tasks", type: "page" },
  { label: "Team Workload", path: "/team-workload", type: "page" },
  { label: "Directives", path: "/directives", type: "page" },
  { label: "Meetings", path: "/meetings", type: "page" },
  { label: "Decisions", path: "/decisions", type: "page" },
  { label: "Documents", path: "/documents", type: "page" },
  { label: "Context Notes", path: "/context-notes", type: "page" },
  { label: "Speaker Review", path: "/review/speakers", type: "page" },
  { label: "Entity Review", path: "/review/entities", type: "page" },
  { label: "Bundle Review", path: "/review/bundles", type: "page" },
  { label: "Daily Brief", path: "/intelligence/daily", type: "page" },
  { label: "Weekly Brief", path: "/intelligence/weekly", type: "page" },
  { label: "AI Configuration", path: "/settings/ai", type: "page" },
  { label: "Dev Console", path: "/developer", type: "page" },
];

const TYPE_ICONS = { page: "\u25a4", matter: "\u25a4", person: "\u22a1", organization: "\u2b21" };
const TYPE_LABELS = { page: "Page", matter: "Matter", person: "Person", organization: "Org" };

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setResults(PAGES.slice(0, 8));
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const doSearch = useCallback(async (q) => {
    if (!q.trim()) {
      setResults(PAGES.slice(0, 8));
      setSelected(0);
      return;
    }

    const lower = q.toLowerCase();
    const pageMatches = PAGES.filter((p) => p.label.toLowerCase().includes(lower));

    if (q.trim().length < 2) {
      setResults(pageMatches.slice(0, 8));
      setSelected(0);
      return;
    }

    setLoading(true);
    try {
      const [mattersRes, peopleRes, orgsRes] = await Promise.all([
        listMatters({ search: q, limit: 5 }).catch(() => ({ items: [] })),
        listPeople({ search: q, limit: 5 }).catch(() => ({ items: [] })),
        listOrganizations({ search: q, limit: 5 }).catch(() => ({ items: [] })),
      ]);

      const matters = (mattersRes?.items || mattersRes || []).map((m) => ({
        label: m.title,
        sub: m.matter_number,
        path: `/matters/${m.id}`,
        type: "matter",
      }));

      const people = (peopleRes?.items || peopleRes || []).map((p) => ({
        label: p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim(),
        sub: p.title || p.relationship_category,
        path: `/people/${p.id}`,
        type: "person",
      }));

      const orgs = (orgsRes?.items || orgsRes || []).map((o) => ({
        label: o.name,
        sub: o.org_type,
        path: `/organizations/${o.id}`,
        type: "organization",
      }));

      const all = [...pageMatches, ...matters, ...people, ...orgs].slice(0, 10);
      setResults(all);
      setSelected(0);
    } catch (err) {
      console.error("Command palette search error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 200);
  };

  const handleSelect = (item) => {
    setOpen(false);
    navigate(item.path);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && results[selected]) {
      handleSelect(results[selected]);
    }
  };

  if (!open) return null;

  return (
    <>
      <div
        onClick={() => setOpen(false)}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
          zIndex: 1000, display: "flex", alignItems: "flex-start", justifyContent: "center",
          paddingTop: "15vh",
        }}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 560, maxHeight: "60vh",
            background: theme.bg.card,
            border: `1px solid ${theme.border.default}`,
            borderRadius: 12,
            boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
            display: "flex", flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "14px 16px",
            borderBottom: `1px solid ${theme.border.default}`,
          }}>
            <span style={{ fontSize: 16, color: theme.text.dim }}>&#x1F50D;</span>
            <input
              ref={inputRef}
              value={query}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Search pages, matters, people, organizations..."
              style={{
                flex: 1, background: "transparent", border: "none",
                fontSize: 15, color: theme.text.primary, outline: "none",
              }}
            />
            {loading && <span style={{ fontSize: 12, color: theme.text.dim }}>...</span>}
            <kbd style={{
              fontSize: 10, color: theme.text.faint, background: theme.bg.input,
              padding: "2px 6px", borderRadius: 4, border: `1px solid ${theme.border.subtle}`,
            }}>ESC</kbd>
          </div>

          <div style={{ overflowY: "auto", maxHeight: "50vh" }}>
            {results.length === 0 ? (
              <div style={{ padding: "24px 16px", textAlign: "center", color: theme.text.faint, fontSize: 13 }}>
                No results found
              </div>
            ) : (
              results.map((item, i) => (
                <div
                  key={item.path + i}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelected(i)}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "10px 16px",
                    background: i === selected ? theme.bg.cardHover : "transparent",
                    cursor: "pointer",
                    borderLeft: i === selected ? `2px solid ${theme.accent.blue}` : "2px solid transparent",
                  }}
                >
                  <span style={{ fontSize: 14, color: theme.text.dim, width: 20, textAlign: "center" }}>
                    {TYPE_ICONS[item.type] || "\u25a4"}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, color: theme.text.secondary, fontWeight: 500,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {item.label}
                    </div>
                    {item.sub && (
                      <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 1 }}>
                        {item.sub}
                      </div>
                    )}
                  </div>
                  <span style={{
                    fontSize: 10, color: theme.text.ghost,
                    background: theme.bg.input, padding: "2px 7px", borderRadius: 3,
                  }}>
                    {TYPE_LABELS[item.type] || item.type}
                  </span>
                </div>
              ))
            )}
          </div>

          <div style={{
            padding: "8px 16px", borderTop: `1px solid ${theme.border.subtle}`,
            display: "flex", gap: 16, fontSize: 10, color: theme.text.ghost,
          }}>
            <span><kbd style={{ background: theme.bg.input, padding: "1px 4px", borderRadius: 2, border: `1px solid ${theme.border.subtle}` }}>&uarr;&darr;</kbd> navigate</span>
            <span><kbd style={{ background: theme.bg.input, padding: "1px 4px", borderRadius: 2, border: `1px solid ${theme.border.subtle}` }}>&crarr;</kbd> select</span>
            <span><kbd style={{ background: theme.bg.input, padding: "1px 4px", borderRadius: 2, border: `1px solid ${theme.border.subtle}` }}>esc</kbd> close</span>
          </div>
        </div>
      </div>
    </>
  );
}
