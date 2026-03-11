import React, { useState, useEffect, useCallback, useMemo } from "react";
import DataTable from "../components/shared/DataTable";
import Badge from "../components/shared/Badge";
import Modal from "../components/shared/Modal";
import StatCard from "../components/shared/StatCard";
import theme from "../styles/theme";
import { useApi } from "../hooks/useApi";
import { useToastContext } from "../contexts/ToastContext";
import {
  getEOActions, getEOSummary, getEODocuments, getEODocument,
  getEOCompliance, listItems, updateItem,
} from "../api/pipeline";

// ── Constants ─────────────────────────────────────────────────────

const STATUS_COLORS = {
  active: { bg: "#172554", text: "#60a5fa", label: "Active" },
  revoked: { bg: "#450a0a", text: "#f87171", label: "Revoked" },
  amended: { bg: "#422006", text: "#fbbf24", label: "Amended" },
  superseded: { bg: "#1f2937", text: "#9ca3af", label: "Superseded" },
};

const ACTION_STATUS_COLORS = {
  in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
  superseded: { bg: "#422006", text: "#fbbf24", label: "Superseded" },
  not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
  pending: { bg: "#1e3a5f", text: "#60a5fa", label: "Pending" },
};

const COMPLIANCE_STATUS_COLORS = {
  overdue: { bg: "#450a0a", text: "#f87171", label: "Overdue" },
  active: { bg: "#172554", text: "#60a5fa", label: "Active" },
  upcoming: { bg: "#422006", text: "#fbbf24", label: "Upcoming" },
  pending: { bg: "#1f2937", text: "#9ca3af", label: "Pending" },
};

const RELEVANCE_COLORS = {
  5: "#22c55e", 4: "#4ade80", 3: "#f59e0b", 2: "#94a3b8", 1: "#64748b", 0: "#475569",
};

const inputStyle = {
  padding: "8px 12px", borderRadius: 6,
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  color: theme.text.secondary, fontSize: 13, outline: "none",
  fontFamily: theme.font.family,
};

const TAG_COLORS = {
  cftc: { bg: "#172554", text: "#60a5fa" },
  interagency: { bg: "#1e1b4b", text: "#a78bfa" },
  selig: { bg: "#14532d", text: "#4ade80" },
  regulatory: { bg: "#422006", text: "#fbbf24" },
};

// ── Helper: build EO columns (with optional compliance map) ──────

function buildEOColumns(complianceEOs, onBadgeClick) {
  return [
    {
      key: "executive_order_number", label: "EO #", width: "8%",
      render: (v, row) => (
        <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.accent.blueLight, fontWeight: 600 }}>
          {v ? `EO ${v}` : row.document_type || "\u2014"}
        </span>
      ),
    },
    {
      key: "title", label: "Title", width: "30%",
      render: (v) => (
        <span title={v} style={{ fontSize: 13 }}>{v && v.length > 60 ? v.slice(0, 60) + "..." : v}</span>
      ),
    },
    {
      key: "president", label: "President", width: "10%",
      render: (v) => <span style={{ fontSize: 12, color: theme.text.muted }}>{v || "\u2014"}</span>,
    },
    {
      key: "signing_date", label: "Signed", width: "9%",
      render: (v) => (
        <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.dim }}>{v || "\u2014"}</span>
      ),
    },
    {
      key: "status", label: "Status", width: "9%",
      render: (v) => {
        const s = STATUS_COLORS[v] || STATUS_COLORS.active;
        return <Badge bg={s.bg} text={s.text} label={s.label} />;
      },
    },
    {
      key: "cftc_relevance_score", label: "CFTC Rel.", width: "7%",
      render: (v) => (
        <span style={{
          fontFamily: theme.font.mono, fontSize: 13, fontWeight: 700,
          color: RELEVANCE_COLORS[v] || RELEVANCE_COLORS[0],
        }}>
          {v}/5
        </span>
      ),
    },
    {
      key: "_compliance", label: "Compliance", width: "9%", sortable: false,
      render: (_, row) => {
        const eoNum = row.executive_order_number;
        if (!eoNum || !complianceEOs) return <span style={{ color: "#334155" }}>{"\u2014"}</span>;
        const info = complianceEOs[eoNum];
        if (!info) return <span style={{ color: "#334155" }}>{"\u2014"}</span>;
        const isMandatory = info.mandatory;
        return (
          <span
            onClick={(e) => { e.stopPropagation(); onBadgeClick && onBadgeClick(eoNum); }}
            style={{ cursor: "pointer" }}
          >
            <Badge
              bg={isMandatory ? "#450a0a" : "#422006"}
              text={isMandatory ? "#f87171" : "#fbbf24"}
              label={isMandatory ? "Mandatory" : "Encouraged"}
            />
          </span>
        );
      },
    },
    {
      key: "crypto_interagency_flag", label: "Crypto", width: "5%", sortable: false,
      render: (v) => v ? <span style={{ color: "#22c55e" }}>{"\u25CF"}</span> : <span style={{ color: "#334155" }}>{"\u2014"}</span>,
    },
    {
      key: "_links", label: "", width: "9%", sortable: false,
      render: (_, row) => (
        <span style={{ display: "flex", gap: 8 }}>
          {row.html_url && (
            <a href={row.html_url} target="_blank" rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ fontSize: 11, color: theme.accent.blueLight, fontWeight: 600, textDecoration: "none" }}>
              FR
            </a>
          )}
          {row.pdf_url && (
            <a href={row.pdf_url} target="_blank" rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ fontSize: 11, color: theme.accent.purple, fontWeight: 600, textDecoration: "none" }}>
              PDF
            </a>
          )}
        </span>
      ),
    },
  ];
}

// ── Action Items Table Columns ────────────────────────────────────

const ACTION_COLUMNS = [
  {
    key: "action_description", label: "Action", width: "35%",
    render: (v, row) => v || row.title || `Action #${row.id}`,
  },
  {
    key: "status", label: "Status", width: "12%",
    render: (v) => {
      const s = ACTION_STATUS_COLORS[v] || ACTION_STATUS_COLORS.not_started;
      return <Badge bg={s.bg} text={s.text} label={s.label} />;
    },
  },
  {
    key: "deadline", label: "Deadline", width: "12%",
    render: (v) => (
      <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.dim }}>{v || "\u2014"}</span>
    ),
  },
  { key: "cftc_role", label: "CFTC Role", width: "14%" },
  { key: "priority", label: "Priority", width: "10%" },
  {
    key: "_link", label: "", width: "7%", sortable: false,
    render: () => (
      <span style={{ fontSize: 11, color: theme.accent.blueLight, fontWeight: 600 }}>Link</span>
    ),
  },
];

// ── Compliance Mandatory Table Columns ────────────────────────────

const MANDATORY_COLUMNS = [
  {
    key: "id", label: "#", width: "4%",
    render: (v) => <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.faint }}>{v}</span>,
  },
  {
    key: "source", label: "Source EO", width: "14%",
    render: (v) => <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.accent.blueLight, fontWeight: 600 }}>{v}</span>,
  },
  {
    key: "directive", label: "Directive", width: "28%",
    render: (v) => <span title={v} style={{ fontSize: 12 }}>{v && v.length > 80 ? v.slice(0, 80) + "..." : v}</span>,
  },
  {
    key: "deadline", label: "Deadline", width: "22%",
    render: (v) => <span style={{ fontSize: 12, color: theme.text.muted }}>{v}</span>,
  },
  {
    key: "status", label: "Status", width: "10%",
    render: (v) => {
      const s = COMPLIANCE_STATUS_COLORS[v] || COMPLIANCE_STATUS_COLORS.pending;
      return <Badge bg={s.bg} text={s.text} label={s.label} />;
    },
  },
];

const ENCOURAGED_COLUMNS = [
  {
    key: "source", label: "Source EO", width: "14%",
    render: (v) => <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.accent.blueLight, fontWeight: 600 }}>{v}</span>,
  },
  {
    key: "directive", label: "Directive", width: "30%",
    render: (v) => <span title={v} style={{ fontSize: 12 }}>{v && v.length > 80 ? v.slice(0, 80) + "..." : v}</span>,
  },
  {
    key: "risk", label: "Risk of Noncompliance", width: "30%",
    render: (v) => <span title={v} style={{ fontSize: 12, color: "#f59e0b" }}>{v && v.length > 80 ? v.slice(0, 80) + "..." : v}</span>,
  },
  {
    key: "deadline", label: "Deadline", width: "16%",
    render: (v) => <span style={{ fontSize: 12, color: theme.text.muted }}>{v}</span>,
  },
];

// ── Detail Expansion Panel ────────────────────────────────────────

function EODetailPanel({ docId }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getEODocument(docId).then((data) => {
      if (!cancelled) { setDetail(data); setLoading(false); }
    }).catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [docId]);

  if (loading) {
    return <div style={{ padding: 24, textAlign: "center", color: theme.text.dim }}>Loading details...</div>;
  }
  if (!detail) {
    return <div style={{ padding: 24, textAlign: "center", color: theme.text.dim }}>Failed to load details</div>;
  }

  const { document: doc, analysis, deadlines, relationships, authorities, action_items } = detail;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20,
      padding: 20, background: theme.bg.card, borderRadius: 8,
      border: `1px solid ${theme.border.subtle}`, margin: "8px 0",
    }}>
      {/* Left column — Summary & Tags */}
      <div>
        {analysis?.plain_language_summary && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Summary</div>
            <div style={{ fontSize: 13, color: theme.text.secondary, lineHeight: 1.6 }}>{analysis.plain_language_summary}</div>
          </div>
        )}
        {analysis?.cftc_relevance_explanation && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>CFTC Relevance</div>
            <div style={{ fontSize: 13, color: theme.text.muted, lineHeight: 1.5 }}>{analysis.cftc_relevance_explanation}</div>
          </div>
        )}
        {/* Tags */}
        {analysis?.cftc_relevance_tags?.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 11, color: theme.text.faint, marginRight: 8 }}>CFTC:</span>
            {analysis.cftc_relevance_tags.map((t) => (
              <Badge key={t} bg={TAG_COLORS.cftc.bg} text={TAG_COLORS.cftc.text} label={t.replace(/_/g, " ")} />
            ))}
          </div>
        )}
        {analysis?.interagency_tags?.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 11, color: theme.text.faint, marginRight: 8 }}>Interagency:</span>
            {analysis.interagency_tags.map((t) => (
              <Badge key={t} bg={TAG_COLORS.interagency.bg} text={TAG_COLORS.interagency.text} label={t.replace(/_/g, " ")} />
            ))}
          </div>
        )}
        {analysis?.selig_priority_alignment?.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 11, color: theme.text.faint, marginRight: 8 }}>Selig Priorities:</span>
            {analysis.selig_priority_alignment.map((t) => (
              <Badge key={t} bg={TAG_COLORS.selig.bg} text={TAG_COLORS.selig.text} label={t.replace(/_/g, " ")} />
            ))}
          </div>
        )}
        {analysis?.regulatory_relevance_tags?.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 11, color: theme.text.faint, marginRight: 8 }}>Regulatory:</span>
            {analysis.regulatory_relevance_tags.map((t) => (
              <Badge key={t} bg={TAG_COLORS.regulatory.bg} text={TAG_COLORS.regulatory.text} label={t.replace(/_/g, " ")} />
            ))}
          </div>
        )}
      </div>

      {/* Right column — Quick Facts, Relationships, Deadlines, Authorities */}
      <div>
        {/* Quick Facts */}
        <div style={{ marginBottom: 16, padding: 12, background: theme.bg.app, borderRadius: 6, border: `1px solid ${theme.border.subtle}` }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Quick Facts</div>
          {[
            ["Type", doc.document_type],
            ["Signed", doc.signing_date],
            ["Published", doc.publication_date],
            ["FR Citation", doc.fr_citation],
            ["Status", doc.status],
          ].map(([label, val]) => val && (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
              <span style={{ color: theme.text.faint }}>{label}</span>
              <span style={{ color: theme.text.muted, fontFamily: theme.font.mono }}>{val}</span>
            </div>
          ))}
        </div>

        {/* Relationships */}
        {(relationships.outgoing.length > 0 || relationships.incoming.length > 0) && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Relationships</div>
            {relationships.outgoing.map((r, i) => (
              <div key={`o-${i}`} style={{ fontSize: 12, color: theme.text.muted, marginBottom: 3 }}>
                <span style={{ color: theme.accent.yellow }}>{r.relationship_type}</span>{" "}
                {r.target_eo_number ? `EO ${r.target_eo_number}` : r.target_description || "unknown"}
                {r.target_title && <span style={{ color: theme.text.faint }}> {"\u2014"} {r.target_title.slice(0, 50)}</span>}
              </div>
            ))}
            {relationships.incoming.map((r, i) => (
              <div key={`i-${i}`} style={{ fontSize: 12, color: theme.text.muted, marginBottom: 3 }}>
                <span style={{ color: theme.accent.purple }}>{r.relationship_type} by</span>{" "}
                {r.source_eo ? `EO ${r.source_eo}` : r.source_title?.slice(0, 40) || "unknown"}
              </div>
            ))}
          </div>
        )}

        {/* Deadlines */}
        {deadlines.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Deadlines ({deadlines.length})</div>
            {deadlines.map((dl) => {
              const overdue = dl.calculated_due_date && dl.calculated_due_date < today;
              const color = overdue ? "#f87171" : "#94a3b8";
              return (
                <div key={dl.id} style={{ fontSize: 12, marginBottom: 6, paddingLeft: 8, borderLeft: `2px solid ${color}` }}>
                  <div style={{ color }}>
                    {dl.calculated_due_date || "TBD"}{" "}
                    {dl.directed_agency && <span style={{ color: theme.text.faint }}>{"\u00B7"} {dl.directed_agency}</span>}
                  </div>
                  <div style={{ color: theme.text.faint, fontSize: 11 }}>
                    {(dl.deliverable || dl.raw_text || "").slice(0, 80)}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Statutory Authorities */}
        {authorities.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Statutory Authorities ({authorities.length})</div>
            {authorities.map((a) => (
              <div key={a.id} style={{ fontSize: 12, color: a.is_cea ? theme.accent.green : theme.text.muted, marginBottom: 2 }}>
                {a.normalized || a.raw_text?.slice(0, 60) || "\u2014"}{a.is_cea ? " [CEA]" : ""}
              </div>
            ))}
          </div>
        )}

        {/* Action Items for this EO */}
        {action_items.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>Action Items ({action_items.length})</div>
            {action_items.map((ai) => {
              const s = ACTION_STATUS_COLORS[ai.status] || ACTION_STATUS_COLORS.not_started;
              return (
                <div key={ai.id} style={{ fontSize: 12, color: theme.text.muted, marginBottom: 4, display: "flex", gap: 8, alignItems: "center" }}>
                  <Badge bg={s.bg} text={s.text} label={s.label} />
                  <span>{(ai.description || "").slice(0, 60)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


// ── Compliance Detail Expansion ───────────────────────────────────

function ComplianceDetailPanel({ item, type }) {
  const sectionStyle = {
    fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 6,
    textTransform: "uppercase", letterSpacing: "0.05em",
  };
  const textStyle = { fontSize: 13, color: theme.text.secondary, lineHeight: 1.6, marginBottom: 16 };

  return (
    <div style={{
      padding: 20, background: theme.bg.card, borderRadius: 8,
      border: `1px solid ${theme.border.subtle}`, margin: "8px 0",
    }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <div style={sectionStyle}>Full Directive</div>
          <div style={textStyle}>{item.directive}</div>
          {type === "mandatory" && (
            <>
              <div style={sectionStyle}>CFTC Obligation</div>
              <div style={textStyle}>{item.cftc_obligation}</div>
            </>
          )}
          {type === "encouraged" && (
            <>
              <div style={sectionStyle}>Rationale for Compliance</div>
              <div style={textStyle}>{item.rationale}</div>
            </>
          )}
        </div>
        <div>
          <div style={{
            padding: 14, background: theme.bg.app, borderRadius: 6,
            border: `1px solid ${theme.border.subtle}`,
          }}>
            <div style={sectionStyle}>Details</div>
            {[
              ["Source", item.source],
              ["EO Number", item.eo_number ? `EO ${item.eo_number}` : null],
              ["Deadline", item.deadline],
              ...(type === "mandatory" ? [["Status", item.status?.toUpperCase()]] : []),
            ].map(([label, val]) => val && (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
                <span style={{ color: theme.text.faint }}>{label}</span>
                <span style={{ color: label === "Status" && item.status === "overdue" ? "#f87171" : theme.text.muted, fontWeight: label === "Status" ? 600 : 400 }}>
                  {val}
                </span>
              </div>
            ))}
          </div>
          {type === "encouraged" && item.risk && (
            <div style={{ marginTop: 16 }}>
              <div style={sectionStyle}>Risk of Noncompliance</div>
              <div style={{ ...textStyle, color: "#f59e0b" }}>{item.risk}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// ── Main Page ─────────────────────────────────────────────────────

export default function EOPage() {
  const toast = useToastContext();

  // View toggle
  const [view, setView] = useState("reference");

  // EO reference filters
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [presidentFilter, setPresidentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [relevanceFilter, setRelevanceFilter] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  // Action items filters
  const [actionStatusFilter, setActionStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [showLinkModal, setShowLinkModal] = useState(null);
  const [linkSearchQuery, setLinkSearchQuery] = useState("");
  const [linking, setLinking] = useState(false);

  // Compliance state
  const [expandedComplianceId, setExpandedComplianceId] = useState(null);
  const [expandedEncouraged, setExpandedEncouraged] = useState(null);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Data fetching
  const { data: summary } = useApi(() => getEOSummary(), []);
  const { data: compliance } = useApi(() => getEOCompliance(), []);

  const docParams = {};
  if (presidentFilter) docParams.president = presidentFilter;
  if (statusFilter) docParams.status = statusFilter;
  if (relevanceFilter) docParams.min_relevance = relevanceFilter;
  if (search) docParams.search = search;

  const { data: documents, loading: docsLoading, error: docsError } = useApi(
    () => getEODocuments(docParams),
    [presidentFilter, statusFilter, relevanceFilter, search]
  );

  const { data: actions, loading: actionsLoading, error: actionsError, refetch: refetchActions } = useApi(
    () => getEOActions(), []
  );

  const { data: linkSearchResults } = useApi(
    () => (linkSearchQuery.length >= 2 ? listItems({ search: linkSearchQuery, page_size: 20 }) : Promise.resolve(null)),
    [linkSearchQuery]
  );

  const allActions = actions || [];
  const allDocuments = documents || [];
  const roles = [...new Set(allActions.map((a) => a.cftc_role).filter(Boolean))];
  const presidents = summary?.by_president ? Object.keys(summary.by_president) : [];

  // Build compliance EO lookup map: { eo_number: { mandatory: bool, encouraged: bool, count: N } }
  const complianceEOs = useMemo(() => {
    if (!compliance) return null;
    const map = {};
    (compliance.mandatory || []).forEach((item) => {
      if (item.eo_number) {
        if (!map[item.eo_number]) map[item.eo_number] = { mandatory: false, encouraged: false, count: 0 };
        map[item.eo_number].mandatory = true;
        map[item.eo_number].count++;
      }
    });
    (compliance.encouraged || []).forEach((item) => {
      if (item.eo_number) {
        if (!map[item.eo_number]) map[item.eo_number] = { mandatory: false, encouraged: false, count: 0 };
        map[item.eo_number].encouraged = true;
        map[item.eo_number].count++;
      }
    });
    return map;
  }, [compliance]);

  // Compliance stats
  const overdueCount = useMemo(() => {
    if (!compliance) return 0;
    return (compliance.mandatory || []).filter((m) => m.status === "overdue").length;
  }, [compliance]);

  const activeCount = useMemo(() => {
    if (!compliance) return 0;
    return (compliance.mandatory || []).filter((m) => m.status === "active").length;
  }, [compliance]);

  const filteredActions = allActions.filter((a) => {
    if (actionStatusFilter && a.status !== actionStatusFilter) return false;
    if (roleFilter && a.cftc_role !== roleFilter) return false;
    return true;
  });

  // Build EO columns with compliance badges
  const eoColumns = useMemo(
    () => buildEOColumns(complianceEOs, (eoNum) => { setView("compliance"); }),
    [complianceEOs]
  );

  const handleRowClick = useCallback((row) => {
    setExpandedId((prev) => (prev === row.id ? null : row.id));
  }, []);

  const handleActionRowClick = (row) => {
    setShowLinkModal(row);
    setLinkSearchQuery("");
  };

  const handleLink = async (pipelineItem) => {
    if (!showLinkModal) return;
    setLinking(true);
    try {
      await updateItem(pipelineItem.id, { eo_action_item_id: showLinkModal.id });
      toast.success(`Linked "${pipelineItem.title}" to EO action`);
      setShowLinkModal(null);
      setLinkSearchQuery("");
      refetchActions();
    } catch (err) {
      toast.error("Failed to link: " + (err.message || "Unknown error"));
    } finally {
      setLinking(false);
    }
  };

  const pipelineItems = linkSearchResults?.items || linkSearchResults || [];
  const hasError = (view === "reference" || view === "actions") ? (view === "reference" ? docsError : actionsError) : false;

  // Tab style helper
  const tabStyle = (active) => ({
    padding: "8px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600,
    cursor: "pointer", border: "none", transition: "all 0.15s",
    background: active ? theme.accent.blue : "transparent",
    color: active ? "#fff" : theme.text.dim,
  });

  return (
    <div>
      {/* Header */}
      <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4, letterSpacing: "-0.02em" }}>
        Executive Order Reference Guide
      </h2>
      <p style={{ fontSize: 13, color: theme.text.faint, marginBottom: 20 }}>
        {summary ? `${summary.total_documents} executive orders across ${presidents.length} administrations` : "Loading..."}
      </p>

      {/* Stat Cards */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 20 }}>
          <StatCard value={summary.total_documents} label="Total Executive Orders" accent={theme.accent.blue} />
          <StatCard value={summary.high_relevance_count} label="High CFTC Relevance" accent="#a78bfa" />
          <StatCard value={summary.open_action_items} label="Open Action Items" accent={theme.accent.yellow} />
          <StatCard value={summary.upcoming_deadlines} label="Upcoming Deadlines (90d)" accent={theme.accent.green} />
          <StatCard
            value={overdueCount}
            label="Compliance Overdue"
            accent={overdueCount > 0 ? theme.accent.red : theme.accent.green}
            pulse={overdueCount > 0}
          />
        </div>
      )}

      {/* View Toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: theme.bg.card, borderRadius: 8, padding: 4, width: "fit-content" }}>
        <button style={tabStyle(view === "reference")} onClick={() => setView("reference")}>EO Reference</button>
        <button style={tabStyle(view === "actions")} onClick={() => setView("actions")}>Action Items</button>
        <button style={tabStyle(view === "compliance")} onClick={() => setView("compliance")}>
          Compliance
          {overdueCount > 0 && (
            <span style={{
              marginLeft: 6, background: "#dc2626", color: "#fff", borderRadius: 10,
              padding: "1px 7px", fontSize: 10, fontWeight: 700,
            }}>
              {overdueCount}
            </span>
          )}
        </button>
      </div>

      {/* Error state */}
      {hasError && (
        <div style={{
          background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
          padding: 40, textAlign: "center",
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.muted }}>EO Tracker database not connected</div>
          <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 8 }}>Connect eo_tracker.db to see executive order data</div>
        </div>
      )}

      {/* ── EO Reference View ── */}
      {view === "reference" && !hasError && (
        <>
          {/* Filters */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by title..."
              style={{ ...inputStyle, width: 220 }}
            />
            <select value={presidentFilter} onChange={(e) => setPresidentFilter(e.target.value)}
              style={{ ...inputStyle, width: 160, cursor: "pointer" }}>
              <option value="">All Presidents</option>
              {presidents.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              style={{ ...inputStyle, width: 140, cursor: "pointer" }}>
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="revoked">Revoked</option>
              <option value="amended">Amended</option>
              <option value="superseded">Superseded</option>
            </select>
            <select value={relevanceFilter} onChange={(e) => setRelevanceFilter(e.target.value)}
              style={{ ...inputStyle, width: 160, cursor: "pointer" }}>
              <option value="">All Relevance</option>
              <option value="5">Score = 5</option>
              <option value="4">Score {"\u2265"} 4</option>
              <option value="3">Score {"\u2265"} 3</option>
              <option value="2">Score {"\u2265"} 2</option>
              <option value="1">Score {"\u2265"} 1</option>
            </select>
          </div>

          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
            {docsLoading ? (
              <div style={{ padding: 30, textAlign: "center", color: theme.text.dim }}>Loading...</div>
            ) : (
              <>
                <DataTable
                  columns={eoColumns}
                  data={allDocuments}
                  onRowClick={handleRowClick}
                  pageSize={25}
                  emptyMessage="No executive orders found"
                />
                {expandedId && allDocuments.some((d) => d.id === expandedId) && (
                  <EODetailPanel docId={expandedId} />
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* ── Action Items View ── */}
      {view === "actions" && !hasError && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
            <select value={actionStatusFilter} onChange={(e) => setActionStatusFilter(e.target.value)}
              style={{ ...inputStyle, width: 160, cursor: "pointer" }}>
              <option value="">All Statuses</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="not_started">Not Started</option>
              <option value="superseded">Superseded</option>
            </select>
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
              style={{ ...inputStyle, width: 200, cursor: "pointer" }}>
              <option value="">All CFTC Roles</option>
              {roles.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
            {actionsLoading ? (
              <div style={{ padding: 30, textAlign: "center", color: theme.text.dim }}>Loading...</div>
            ) : (
              <DataTable
                columns={ACTION_COLUMNS}
                data={filteredActions}
                onRowClick={handleActionRowClick}
                pageSize={25}
                emptyMessage="No EO action items found"
              />
            )}
          </div>
        </>
      )}

      {/* ── Compliance View ── */}
      {view === "compliance" && (
        <>
          {/* Alert Banner */}
          {compliance && (overdueCount > 0 || activeCount > 0) && (
            <div style={{
              display: "flex", gap: 16, marginBottom: 16, padding: "14px 20px",
              background: overdueCount > 0 ? "#450a0a" : "#172554",
              border: `1px solid ${overdueCount > 0 ? "#7f1d1d" : "#1e3a5f"}`,
              borderRadius: 10, alignItems: "center",
            }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: overdueCount > 0 ? "#f87171" : "#60a5fa" }}>
                {overdueCount > 0 ? `${overdueCount} Overdue` : `${activeCount} Active`}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, color: "#f1f5f9", fontWeight: 600 }}>
                  Presidential Compliance Obligations
                </div>
                <div style={{ fontSize: 12, color: overdueCount > 0 ? "#fca5a5" : "#93c5fd" }}>
                  {overdueCount > 0
                    ? `${overdueCount} mandatory deadlines have passed. ${activeCount} obligations are actively ongoing.`
                    : `All deadline obligations are current. ${activeCount} obligations require ongoing compliance.`
                  }
                </div>
              </div>
              <div style={{ fontSize: 11, color: theme.text.faint }}>
                Generated {compliance?.generated || ""}
              </div>
            </div>
          )}

          {!compliance ? (
            <div style={{ padding: 30, textAlign: "center", color: theme.text.dim }}>Loading compliance data...</div>
          ) : (
            <>
              {/* Mandatory Actions */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: "#f87171", marginBottom: 4, letterSpacing: "-0.01em" }}>
                  Mandatory Actions
                  <span style={{ fontSize: 12, fontWeight: 500, color: theme.text.faint, marginLeft: 8 }}>
                    {compliance.mandatory?.length || 0} obligations
                  </span>
                </h3>
                <p style={{ fontSize: 12, color: theme.text.faint, marginBottom: 12 }}>
                  Direct presidential directives requiring CFTC compliance
                </p>
                <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
                  <DataTable
                    columns={MANDATORY_COLUMNS}
                    data={compliance.mandatory || []}
                    onRowClick={(row) => setExpandedComplianceId((prev) => prev === row.id ? null : row.id)}
                    pageSize={15}
                    emptyMessage="No mandatory compliance items"
                  />
                  {expandedComplianceId != null && (compliance.mandatory || []).some((m) => m.id === expandedComplianceId) && (
                    <ComplianceDetailPanel
                      item={(compliance.mandatory || []).find((m) => m.id === expandedComplianceId)}
                      type="mandatory"
                    />
                  )}
                </div>
              </div>

              {/* Encouraged Actions */}
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: "#fbbf24", marginBottom: 4, letterSpacing: "-0.01em" }}>
                  Strongly Encouraged Actions
                  <span style={{ fontSize: 12, fontWeight: 500, color: theme.text.faint, marginLeft: 8 }}>
                    {compliance.encouraged?.length || 0} recommendations
                  </span>
                </h3>
                <p style={{ fontSize: 12, color: theme.text.faint, marginBottom: 12 }}>
                  Strategic compliance recommendations with risk assessment
                </p>
                <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
                  <DataTable
                    columns={ENCOURAGED_COLUMNS}
                    data={compliance.encouraged || []}
                    onRowClick={(row) => setExpandedEncouraged((prev) => prev === row.source ? null : row.source)}
                    pageSize={15}
                    emptyMessage="No encouraged compliance items"
                  />
                  {expandedEncouraged && (compliance.encouraged || []).some((e) => e.source === expandedEncouraged) && (
                    <ComplianceDetailPanel
                      item={(compliance.encouraged || []).find((e) => e.source === expandedEncouraged)}
                      type="encouraged"
                    />
                  )}
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Link to Pipeline Item Modal (Action Items view) */}
      <Modal isOpen={!!showLinkModal} onClose={() => setShowLinkModal(null)} title="Link to Pipeline Item" width={560}>
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, color: theme.text.faint, marginBottom: 8 }}>
            Linking EO action: <strong style={{ color: theme.text.secondary }}>
              {showLinkModal?.action_description || showLinkModal?.title || ""}
            </strong>
          </div>
          <input
            value={linkSearchQuery}
            onChange={(e) => setLinkSearchQuery(e.target.value)}
            placeholder="Search pipeline items by title..."
            style={{ ...inputStyle, width: "100%" }}
            autoFocus
          />
        </div>
        {linkSearchQuery.length >= 2 && (
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {pipelineItems.length === 0 ? (
              <div style={{ padding: 20, textAlign: "center", color: theme.text.faint, fontSize: 12 }}>No items found</div>
            ) : (
              pipelineItems.map((item) => (
                <div key={item.id} onClick={() => !linking && handleLink(item)} style={{
                  padding: "10px 14px", marginBottom: 4, borderRadius: 6,
                  background: theme.bg.cardHover, border: `1px solid ${theme.border.default}`,
                  cursor: linking ? "wait" : "pointer", fontSize: 13, transition: "border-color 0.15s",
                }}>
                  <div style={{ fontWeight: 600, color: theme.text.secondary }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>
                    {item.module || ""} {"\u00B7"} {item.item_type || ""} {"\u00B7"} {item.docket_number || "No docket"}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
        {linkSearchQuery.length > 0 && linkSearchQuery.length < 2 && (
          <div style={{ padding: 12, textAlign: "center", color: theme.text.faint, fontSize: 12 }}>
            Type at least 2 characters to search
          </div>
        )}
      </Modal>
    </div>
  );
}
