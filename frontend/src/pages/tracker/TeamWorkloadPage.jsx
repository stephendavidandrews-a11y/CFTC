import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listPeople, listTasks } from "../../api/tracker";

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 24 };

export default function TeamWorkloadPage() {
  const navigate = useNavigate();
  const { data: peopleData, loading: loadingPeople } = useApi(
    () => listPeople({ limit: 500 }),
    []
  );
  const { data: tasksData, loading: loadingTasks } = useApi(
    () => listTasks({ limit: 2000 }),
    []
  );

  const loading = loadingPeople || loadingTasks;

  const teamMembers = useMemo(() => {
    const people = peopleData?.items || peopleData || [];
    const tasks = tasksData?.items || tasksData || [];

    // Filter to team workload people
    const team = people.filter((p) => p.include_in_team_workload);

    const now = new Date();

    return team.map((person) => {
      const personTasks = tasks.filter(
        (t) => (t.assigned_to_person_id === person.id) &&
               t.status !== "done" && t.status !== "deferred"
      );
      const overdue = personTasks.filter((t) => t.due_date && new Date(t.due_date) < now);

      return {
        ...person,
        fullName: person.full_name || `${person.first_name || ""} ${person.last_name || ""}`.trim(),
        activeTasks: personTasks.length,
        overdueTasks: overdue.length,
      };
    }).sort((a, b) => b.activeTasks - a.activeTasks);
  }, [peopleData, tasksData]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading team workload...</div>;
  }

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Team Workload</div>
      <div style={subtitleStyle}>Active task distribution across team members</div>

      {teamMembers.length === 0 ? (
        <div style={{ ...cardStyle, textAlign: "center", color: theme.text.faint, fontSize: 13, padding: 40 }}>
          No team members with workload tracking enabled.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280, 1fr))", gap: 16 }}>
          {teamMembers.map((member) => (
            <div key={member.id} style={{ ...cardStyle, cursor: "pointer" }}
              onClick={() => navigate(`/tasks?assigned_to=${member.id}`)}
              title={`View ${member.fullName}'s tasks`}
            >
              <div style={{ fontSize: 15, fontWeight: 600, color: theme.text.primary, marginBottom: 2 }}>
                {member.fullName}
              </div>
              <div style={{ fontSize: 12, color: theme.text.faint, marginBottom: 16 }}>
                {member.title || "No title"}
              </div>

              <div style={{ display: "flex", gap: 16 }}>
                <div>
                  <div style={{
                    fontSize: 24, fontWeight: 700,
                    color: member.activeTasks > 0 ? theme.accent.blue : theme.text.ghost,
                  }}>
                    {member.activeTasks}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>Active Tasks</div>
                </div>
                <div>
                  <div style={{
                    fontSize: 24, fontWeight: 700,
                    color: member.overdueTasks > 0 ? theme.accent.red : theme.text.ghost,
                  }}>
                    {member.overdueTasks}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>Overdue</div>
                </div>
              </div>

              {/* Simple load indicator bar */}
              <div style={{
                marginTop: 14, height: 4, borderRadius: 2,
                background: theme.bg.input, overflow: "hidden",
              }}>
                <div style={{
                  width: `${Math.min(member.activeTasks * 10, 100)}%`,
                  height: "100%",
                  borderRadius: 2,
                  background: member.overdueTasks > 0
                    ? theme.accent.red
                    : member.activeTasks > 7
                      ? theme.accent.yellow
                      : theme.accent.blue,
                  transition: "width 0.3s ease",
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
