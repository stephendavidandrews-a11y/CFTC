"""Tracker writeback — converts reviewed bundle items to tracker batch operations.

Modules:
    committer       — Top-level commit orchestrator
    item_converters — Per-item-type conversion to tracker batch ops
    ordering        — Dependency ordering within a bundle
    tracker_client  — HTTP client for POST /tracker/batch
"""
