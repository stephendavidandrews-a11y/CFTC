"""
Work item CRUD, tree, reorder, move, assignments, dependencies.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import (
    WorkItemCreate, WorkItemUpdate, WorkItemResponse, WorkItemMoveRequest,
    ReorderRequest, AssignmentCreate, AssignmentResponse,
    DependencyCreate, DependencyResponse,
)
from app.work.services import items as svc

router = APIRouter(tags=["Work Items"])


def _conn():
    conn = get_connection()
    attach_pipeline(conn)
    return conn


# ── Work Items ──────────────────────────────────────────────────────

@router.get("/projects/{project_id}/items", response_model=list[WorkItemResponse])
async def get_items_tree(project_id: int):
    def _query():
        conn = _conn()
        try:
            return svc.get_items_tree(conn, project_id)
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/projects/{project_id}/items", response_model=WorkItemResponse, status_code=201)
async def create_item(project_id: int, body: WorkItemCreate):
    def _query():
        conn = _conn()
        try:
            return svc.create_item(conn, project_id, body.model_dump())
        finally:
            conn.close()
    return await run_db(_query)


@router.patch("/items/{item_id}", response_model=WorkItemResponse)
async def update_item(item_id: int, body: WorkItemUpdate):
    def _query():
        conn = _conn()
        try:
            result = svc.update_item(conn, item_id, body.model_dump(exclude_unset=True))
            if not result:
                raise HTTPException(status_code=404, detail="Work item not found")
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    def _query():
        conn = _conn()
        try:
            svc.delete_item(conn, item_id)
        finally:
            conn.close()
    await run_db(_query)


@router.patch("/items/reorder", status_code=204)
async def reorder_items(body: ReorderRequest):
    def _query():
        conn = _conn()
        try:
            svc.reorder_items(conn, [i.model_dump() for i in body.items])
        finally:
            conn.close()
    await run_db(_query)


@router.post("/items/{item_id}/move", response_model=WorkItemResponse)
async def move_item(item_id: int, body: WorkItemMoveRequest):
    def _query():
        conn = _conn()
        try:
            result = svc.move_item(conn, item_id, body.parent_id, body.project_id)
            if not result:
                raise HTTPException(status_code=404, detail="Work item not found")
            return result
        finally:
            conn.close()
    return await run_db(_query)


# ── Assignments ─────────────────────────────────────────────────────

@router.get("/items/{item_id}/assignments", response_model=list[AssignmentResponse])
async def list_assignments(item_id: int):
    def _query():
        conn = _conn()
        try:
            return svc.list_assignments(conn, item_id)
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/items/{item_id}/assignments", response_model=AssignmentResponse, status_code=201)
async def add_assignment(item_id: int, body: AssignmentCreate):
    def _query():
        conn = _conn()
        try:
            return svc.add_assignment(conn, item_id, body.team_member_id, body.role)
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/assignments/{assignment_id}", status_code=204)
async def remove_assignment(assignment_id: int):
    def _query():
        conn = _conn()
        try:
            svc.remove_assignment(conn, assignment_id)
        finally:
            conn.close()
    await run_db(_query)


@router.get("/team/{member_id}/items", response_model=list[WorkItemResponse])
async def get_member_items(member_id: int):
    def _query():
        conn = _conn()
        try:
            return svc.get_member_items(conn, member_id)
        finally:
            conn.close()
    return await run_db(_query)


# ── Dependencies ────────────────────────────────────────────────────

@router.post("/items/{item_id}/dependencies", response_model=DependencyResponse, status_code=201)
async def add_dependency(item_id: int, body: DependencyCreate):
    def _query():
        conn = _conn()
        try:
            return svc.add_dependency(conn, item_id, body.blocking_item_id)
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/dependencies/{dep_id}", status_code=204)
async def remove_dependency(dep_id: int):
    def _query():
        conn = _conn()
        try:
            svc.remove_dependency(conn, dep_id)
        finally:
            conn.close()
    await run_db(_query)
