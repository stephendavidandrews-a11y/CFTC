"""
Template CRUD routes.
"""

from fastapi import APIRouter
from typing import List

from app.work.db import get_connection
from app.pipeline.db_async import run_db

router = APIRouter(prefix="/templates", tags=["Work Templates"])


def _conn():
    return get_connection()


@router.get("/{project_type}")
async def get_templates(project_type: str):
    def _query():
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT * FROM project_type_templates WHERE project_type = ? ORDER BY item_sort_order",
                (project_type,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)


@router.put("/{project_type}")
async def replace_templates(project_type: str, body: List[dict]):
    def _query():
        conn = _conn()
        try:
            conn.execute("DELETE FROM project_type_templates WHERE project_type = ?", (project_type,))
            for i, item in enumerate(body):
                conn.execute(
                    "INSERT INTO project_type_templates (project_type, item_title, item_description, item_sort_order, parent_ref) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (project_type, item.get("item_title"), item.get("item_description"),
                     item.get("item_sort_order", i), item.get("parent_ref"))
                )
            conn.commit()
            rows = conn.execute(
                "SELECT * FROM project_type_templates WHERE project_type = ? ORDER BY item_sort_order",
                (project_type,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)
