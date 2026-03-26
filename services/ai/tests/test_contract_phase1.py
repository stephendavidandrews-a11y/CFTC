"""Contract-focused tests for Phase 1 extraction/writeback stabilization."""

import importlib.util
import sqlite3
import sys
import uuid
from pathlib import Path


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.writeback.item_converters import convert_item  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TRACKER_APP_DIR = Path(__file__).resolve().parents[2] / "tracker" / "app"
TRACKER_CONTRACTS = _load_module("tracker_contracts", TRACKER_APP_DIR / "contracts.py")
TRACKER_SCHEMA = _load_module("tracker_schema", TRACKER_APP_DIR / "schema.py")


def _tracker_columns():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    TRACKER_SCHEMA.init_schema(conn)
    TRACKER_SCHEMA.migrate_schema(conn)
    columns = {}
    for table in TRACKER_CONTRACTS.AI_WRITABLE_TABLES:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        columns[table] = {row["name"] for row in rows}
    conn.close()
    return columns


def test_converter_outputs_match_tracker_contract():
    """Representative converter output stays inside the stabilized tracker contract."""
    bundle = {
        "id": "bundle-001",
        "bundle_type": "matter",
        "target_matter_id": "matter-001",
        "_communication_id": "comm-001",
    }
    refs = {}

    items = [
        {
            "id": str(uuid.uuid4()),
            "item_type": "context_note",
            "confidence": 0.93,
            "proposed_data": {
                "title": "Leadership preference",
                "category": "policy_operating_rule",
                "body": "Major rules should come with options and deadlines.",
                "linked_entities": [
                    {
                        "entity_type": "matter",
                        "entity_id": "matter-001",
                        "relationship_role": "subject",
                    },
                    {
                        "entity_type": "organization",
                        "entity_id": "org-001",
                        "relationship_role": "source",
                    },
                ],
            },
        },
        {
            "id": str(uuid.uuid4()),
            "item_type": "person_detail_update",
            "confidence": 0.88,
            "proposed_data": {
                "person_id": "person-001",
                "fields": {
                    "education_summary": "Georgetown Law",
                    "prior_roles_summary": "SEC Division of Trading and Markets",
                    "email": "person@example.com",
                },
            },
        },
        {
            "id": str(uuid.uuid4()),
            "item_type": "meeting_record",
            "confidence": 0.95,
            "proposed_data": {
                "title": "Leadership sync",
                "date_time_start": "2026-03-19T10:00:00",
                "meeting_type": "leadership meeting",
                "participants": [{"person_id": "person-001", "meeting_role": "chair"}],
                "matter_links": [{"matter_id": "matter-002"}],
            },
        },
        {
            "id": str(uuid.uuid4()),
            "item_type": "stakeholder_addition",
            "confidence": 0.8,
            "proposed_data": {
                "organization_id": "org-001",
                "organization_role": "partner agency",
                "notes": "Coordinates on related issues.",
            },
        },
    ]

    operations = []
    for item in items:
        operations.extend(op for op, _ in convert_item(item, bundle, refs))

    columns_by_table = _tracker_columns()
    relationship_types = []
    context_link_count = 0
    saw_profile_upsert = False

    for op in operations:
        table = op["table"]
        assert table in TRACKER_CONTRACTS.AI_WRITABLE_TABLES
        data = op.get("data", {})
        assert set(data.keys()).issubset(columns_by_table[table])

        for column, enum_name in TRACKER_CONTRACTS.AI_WRITABLE_ENUM_COLUMNS.get(
            table, {}
        ).items():
            value = data.get(column)
            if value is not None:
                assert value in TRACKER_CONTRACTS.ENUMS[enum_name]

        if table == "meeting_matters":
            relationship_types.append(data["relationship_type"])
        if table == "context_note_links":
            context_link_count += 1
        if table == "person_profiles":
            assert op["_meta"]["upsert_by"] == "person_id"
            saw_profile_upsert = True
        if table == "matter_organizations":
            assert "engagement_level" not in data

    assert "primary topic" in relationship_types
    assert "secondary topic" in relationship_types
    assert context_link_count == 2
    assert saw_profile_upsert is True
