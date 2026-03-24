# Extraction V3 - Concrete Schema Draft

## Goal

This document turns the `v3` design into concrete data shapes.

`v3` uses three structured artifacts:

1. Pass 1 output: communication understanding
2. Middle artifact: deterministic routing and resolution package
3. Pass 2 output: reviewable tracker proposals

The final proposal layer stays constrained by:

- `services/tracker/app/contracts.py`
- `services/tracker/app/schema.py`

## 1. Pass 1 Output Schema

Pass 1 is high-recall and should not emit tracker-write-shaped operations yet.

### Top-Level Shape

```json
{
  "schema_version": "3.0.0-pass1",
  "communication_id": "uuid",
  "communication_kind": "audio",
  "communication_summary": "Short factual summary of what happened.",
  "participants": [],
  "observations": []
}
```

### `participants`

```json
{
  "speaker_label": "Speaker 1",
  "display_name": "Tyler S. Badgley",
  "tracker_person_id": "uuid-or-null",
  "organization_name": "CFTC",
  "tracker_org_id": "uuid-or-null",
  "confidence": 0.97
}
```

### `observations`

Each observation is an atomic signal noticed in the communication.

```json
{
  "id": "obs_001",
  "observation_type": "task_signal",
  "observation_subtype": "deadline_change",
  "summary": "Tyler moved Priya's memo deadline to April 15.",
  "directness": "direct_statement",
  "confidence": 0.95,
  "durability": "working",
  "memory_value": "medium",
  "speaker_refs": [
    {
      "name": "Tyler S. Badgley",
      "tracker_person_id": "uuid-or-null"
    }
  ],
  "entity_refs": [
    {
      "entity_type": "person",
      "name": "Priya Sharma",
      "tracker_id": "uuid-or-null"
    }
  ],
  "candidate_matter_refs": [
    {
      "matter_id": "uuid",
      "matter_title": "Crypto Derivatives NPRM",
      "score": 0.92,
      "reason": "Speakers and work product match this matter."
    }
  ],
  "candidate_record_refs": [
    {
      "record_type": "task",
      "record_id": "uuid",
      "score": 0.94,
      "reason": "References existing custody memo task."
    }
  ],
  "field_hints": {
    "due_date": "2026-04-15",
    "priority": "high",
    "deadline_type": "soft"
  },
  "evidence": [
    {
      "excerpt": "I need it by the 15th now, not end of month.",
      "speaker": "Tyler S. Badgley",
      "segments": ["seg-005"],
      "time_range": {
        "start": 312.4,
        "end": 325.8
      }
    }
  ]
}
```

## 2. Observation Type Vocabulary

Final top-level `observation_type` values:

- `task_signal`
- `decision_signal`
- `matter_signal`
- `meeting_signal`
- `stakeholder_signal`
- `document_signal`
- `person_memory_signal`
- `institutional_memory_signal`

## 3. Observation Subtype Vocabulary

`observation_subtype` is required.

### `task_signal`

- `commitment`
- `request`
- `follow_up_need`
- `deadline_change`
- `state_change`
- `blocker`

### `decision_signal`

- `decision_made`
- `recommendation`
- `decision_request`
- `open_question`

### `matter_signal`

- `status_change`
- `state_change`
- `priority_change`
- `risk_or_sensitivity_change`
- `scope_change`
- `dependency_change`

### `meeting_signal`

- `meeting_occurred`
- `meeting_planned`
- `meeting_recap`

### `stakeholder_signal`

- `involvement`
- `role`
- `stance`

### `document_signal`

- `document_created`
- `document_requested`
- `document_revised`
- `document_referenced`

### `person_memory_signal`

- `biography`
- `preference`
- `working_style`
- `management_guidance`
- `relationship_dynamic`

### `institutional_memory_signal`

- `operating_rule`
- `process_norm`
- `leadership_preference`
- `strategic_context`
- `organization_fact`
- `stakeholder_posture`

## 4. Observation Type -> Proposal Bias

This is not a hard rule, but it is the intended mapping for Pass 2.

- `task_signal`
  Usually becomes `task` or `task_update`
- `decision_signal`
  Usually becomes `decision` or `decision_update`
- `matter_signal`
  Usually becomes `matter_update`, `status_change`, or occasionally `new_matter`
- `meeting_signal`
  Usually becomes `meeting_record`
- `stakeholder_signal`
  Usually becomes `stakeholder_addition`
- `document_signal`
  Usually becomes `document`
- `institutional_memory_signal`
  Usually becomes `context_note`
- `person_memory_signal`
  Usually becomes `person_detail_update`
- `institutional_memory_signal`
  Usually becomes `org_detail_update`

For delegated or third-party commitments relevant to Stephen:

- `task_signal.commitment` should usually map to the action task for the other person
- `task_signal.follow_up_need` should usually map to Stephen's paired `follow_up` task

## 5. Person Memory -> Tracker Field Mapping

These mappings are design guidance for Pass 2.

### `person_memory_signal.biography`

Primary target fields:

- `education_summary`
- `prior_roles_summary`
- `hometown`
- `current_city`
- `birthday`
- `spouse_name`
- `children_count`
- `children_names`

### `person_memory_signal.preference`

Primary target fields:

- `relationship_preferences`
- `scheduling_notes`
- `interests`

### `person_memory_signal.working_style`

Primary target fields:

- `relationship_preferences`
- `leadership_notes`
- `personal_notes_summary`

### `person_memory_signal.management_guidance`

Meaning:

- how Stephen should manage, lead, brief, or work with this person effectively

Primary target fields:

- `leadership_notes`
- `relationship_preferences`

### `person_memory_signal.relationship_dynamic`

Primary target fields:

- `relationship_preferences`
- `personal_notes_summary`
- `leadership_notes`

## 6. Institutional Memory -> Tracker Field Mapping

### `institutional_memory_signal.operating_rule`

Usually becomes:

- `context_note`

### `institutional_memory_signal.process_norm`

Usually becomes:

- `context_note`

### `institutional_memory_signal.leadership_preference`

Usually becomes:

- `context_note`

### `institutional_memory_signal.strategic_context`

Usually becomes:

- `context_note`

### `institutional_memory_signal.organization_fact`

Usually becomes:

- `org_detail_update` when the fact fits a durable org field
- otherwise `context_note`

### `institutional_memory_signal.stakeholder_posture`

Usually becomes:

- `context_note`

## 7. Person Memory Commit Gate

Pass 2 should only emit `person_detail_update` when:

1. the signal maps to a real tracker field
2. the detail is directly stated or strongly evidenced
3. the detail is likely to matter later
4. the detail would actually help Stephen remember how to work with or relate to the person

If a detail is useful but does not fit a real field, it should not be forced into `person_detail_update`.

## 7A. Paired Follow-Up Task Rule

`v3` should preserve the paired-task behavior from the current system.

When someone other than Stephen owns an action that Stephen needs tracked, Pass 1 should normally emit two observations:

1. `task_signal.commitment`
2. `task_signal.follow_up_need`

Then Pass 2 should normally emit two task proposals in the same bundle:

1. the action task assigned to the other person
2. the paired `follow_up` task for Stephen

When Stephen himself owns the work, only the action task should be proposed.

## 8. Directness Vocabulary

Recommended `directness` values:

- `direct_statement`
- `direct_commitment`
- `direct_request`
- `inferred_from_context`
- `inferred_from_pattern`

## 9. Durability Vocabulary

Recommended `durability` values:

- `ephemeral`
- `working`
- `durable`

## 10. Memory Value Vocabulary

Recommended `memory_value` values:

- `none`
- `low`
- `medium`
- `high`

## 11. Middle Artifact: Routing And Resolution Package

This is not an LLM output. It is the deterministic bridge between the two prompts.

### Top-Level Shape

```json
{
  "schema_version": "3.0.0-routing",
  "communication_id": "uuid",
  "resolved_people": [],
  "resolved_organizations": [],
  "matter_routing": {},
  "record_matches": {},
  "relevant_tracker_context": {}
}
```

### `resolved_people`

```json
{
  "name": "Tyler S. Badgley",
  "tracker_person_id": "uuid",
  "resolution_confidence": 0.99,
  "source": "participant_match"
}
```

### `resolved_organizations`

```json
{
  "name": "Securities and Exchange Commission",
  "tracker_org_id": "uuid",
  "resolution_confidence": 0.96,
  "source": "entity_match"
}
```

### `matter_routing`

```json
{
  "primary_matter_id": "uuid-or-null",
  "secondary_matter_ids": ["uuid"],
  "routing_confidence": "high",
  "routing_basis": [
    "speaker is matter stakeholder",
    "open task match",
    "identifier overlap"
  ],
  "standalone_reason": null,
  "new_matter_candidate": false
}
```

### `record_matches`

```json
{
  "tasks": [
    {
      "observation_id": "obs_001",
      "record_id": "uuid",
      "match_score": 0.94,
      "match_reason": "Same deliverable and assignee."
    }
  ],
  "decisions": [
    {
      "observation_id": "obs_004",
      "record_id": "uuid",
      "match_score": 0.9,
      "match_reason": "Same decision title and matter."
    }
  ]
}
```

### `relevant_tracker_context`

This should be a narrowed context package for Pass 2, not the full tracker dump.

Suggested contents:

- routed matters
- matched open tasks
- matched open decisions
- relevant people
- relevant organizations
- recent updates

## 12. Pass 2 Output Schema

Pass 2 is conservative and review-facing.

It should emit only proposal types that map to the current tracker contract.

### Top-Level Shape

```json
{
  "schema_version": "3.0.0-pass2",
  "communication_id": "uuid",
  "extraction_summary": "Short explanation of what changed and what was proposed.",
  "routing_assessment": {},
  "bundles": [],
  "suppressed_observations": []
}
```

## 13. `routing_assessment`

```json
{
  "primary_matter_id": "uuid-or-null",
  "secondary_matter_ids": ["uuid"],
  "routing_confidence": "high",
  "routing_basis": [
    "speaker is matter stakeholder",
    "linked organization is on the matter"
  ],
  "standalone_reason": null,
  "new_matter_candidate": false
}
```

## 14. `bundles`

Bundle types stay aligned with the current extraction flow:

- `matter`
- `standalone`
- `new_matter`

### Bundle Shape

```json
{
  "bundle_type": "matter",
  "target_matter_id": "uuid-or-null",
  "target_matter_title": "Crypto Derivatives NPRM",
  "proposed_matter": null,
  "confidence": 0.94,
  "rationale": "Most signals belong to the crypto NPRM workstream.",
  "intelligence_notes": null,
  "uncertainty_flags": [],
  "items": []
}
```

## 15. `items`

Each item is a commit-ready proposal that maps to the tracker contract.

### Common Item Shape

```json
{
  "item_type": "task_update",
  "proposed_data": {},
  "confidence": 0.95,
  "rationale": "Existing task clearly changed.",
  "why_new_vs_update": "Matches existing open memo task by title, assignee, and due date discussion.",
  "why_this_matter": "The memo is tracked under the crypto NPRM matter.",
  "source_observation_ids": ["obs_001"],
  "source_evidence": []
}
```

### Required Shared Fields

- `item_type`
- `proposed_data`
- `confidence`
- `rationale`
- `why_new_vs_update`
- `why_this_matter`
- `source_observation_ids`
- `source_evidence`

## 16. Valid `item_type` Values

These must remain aligned to the tracker contract and current extraction flow:

- `task`
- `task_update`
- `decision`
- `decision_update`
- `matter_update`
- `status_change`
- `meeting_record`
- `stakeholder_addition`
- `document`
- `context_note`
- `person_detail_update`
- `org_detail_update`
- `new_person`
- `new_organization`
- `new_matter`

## 17. Review Ordering Rule

The schema itself does not need a new workflow concept.

The review layer should simply sort:

1. operational items first
2. `context_note` after operational items
3. `person_detail_update` last

That keeps review simple and matches the existing page structure more closely.

## 18. `suppressed_observations`

This is how `v3` can retain useful but uncommitted signal without forcing UI changes.

### Shape

```json
{
  "observation_id": "obs_009",
  "observation_type": "person_memory_signal",
  "observation_subtype": "biography",
  "description": "Possible useful personal detail noticed but not committed.",
  "reason_noted": "Useful but below commit threshold.",
  "candidate_item_type": "person_detail_update",
  "candidate_fields": {
    "interests": "distance running"
  },
  "confidence_if_enabled": 0.63,
  "source_excerpt": "I usually do long runs before work.",
  "source_segments": ["seg-021"]
}
```

This should be stored in the extraction artifact for evaluation and tuning.

It does not require a new review UI in the first implementation.

## 19. Example Pass 2 Output

```json
{
  "schema_version": "3.0.0-pass2",
  "communication_id": "ffffffff-9999-4000-8000-000000000001",
  "extraction_summary": "Tyler moved a memo deadline, recommended an option, and disclosed useful background context.",
  "routing_assessment": {
    "primary_matter_id": "cccccccc-3333-4000-8000-000000000001",
    "secondary_matter_ids": [],
    "routing_confidence": "high",
    "routing_basis": [
      "speaker is matter stakeholder",
      "open task match"
    ],
    "standalone_reason": null,
    "new_matter_candidate": false
  },
  "bundles": [
    {
      "bundle_type": "matter",
      "target_matter_id": "cccccccc-3333-4000-8000-000000000001",
      "target_matter_title": "Crypto Derivatives NPRM",
      "proposed_matter": null,
      "confidence": 0.94,
      "rationale": "Most changes belong to the crypto NPRM matter.",
      "intelligence_notes": null,
      "uncertainty_flags": [],
      "items": [
        {
          "item_type": "task_update",
          "proposed_data": {
            "existing_task_id": "dddddddd-4444-4000-8000-000000000001",
            "changes": {
              "due_date": "2026-04-15",
              "priority": "high",
              "deadline_type": "soft"
            }
          },
          "confidence": 0.95,
          "rationale": "The existing memo task clearly changed.",
          "why_new_vs_update": "Existing task match is strong.",
          "why_this_matter": "The memo is already tracked under the routed matter.",
          "source_observation_ids": ["obs_001"],
          "source_evidence": [
            {
              "excerpt": "I need it by the 15th now, not end of month.",
              "speaker": "Tyler S. Badgley",
              "segments": ["seg-005"]
            }
          ]
        },
        {
          "item_type": "person_detail_update",
          "proposed_data": {
            "person_id": "aaaaaaaa-1111-4000-8000-000000000001",
            "fields": {
              "education_summary": "Georgetown Law",
              "prior_roles_summary": "Approximately eight years at the SEC, Division of Trading and Markets"
            }
          },
          "confidence": 0.91,
          "rationale": "Directly stated, durable, and useful relationship memory.",
          "why_new_vs_update": "No new record is needed; this belongs on the existing person profile.",
          "why_this_matter": "Not matter-dependent, but included in the same communication bundle.",
          "source_observation_ids": ["obs_008"],
          "source_evidence": [
            {
              "excerpt": "I went to Georgetown Law, actually.",
              "speaker": "Tyler S. Badgley",
              "segments": ["seg-009"]
            }
          ]
        }
      ]
    }
  ],
  "suppressed_observations": []
}
```

## 20. Recommended Next Step

Use this schema document to define:

1. the Pass 1 pydantic model
2. the deterministic routing package contract
3. the Pass 2 pydantic model
4. the new prompts for both LLM passes
