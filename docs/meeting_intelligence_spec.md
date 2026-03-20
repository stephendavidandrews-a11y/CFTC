# Meeting Intelligence Layer — Design Spec

## Problem
The current `readout_summary` on meetings is a single text blob. It doesn't serve as an operating brief. The extraction LLM writes a paragraph and moves on — no structure, no institutional judgment, no skim layer.

## Design Decisions
- **Separate `meeting_intelligence` table** (not a column on meetings) — lets you version, regenerate, and evolve summaries independently of the meeting record itself.
- **Tiered depth** — meeting characteristics determine how much structure the LLM produces. Short 1:1s get the 5-block core. Substantive multi-party meetings get the full treatment.

## Tier Gating Logic

| Signal | Tier 1 (Core) | Tier 2 (Full) |
|--------|--------------|---------------|
| Duration | < 20 min | ≥ 20 min |
| Participants | ≤ 2 | ≥ 3 |
| Meeting type | one_on_one, internal | congressional, interagency, external, briefing, working_group |
| Boss attends | no | yes |
| External parties | no | yes |

**Rule**: If ANY Tier 2 signal is true, produce the full treatment. Otherwise, Core only.

## Schema: `meeting_intelligence` table

```sql
CREATE TABLE IF NOT EXISTS meeting_intelligence (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id),
    communication_id TEXT,              -- source conversation
    version INTEGER NOT NULL DEFAULT 1, -- allows regeneration
    tier TEXT NOT NULL DEFAULT 'core',  -- 'core' or 'full'

    -- Layer 1: Skim (always populated)
    executive_summary TEXT NOT NULL,        -- 4-8 lines, the single most important block
    decisions_made TEXT,                    -- JSON array of {decision, owner, type, scope, status, dependencies}
    non_decisions TEXT,                     -- JSON array of {issue, why_unresolved, who_resolves, by_when, info_needed}
    action_items_summary TEXT,             -- JSON array of {action, owner, due_date, deliverable, priority}
    risks_surfaced TEXT,                   -- JSON array of {description, category, severity, likelihood, owner, mitigation}
    briefing_required TEXT,                -- JSON: {needed: bool, when, format, why, recommended_framing, recommended_ask}

    -- Layer 2: Operating (populated for Tier 2)
    key_issues_discussed TEXT,             -- JSON array of {issue, discussion, positions, open_questions, category}
    participant_positions TEXT,            -- JSON array of {person_id, position, support_level, reason, influence, follow_up}
    dependencies_surfaced TEXT,           -- JSON array of {dependency, type, internal_external, owner, status, expected_resolution}
    what_changed_in_matter TEXT,          -- structured text: priority/timeline/scope/stakeholder/risk/decision_path changes
    recommended_next_move TEXT,           -- JSON: {move, why, who_leads, handle_personally_delegate_elevate_monitor}
    commitments_made TEXT,               -- JSON array of {statement, speaker, audience, binding_level, follow_up, risk_if_not_honored}

    -- Layer 3: Record (populated for Tier 2)
    purpose_and_context TEXT,             -- why meeting happened, trigger, matter stage, prior events
    materials_referenced TEXT,            -- JSON array of {name, type, version_date, relevance}
    detailed_notes TEXT,                  -- structured notes by issue (for archival/retrieval)
    tags TEXT,                            -- JSON array of string tags for later retrieval

    -- Closing block (always populated)
    why_this_meeting_mattered TEXT,
    what_changed TEXT,
    what_i_need_to_do TEXT,
    what_boss_needs_to_know TEXT,
    what_can_wait TEXT,

    -- Metadata
    generated_by TEXT,                    -- model used (e.g. "claude-sonnet-4")
    prompt_version TEXT,                  -- extraction prompt version
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_meeting_intel_meeting ON meeting_intelligence(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_intel_comm ON meeting_intelligence(communication_id);
```

## Extraction Flow

### When it runs
After the main extraction produces a `meeting_record` item AND that item passes bundle review and is committed to the tracker, a **post-commit hook** triggers meeting intelligence generation. This is a separate LLM call — not part of the main extraction.

Why post-commit, not during extraction:
1. The meeting_record needs a real `meeting_id` in the tracker first
2. The intelligence generation benefits from knowing what tasks/decisions/updates were ALSO committed from this conversation
3. It's a separate concern — extraction identifies WHAT happened; intelligence generation interprets what it MEANS

### Prompt design
A dedicated system prompt (`prompts/meeting_intelligence/v1.0.0.md`) that receives:
- The full transcript
- The committed meeting record (participants, matter links)
- All other items committed from this conversation (tasks, decisions, updates)
- The matter context (current status, priority, recent history)
- The tier determination (core vs full)

The prompt asks for structured JSON output matching the schema above.

### Model selection
- **Tier 1 (Core)**: Haiku — fast, cheap, sufficient for 5-block summaries of short meetings
- **Tier 2 (Full)**: Sonnet — needed for institutional judgment, participant position analysis, and strategic recommendations

### Cost estimate
- Tier 1: ~$0.02-0.05 per meeting (Haiku, ~2K input / ~1K output)
- Tier 2: ~$0.15-0.40 per meeting (Sonnet, ~4K input / ~3K output)

## Frontend: Meeting Intelligence Panel

On the MeetingDetailPage, below the existing meeting header:

### Skim View (default, always shown)
- Executive summary (prominent, larger text)
- Decisions / Non-decisions (two columns)
- Action items (table with owner, due, deliverable)
- Risks (colored by severity)
- Briefing block (highlighted if needed=true)
- Closing block ("Why this mattered / What changed / What I do / Boss needs to know / What can wait")

### Operating View (expandable, Tier 2 only)
- Key issues discussed (accordion by issue)
- Participant positions (person cards with stance indicators)
- Dependencies (visual list with status)
- What changed in matter (diff-style display)
- Recommended next move (highlighted)
- Commitments made (table)

### Record View (expandable, Tier 2 only)
- Purpose & context
- Detailed notes by issue
- Materials referenced
- Tags

## Implementation Phases

### Phase A: Schema + Generation
1. Add `meeting_intelligence` table to tracker DB
2. Create `prompts/meeting_intelligence/v1.0.0.md` (core + full variants)
3. Add `app/pipeline/stages/meeting_intelligence.py` — tier gating + LLM call + DB write
4. Add post-commit hook in committer.py — detect meeting_record commits, trigger generation

### Phase B: API + Frontend
5. Add GET `/tracker/meetings/{id}/intelligence` endpoint
6. Add Meeting Intelligence panel to MeetingDetailPage
7. Add "Regenerate" button (creates new version)

### Phase C: Refinement
8. Tune prompts based on real meetings
9. Add intelligence to meeting list view (executive_summary preview)
10. Add briefing_required flag to dashboard indicators
