"""Bundle review service — business logic for the human review gate.

This package contains the core logic for bundle review, separated from
the FastAPI router layer. All public functions accept a db connection
as their first argument (no framework dependencies), making them
reusable from Phase 5 writeback and testable in isolation.

Modules:
    models      — Pydantic request models + status constants
    guards      — State checks and DB lookups (check_review_state, get_bundle, get_item)
    audit       — review_action_log writer
    validation  — proposed_data validation, completion blockers
    item_actions    — accept/reject/edit/restore/add items
    bundle_actions  — accept/reject/edit bundles, accept-all
    restructure     — move item, create bundle, merge bundles
    retrieval       — queue listing, full detail with suppression visibility
    completion      — review completion + pipeline resume
"""
