# CFTC Ops Tracker — Future Developments

## Daily Task Review Dashboard (Post-Commit Review Layer)

**Context**: After AI pipeline commits create tracker objects, the user needs a review step to see what was created and take action.

**Requirements**:
- Show all tasks created today (across all communications processed that day)
- Include conversation context: which communication each task came from, key quotes, participants
- Highlight tasks that need assignment (assigned_to_person_id is null)
- Highlight tasks that may need date adjustment (flagged as approximate/relative)
- Allow quick actions: assign person, adjust due date, edit title, mark as duplicate, dismiss
- Optionally group by matter or by communication source

**Not a replacement for bundle review** — this is a post-commit sanity check focused on "what landed in the tracker today and do I need to do anything about it."

**Priority**: Medium — becomes important once pipeline is processing multiple communications per day.
