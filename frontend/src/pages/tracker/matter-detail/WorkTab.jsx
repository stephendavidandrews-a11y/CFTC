import React from "react";
import theme from "../../../styles/theme";
import { listTasks } from "../../../api/tracker";
import { useDrawer } from "../../../contexts/DrawerContext";
import Badge from "../../../components/shared/Badge";
import DataTable from "../../../components/shared/DataTable";
import EmptyState from "../../../components/shared/EmptyState";
import { formatDate } from "../../../utils/dateUtils";
import useLazyTab from "../../../hooks/useLazyTab";

const btnPrimary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};

const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

export default function WorkTab({ matterId, activeTab }) {
  const { openDrawer } = useDrawer();

  const { data: tasksData, refetch: refetchTasks } = useLazyTab(
    "Tasks", activeTab, () => listTasks({ matter_id: matterId }), [matterId]
  );
  const tasks = tasksData?.items || tasksData || [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={sectionTitle}>Tasks</div>
        <button style={btnPrimary} onClick={() => openDrawer("task", { matter_id: matterId }, refetchTasks)}>
          + Add Task
        </button>
      </div>
      {tasks.length === 0 ? (
        <EmptyState title="No tasks" message="Add tasks to track work on this matter." />
      ) : (
        <DataTable
          columns={[
            { key: "title", label: "Title" },
            {
              key: "status", label: "Status", width: 110,
              render: (val) => {
                const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
              },
            },
            { key: "owner_name", label: "Assignee", width: 130 },
            { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
            {
              key: "priority", label: "Priority", width: 100,
              render: (val) => {
                const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
              },
            },
          ]}
          data={tasks}
          onRowClick={(row) => openDrawer("task", row, refetchTasks)}
        />
      )}
    </div>
  );
}
