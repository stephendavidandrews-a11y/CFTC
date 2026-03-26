"""Pydantic request models and status constants for bundle review."""

from typing import Optional
from pydantic import BaseModel

# ── Status constants ──────────────────────────────────────────────────

# States where bundle review is accessible
BUNDLE_REVIEW_STATES = {"awaiting_bundle_review", "bundle_review_in_progress"}

# Terminal statuses for bundles and items
BUNDLE_TERMINAL = {"accepted", "rejected"}
ITEM_TERMINAL = {"accepted", "rejected", "edited", "moved"}


# ── Request models ────────────────────────────────────────────────────


class AcceptBundleRequest(BaseModel):
    bundle_id: str


class RejectBundleRequest(BaseModel):
    bundle_id: str
    reason: Optional[str] = None


class EditBundleRequest(BaseModel):
    bundle_id: str
    target_matter_id: Optional[str] = None
    target_matter_title: Optional[str] = None
    bundle_type: Optional[str] = None
    intelligence_notes: Optional[str] = None
    rationale: Optional[str] = None


class AcceptItemRequest(BaseModel):
    bundle_id: str
    item_id: str


class RejectItemRequest(BaseModel):
    bundle_id: str
    item_id: str
    reason: Optional[str] = None


class EditItemRequest(BaseModel):
    bundle_id: str
    item_id: str
    proposed_data: dict


class RestoreItemRequest(BaseModel):
    bundle_id: str
    item_id: str


class AddItemRequest(BaseModel):
    bundle_id: str
    item_type: str
    proposed_data: dict
    rationale: Optional[str] = "Reviewer-created item"
    source_excerpt: Optional[str] = None
    source_start_time: Optional[float] = None
    source_end_time: Optional[float] = None


class MoveItemRequest(BaseModel):
    item_id: str
    from_bundle_id: str
    to_bundle_id: str


class CreateBundleRequest(BaseModel):
    bundle_type: str = "standalone"
    target_matter_id: Optional[str] = None
    target_matter_title: Optional[str] = None
    rationale: Optional[str] = "Reviewer-created bundle"
    intelligence_notes: Optional[str] = None


class MergeBundlesRequest(BaseModel):
    source_bundle_id: str
    target_bundle_id: str
