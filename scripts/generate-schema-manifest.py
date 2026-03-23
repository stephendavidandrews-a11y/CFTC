#!/usr/bin/env python3
"""
Generate a JSON schema manifest for the CFTC Command Center.

Parses CREATE TABLE statements from all service schema files, extracts
column metadata, relationships, and enum mappings, then writes a
structured JSON manifest for the frontend.

Usage:
    python3 scripts/generate-schema-manifest.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_SOURCES = {
    "tracker": REPO_ROOT / "services" / "tracker" / "app" / "schema.py",
    "ai": REPO_ROOT / "services" / "ai" / "app" / "schema.py",
    "intake": REPO_ROOT / "services" / "intake" / "db" / "schema.py",
}

LOOKUPS_PATH = REPO_ROOT / "services" / "tracker" / "app" / "routers" / "lookups.py"
OUTPUT_PATH = REPO_ROOT / "frontend" / "src" / "data" / "schema-manifest.json"

SERVICE_META = {
    "tracker": {"port": 8004, "db": "tracker.db", "tech": "FastAPI + SQLite (WAL)"},
    "ai": {"port": 8006, "db": "ai.db", "tech": "FastAPI + SQLite (WAL)"},
    "intake": {"port": 8005, "db": "intake.db", "tech": "FastAPI + SQLite (WAL) — native/GPU"},
}

# ---------------------------------------------------------------------------
# Enum extraction
# ---------------------------------------------------------------------------

def parse_enums(path: Path) -> dict[str, list[str]]:
    """Parse the ENUMS dict from lookups.py using regex."""
    text = path.read_text(encoding="utf-8")

    # Find the ENUMS = { ... } block
    m = re.search(r"ENUMS\s*=\s*\{", text)
    if not m:
        print("WARNING: Could not find ENUMS dict in lookups.py", file=sys.stderr)
        return {}

    # Find matching closing brace
    start = m.start()
    depth = 0
    end = start
    for i in range(m.end() - 1, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    enums_text = text[start:end]

    enums = {}
    # Match each key: [...] pair
    for key_match in re.finditer(r'"(\w+)"\s*:\s*\[', enums_text):
        key = key_match.group(1)
        # Find the closing bracket for this list
        list_start = key_match.end() - 1
        bracket_depth = 0
        list_end = list_start
        for i in range(list_start, len(enums_text)):
            if enums_text[i] == "[":
                bracket_depth += 1
            elif enums_text[i] == "]":
                bracket_depth -= 1
                if bracket_depth == 0:
                    list_end = i + 1
                    break
        list_text = enums_text[list_start:list_end]
        values = re.findall(r'"([^"]*)"', list_text)
        enums[key] = values

    return enums


# ---------------------------------------------------------------------------
# SQL parsing
# ---------------------------------------------------------------------------

def extract_table_sql_blocks(path: Path, service: str) -> list[tuple[str, str]]:
    """Extract (table_name, CREATE TABLE sql) tuples from a schema file."""
    text = path.read_text(encoding="utf-8")
    results = []

    # Find CREATE TABLE headers, then balance parentheses to get the full body
    header_pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\(",
        re.IGNORECASE,
    )

    for hm in header_pattern.finditer(text):
        table_name = hm.group(1)
        # Balance parentheses starting from the opening '('
        paren_start = hm.end() - 1  # position of '('
        depth = 0
        body_end = paren_start
        for i in range(paren_start, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break
        body = text[paren_start + 1 : body_end]
        results.append((table_name, body))

    return results


def extract_index_columns(path: Path, service: str) -> dict[str, set[str]]:
    """Parse CREATE INDEX statements to build table -> {indexed_columns} map."""
    text = path.read_text(encoding="utf-8")
    idx_map: dict[str, set[str]] = {}

    # Match: CREATE [UNIQUE] INDEX ... ON table_name(col1[, col2, ...])
    pattern = re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+\w+\s+ON\s+(\w+)\(([^)]+)\)",
        re.IGNORECASE,
    )

    for m in pattern.finditer(text):
        table = m.group(1)
        cols = [c.strip() for c in m.group(2).split(",")]
        if table not in idx_map:
            idx_map[table] = set()
        for c in cols:
            idx_map[table].add(c)

    return idx_map


def extract_migration_columns(path: Path) -> dict[str, list[tuple[str, str]]]:
    """Parse ALTER TABLE ... ADD COLUMN from migration functions.

    Returns: {table_name: [(col_name, col_def), ...]}
    """
    text = path.read_text(encoding="utf-8")
    result: dict[str, list[tuple[str, str]]] = {}

    # Match patterns like:
    #   ALTER TABLE team_members ADD COLUMN background_summary TEXT
    #   f"ALTER TABLE team_members ADD COLUMN {col_name} {col_def}"
    # The latter uses dict iteration, so we parse the dict instead.

    # Strategy: find dicts of new columns like:
    #   new_tm_cols = { "col_name": "TEXT DEFAULT 'foo'", ... }
    # and the table they apply to from context (ALTER TABLE <table> ADD COLUMN)

    # First, try direct ALTER TABLE statements
    direct_pattern = re.compile(
        r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)\s+(.+?)(?:["\']|$)',
        re.IGNORECASE,
    )
    for m in direct_pattern.finditer(text):
        table = m.group(1)
        col_name = m.group(2)
        col_def = m.group(3).strip().rstrip('"\')')
        if table not in result:
            result[table] = []
        result[table].append((col_name, col_def))

    # Second, parse dict-based migration patterns
    # Find blocks like: new_XX_cols = { "col": "DEF", ... }
    # followed by: ALTER TABLE <table> ADD COLUMN {col_name} {col_def}
    dict_pattern = re.compile(
        r'(new_\w+_cols)\s*=\s*\{([^}]+)\}',
        re.DOTALL,
    )
    alter_pattern = re.compile(
        r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+\{(\w+)\}\s+\{(\w+)\}',
        re.IGNORECASE,
    )

    for dm in dict_pattern.finditer(text):
        dict_name = dm.group(1)
        dict_body = dm.group(2)

        # Parse dict entries: "col_name": "TYPE DEFAULT ..."
        entries = re.findall(r'"(\w+)"\s*:\s*"([^"]*)"', dict_body)

        # Find which table this applies to by looking for ALTER TABLE nearby
        # Look in the ~500 chars after the dict definition
        search_region = text[dm.end():dm.end() + 500]
        table_match = re.search(r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN', search_region, re.IGNORECASE)
        if table_match:
            table = table_match.group(1)
            if table not in result:
                result[table] = []
            for col_name, col_def in entries:
                # Avoid duplicates
                existing_names = {c[0] for c in result[table]}
                if col_name not in existing_names:
                    result[table].append((col_name, col_def))

    return result


def parse_column_line(line: str) -> dict | None:
    """Parse a single column definition line from a CREATE TABLE body.

    Returns dict with: name, type, pk, fk_target, not_null, default, unique
    or None if the line is not a column definition.
    """
    line = line.strip().rstrip(",")
    if not line:
        return None

    # Skip table-level constraints
    upper = line.upper().lstrip()
    if upper.startswith(("PRIMARY KEY", "UNIQUE(", "UNIQUE (", "FOREIGN KEY", "CHECK", "CONSTRAINT")):
        return None

    # Column pattern: name TYPE [constraints...]
    m = re.match(r"(\w+)\s+(TEXT|INTEGER|REAL|BLOB|NUMERIC|BOOLEAN|DATETIME)(\b.*)?", line, re.IGNORECASE)
    if not m:
        return None

    col_name = m.group(1)
    col_type = m.group(2).upper()
    rest = m.group(3) or ""

    result = {
        "name": col_name,
        "type": col_type,
        "pk": False,
        "autoincrement": False,
        "fk_target": None,
        "not_null": False,
        "default": None,
        "unique": False,
    }

    rest_upper = rest.upper()

    if "PRIMARY KEY" in rest_upper:
        result["pk"] = True
        result["not_null"] = True
    if "AUTOINCREMENT" in rest_upper:
        result["autoincrement"] = True
    if "NOT NULL" in rest_upper:
        result["not_null"] = True
    if "UNIQUE" in rest_upper:
        result["unique"] = True

    # REFERENCES table(column)
    fk_match = re.search(r"REFERENCES\s+(\w+)\((\w+)\)", rest, re.IGNORECASE)
    if fk_match:
        result["fk_target"] = f"{fk_match.group(1)}.{fk_match.group(2)}"

    # DEFAULT value
    default_match = re.search(r"DEFAULT\s+(.+?)(?:\s+(?:NOT|UNIQUE|REFERENCES|ON|CHECK)|$)", rest, re.IGNORECASE)
    if default_match:
        val = default_match.group(1).strip().rstrip(",")
        # Clean up
        if val.startswith("(") and val.endswith(")"):
            val = val[1:-1]
        result["default"] = val

    return result


def parse_table_body(body: str) -> list[dict]:
    """Parse column definitions from a CREATE TABLE body."""
    columns = []
    table_pk_cols = set()

    # Split by lines
    lines = body.split("\n")
    for line in lines:
        stripped = line.strip().rstrip(",")
        if not stripped:
            continue

        # Check for table-level PRIMARY KEY
        pk_match = re.match(r"PRIMARY\s+KEY\s*\(([^)]+)\)", stripped, re.IGNORECASE)
        if pk_match:
            for pk_col in pk_match.group(1).split(","):
                table_pk_cols.add(pk_col.strip())
            continue

        col = parse_column_line(stripped)
        if col:
            columns.append(col)

    # Apply table-level PK
    for col in columns:
        if col["name"] in table_pk_cols:
            col["pk"] = True
            col["not_null"] = True

    return columns


def build_field(
    col: dict,
    enum_keys: set[str],
    indexed_cols: set[str],
) -> dict:
    """Build a field descriptor dict from a parsed column."""
    tags = []
    notes = []

    if col["pk"]:
        tags.append("PK")
    if col["fk_target"]:
        tags.append("FK")

    # ENUM check (case-insensitive match against enum keys)
    col_lower = col["name"].lower()
    if col_lower in enum_keys:
        tags.append("ENUM")

    # BOOL check
    if col["type"] in ("INTEGER", "BOOLEAN") and (
        col_lower.startswith("is_") or col_lower.startswith("has_")
        or col_lower.endswith("_confirmed") or col_lower == "confirmed"
        or col_lower == "user_corrected"
        or col.get("default") in ("0", "1")
    ):
        tags.append("BOOL")

    # Timestamp check
    if col_lower in ("created_at", "updated_at", "captured_at") or (
        col.get("default") and "datetime('now')" in str(col.get("default", ""))
    ):
        tags.append("TS")

    # Index check
    if col["name"] in indexed_cols:
        tags.append("IDX")

    # JSON check
    default_str = str(col.get("default", "") or "")
    if default_str in ("'[]'", "'{}'" , "[]", "{}") or (
        col["type"] == "TEXT" and col_lower in (
            "external_refs", "specializations", "areas_of_focus",
            "topics", "key_dates", "linked_pipeline_ids",
            "strengths", "growth_areas", "recent_wins",
            "name_variations", "tags", "changed_fields",
            "old_values", "new_values", "word_timestamps",
            "topic_segments_json", "source_metadata", "sensitivity_flags",
            "source_locator_json", "proposed_matter_json", "proposed_data",
            "original_proposed_data", "written_data", "previous_data",
            "vocal_quality_json", "candidate_list", "alert_data",
            "overlap_regions_json", "tracker_response", "details",
            "tracker_context_snapshot", "config_json",
        )
    ):
        tags.append("JSON")

    # Build note
    if col["not_null"] and not col["pk"]:
        notes.append("NOT NULL")
    if col["unique"]:
        notes.append("UNIQUE")
    if col.get("default") is not None:
        notes.append(f"DEFAULT {col['default']}")
    if col["fk_target"]:
        notes.append(f"REFERENCES {col['fk_target']}")
    if col["pk"] and col["autoincrement"]:
        notes.append("AUTOINCREMENT")
    elif col["pk"] and col["type"] == "TEXT":
        notes.append("UUID")

    field = {
        "name": col["name"],
        "type": col["type"],
        "tags": tags,
        "not_null": col["not_null"] or col["pk"],
    }
    if notes:
        field["note"] = "; ".join(notes)
    if col.get("default") is not None:
        field["default"] = col["default"]

    return field


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Parse enums
    print("Parsing enums from lookups.py...")
    enums = parse_enums(LOOKUPS_PATH)
    enum_keys = {k.lower() for k in enums}
    print(f"  Found {len(enums)} enum definitions")

    # 2. Parse all schemas
    all_tables = []  # list of (service, table_name, columns)
    all_relationships = []
    service_table_counts = {}

    for service, schema_path in SCHEMA_SOURCES.items():
        print(f"\nParsing {service} schema from {schema_path.name}...")

        if not schema_path.exists():
            print(f"  WARNING: {schema_path} not found, skipping", file=sys.stderr)
            continue

        # Extract tables
        table_blocks = extract_table_sql_blocks(schema_path, service)
        # Extract indexes
        idx_map = extract_index_columns(schema_path, service)
        # Extract migration columns
        migration_cols = extract_migration_columns(schema_path)

        count = 0
        for table_name, body in table_blocks:
            columns = parse_table_body(body)

            # Apply migration columns
            if table_name in migration_cols:
                existing_names = {c["name"] for c in columns}
                for col_name, col_def in migration_cols[table_name]:
                    if col_name not in existing_names:
                        # Parse the migration column definition
                        # Format: TYPE [DEFAULT ...]
                        mig_line = f"{col_name} {col_def}"
                        mig_col = parse_column_line(mig_line)
                        if mig_col:
                            columns.append(mig_col)

            indexed_cols = idx_map.get(table_name, set())

            fields = []
            for col in columns:
                field = build_field(col, enum_keys, indexed_cols)
                fields.append(field)

                # Collect relationships
                if col["fk_target"]:
                    target_table, target_col = col["fk_target"].split(".")
                    all_relationships.append({
                        "from": table_name,
                        "fromField": col["name"],
                        "to": target_table,
                        "toField": target_col,
                        "label": "FK",
                    })

            all_tables.append({
                "name": table_name,
                "service": service,
                "fields": fields,
            })
            count += 1

        service_table_counts[service] = count
        print(f"  Found {count} tables, {len(idx_map)} indexed tables, {len(migration_cols)} migration targets")

    # 3. Build output
    services = {}
    for svc, meta in SERVICE_META.items():
        services[svc] = {
            "tables": service_table_counts.get(svc, 0),
            **meta,
        }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services": services,
        "tables": all_tables,
        "relationships": all_relationships,
        "enums": enums,
    }

    # 4. Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nSchema manifest written to {OUTPUT_PATH}")
    print(f"\nSummary:")
    print(f"  Total tables: {len(all_tables)}")
    for svc, count in service_table_counts.items():
        print(f"    {svc}: {count} tables")
    print(f"  Total relationships: {len(all_relationships)}")
    print(f"  Total enums: {len(enums)}")


if __name__ == "__main__":
    main()
