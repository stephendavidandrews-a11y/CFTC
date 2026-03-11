import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../styles/theme";
import Badge from "../components/shared/Badge";
import EmptyState from "../components/shared/EmptyState";
import { crossSearch, getStage1Scores } from "../api/pipeline";

export default function ResearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [s1Query, setS1Query] = useState("");
  const [s1Result, setS1Result] = useState(null);
  const [s1Loading, setS1Loading] = useState(false);
  const [tab, setTab] = useState("search");

  const doSearch = useCallback(async () => {
    if (!query.trim() || query.trim().length < 2) return;
    setSearching(true);
    try {
      const data = await crossSearch(query.trim());
      setResults(data);
    } catch (e) {
      setResults({ pipeline_items: [], regulatory_docs: [], error: e.message });
    }
    setSearching(false);
  }, [query]);

  const doS1Lookup = useCallback(async () => {
    if (!s1Query.trim()) return;
    setS1Loading(true);
    try {
      const data = await getStage1Scores(s1Query.trim());
      setS1Result(data);
    } catch (e) {
      setS1Result({ error: e.message });
    }
    setS1Loading(false);
  }, [s1Query]);

  const tabStyle = (active) => ({
    padding: "8px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
    background: active ? "rgba(59,130,246,0.12)" : "transparent",
    color: active ? theme.accent.blueLight : theme.text.dim,
    border: active ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
    cursor: "pointer",
  });

  const inputStyle = {
    flex: 1, padding: "10px 14px", borderRadius: 8, fontSize: 14,
    background: theme.bg.input, color: theme.text.primary,
    border: `1px solid ${theme.border.default}`, outline: "none",
    fontFamily: theme.font.family,
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: "0 0 4px" }}>Research</h1>
      <p style={{ color: theme.text.faint, fontSize: 13, margin: "0 0 20px" }}>Cross-database search and Stage 1 score lookup</p>

      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        <button style={tabStyle(tab === "search")} onClick={() => setTab("search")}>Cross-DB Search</button>
        <button style={tabStyle(tab === "stage1")} onClick={() => setTab("stage1")}>Stage 1 Scores</button>
      </div>

      {tab === "search" && (
        <div>
          <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
            <input
              style={inputStyle}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder="Search pipeline items and regulatory documents..."
            />
            <button
              onClick={doSearch}
              disabled={searching || query.trim().length < 2}
              style={{
                padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: "#1e40af", color: "#fff", border: "none",
                cursor: searching ? "wait" : "pointer", opacity: searching ? 0.6 : 1,
              }}
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </div>

          {results && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Pipeline Items */}
              <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, margin: "0 0 12px" }}>
                  Pipeline Items ({results.pipeline_items?.length || 0})
                </h3>
                {results.pipeline_items?.length ? results.pipeline_items.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => navigate(`/${item.module === "rulemaking" ? "pipeline" : "regulatory"}/${item.id}`)}
                    style={{
                      padding: "10px 14px", borderRadius: 8, cursor: "pointer", marginBottom: 4,
                      border: `1px solid ${theme.border.subtle}`, transition: "background 0.1s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = theme.bg.cardHover}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>{item.title}</span>
                      <Badge bg="#172554" text="#60a5fa" label={item.item_type} />
                      {item.status && <Badge {...(theme.status[item.status] || {})} label={item.status} />}
                    </div>
                    {item.docket_number && <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 4 }}>{item.docket_number}</div>}
                  </div>
                )) : <div style={{ color: theme.text.faint, fontSize: 13 }}>No pipeline items found</div>}
              </div>

              {/* Regulatory Documents */}
              <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, margin: "0 0 12px" }}>
                  Regulatory Documents ({results.regulatory_docs?.length || 0})
                </h3>
                {results.regulatory_docs?.length ? results.regulatory_docs.map((doc) => (
                  <div key={doc.id} style={{
                    padding: "10px 14px", borderRadius: 8, marginBottom: 4,
                    border: `1px solid ${theme.border.subtle}`,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>{doc.title}</span>
                      <Badge bg="#2e1065" text="#a78bfa" label={doc.doc_type || "doc"} />
                    </div>
                    <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 4 }}>
                      {doc.fr_citation && <span>FR: {doc.fr_citation}</span>}
                      {doc.cfr_title && <span style={{ marginLeft: 12 }}>CFR: {doc.cfr_title}</span>}
                    </div>
                  </div>
                )) : <div style={{ color: theme.text.faint, fontSize: 13 }}>No regulatory documents found</div>}
              </div>
            </div>
          )}

          {!results && (
            <EmptyState icon="⊞" title="Search Across Databases" message="Search pipeline items and cftc_regulatory.db documents simultaneously." />
          )}
        </div>
      )}

      {tab === "stage1" && (
        <div>
          <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
            <input
              style={inputStyle}
              value={s1Query}
              onChange={(e) => setS1Query(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doS1Lookup()}
              placeholder="Enter FR citation (e.g., 85 FR 44398)"
            />
            <button
              onClick={doS1Lookup}
              disabled={s1Loading || !s1Query.trim()}
              style={{
                padding: "10px 24px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: "#1e40af", color: "#fff", border: "none",
                cursor: s1Loading ? "wait" : "pointer", opacity: s1Loading ? 0.6 : 1,
              }}
            >
              {s1Loading ? "Loading..." : "Lookup"}
            </button>
          </div>

          {s1Result && !s1Result.error && s1Result.scores && (
            <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
                  Stage 1 Scores
                </h3>
                <Badge bg="#2e1065" text="#a78bfa" label={s1Result.type || "unknown"} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                {Object.entries(s1Result.scores).filter(([k]) => /^[dg]\d/i.test(k)).map(([key, val]) => (
                  <div key={key} style={{
                    padding: "12px 14px", borderRadius: 8, background: theme.bg.input,
                    border: `1px solid ${theme.border.subtle}`,
                  }}>
                    <div style={{ fontSize: 11, color: theme.text.faint, fontWeight: 600, textTransform: "uppercase" }}>{key}</div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, marginTop: 4 }}>
                      {typeof val === "number" ? val.toFixed(2) : val ?? "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {s1Result && s1Result.scores === null && (
            <EmptyState icon="∅" title="No Scores Found" message={`No Stage 1 scores found for "${s1Query}"`} />
          )}

          {s1Result?.error && (
            <div style={{ color: theme.accent.red, fontSize: 13, padding: 20 }}>Error: {s1Result.error}</div>
          )}

          {!s1Result && (
            <EmptyState icon="⊞" title="Stage 1 Score Lookup" message="Look up Loper Bright vulnerability scores by Federal Register citation." />
          )}
        </div>
      )}
    </div>
  );
}
