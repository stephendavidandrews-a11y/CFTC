"""
Project CRUD + reorder routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ReorderRequest,
)
from app.work.services import projects as svc

router = APIRouter(prefix="/projects", tags=["Work Projects"])


def _conn():
    conn = get_connection()
    attach_pipeline(conn)
    return conn


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    project_type: Optional[str] = None,
    priority_label: Optional[str] = None,
    lead_attorney_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "sort_order",
    sort_dir: Optional[str] = "asc",
):
    def _query():
        conn = _conn()
        try:
            return svc.list_projects(conn,
                status=status, project_type=project_type,
                priority_label=priority_label, lead_attorney_id=lead_attorney_id,
                search=search, sort_by=sort_by, sort_dir=sort_dir,
            )
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/by-pipeline-item/{pipeline_item_id}", response_model=ProjectResponse)
async def get_project_by_pipeline_item(pipeline_item_id: int):
    """Look up the work project linked to a pipeline item."""
    def _query():
        conn = _conn()
        try:
            result = svc.get_project_by_pipeline_item(conn, pipeline_item_id)
            if not result:
                raise HTTPException(status_code=404, detail="No project linked to this pipeline item")
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int):
    def _query():
        conn = _conn()
        try:
            result = svc.get_project(conn, project_id)
            if not result:
                raise HTTPException(status_code=404, detail="Project not found")
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate):
    def _query():
        conn = _conn()
        try:
            return svc.create_project(conn, body.model_dump())
        finally:
            conn.close()
    return await run_db(_query)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, body: ProjectUpdate):
    def _query():
        conn = _conn()
        try:
            result = svc.update_project(conn, project_id, body.model_dump(exclude_unset=True))
            if not result:
                raise HTTPException(status_code=404, detail="Project not found")
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int):
    def _query():
        conn = _conn()
        try:
            svc.delete_project(conn, project_id)
        finally:
            conn.close()
    await run_db(_query)


@router.patch("/reorder", status_code=204)
async def reorder_projects(body: ReorderRequest):
    def _query():
        conn = _conn()
        try:
            svc.reorder_projects(conn, [i.model_dump() for i in body.items])
        finally:
            conn.close()
    await run_db(_query)
