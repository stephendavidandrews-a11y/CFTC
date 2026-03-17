# CFTC Rulemaking Pipeline — Reference Specification

## Purpose
A rulemaking lifecycle tracker that monitors every active CFTC regulation from conception through final publication. Pulls from two government data sources and cross-references them per EO 14192 requirements.

---

## Data Sources

### 1. Unified Regulatory Agenda (reginfo.gov)
- **URL**: `https://www.reginfo.gov/public/do/XMLViewFileAction?f=REGINFO_RIN_DATA_202504.xml`
- **Agency code**: `3038` (CFTC)
- **Current active items**: ~26 (Prerule: 2, Proposed Rule: 19, Final Rule: 5)
- **Fields**: RIN, title, abstract, priority designation, legal authority, CFR citation, timetable (action + date pairs), agency contact, major rule flag, EO 14192 designation, stage
- **Individual entry**: `https://www.reginfo.gov/public/do/eAgendaViewRule?pubId=202504&RIN=3038-XXXX`
- **Published**: Semi-annually (Spring/Fall)

### 2. Federal Register API (federalregister.gov)
- **Endpoint**: `https://www.federalregister.gov/api/v1/documents.json`
- **Filter**: `conditions[agencies][]=commodity-futures-trading-commission`
- **Document types**: `PRORULE`, `RULE`, `NOTICE` (selective)
- **No API key required**
- **Key fields**: title, type, action, document_number, publication_date, regulation_id_numbers, docket_ids, comments_close_on, effective_on, abstract, html_url, pdf_url
- **Published**: Daily (business days)

---

## Rulemaking Lifecycle

The pipeline tracks every step of the notice-and-comment rulemaking process:

```
Unified Agenda Listing (Pre-rule)
        |
        v
   ANPRM (Advance Notice of Proposed Rulemaking)
        |
        v
   NPRM / Proposed Rule
        |
        +-- Extension of comment period
        +-- Reopening of comment period
        +-- Supplemental notice / Further NPRM
        |
        v
   Comment Period Closes --> Comment Analysis
        |
        v
   Final Rule (or Interim Final Rule, or Direct Final Rule)
        |
        +-- Correcting amendment
        +-- Delay of effective date
        |
        v
   Effective / Published in CFR
```

**Also tracked**: Withdrawals, petitions for rulemaking, requests for comment.

---

## FR Action Field Mapping

| FR `action` Pattern | Lifecycle Event | Pipeline Effect |
|---|---|---|
| "Advance notice of proposed rulemaking" | ANPRM published | Create/update item, stage -> comment_period |
| "Proposed rule" / "Notice of proposed rulemaking" | NPRM published | Create/update item, stage -> comment_period |
| "Extension of comment period" | Comment period extended | Update comments_close_on, log event |
| "Reopening of comment period" | Comments reopened | Update comments_close_on, log event |
| "Supplemental notice" / "Further notice" | Supplemental NPRM | Log event, may reset comment period |
| "Request for comment" (NOTICE type) | Standalone RFC | Log event on related item if RIN matches |
| "Withdrawal of proposed rule" | Rule withdrawn | Set status -> withdrawn |
| "Final rule" | Final rule published | Stage -> published, set effective_on |
| "Interim final rule" | IFR published | Stage -> published, flag as interim |
| "Direct final rule" | DFR published | Stage -> published |
| "Correcting amendment" | Post-publication correction | Log event only |
| "Delay of effective date" | Effective date pushed | Update effective_on, log event |
| "Petition for rulemaking" (NOTICE type) | External petition | Create item if new RIN, stage -> concept |

---

## Stage Mapping

| Source | item_type | current_stage |
|--------|-----------|---------------|
| UA Prerule / FR ANPRM | ANPRM | concept (no FR pub) or comment_period (published) |
| UA Proposed / FR NPRM | NPRM | drafting (no FR pub), comment_period (published), comment_analysis (comments closed) |
| FR Extension/Reopening | (unchanged) | stays at comment_period, update close date |
| FR Withdrawal | (unchanged) | status -> withdrawn |
| UA Final / FR Final Rule | final_rule | final_drafting (not yet published), published (in FR) |
| FR Interim Final Rule | IFR | published |
| FR Direct Final Rule | DFR | published or comment_period |
| FR Correcting Amendment | (unchanged) | no stage change |

---

## Deadline Tracking

### From Federal Register
| Field | Deadline Type | Description |
|-------|--------------|-------------|
| `comments_close_on` | comment_period | When public comment period ends |
| `effective_on` | effective_date | When rule takes legal effect |
| Updated `comments_close_on` | comment_period (updated) | Extension notice pushes deadline |
| Updated `effective_on` | effective_date (updated) | Delay notice pushes effective date |

### From Unified Agenda Timetable
| Timetable Action | Deadline Type | Description |
|-----------------|--------------|-------------|
| "NPRM" (future) | nprm_target | Planned NPRM publication date |
| "Final Action" (future) | final_rule_target | Planned final rule date |
| "ANPRM" (future) | anprm_target | Planned ANPRM date |

### Status Management
- Hard deadlines (comment period, statutory): red indicator
- Target dates (UA timetable): yellow indicator
- Completed deadlines: marked when date passes or action published
- Extended deadlines: old deadline gets `extended_to` field set

---

## EO 14192 Compliance

Executive Order 14192 requires that rules appear on the Unified Regulatory Agenda **before** being published in the Federal Register.

**Cross-reference logic**:
- Items on BOTH UA and FR: compliant
- Items on UA only: "Not yet in Federal Register" (expected for pre-publication items)
- Items on FR only: "Not on Unified Agenda" (potential EO 14192 violation)

---

## Sync Schedule
- **Daily auto-sync**: background task runs every 24 hours
- **Incremental updates**: FR API queried with `publication_date[gte]` set to last sync date
- **Full sync**: on first run or manual trigger
- **Manual trigger**: `POST /pipeline/integrations/sync`

---

## Database Tables

### Core
- `pipeline_items`: Main tracking table (module='rulemaking', item_type, rin, current_stage, etc.)
- `pipeline_unified_agenda`: UA metadata (abstract, timetable, legal authority, priority, contact)
- `pipeline_deadlines`: All tracked deadlines with type, due_date, status, is_hard_deadline
- `pipeline_decision_log`: Full audit trail including every FR document event
- `pipeline_publication_status`: OFR, PRA, OIRA, CRA, FR publication tracking

### Stage Templates (pre-seeded)
- NPRM: 11 stages (concept -> drafting -> cba_development -> chairman_review -> commission_review -> ofr_submission -> comment_period -> comment_analysis -> final_drafting -> final_commission -> published)
- ANPRM: 5 stages (concept -> drafting -> chairman_review -> commission_review -> published)
- IFR: 6 stages (concept -> drafting -> good_cause -> chairman_review -> commission_review -> published)
- DFR: 7 stages (concept -> drafting -> chairman_review -> commission_review -> ofr_submission -> comment_period -> effective)
- final_rule: 6 stages (drafting -> cba_development -> chairman_review -> commission_review -> ofr_submission -> published)

---

## Architecture

```
[reginfo.gov XML] ---+
                     |
                     +--> sync.py --> pipeline_items + pipeline_deadlines + pipeline_decision_log
                     |
[FR API JSON] -------+

sync.py runs:
  - On startup (non-blocking)
  - Every 24 hours (background task)
  - On demand (POST /pipeline/integrations/sync)
```

---

## Key Files
| File | Purpose |
|------|---------|
| `app/pipeline/services/sync.py` | UA XML + FR API sync service |
| `app/pipeline/routers/integrations.py` | Sync endpoint + cross-DB queries |
| `app/pipeline/main.py` | FastAPI app, startup hooks, daily sync |
| `app/pipeline/schema.py` | 19 SQLite tables |
| `app/pipeline/seed.py` | Team members + stage templates |
| `app/pipeline/services/items.py` | CRUD for pipeline items |
| `app/pipeline/config.py` | Item types, priority weights, deadline types |
| `frontend/src/pages/tracker/TrackerDashboardPage.jsx` | Executive Summary (dark theme) |
| `frontend/src/pages/PipelinePage.jsx` | Pipeline kanban view |
| `frontend/src/pages/ItemDetailPage.jsx` | Item detail page |

---

## What Each Pipeline Item Looks Like

```
Title: "Operational Resilience Framework for Certain Commission Registrants"
RIN: 3038-AF23
Item Type: NPRM
Stage: Comment Period
Docket: CFTC-2024-XXXX
Priority: Economically Significant

Sources: [check] Unified Agenda  [check] Federal Register
Legal Authority: 7 U.S.C. 6b, 6c, 12a
Contact: [name] @ CFTC OGC
Abstract: [from UA]

Timetable:
  - NPRM: 03/2025 (published)
  - Final Rule: 12/2025 (target)

Active Deadlines:
  - Comment period closes: April 15, 2025 (12 days)
  - Final rule target: December 2025

FR Document Timeline:
  1. 2025-01-15 - ANPRM published (FR 2025-00XXX)
  2. 2025-03-01 - NPRM published (FR 2025-00YYY)
  3. 2025-03-20 - Extension of comment period (FR 2025-00ZZZ)
```
