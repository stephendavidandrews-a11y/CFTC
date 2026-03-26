"""Fix schema.py DDL to match the post-Phase-4 column structure.

Run on Mac Mini:
    cd /Users/stephen/Documents/Website/cftc/services/tracker/app
    python3 /Users/stephen/Documents/Website/cftc/scripts/fix_schema_ddl.py
"""
import re

SCHEMA_PATH = "/Users/stephen/Documents/Website/cftc/services/tracker/app/schema.py"

with open(SCHEMA_PATH, "r") as f:
    content = f.read()

original_len = len(content)

# 1. Remove obsolete index lines from INDEXES list
obsolete_indexes = [
    "idx_matters_decision_deadline",
    "idx_matters_revisit_date",
    "idx_matters_rin",
    "idx_matters_regulatory_stage",
    "idx_matters_docket_number",
]
for idx_name in obsolete_indexes:
    pattern = re.compile(r'^\s*"CREATE INDEX.*' + re.escape(idx_name) + r'.*;\s*",?\s*\n', re.MULTILINE)
    content = pattern.sub("", content)

# 2. Remove dropped column lines from CREATE TABLE matters
dropped_col_patterns = [
    r"\s*problem_statement TEXT,\s*\n",
    r"\s*why_it_matters TEXT,\s*\n",
    r"\s*risk_level TEXT,\s*\n",
    r"\s*boss_involvement_level TEXT NOT NULL,\s*\n",
    r"\s*supervisor_person_id TEXT REFERENCES people\(id\),\s*\n",
    r"\s*requesting_organization_id TEXT REFERENCES organizations\(id\),\s*\n",
    r"\s*reviewing_organization_id TEXT REFERENCES organizations\(id\),\s*\n",
    r"\s*lead_external_org_id TEXT REFERENCES organizations\(id\),\s*\n",
    r"\s*decision_deadline TEXT,\s*\n",
    r"\s*revisit_date TEXT,\s*\n",
    r"\s*next_step_assigned_to_person_id TEXT REFERENCES people\(id\),\s*\n",
    r"\s*pending_decision TEXT,\s*\n",
    r"\s*-- Regulatory metadata\s*\n",
    r"\s*rin TEXT,\s*\n",
    r"\s*regulatory_stage TEXT,\s*\n",
    r"\s*federal_register_citation TEXT,\s*\n",
    r"\s*unified_agenda_priority TEXT,\s*\n",
    r"\s*cfr_citation TEXT,\s*\n",
    r"\s*docket_number TEXT,\s*\n",
    r"\s*fr_doc_number TEXT,\s*\n",
]

for pat in dropped_col_patterns:
    content = re.sub(pat, "", content, count=1)

# 3. Add blocker column to CREATE TABLE if not present
# Find the matters CREATE TABLE and check if blocker is there
matters_ddl_match = re.search(r"CREATE TABLE IF NOT EXISTS matters \(.*?\)", content, re.DOTALL)
if matters_ddl_match:
    matters_ddl = matters_ddl_match.group()
    if "blocker" not in matters_ddl:
        # Insert blocker before "-- Source & automation" or before "source TEXT"
        content = content.replace(
            "        -- Source & automation\n        source TEXT",
            "        blocker TEXT,\n        -- Source & automation\n        source TEXT",
            1,
        )
        print("Added blocker column to CREATE TABLE matters")
    else:
        print("blocker already in CREATE TABLE")
else:
    print("WARNING: Could not find matters CREATE TABLE DDL")

# 4. Verify
try:
    compile(content, "schema.py", "exec")
    print("Compile check: OK")
except SyntaxError as e:
    print(f"COMPILE ERROR: {e}")
    exit(1)

with open(SCHEMA_PATH, "w") as f:
    f.write(content)

print(f"schema.py updated: {original_len} -> {len(content)} chars ({original_len - len(content)} removed)")
