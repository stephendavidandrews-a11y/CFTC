import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getDocument } from "../../api/tracker";
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

export default function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: docData, loading, error } = useApi(() => getDocument(id), [id]);

  React.useEffect(() => {
    if (docData?.title) document.title = docData.title + " | Command Center";
  }, [docData?.title]);

  if (loading) return <div style={{ padding: 40, color: theme.text.dim }}>Loading...</div>;
  if (error) return <div style={{ padding: 40, color: theme.accent.red }}>Error: {error.message}</div>;
  if (!docData) return <div style={{ padding: 40, color: theme.text.dim }}>Document not found</div>;

  const doc = docData;

  const statusTheme = theme.status?.[doc.status] || { bg: theme.bg.input, text: theme.text.faint };

  return (
    <div style={{ padding: 24, maxWidth: 860 }}>
      <Breadcrumb items={[{ label: "Documents", path: "/documents" }, { label: doc.title }]} />

      {/* Title + badges */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
          {doc.title}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Badge bg={statusTheme.bg} text={statusTheme.text} label={statusTheme.label || fmt(doc.status)} />
          {doc.document_type && (
            <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(doc.document_type)} />
          )}
        </div>
      </div>

      {/* Metadata grid */}
      <div style={cardStyle}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 32px" }}>
          <div>
            <div style={labelStyle}>Document Type</div>
            <div style={valueStyle}>{fmt(doc.document_type)}</div>
          </div>
          <div>
            <div style={labelStyle}>Status</div>
            <div style={valueStyle}>
              <Badge bg={statusTheme.bg} text={statusTheme.text} label={statusTheme.label || fmt(doc.status)} />
            </div>
          </div>
          <div>
            <div style={labelStyle}>Owner</div>
            <div style={valueStyle}>{doc.owner_name || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Version</div>
            <div style={valueStyle}>{doc.version_label || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Due Date</div>
            <div style={valueStyle}>{formatDate(doc.due_date) || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Linked Matter</div>
            <div style={valueStyle}>
              {doc.matter_id ? (
                <span
                  onClick={() => navigate(`/matters/${doc.matter_id}`)}
                  style={{ color: theme.accent.blue, cursor: "pointer" }}
                >
                  {doc.matter_title || doc.matter_id}
                </span>
              ) : "--"}
            </div>
          </div>
          <div>
            <div style={labelStyle}>Created</div>
            <div style={valueStyle}>{formatDate(doc.created_at) || "--"}</div>
          </div>
          <div>
            <div style={labelStyle}>Updated</div>
            <div style={valueStyle}>{formatDate(doc.updated_at) || "--"}</div>
          </div>
        </div>
      </div>

      {/* Notes */}
      {doc.notes && (
        <div style={cardStyle}>
          <div style={labelStyle}>Notes</div>
          <div style={{ fontSize: 14, color: theme.text.primary, whiteSpace: "pre-wrap", lineHeight: 1.6, marginTop: 6 }}>
            {doc.notes}
          </div>
        </div>
      )}
    </div>
  );
}
