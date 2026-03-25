import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getDecision } from "../../api/tracker";
import Breadcrumb from "../../components/shared/Breadcrumb";
import Badge from "../../components/shared/Badge";
import { formatDate } from "../../utils/dateUtils";
import { cardStyle } from "../../styles/pageStyles";

const labelStyle = {
  fontSize: 11, color: theme.text.dim, marginBottom: 2,
  textTransform: "uppercase", letterSpacing: "0.05em",
};
const valueStyle = { fontSize: 14, color: theme.text.primary, marginBottom: 0 };

function fmt(val) {
  if (!val) return "--";
  return val.replace(/_/g, " ");
}

export default function DecisionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: decision, loading, error } = useApi(() => getDecision(id), [id]);

  React.useEffect(() => {
    if (decision?.title) document.title = decision.title + " | Command Center";
  }, [decision?.title]);

  if (loading) return <div style={{ padding: 40, color: theme.text.dim }}>Loading...</div>;
  if (error) return <div style={{ padding: 40, color: theme.accent.red }}>Error: {error.message}</div>;
  if (!decision) return <div style={{ padding: 40, color: theme.text.dim }}>Decision not found</div>;

  const d = decision;

  const isOverdue =
    d.decision_due_date &&
    new Date(d.decision_due_date) < new Date() &&
    d.status !== "made" &&
    d.status !== "deferred";

  const statusTheme = theme.status?.[d.status] || { bg: theme.bg.input, text: theme.text.faint };

  return (
    <div style={{ padding: 24, maxWidth: 860 }}>
      <Breadcrumb items={[{ label: "Decisions", path: "/decisions" }, { label: d.title }]} />

      {/* Title + status badge */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
          {d.title}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Badge bg={statusTheme.bg} text={statusTheme.text} label={statusTheme.label || fmt(d.status)} />
          {d.decision_type && (
            <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(d.decision_type)} />
          )}
        </div>
      </div>

      {/* Metadata grid */}
      <div style={cardStyle}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 32px" }}>
          <div>
            <div style={labelStyle}>Status</div>
            <div style={valueStyle}>
              <Badge bg={statusTheme.bg} text={statusTheme.text} label={statusTheme.label || fmt(d.status)} />
            </div>
          </div>
          <div>
            <div style={labelStyle}>Decision Type</div>
            <div style={valueStyle}>{fmt(d.decision_type)}</div>
          </div>
          <div>
            <div style={labelStyle}>Owner</div>
            <div style={valueStyle}>{d.owner_name || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Due Date</div>
            <div style={{
              ...valueStyle,
              color: isOverdue ? theme.accent.red : theme.text.primary,
              fontWeight: isOverdue ? 600 : 400,
            }}>
              {formatDate(d.decision_due_date) || "--"}
              {isOverdue && " (overdue)"}
            </div>
          </div>
          <div>
            <div style={labelStyle}>Linked Matter</div>
            <div style={valueStyle}>
              {d.matter_id ? (
                <span
                  onClick={() => navigate(`/matters/${d.matter_id}`)}
                  style={{ color: theme.accent.blue, cursor: "pointer" }}
                >
                  {d.matter_title || d.matter_id}
                </span>
              ) : "--"}
            </div>
          </div>
          <div>
            <div style={labelStyle}>Created</div>
            <div style={valueStyle}>{formatDate(d.created_at) || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Updated</div>
            <div style={valueStyle}>{formatDate(d.updated_at) || "--"}</div>
          </div>
        </div>
      </div>

      {/* Notes / description */}
      {d.notes && (
        <div style={cardStyle}>
          <div style={labelStyle}>Notes</div>
          <div style={{ fontSize: 14, color: theme.text.primary, whiteSpace: "pre-wrap", lineHeight: 1.6, marginTop: 6 }}>
            {d.notes}
          </div>
        </div>
      )}
    </div>
  );
}
