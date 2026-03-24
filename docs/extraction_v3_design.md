# Extraction V3 - Design Draft

## Purpose

`v3` should make the extraction system behave like a chief-of-staff operating layer, not a meeting summarizer.

Its job is to turn communications into:

- high-quality reviewable tracker proposals
- durable institutional memory
- relationship and team intelligence worth remembering
- matter-centered operating updates

The design target is:

- fewer items
- better items
- stronger routing
- better update-vs-new judgment
- better memory capture for team members and recurring stakeholders

## Contract Anchor

`v3` is not a new ontology.

It is anchored to the tracker contract we just stabilized:

- `services/tracker/app/contracts.py`
  Master for AI-facing enums, writable tables, validation rules, soft deletes, and upsert behavior
- `services/tracker/app/schema.py`
  Master for real database tables and columns

That means `v3` can improve understanding, routing, and proposal quality without drifting away from what the tracker can actually validate and write.

## Core Tension

The system should be conservative about creating tracker writes, but it should not miss memorable personal details that are genuinely useful to remember.

That means `v3` should not use one blunt threshold for everything.

Instead:

- operational writes should be conservative
- relationship memory should be selective, but intentionally capture-worthy
- commit-ready person memory should appear in the normal review flow
- weaker memory signals can be retained internally for evaluation and tuning without forcing immediate UI changes

## Product Definition

The app should answer five questions after every communication:

1. What changed?
2. What now requires action?
3. What matter or matters does this belong to?
4. What is worth remembering later?
5. What is too weak, duplicative, or ephemeral to save?

## Design Principles

1. Prefer precision over volume.
2. Prefer updates over duplicates.
3. Prefer durable memory over recap.
4. Prefer explicit uncertainty over false confidence.
5. Prefer matter-centered routing, but allow standalone output when routing is weak.
6. Preserve important personal/team memory even when it is not an operational item.
7. Keep the existing review workflow unless a change creates clear product value.

## Success Criteria

`v3` is good if it improves:

- reviewer trust
- routing accuracy
- duplicate suppression
- usefulness of `context_note`
- usefulness of `person_detail_update`
- action quality in tasks and updates

It is not good merely because it emits more items.

## Recommended Architecture

The best architecture is not "route first and extract second."

The best architecture is:

1. LLM Pass 1: Communication Understanding
2. Deterministic Resolution and Routing
3. LLM Pass 2: Proposal Synthesis

### Pass 1: Communication Understanding

This pass should be high-recall.

Its job is to notice candidate signal without trying to emit final tracker writes yet.

It should extract:

- commitments
- requests
- deadlines
- decision and recommendation signals
- matter state movement
- meeting facts
- stakeholder relevance
- document references
- durable context signals
- person memory signals
- organization memory signals

This pass should identify objects and observations, not final writeback operations.

### Final Observation Vocabulary

Pass 1 should use a small top-level observation vocabulary plus required subtypes.

Top-level observation types:

- `task_signal`
- `decision_signal`
- `matter_signal`
- `meeting_signal`
- `stakeholder_signal`
- `document_signal`
- `person_memory_signal`
- `institutional_memory_signal`

Required subtypes:

- `task_signal`
  - `commitment`
  - `request`
  - `follow_up_need`
  - `deadline_change`
  - `state_change`
  - `blocker`
- `decision_signal`
  - `decision_made`
  - `recommendation`
  - `decision_request`
  - `open_question`
- `matter_signal`
  - `status_change`
  - `state_change`
  - `priority_change`
  - `risk_or_sensitivity_change`
  - `scope_change`
  - `dependency_change`
- `meeting_signal`
  - `meeting_occurred`
  - `meeting_planned`
  - `meeting_recap`
- `stakeholder_signal`
  - `involvement`
  - `role`
  - `stance`
- `document_signal`
  - `document_created`
  - `document_requested`
  - `document_revised`
  - `document_referenced`
- `person_memory_signal`
  - `biography`
  - `preference`
  - `working_style`
  - `management_guidance`
  - `relationship_dynamic`
- `institutional_memory_signal`
  - `operating_rule`
  - `process_norm`
  - `leadership_preference`
  - `strategic_context`
  - `organization_fact`
  - `stakeholder_posture`

This is the finalized observation vocabulary I recommend for `v3`.

### Why This Vocabulary Is Best

It works well because:

- it is small enough for the model to use consistently
- it maps cleanly to the tracker contract
- it makes person memory and institutional memory first-class product concepts
- it gives `person_detail_update` and `context_note` clearer upstream signal lanes
- it avoids forcing one observation type per final item type

### Deterministic Resolution and Routing

This is the middle layer, and it should not be a free-form prompt.

This step should:

- resolve people and organizations to tracker IDs where possible
- match likely matters
- match open tasks and decisions
- determine likely bundle targets
- gather only relevant tracker context for Pass 2

This is where we use the contract and tracker context mechanically rather than asking the LLM to improvise DB-shape reasoning.

### Pass 2: Proposal Synthesis

This pass should be conservative.

Its job is to turn observations plus routed tracker context into reviewable tracker proposals that conform to the existing contract.

Pass 2 should:

- prefer updates over creates
- reject weak clutter
- create `person_detail_update` when a detail is truly worth remembering
- create `context_note` only for durable memory
- stay within the item types and fields allowed by the tracker contract

## Why This Architecture Is Best

This structure works better than a single giant prompt because:

- Pass 1 can be high-recall without polluting the tracker
- routing can be more reliable and consistent when deterministic
- Pass 2 can focus on judgment and selectivity
- update-vs-new decisions become much easier
- person memory can be captured thoughtfully without flooding the review queue

## Proposal Philosophy By Item Type

### `task`

Create only when there is a clear commitment, ask, or follow-through obligation.

This includes delegated and third-party commitments that matter to Stephen.

If someone other than Stephen is doing the work and Stephen still needs to track the outcome, `v3` should preserve the paired-task behavior:

- one action task for the other person
- one `follow_up` task for Stephen

### `task_update`

Use when an existing task clearly changed in one of these ways:

- status
- due date
- deadline type
- assignee
- waiting state
- expected output
- priority

Default to `task_update` when the evidence clearly refers to an existing open task.

### Paired Follow-Up Invariant

This should remain a hard product rule in `v3`.

When someone other than Stephen owns an action that is relevant to Stephen, the system should normally create both:

- the action task assigned to them
- the paired `follow_up` task for Stephen

Examples:

- Stephen delegates work to someone on his team
- a colleague says they will look into something for Stephen
- someone commits to make an introduction, send a document, get an answer, or advance coordination Stephen depends on

When Stephen owns the action himself, only the action task should be created.

This matters because the tracker is not just logging commitments. It is helping Stephen manage delegated execution.

### `decision`

Create only for a real tracked choice.

### `decision_update`

Use when the communication changes:

- status
- owner
- due date
- recommended option
- final result

### `matter_update`

Use for meaningful state-of-play movement that does not belong as a task or decision.

### `status_change`

Use only when the matter status itself has clearly changed.

### `meeting_record`

Create when the communication represents an actual meeting or a meeting recap worth preserving as a structured event.

### `stakeholder_addition`

Create only when a person or organization is meaningfully part of the matter, not just mentioned in passing.

### `document`

Create only when there is a real document artifact worth tracking.

### `context_note`

This should be durable memory, not recap.

Good:

- operating norms
- leadership preferences
- durable strategic framing
- stakeholder posture that matters over time
- office process realities

Bad:

- a normal one-off recap
- generic "we discussed X"
- low-value color commentary

### `person_detail_update`

Keep the current tracker name for now, but conceptually this is "relationship memory."

This is where `v3` should intentionally preserve memorable and useful human details, especially for:

- team members
- recurring internal stakeholders
- leadership
- high-frequency external counterparts

Good:

- education
- prior roles
- hometown or current city if relationship-relevant
- spouse or children details if directly and comfortably disclosed
- interests likely useful for future rapport
- scheduling preferences
- management preferences
- guidance on how Stephen should manage or lead the person well

Bad:

- trivial small talk with no later value
- speculative or secondhand claims
- awkwardly intimate details with no clear working purpose
- details that do not fit current tracker fields

### `org_detail_update`

Use for durable facts about organizations, jurisdictions, or roles that matter operationally.

### `new_matter`

Create only when there is a genuine ongoing workstream, not just a discussed topic.

## Relationship Memory Strategy

This is the part that should explicitly reflect your preference.

`v3` should be conservative about operational clutter, but it should be intentionally good at capturing useful person memory.

### Memory-Worthiness Test

A personal detail should be proposed as `person_detail_update` when all of the following are true:

1. It fits a real tracker field.
2. It was directly stated or strongly evidenced.
3. It is stable or likely to matter later.
4. It is useful for working memory, relationship management, scheduling, or leadership understanding.

### Team-Member Bias

For team members and close recurring stakeholders, the system should be somewhat more willing to capture:

- education
- prior roles
- interests
- scheduling preferences
- leadership notes
- relationship preferences

Reason:

These details have higher future utility and lower irrelevance risk for close collaborators.

### Practical Memory Thresholds

`v3` should use:

- a strict threshold for operational writes
- a very strict threshold for `context_note`
- a medium-strict threshold for `person_detail_update`
- a slightly more permissive `person_detail_update` threshold for team members and recurring close collaborators

This is how we get fewer operational items without missing the human details that are actually worth remembering.

### Person Memory Field Mapping

`person_memory_signal` should only become `person_detail_update` when it maps to real tracker fields.

Recommended mapping:

- `biography`
  Usually maps to:
  - `education_summary`
  - `prior_roles_summary`
  - `hometown`
  - `current_city`
  - occasionally `children_count`, `children_names`, `spouse_name`, `birthday`
- `preference`
  Usually maps to:
  - `relationship_preferences`
  - `scheduling_notes`
  - occasionally `interests`
- `working_style`
  Usually maps to:
  - `relationship_preferences`
  - `leadership_notes`
  - sometimes `personal_notes_summary`
- `management_guidance`
  Usually maps to:
  - `leadership_notes`
  - sometimes `relationship_preferences`
- `relationship_dynamic`
  Usually maps to:
  - `relationship_preferences`
  - `personal_notes_summary`
  - sometimes `leadership_notes`

If a detail is useful but does not fit a real field cleanly, `v3` should not force it into `person_detail_update`.

### Institutional Memory Mapping

`institutional_memory_signal` should map primarily to `context_note`, and sometimes to `org_detail_update`.

Recommended mapping:

- `operating_rule`
  Usually becomes `context_note`
- `process_norm`
  Usually becomes `context_note`
- `leadership_preference`
  Usually becomes `context_note`
- `strategic_context`
  Usually becomes `context_note`
- `organization_fact`
  Usually becomes `org_detail_update` if it is a durable org fact that fits the org record
  Otherwise `context_note`
- `stakeholder_posture`
  Usually becomes `context_note`

This is important because institutional memory is broader than organization metadata.
Most institutional memory belongs in `context_note`, not in org records.

### Memory Capture Rule Of Thumb

If the system asks "should I save this as person memory or institutional memory?", the answer should be:

- save as `person_detail_update` if it is a durable thing to remember about a specific person and it fits a real field
- save as `context_note` if it is a durable thing to remember about how the office, leadership, process, or stakeholder environment works
- save as `org_detail_update` only if it is truly a durable fact about the organization itself

## Review Flow Recommendation

Do not create a separate review workflow for `v3`.

Use the existing review page.

The recommendation is:

- keep the same approve/reject process
- keep the same item types
- order `person_detail_update` items at the bottom of the same review page

That gives us:

- minimal UI churn
- minimal code churn
- better memory capture without changing how review fundamentally works

## Internal Handling Of Weaker Memory Signals

We do not need a new review UI section in the first implementation.

If Pass 1 finds a potentially useful personal detail that does not clear the commit threshold:

- keep it in the extraction artifact or evaluation logs
- do not show it in the main review UI yet
- use it for prompt tuning and threshold tuning

This gives us a way to avoid silent loss during development without forcing immediate review-page complexity.

## Routing Rules

Routing should happen after Pass 1 and before Pass 2.

### Routing Confidence Bands

- `high`
  Clear primary matter.
- `medium`
  Good candidate matter, but not definitive.
- `multi`
  More than one matter materially involved.
- `standalone`
  No matter has enough support.
- `new_matter_candidate`
  Real workstream appears to exist outside known matters.

### Routing Signals

Strong signals:

- known matter stakeholder overlap
- known linked organization overlap
- explicit identifier match
- explicit matter naming
- owner, supervisor, or next-step-owner overlap

Moderate signals:

- thematic overlap with recent matter activity
- repeated references to the same workstream
- document or decision references associated with a matter

Weak signals:

- vague topical similarity alone

### Routing Rules Of Thumb

- A wrong matter link is worse than a standalone output.
- Multi-matter should be used when the communication genuinely spans multiple tracked workstreams.
- `new_matter` should require evidence of continuing ownership, work, or decisions, not merely a topic.

## Bundle Strategy

`v3` should keep bundles, but make them clearer.

Recommended bundle types:

- `matter`
- `standalone`
- `new_matter`

Within each bundle:

- items should be tightly related
- rationale should be short and explicit
- proposal ordering should prioritize updates before creates
- `person_detail_update` items should sort last in the review page

## Uncertainty Model

Each observation and proposal should classify directness as:

- `direct_statement`
- `direct_commitment`
- `direct_request`
- `inferred_from_context`
- `inferred_from_pattern`

This gives reviewers a fast trust signal.

## New-vs-Update Rules

This is one of the most important `v3` improvements.

### Default Update Preference

If an existing tracker record clearly matches, prefer update.

That applies especially to:

- tasks
- decisions
- organizations
- person memory

### New Record Preference

Create new only when:

- there is no plausible existing record
- the communication clearly introduces a distinct new object
- merging would lose meaning

## Prompt Design Direction

### Pass 1 Prompt

Pass 1 should instruct the model to:

1. understand the communication
2. identify atomic observations and candidate objects
3. capture both operational and memory signal
4. avoid premature tracker-write assumptions

### Pass 2 Prompt

Pass 2 should instruct the model to:

1. read observations plus routed tracker context
2. choose only commit-worthy proposals
3. prefer updates over duplicates
4. stay inside the tracker contract
5. be conservative on clutter
6. do not suppress memorable team or stakeholder details that fit person-memory fields

## Prompt Rules That Should Be Explicit

- Do not create tracker writes just because something was discussed.
- Do not create a `context_note` for ordinary recap.
- Do not create a `person_detail_update` unless the detail fits a real field and is worth remembering.
- Do create `person_detail_update` for stable team-member details that improve future relationship or management context.
- Prefer `task_update` over `task` when an existing open task clearly matches.
- Prefer `decision_update` over `decision` when an existing decision clearly matches.
- Use standalone outputs when routing is weak.

## Suggested V3 Evaluation Rubric

Score each communication on:

1. Routing accuracy
2. Task precision
3. Update-vs-new judgment
4. Context note quality
5. Person-memory quality
6. Duplicate suppression
7. Reviewer trust

### Reviewer Trust Questions

- Would I approve these items quickly?
- Do these items feel like real operating intelligence?
- Did it miss anything I actually wish I had remembered?
- Did it create anything I would immediately delete?

## Recommended First Implementation Order

1. Finalize the concrete `v3` schemas for Pass 1 and Pass 2.
2. Write the new Pass 1 prompt.
3. Implement deterministic resolution and routing between the passes.
4. Write the new Pass 2 prompt against the stabilized tracker contract.
5. Add item-level evaluation fixtures from real communications.
6. Tune routing and memory capture before tuning anything cosmetic.

## Open Decisions

1. Should the UI keep the backend label `person_detail_update`, or rename it visually to "Person Memory" while leaving the backend unchanged?
2. How strict should `new_matter` be in borderline multi-topic conversations?
3. Should `context_note` use a stronger threshold than `person_detail_update`?

## Recommended Position On Those Open Decisions

My recommendation:

1. Keep backend `person_detail_update`, and optionally rename it in the UI later if desired.
2. Make `new_matter` strict.
3. Use a slightly higher threshold for `context_note` than for `person_detail_update` for team members and high-value recurring stakeholders.

## Practical Summary

The heart of `v3` is:

- LLM Pass 1 for understanding and candidate signal capture
- deterministic routing and record matching in the middle
- LLM Pass 2 for conservative proposal generation
- strong update preference
- durable memory only
- explicit relationship-memory capture for people worth remembering
- same review page, with `person_detail_update` items at the bottom
