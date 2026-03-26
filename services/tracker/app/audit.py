"""Audit logging helper for tracker mutations."""

import json


def log_event(
    db, *, table_name, record_id, action, source="human", old_record=None, new_data=None
):
    """Log a mutation to system_events. Call within the same transaction."""
    changed_fields = None
    old_values = None
    new_values = None

    if action == "update" and old_record and new_data:
        old_dict = dict(old_record) if hasattr(old_record, "keys") else old_record
        changes = {}
        olds = {}
        for k, v in new_data.items():
            if k in ("updated_at", "last_material_update_at"):
                continue
            old_val = old_dict.get(k)
            if old_val != v:
                changes[k] = v
                olds[k] = old_val
        if changes:
            changed_fields = json.dumps(list(changes.keys()))
            old_values = json.dumps(olds, default=str)
            new_values = json.dumps(changes, default=str)
        else:
            changed_fields = json.dumps([])

    elif action == "create" and new_data:
        data = new_data if isinstance(new_data, dict) else {}
        changed_fields = json.dumps(list(data.keys()))
        new_values = json.dumps(data, default=str)

    elif action == "delete" and old_record:
        old_dict = dict(old_record) if hasattr(old_record, "keys") else old_record
        old_values = json.dumps(old_dict, default=str)

    db.execute(
        """
        INSERT INTO system_events (table_name, record_id, action, source,
            changed_fields, old_values, new_values)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (table_name, record_id, action, source, changed_fields, old_values, new_values),
    )
