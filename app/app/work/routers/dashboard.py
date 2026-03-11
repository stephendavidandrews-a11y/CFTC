"""
Dashboard aggregation and bottleneck routes.
"""

from fastapi import APIRouter
from datetime import datetime, timedelta

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import DashboardResponse, BottleneckResponse, ProjectTypeResponse

router = APIRouter(tags=["Work Dashboard"])


def _conn():
    conn = get_connection()
    attach_pipeline(conn)
    return conn


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    def _query():
        conn = _conn()
        try:
            # Active projects by type
            rows = conn.execute(
                "SELECT project_type, COUNT(*) as cnt FROM projects "
                "WHERE status = 'active' GROUP BY project_type"
            ).fetchall()
            by_type = {r["project_type"]: r["cnt"] for r in rows}

            # Work items by status
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM work_items "
                "JOIN projects ON work_items.project_id = projects.id "
                "WHERE projects.status = 'active' GROUP BY work_items.status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in rows}

            # Overdue items
            today = datetime.utcnow().strftime("%Y-%m-%d")
            overdue = conn.execute(
                "SELECT COUNT(*) as cnt FROM work_items "
                "WHERE due_date < ? AND status NOT IN ('completed')",
                (today,)
            ).fetchone()["cnt"]

            # Blocked items
            blocked = conn.execute(
                "SELECT COUNT(*) as cnt FROM work_items WHERE status = 'blocked'"
            ).fetchone()["cnt"]

            # Upcoming deadlines (next 14 days)
            future = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
            deadline_rows = conn.execute(
                "SELECT wi.id, wi.title, wi.due_date, wi.status, wi.project_id, p.title as project_title "
                "FROM work_items wi JOIN projects p ON wi.project_id = p.id "
                "WHERE wi.due_date BETWEEN ? AND ? AND wi.status != 'completed' "
                "ORDER BY wi.due_date ASC LIMIT 20",
                (today, future)
            ).fetchall()
            upcoming = [dict(r) for r in deadline_rows]

            # Task summary
            task_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
            ).fetchall()
            task_summary = {r["status"]: r["cnt"] for r in task_rows}
            overdue_tasks = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks "
                "WHERE due_date < ? AND status NOT IN ('done', 'deferred')",
                (today,)
            ).fetchone()["cnt"]
            task_summary["overdue"] = overdue_tasks

            return {
                "active_projects_by_type": by_type,
                "total_work_items_by_status": by_status,
                "overdue_items": overdue,
                "blocked_items": blocked,
                "upcoming_deadlines": upcoming,
                "task_summary": task_summary,
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/dashboard/bottlenecks", response_model=BottleneckResponse)
async def get_bottlenecks():
    def _query():
        conn = _conn()
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")

            # Blocked items
            blocked_rows = conn.execute(
                "SELECT wi.id, wi.title, wi.blocked_reason, wi.project_id, p.title as project_title "
                "FROM work_items wi JOIN projects p ON wi.project_id = p.id "
                "WHERE wi.status = 'blocked' ORDER BY wi.updated_at DESC"
            ).fetchall()

            # Unassigned active items
            unassigned_rows = conn.execute(
                "SELECT wi.id, wi.title, wi.project_id, p.title as project_title "
                "FROM work_items wi JOIN projects p ON wi.project_id = p.id "
                "LEFT JOIN work_item_assignments wia ON wi.id = wia.work_item_id "
                "WHERE wia.id IS NULL AND wi.status IN ('not_started', 'in_progress', 'in_review') "
                "AND p.status = 'active' ORDER BY wi.due_date ASC NULLS LAST"
            ).fetchall()

            # Overdue items
            overdue_rows = conn.execute(
                "SELECT wi.id, wi.title, wi.due_date, wi.project_id, p.title as project_title "
                "FROM work_items wi JOIN projects p ON wi.project_id = p.id "
                "WHERE wi.due_date < ? AND wi.status NOT IN ('completed') "
                "ORDER BY wi.due_date ASC",
                (today,)
            ).fetchall()

            # Overloaded attorneys (more than 5 active items)
            overloaded = []
            try:
                attorney_rows = conn.execute(
                    "SELECT wia.team_member_id, COUNT(*) as cnt "
                    "FROM work_item_assignments wia "
                    "JOIN work_items wi ON wia.work_item_id = wi.id "
                    "WHERE wi.status IN ('in_progress', 'in_review') "
                    "GROUP BY wia.team_member_id HAVING cnt > 5"
                ).fetchall()
                for ar in attorney_rows:
                    try:
                        member = conn.execute(
                            "SELECT name FROM pipeline.team_members WHERE id = ?",
                            (ar["team_member_id"],)
                        ).fetchone()
                        overloaded.append({
                            "team_member_id": ar["team_member_id"],
                            "name": member["name"] if member else "Unknown",
                            "active_items": ar["cnt"],
                        })
                    except Exception:
                        pass
            except Exception:
                pass

            return {
                "blocked_items": [dict(r) for r in blocked_rows],
                "unassigned_items": [dict(r) for r in unassigned_rows],
                "overdue_items": [dict(r) for r in overdue_rows],
                "overloaded_attorneys": overloaded,
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/types", response_model=list[ProjectTypeResponse])
async def list_types():
    def _query():
        conn = _conn()
        try:
            rows = conn.execute("SELECT * FROM project_types ORDER BY sort_order").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/types", response_model=ProjectTypeResponse, status_code=201)
async def create_type(body: dict):
    def _query():
        conn = _conn()
        try:
            max_sort = conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM project_types").fetchone()[0]
            conn.execute(
                "INSERT INTO project_types (type_key, label, description, sort_order) VALUES (?, ?, ?, ?)",
                (body.get("type_key"), body.get("label"), body.get("description"), max_sort + 1)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM project_types WHERE type_key = ?", (body.get("type_key"),)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()
    return await run_db(_query)
