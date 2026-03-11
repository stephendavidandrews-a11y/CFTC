"""
Personal task CRUD routes.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import TaskCreate, TaskUpdate, TaskResponse
from app.work.services import tasks as svc

router = APIRouter(prefix="/tasks", tags=["Work Tasks"])


def _conn():
    conn = get_connection()
    attach_pipeline(conn)
    return conn


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    priority_label: Optional[str] = None,
    project_id: Optional[int] = None,
    linked_member_id: Optional[int] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    tags: Optional[str] = None,
):
    def _query():
        conn = _conn()
        try:
            return svc.list_tasks(conn,
                status=status, priority_label=priority_label,
                project_id=project_id, linked_member_id=linked_member_id,
                due_before=due_before, due_after=due_after, tags=tags,
            )
        finally:
            conn.close()
    return await run_db(_query)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreate):
    def _query():
        conn = _conn()
        try:
            return svc.create_task(conn, body.model_dump())
        finally:
            conn.close()
    return await run_db(_query)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, body: TaskUpdate):
    def _query():
        conn = _conn()
        try:
            result = svc.update_task(conn, task_id, body.model_dump(exclude_unset=True))
            if not result:
                raise HTTPException(status_code=404, detail="Task not found")
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int):
    def _query():
        conn = _conn()
        try:
            svc.delete_task(conn, task_id)
        finally:
            conn.close()
    await run_db(_query)
