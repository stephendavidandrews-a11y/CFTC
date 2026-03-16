/**
 * Dark theme constants extracted from command-center-dark.jsx.
 */

const theme = {
  // Backgrounds
  bg: {
    app: "#0a0f1a",
    sidebar: "#070b14",
    card: "#111827",
    cardHover: "#0f172a",
    input: "#0f172a",
  },

  // Borders
  border: {
    default: "#1f2937",
    subtle: "#1e293b",
    active: "#3b82f6",
  },

  // Text
  text: {
    primary: "#f1f5f9",
    secondary: "#e2e8f0",
    muted: "#94a3b8",
    dim: "#64748b",
    faint: "#475569",
    ghost: "#334155",
  },

  // Accent colors
  accent: {
    blue: "#3b82f6",
    blueLight: "#60a5fa",
    purple: "#a78bfa",
    green: "#22c55e",
    greenLight: "#4ade80",
    yellow: "#f59e0b",
    yellowLight: "#fbbf24",
    red: "#ef4444",
    redLight: "#f87171",
    twitter: "#1d9bf0",
    teal: "#34d399",
  },

  // Status badge styles (legacy pipeline + tracker matter statuses)
  status: {
    in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
    completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
    superseded: { bg: "#422006", text: "#fbbf24", label: "Superseded" },
    not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
    active: { bg: "#172554", text: "#60a5fa", label: "Active" },
    paused: { bg: "#422006", text: "#fbbf24", label: "Paused" },
    withdrawn: { bg: "#1f2937", text: "#9ca3af", label: "Withdrawn" },
    archived: { bg: "#1f2937", text: "#6b7280", label: "Archived" },
    // Tracker matter statuses
    "draft in progress": { bg: "#1e3a5f", text: "#60a5fa", label: "Draft in Progress" },
    "internal review": { bg: "#172554", text: "#60a5fa", label: "Internal Review" },
    "awaiting comments": { bg: "#422006", text: "#fbbf24", label: "Awaiting Comments" },
    "external coordination": { bg: "#1e1b4b", text: "#a78bfa", label: "External Coordination" },
    "research in progress": { bg: "#0c4a6e", text: "#38bdf8", label: "Research in Progress" },
    "parked / monitoring": { bg: "#1f2937", text: "#9ca3af", label: "Parked / Monitoring" },
    "escalated": { bg: "#450a0a", text: "#f87171", label: "Escalated" },
    "closed": { bg: "#1f2937", text: "#6b7280", label: "Closed" },
    // Tracker task statuses
    "waiting on others": { bg: "#422006", text: "#fbbf24", label: "Waiting" },
    "deferred": { bg: "#1f2937", text: "#9ca3af", label: "Deferred" },
  },

  // Priority badge styles (legacy + tracker priorities)
  priority: {
    critical: { bg: "#450a0a", text: "#f87171", label: "Critical" },
    high: { bg: "#422006", text: "#fbbf24", label: "High" },
    medium: { bg: "#172554", text: "#60a5fa", label: "Medium" },
    low: { bg: "#1f2937", text: "#9ca3af", label: "Low" },
    normal: { bg: "#1f2937", text: "#94a3b8", label: "Normal" },
    // Tracker priorities
    "critical this week": { bg: "#450a0a", text: "#f87171", label: "Critical This Week" },
    "important this month": { bg: "#422006", text: "#fbbf24", label: "Important This Month" },
    "strategic / slow burn": { bg: "#172554", text: "#60a5fa", label: "Strategic" },
    "monitoring only": { bg: "#1f2937", text: "#9ca3af", label: "Monitoring" },
    "backlog": { bg: "#1f2937", text: "#6b7280", label: "Backlog" },
  },

  // Deadline severity
  deadline: {
    overdue: "#ef4444",
    critical: "#ef4444",
    warning: "#f59e0b",
    ok: "#334155",
  },

  // Feed type colors
  feed: {
    tweet: { accent: "#1d9bf0", bg: "rgba(29,155,240,0.08)" },
    news: { accent: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
    fr: { accent: "#a78bfa", bg: "rgba(167,139,250,0.08)" },
    regulatory: { accent: "#34d399", bg: "rgba(52,211,153,0.08)" },
  },

  // Typography
  font: {
    family: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    mono: "ui-monospace, SFMono-Regular, 'Cascadia Code', Consolas, monospace",
  },

  // Sizing
  sidebar: { width: 250 },
  card: { radius: 10 },
};

export default theme;
