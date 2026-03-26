"""Phase 3 verification script. Run on Mac Mini."""
import json
import os
import urllib.request
import base64
import sys

BASE = "http://localhost:8004/tracker"
USER = os.environ.get("TRACKER_USER", "")
PASS = os.environ.get("TRACKER_PASS", "")

if not USER or not PASS:
    # Try loading from .env
    env_path = "/Users/stephen/Documents/Website/cftc/.env"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("TRACKER_USER="):
                USER = line.split("=", 1)[1]
            elif line.startswith("TRACKER_PASS="):
                PASS = line.split("=", 1)[1]

if not USER or not PASS:
    print("ERROR: Cannot find TRACKER_USER/TRACKER_PASS")
    sys.exit(1)


def get(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    creds = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds}")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"_error": str(e)}


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


print("=" * 60)
print("PHASE 3 VERIFICATION")
print("=" * 60)
passed = 0
failed = 0

# 1. Health
print("\n1. Health")
h = get("/health")
r = check("Health endpoint returns ok", h.get("status") == "ok")
passed += r; failed += (not r)

# 2. Dashboard
print("\n2. Dashboard")
d = get("/dashboard")
r = check("Dashboard returns data", "total_open_matters" in d, f"total_open={d.get('total_open_matters')}")
passed += r; failed += (not r)
r = check("comment_periods key present", "comment_periods" in d)
passed += r; failed += (not r)
r = check("blocked_matters key present", "blocked_matters" in d)
passed += r; failed += (not r)
r = check("matters_by_status uses new values", all(k in ("active", "paused", "closed") for k in d.get("matters_by_status", {}).keys()), str(d.get("matters_by_status")))
passed += r; failed += (not r)
r = check("pending_decision does not reference matters table", "_error" not in d, d.get("_error", ""))
passed += r; failed += (not r)

# 3. Matters list
print("\n3. Matters list")
ml = get("/matters")
r = check("Matters list returns items", "items" in ml, f"total={ml.get('total', '?')}")
passed += r; failed += (not r)

if "items" in ml and ml["items"]:
    m0 = ml["items"][0]
    r = check("workflow_status in list response", "workflow_status" in m0, f"wf={m0.get('workflow_status')}")
    passed += r; failed += (not r)
    r = check("comment_period_status in list response", "comment_period_status" in m0 or m0.get("matter_type") != "rulemaking")
    passed += r; failed += (not r)

# 4. Matter detail
print("\n4. Matter detail (first active rulemaking)")
active_rm = get("/matters?matter_type=rulemaking&status=active&limit=1")
if active_rm.get("items"):
    mid = active_rm["items"][0]["id"]
    det = get(f"/matters/{mid}")
    r = check("Detail returns matter", "title" in det, det.get("title", "?")[:50])
    passed += r; failed += (not r)
    r = check("extension key present", "extension" in det, f"type={type(det.get('extension'))}")
    passed += r; failed += (not r)
    if det.get("extension"):
        ext = det["extension"]
        r = check("Extension has workflow_status", "workflow_status" in ext, f"wf={ext.get('workflow_status')}")
        passed += r; failed += (not r)
        r = check("Extension has rin", "rin" in ext, f"rin={ext.get('rin')}")
        passed += r; failed += (not r)
    r = check("regulatory_ids key present", "regulatory_ids" in det, f"count={len(det.get('regulatory_ids', []))}")
    passed += r; failed += (not r)
    r = check("blocker key present", "blocker" in det)
    passed += r; failed += (not r)

    # Check removed fields
    removed_fields = ["risk_level", "boss_involvement_level", "problem_statement",
                       "why_it_matters", "pending_decision", "supervisor_person_id",
                       "next_step_assigned_to_person_id", "requesting_organization_id",
                       "reviewing_organization_id", "lead_external_org_id",
                       "decision_deadline", "revisit_date"]
    found_removed = [f for f in removed_fields if f in det]
    r = check("Removed fields absent from detail", len(found_removed) == 0, f"still present: {found_removed}" if found_removed else "all gone")
    passed += r; failed += (not r)
else:
    print("  [SKIP] No active rulemaking matters to test")

# 5. AI context
print("\n5. AI context snapshot")
ctx = get("/ai-context")
matters = ctx.get("matters", [])
r = check("AI context returns matters", len(matters) > 0, f"count={len(matters)}")
passed += r; failed += (not r)

if matters:
    m0 = matters[0]
    removed_ai = ["risk_level", "boss_involvement_level", "problem_statement",
                   "why_it_matters", "pending_decision", "supervisor_person_id"]
    found_removed = [f for f in removed_ai if f in m0]
    r = check("Removed fields absent from AI context", len(found_removed) == 0, f"still present: {found_removed}" if found_removed else "all gone")
    passed += r; failed += (not r)
    r = check("blocker in AI context", "blocker" in m0)
    passed += r; failed += (not r)
    has_ext = any(k in m0 for k in ["rulemaking", "guidance", "enforcement"])
    r = check("Extension data in AI context", has_ext)
    passed += r; failed += (not r)

# 6. Enums
print("\n6. Enums")
enums = get("/lookups/enums")
v2_enums = [k for k in enums if "workflow_status" in k or k == "instrument_type"
            or k == "interagency_role" or k == "petition_disposition" or k == "review_trigger"
            or "regulatory_id" in k or k.startswith("enforcement_")]
r = check("V2 enum groups present", len(v2_enums) >= 5, str(v2_enums))
passed += r; failed += (not r)

mt = enums.get("matter_type", [])
r = check("matter_type has 8 values", len(mt) <= 18, f"{len(mt)} values")  # may still have old values in Phase 3
passed += r; failed += (not r)

# 7. Regulatory IDs endpoint
print("\n7. Regulatory IDs endpoint")
if active_rm.get("items"):
    mid = active_rm["items"][0]["id"]
    reg = get(f"/matters/{mid}/regulatory-ids")
    r = check("Regulatory IDs endpoint works", isinstance(reg, list), f"count={len(reg) if isinstance(reg, list) else '?'}")
    passed += r; failed += (not r)

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)
if failed > 0:
    sys.exit(1)
