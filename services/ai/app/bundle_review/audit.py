"""Review action audit trail for bundle review.

Writes to review_action_log with bundle_id and item_id foreign keys.
All entries are attributed to 'user' actor (multi-user auth is future work).
"""

import json
import uuid as uuid_mod


def write_audit(db, communication_id: str, bundle_id: str | None,
                item_id: str | None, action_type: str, details: dict):
    """Write a single review_action_log entry.

    Args:
        db: sqlite3 connection
        communication_id: required FK
        bundle_id: optional FK (None for communication-level actions)
        item_id: optional FK (None for bundle-level actions)
        action_type: e.g. 'accept_item', 'move_item', 'complete_bundle_review'
        details: dict serialized to JSON (old_state, new_state, context)
    """
    db.execute("""
        INSERT INTO review_action_log
            (id, actor, communication_id, bundle_id, item_id, action_type, details)
        VALUES (?, 'user', ?, ?, ?, ?, ?)
    """, (str(uuid_mod.uuid4()), communication_id, bundle_id, item_id,
          action_type, json.dumps(details, default=str)))
