"""Speaker review API — human gate for confirming diarized speaker identities.

After transcription + Haiku cleanup, audio communications enter
awaiting_speaker_review. This router provides endpoints to:
1. List communications needing speaker review
2. Get speaker details + transcript + voiceprint candidates
3. Link a speaker to an existing tracker person (with optional voiceprint confirm)
4. Create a provisional new person for an unknown speaker
5. Skip a speaker (mark as unresolved)
6. Reject a voiceprint suggestion (audit only)
7. Complete speaker review (advances pipeline to enrichment)

Design principles:
- Human-in-the-loop only — no auto-confirm at any threshold
- Voiceprint candidates are suggestions, never auto-assigned
- Provisional people have no tracker_person_id until bundle commit
- Full audit trail in voiceprint_match_log + review_action_log
"""
import json
import logging
import uuid
import difflib
import re as re_module
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from app.db import get_db
from app.pipeline.orchestrator import cas_transition
from app.routers.events import publish_event
from app.voiceprint.matcher import match_all_speakers
from app.voiceprint.profiles import promote_sample_to_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speaker-review", tags=["speaker-review"])

SPEAKER_REVIEW_STATES = {"awaiting_speaker_review", "speaker_review_in_progress"}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LinkSpeakerRequest(BaseModel):
    """Link a speaker to an existing tracker person."""
    participant_id: str
    tracker_person_id: str
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None
    voiceprint_match_log_id: Optional[str] = None  # if confirming a voiceprint candidate


class NewPersonRequest(BaseModel):
    """Create a provisional new person for an unknown speaker."""
    participant_id: str
    proposed_name: str
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None
    proposed_org_id: Optional[str] = None
    participant_role: Optional[str] = None


class SkipSpeakerRequest(BaseModel):
    participant_id: str


class RejectMatchRequest(BaseModel):
    """Reject a voiceprint suggestion (audit log only, no state change)."""
    participant_id: str
    match_log_id: str
    reason: Optional[str] = None


class SpeakerInfo(BaseModel):
    id: str
    speaker_label: Optional[str] = None
    tracker_person_id: Optional[str] = None
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None
    participant_role: Optional[str] = None
    match_source: Optional[str] = None
    confirmed: bool = False
    voiceprint_confidence: Optional[float] = None
    voiceprint_method: Optional[str] = None
    # Computed fields
    speech_seconds: Optional[float] = None
    sample_utterances: Optional[list[str]] = None
    voiceprint_candidates: Optional[list[dict]] = None


class SpeakerReviewDetail(BaseModel):
    communication_id: str
    processing_status: str
    original_filename: Optional[str] = None
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    speakers: list[SpeakerInfo]
    transcript_segments: list[dict]
    voiceprint_summary: Optional[dict] = None  # overall match stats


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/queue")
async def get_speaker_review_queue(db=Depends(get_db)):
    """List all audio communications awaiting speaker review."""
    rows = db.execute("""
        SELECT c.id, c.original_filename, c.title, c.processing_status,
               c.source_type, c.duration_seconds,
               c.created_at, c.updated_at,
               (SELECT COUNT(*) FROM communication_participants cp
                WHERE cp.communication_id = c.id) as speaker_count,
               (SELECT COUNT(*) FROM communication_participants cp
                WHERE cp.communication_id = c.id AND cp.confirmed = 1) as confirmed_count
        FROM communications c
        WHERE c.processing_status IN ('awaiting_speaker_review', 'speaker_review_in_progress')
        ORDER BY c.created_at ASC
    """).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": len(rows),
    }


@router.get("/{communication_id}")
async def get_speaker_review_detail(communication_id: str, db=Depends(get_db)):
    """Get detailed speaker information + transcript + voiceprint candidates for review."""
    comm = db.execute(
        """SELECT id, processing_status, original_filename, title, duration_seconds
           FROM communications WHERE id = ?""",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    # Participants (speakers)
    participants = db.execute("""
        SELECT id, speaker_label, tracker_person_id, proposed_name,
               proposed_title, proposed_org, participant_role,
               match_source, confirmed, voiceprint_confidence, voiceprint_method
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY speaker_label
    """, (communication_id,)).fetchall()

    # Transcript segments (cleaned preferred, fall back to raw)
    segments = db.execute("""
        SELECT id, speaker_label, start_time, end_time,
               COALESCE(reviewed_text, cleaned_text, raw_text) as text,
               confidence
        FROM transcripts
        WHERE communication_id = ?
        ORDER BY start_time
    """, (communication_id,)).fetchall()

    # Run voiceprint matching (on-demand, always uses latest profile library)
    vp_results = match_all_speakers(db, communication_id)

    # Build speaker info with computed fields
    speakers = []
    matched_count = 0
    for p in participants:
        label = p["speaker_label"]

        # Compute speech duration
        dur_row = db.execute(
            "SELECT SUM(end_time - start_time) as total FROM transcripts WHERE communication_id = ? AND speaker_label = ?",
            (communication_id, label),
        ).fetchone()
        speech_secs = round(dur_row["total"], 1) if dur_row and dur_row["total"] else 0.0

        # Get sample utterances (first 3 things this speaker said)
        first_utterances = db.execute("""
            SELECT COALESCE(reviewed_text, cleaned_text, raw_text) as text
            FROM transcripts
            WHERE communication_id = ? AND speaker_label = ?
            ORDER BY start_time LIMIT 3
        """, (communication_id, label)).fetchall()
        utterances = [u["text"] for u in first_utterances if u["text"]]

        # Voiceprint candidates for this speaker
        vp = vp_results.get(label, {})
        candidates = vp.get("candidates", [])
        if candidates:
            matched_count += 1

        speakers.append(SpeakerInfo(
            id=p["id"],
            speaker_label=label,
            tracker_person_id=p["tracker_person_id"],
            proposed_name=p["proposed_name"],
            proposed_title=p["proposed_title"],
            proposed_org=p["proposed_org"],
            participant_role=p["participant_role"],
            match_source=p["match_source"],
            confirmed=bool(p["confirmed"]),
            voiceprint_confidence=p["voiceprint_confidence"],
            voiceprint_method=p["voiceprint_method"],
            speech_seconds=speech_secs,
            sample_utterances=utterances,
            voiceprint_candidates=candidates if candidates else None,
        ))

    vp_summary = {
        "total_speakers": len(speakers),
        "speakers_with_candidates": matched_count,
        "profiles_in_library": db.execute(
            "SELECT COUNT(*) as cnt FROM speaker_voice_profiles WHERE status = 'active'"
        ).fetchone()["cnt"],
    }

    return SpeakerReviewDetail(
        communication_id=communication_id,
        processing_status=comm["processing_status"],
        original_filename=comm["original_filename"],
        title=comm["title"],
        duration_seconds=comm["duration_seconds"],
        speakers=speakers,
        transcript_segments=[dict(s) for s in segments],
        voiceprint_summary=vp_summary,
    )


@router.post("/{communication_id}/link-speaker")
async def link_speaker(
    communication_id: str,
    req: LinkSpeakerRequest,
    db=Depends(get_db),
):
    """Link a speaker to an existing tracker person.

    This is the primary confirm action — either confirming a voiceprint suggestion
    or manually linking via search/select. Also triggers quality-gated profile promotion.
    """
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    # Get the participant record to find speaker_label
    participant = db.execute(
        "SELECT id, speaker_label FROM communication_participants WHERE id = ? AND communication_id = ?",
        (req.participant_id, communication_id),
    ).fetchone()
    if not participant:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Participant {req.participant_id} not found",
        })

    # Determine match source
    match_source = "voiceprint_confirmed" if req.voiceprint_match_log_id else "manual"

    # Update participant
    db.execute("""
        UPDATE communication_participants
        SET tracker_person_id = ?,
            proposed_name = COALESCE(?, proposed_name),
            proposed_title = COALESCE(?, proposed_title),
            proposed_org = COALESCE(?, proposed_org),
            confirmed = 1,
            match_source = ?,
            voiceprint_method = ?,
            updated_at = datetime('now')
        WHERE id = ? AND communication_id = ?
    """, (
        req.tracker_person_id,
        req.proposed_name, req.proposed_title, req.proposed_org,
        match_source,
        match_source,
        req.participant_id, communication_id,
    ))

    # If confirming a voiceprint candidate, update the match log
    if req.voiceprint_match_log_id:
        db.execute("""
            UPDATE voiceprint_match_log
            SET reviewer_action = 'confirmed',
                confirmed_person_id = ?,
                reviewed_at = datetime('now')
            WHERE id = ?
        """, (req.tracker_person_id, req.voiceprint_match_log_id))

    # Audit log
    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, 'link_speaker', ?)
    """, (
        str(uuid.uuid4()), communication_id,
        json.dumps({
            "participant_id": req.participant_id,
            "speaker_label": participant["speaker_label"],
            "tracker_person_id": req.tracker_person_id,
            "match_source": match_source,
            "voiceprint_match_log_id": req.voiceprint_match_log_id,
        }),
    ))
    db.commit()

    # Quality-gated profile promotion (non-blocking)
    profile_result = promote_sample_to_profile(
        db, communication_id, participant["speaker_label"], req.tracker_person_id
    )

    return {
        "status": "ok",
        "participant_id": req.participant_id,
        "confirmed": True,
        "match_source": match_source,
        "profile_promotion": profile_result,
    }


@router.post("/{communication_id}/new-person")
async def create_provisional_person(
    communication_id: str,
    req: NewPersonRequest,
    db=Depends(get_db),
):
    """Create a provisional new person for an unknown speaker.

    Sets proposed_name/title/org on the participant record with tracker_person_id=NULL.
    The extraction stage will later propose a new_person bundle item for commit.
    No voiceprint profile is created (no tracker_person_id to anchor it).
    """
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    # Verify participant exists
    participant = db.execute(
        "SELECT id, speaker_label FROM communication_participants WHERE id = ? AND communication_id = ?",
        (req.participant_id, communication_id),
    ).fetchone()
    if not participant:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Participant {req.participant_id} not found",
        })

    # Update participant with provisional person info
    db.execute("""
        UPDATE communication_participants
        SET tracker_person_id = NULL,
            proposed_name = ?,
            proposed_title = ?,
            proposed_org = ?,
            proposed_org_id = ?,
            participant_role = COALESCE(?, participant_role),
            confirmed = 1,
            match_source = 'provisional',
            voiceprint_method = NULL,
            voiceprint_confidence = NULL,
            updated_at = datetime('now')
        WHERE id = ? AND communication_id = ?
    """, (
        req.proposed_name, req.proposed_title, req.proposed_org,
        req.proposed_org_id, req.participant_role,
        req.participant_id, communication_id,
    ))

    # Update any voiceprint match log entries for this speaker
    db.execute("""
        UPDATE voiceprint_match_log
        SET reviewer_action = 'new_person', reviewed_at = datetime('now')
        WHERE communication_id = ? AND speaker_label = ? AND reviewer_action IS NULL
    """, (communication_id, participant["speaker_label"]))

    # Audit log
    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, 'create_provisional_person', ?)
    """, (
        str(uuid.uuid4()), communication_id,
        json.dumps({
            "participant_id": req.participant_id,
            "speaker_label": participant["speaker_label"],
            "proposed_name": req.proposed_name,
            "proposed_title": req.proposed_title,
            "proposed_org": req.proposed_org,
        }),
    ))
    db.commit()

    return {
        "status": "ok",
        "participant_id": req.participant_id,
        "confirmed": True,
        "match_source": "provisional",
        "proposed_name": req.proposed_name,
    }


@router.post("/{communication_id}/skip-speaker")
async def skip_speaker(
    communication_id: str,
    req: SkipSpeakerRequest,
    db=Depends(get_db),
):
    """Mark a speaker as skipped/unresolved. Confirmed=1 so pipeline can advance."""
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    participant = db.execute(
        "SELECT id, speaker_label FROM communication_participants WHERE id = ? AND communication_id = ?",
        (req.participant_id, communication_id),
    ).fetchone()
    if not participant:
        raise HTTPException(404, detail={"error_type": "not_found"})

    db.execute("""
        UPDATE communication_participants
        SET confirmed = 1, match_source = 'skipped', updated_at = datetime('now')
        WHERE id = ? AND communication_id = ?
    """, (req.participant_id, communication_id))

    # Update any voiceprint match log entries
    db.execute("""
        UPDATE voiceprint_match_log
        SET reviewer_action = 'skipped', reviewed_at = datetime('now')
        WHERE communication_id = ? AND speaker_label = ? AND reviewer_action IS NULL
    """, (communication_id, participant["speaker_label"]))

    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, 'skip_speaker', ?)
    """, (
        str(uuid.uuid4()), communication_id,
        json.dumps({"participant_id": req.participant_id, "speaker_label": participant["speaker_label"]}),
    ))
    db.commit()

    return {"status": "ok", "participant_id": req.participant_id, "skipped": True}


@router.post("/{communication_id}/reject-match")
async def reject_match(
    communication_id: str,
    req: RejectMatchRequest,
    db=Depends(get_db),
):
    """Reject a voiceprint suggestion. Audit log only — does not change participant state."""
    _check_review_state(db, communication_id)

    # Update voiceprint match log
    result = db.execute("""
        UPDATE voiceprint_match_log
        SET reviewer_action = 'rejected', reviewed_at = datetime('now')
        WHERE id = ? AND communication_id = ?
    """, (req.match_log_id, communication_id))

    if result.rowcount == 0:
        raise HTTPException(404, detail={"error_type": "not_found", "message": "Match log entry not found"})

    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, 'reject_voiceprint_match', ?)
    """, (
        str(uuid.uuid4()), communication_id,
        json.dumps({
            "participant_id": req.participant_id,
            "match_log_id": req.match_log_id,
            "reason": req.reason,
        }),
    ))
    db.commit()

    return {"status": "ok", "match_log_id": req.match_log_id, "rejected": True}


@router.post("/{communication_id}/complete")
async def complete_speaker_review(
    communication_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Complete speaker review and advance the pipeline to enrichment.

    All speakers must be confirmed (linked, provisional, or skipped) before completing.
    Transitions: speaker_review_in_progress -> speakers_confirmed
    """
    comm = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    status = comm["processing_status"]
    if status not in SPEAKER_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in speaker review (current: {status})",
        })

    # Check all confirmed
    unconfirmed = db.execute("""
        SELECT id, speaker_label FROM communication_participants
        WHERE communication_id = ? AND confirmed = 0
    """, (communication_id,)).fetchall()

    if unconfirmed:
        labels = [r["speaker_label"] for r in unconfirmed]
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Unconfirmed speakers remain: {labels}",
            "unconfirmed_speakers": labels,
        })

    # Advance state
    if status == "awaiting_speaker_review":
        cas_transition(db, communication_id, "awaiting_speaker_review", "speaker_review_in_progress")

    if not cas_transition(db, communication_id, "speaker_review_in_progress", "speakers_confirmed"):
        raise HTTPException(409, detail={"error_type": "conflict"})

    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, old_state, new_state)
        VALUES (?, 'user', ?, 'complete_speaker_review', 'speaker_review_in_progress', 'speakers_confirmed')
    """, (str(uuid.uuid4()), communication_id))
    db.commit()

    await publish_event("speaker_review_complete", {
        "communication_id": communication_id,
        "status": "speakers_confirmed",
    })

    background_tasks.add_task(_resume_pipeline, communication_id)

    return {"status": "speakers_confirmed", "communication_id": communication_id}


@router.get("/{communication_id}/transcript")
async def get_transcript(communication_id: str, db=Depends(get_db)):
    """Get the full transcript for display during speaker review."""
    segments = db.execute("""
        SELECT id, speaker_label, start_time, end_time,
               COALESCE(reviewed_text, cleaned_text, raw_text) as text,
               confidence
        FROM transcripts
        WHERE communication_id = ?
        ORDER BY start_time
    """, (communication_id,)).fetchall()

    return {
        "communication_id": communication_id,
        "segments": [dict(s) for s in segments],
        "total": len(segments),
    }


# ---------------------------------------------------------------------------
# Voiceprint Profile Management (Phase D — minimal CRUD)
# ---------------------------------------------------------------------------

@router.get("/profiles/list")
async def list_voice_profiles(status: Optional[str] = "active", db=Depends(get_db)):
    """List all voice profiles in the library."""
    from app.voiceprint.profiles import list_profiles
    profiles = list_profiles(db, status=status)
    return {"profiles": profiles, "total": len(profiles)}


@router.get("/profiles/{tracker_person_id}")
async def get_voice_profile(tracker_person_id: str, db=Depends(get_db)):
    """Get a specific voice profile with contributing sample history."""
    from app.voiceprint.profiles import get_profile, get_sample_history
    profile = get_profile(db, tracker_person_id)
    if not profile:
        raise HTTPException(404, detail={"error_type": "not_found", "message": "No voice profile for this person"})
    samples = get_sample_history(db, tracker_person_id)
    return {"profile": profile, "sample_history": samples}


@router.post("/profiles/{tracker_person_id}/deactivate")
async def deactivate_voice_profile(tracker_person_id: str, db=Depends(get_db)):
    """Deactivate a voice profile (stops matching). Can be reactivated later."""
    from app.voiceprint.profiles import deactivate_profile
    if not deactivate_profile(db, tracker_person_id):
        raise HTTPException(404, detail={"error_type": "not_found"})
    db.execute("""
        INSERT INTO review_action_log (id, actor, action_type, details)
        VALUES (?, 'user', 'deactivate_voice_profile', ?)
    """, (str(uuid.uuid4()), json.dumps({"tracker_person_id": tracker_person_id})))
    db.commit()
    return {"status": "deactivated", "tracker_person_id": tracker_person_id}


@router.post("/profiles/{tracker_person_id}/activate")
async def activate_voice_profile(tracker_person_id: str, db=Depends(get_db)):
    """Reactivate an inactive voice profile."""
    from app.voiceprint.profiles import activate_profile
    if not activate_profile(db, tracker_person_id):
        raise HTTPException(404, detail={"error_type": "not_found"})
    db.execute("""
        INSERT INTO review_action_log (id, actor, action_type, details)
        VALUES (?, 'user', 'activate_voice_profile', ?)
    """, (str(uuid.uuid4()), json.dumps({"tracker_person_id": tracker_person_id})))
    db.commit()
    return {"status": "active", "tracker_person_id": tracker_person_id}




# ---------------------------------------------------------------------------
# Transcript editing endpoints
# ---------------------------------------------------------------------------

@router.patch("/{communication_id}/transcripts/{transcript_id}")
async def edit_transcript_segment(communication_id: str, transcript_id: str, request: Request, db=Depends(get_db)):
    """Save human-corrected text for a transcript segment."""
    body = await request.json()
    reviewed_text = body.get("reviewed_text", "").strip()
    if not reviewed_text:
        raise HTTPException(400, "reviewed_text is required")

    # Get current text
    seg = db.execute(
        "SELECT cleaned_text, raw_text FROM transcripts WHERE id = ? AND communication_id = ?",
        (transcript_id, communication_id),
    ).fetchone()
    if not seg:
        raise HTTPException(404, "Transcript segment not found")

    original_text = seg["cleaned_text"] or seg["raw_text"] or ""

    # If no actual change, skip
    if reviewed_text == original_text:
        return {"changed": False, "similar_count": 0}

    # Write reviewed_text
    db.execute(
        "UPDATE transcripts SET reviewed_text = ? WHERE id = ?",
        (reviewed_text, transcript_id),
    )

    # Extract pattern (find the longest differing substring)
    pattern_from, pattern_to = _extract_correction_pattern(original_text, reviewed_text)

    # Log correction
    correction_id = str(uuid.uuid4())
    db.execute("""
        INSERT INTO transcript_corrections
            (id, communication_id, transcript_id, original_text, corrected_text,
             correction_type, pattern_from, pattern_to, applied_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        correction_id, communication_id, transcript_id,
        original_text, reviewed_text,
        "manual", pattern_from, pattern_to,
    ))

    # Count similar segments (quick string match)
    similar_count = 0
    if pattern_from and len(pattern_from) >= 3:
        row = db.execute("""
            SELECT COUNT(*) as cnt FROM transcripts
            WHERE communication_id = ? AND id != ?
              AND reviewed_text IS NULL
              AND LOWER(COALESCE(cleaned_text, raw_text, '')) LIKE ?
        """, (communication_id, transcript_id, f"%{pattern_from.lower()}%")).fetchone()
        similar_count = row["cnt"] if row else 0

    db.commit()

    return {
        "changed": True,
        "correction_id": correction_id,
        "pattern_from": pattern_from,
        "pattern_to": pattern_to,
        "similar_count": similar_count,
    }


@router.post("/{communication_id}/transcripts/find-similar")
async def find_similar_corrections(communication_id: str, request: Request, db=Depends(get_db)):
    """Find other segments with similar text that could receive the same correction."""
    body = await request.json()
    correction_id = body.get("correction_id")

    if not correction_id:
        raise HTTPException(400, "correction_id is required")


    # Get the correction pattern
    corr = db.execute(
        "SELECT pattern_from, pattern_to, original_text, corrected_text FROM transcript_corrections WHERE id = ?",
        (correction_id,),
    ).fetchone()
    if not corr:
        raise HTTPException(404, "Correction not found")

    pattern_from = corr["pattern_from"]
    pattern_to = corr["pattern_to"]

    if not pattern_from or len(pattern_from) < 2:
        return {"candidates": []}

    # Find segments containing the pattern
    rows = db.execute("""
        SELECT id, speaker_label, start_time,
               COALESCE(cleaned_text, raw_text, '') as current_text
        FROM transcripts
        WHERE communication_id = ? AND reviewed_text IS NULL
          AND LOWER(COALESCE(cleaned_text, raw_text, '')) LIKE ?
        ORDER BY start_time
    """, (communication_id, f"%{pattern_from.lower()}%")).fetchall()

    candidates = []
    for row in rows:
        current = row["current_text"]
        # Case-insensitive replacement for the suggested text
        suggested = re_module.sub(re_module.escape(pattern_from), pattern_to, current, flags=re_module.IGNORECASE)

        candidates.append({
            "transcript_id": row["id"],
            "speaker_label": row["speaker_label"],
            "start_time": row["start_time"],
            "current_text": current,
            "suggested_text": suggested,
            "match_type": "exact",
        })

    return {"candidates": candidates, "pattern_from": pattern_from, "pattern_to": pattern_to}


@router.post("/{communication_id}/transcripts/apply-corrections")
async def apply_corrections(communication_id: str, request: Request, db=Depends(get_db)):
    """Bulk-apply reviewed_text corrections to selected segments."""
    body = await request.json()
    corrections = body.get("corrections", [])
    correction_id = body.get("correction_id")  # original correction for logging

    if not corrections:
        raise HTTPException(400, "corrections list is required")


    # Get original correction pattern for logging
    pattern_from = None
    pattern_to = None
    if correction_id:
        corr = db.execute(
            "SELECT pattern_from, pattern_to FROM transcript_corrections WHERE id = ?",
            (correction_id,),
        ).fetchone()
        if corr:
            pattern_from = corr["pattern_from"]
            pattern_to = corr["pattern_to"]

    applied = 0
    for item in corrections:
        tid = item.get("transcript_id")
        text = item.get("reviewed_text", "").strip()
        if not tid or not text:
            continue

        # Get original for logging
        seg = db.execute(
            "SELECT COALESCE(cleaned_text, raw_text, '') as original FROM transcripts WHERE id = ? AND communication_id = ?",
            (tid, communication_id),
        ).fetchone()
        if not seg:
            continue

        db.execute(
            "UPDATE transcripts SET reviewed_text = ? WHERE id = ?",
            (text, tid),
        )

        # Log each propagated correction
        db.execute("""
            INSERT INTO transcript_corrections
                (id, communication_id, transcript_id, original_text, corrected_text,
                 correction_type, pattern_from, pattern_to, applied_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            str(uuid.uuid4()), communication_id, tid,
            seg["original"], text,
            "propagated", pattern_from, pattern_to,
        ))
        applied += 1

    # Update applied_count on original correction
    if correction_id and applied > 0:
        db.execute(
            "UPDATE transcript_corrections SET applied_count = applied_count + ? WHERE id = ?",
            (applied, correction_id),
        )

    db.commit()

    return {"applied": applied}


def _extract_correction_pattern(original: str, corrected: str):
    """Extract the most meaningful changed substring between original and corrected text.

    Returns (pattern_from, pattern_to) -- the changed parts.
    """
    sm = difflib.SequenceMatcher(None, original.lower(), corrected.lower())

    best_from = ""
    best_to = ""

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        chunk_from = original[i1:i2].strip()
        chunk_to = corrected[j1:j2].strip()
        if len(chunk_from) + len(chunk_to) > len(best_from) + len(best_to):
            best_from = chunk_from
            best_to = chunk_to

    if not best_from and not best_to:
        return None, None

    return best_from or None, best_to or None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_review_state(db, communication_id: str):
    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["processing_status"] not in SPEAKER_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in speaker review (current: {row['processing_status']})",
        })


def _ensure_in_progress(db, communication_id: str):
    """Auto-transition from awaiting → in_progress on first interaction."""
    cas_transition(db, communication_id, "awaiting_speaker_review", "speaker_review_in_progress")


async def _resume_pipeline(communication_id: str):
    from app.pipeline.orchestrator import process_communication
    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline resume failed for %s: %s", communication_id, e)
