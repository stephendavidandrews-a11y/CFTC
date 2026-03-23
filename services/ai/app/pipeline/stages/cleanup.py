"""Haiku cleanup stage — removes transcription artifacts from raw text.

Pipeline position: transcribing → **cleaning** → awaiting_speaker_review

Takes raw_text from transcript segments, sends to Haiku for cleanup
(filler removal, punctuation, false start repair), writes cleaned_text.
Runs BEFORE speaker review since cleanup doesn't need speaker identity.

Batching: segments are batched to reduce API calls. Default batch size
is 15 segments per call (~2-4K tokens per call for typical conversations).
"""

import json
import logging

from app.config import load_policy, PROMPT_BASE_DIR
from app.llm.client import call_llm

logger = logging.getLogger(__name__)

# Prompt file location — centralized via config.PROMPT_BASE_DIR
PROMPT_DIR = PROMPT_BASE_DIR / "haiku_cleanup"

# Batch size: how many segments per Haiku call
CLEANUP_BATCH_SIZE = 15


def _load_system_prompt(version: str) -> str:
    """Load the cleanup system prompt for the given version."""
    prompt_path = PROMPT_DIR / f"{version}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Cleanup prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _build_batch_payload(segments: list[dict]) -> str:
    """Build the user prompt payload for a batch of segments."""
    batch = []
    for seg in segments:
        batch.append({
            "id": seg["id"],
            "speaker": seg["speaker_label"],
            "text": seg["raw_text"],
            "confidence": round(seg["confidence"], 3) if seg["confidence"] else None,
        })
    return json.dumps(batch, ensure_ascii=False)


def _parse_cleanup_response(text: str, segment_ids: set[str]) -> tuple[dict[str, str], str | None]:
    """Parse Haiku's cleanup response into ({segment_id: cleaned_text}, proposed_title).

    Tolerates markdown fencing, partial responses, and both old (array)
    and new (object with segments + proposed_title) formats.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("Cleanup response JSON parse failed: %s", e)
        return {}, None

    # Handle both formats: bare array (old) or object with segments key (new)
    proposed_title = None
    if isinstance(parsed, dict):
        proposed_title = parsed.get("proposed_title")
        items = parsed.get("segments", [])
    elif isinstance(parsed, list):
        items = parsed
    else:
        logger.warning("Cleanup response is unexpected type: %s", type(parsed).__name__)
        return {}, None

    result = {}
    for item in items:
        seg_id = item.get("id", "")
        cleaned_text = item.get("cleaned_text", "")
        if seg_id in segment_ids and cleaned_text:
            result[seg_id] = cleaned_text

    return result, proposed_title



def _build_correction_glossary(db) -> str:
    """Build a glossary appendix from accumulated human corrections."""
    try:
        rows = db.execute("""
            SELECT pattern_from, pattern_to, SUM(applied_count) as freq
            FROM transcript_corrections
            WHERE pattern_from IS NOT NULL AND pattern_to IS NOT NULL
              AND LENGTH(pattern_from) >= 3
            GROUP BY LOWER(pattern_from), LOWER(pattern_to)
            HAVING freq >= 2
            ORDER BY freq DESC
            LIMIT 50
        """).fetchall()
    except Exception:
        return ""

    if not rows:
        return ""

    lines = ["## Domain Corrections (learned from reviewer feedback)",
             "These corrections have been consistently made by reviewers. Apply them proactively:"]
    for row in rows:
        lines.append(f'- "{row["pattern_from"]}" \u2192 "{row["pattern_to"]}" ({row["freq"]} occurrences)')

    return "\n".join(lines)


async def run_cleanup_stage(db, communication_id: str) -> dict:
    """Run Haiku cleanup on all transcript segments for a communication.

    Returns summary dict with segment counts and total cost.
    Raises BudgetExceededError if budget is exhausted.
    """
    # Load config
    policy = load_policy()
    model_config = policy.get("model_config", {})
    haiku_model = model_config.get("haiku_model", "claude-haiku-4-5-20251001")
    prompt_version = model_config.get("active_prompt_versions", {}).get(
        "haiku_cleanup", "v1.0.0"
    )

    system_prompt = _load_system_prompt(prompt_version)

    # Inject learned correction glossary into system prompt
    glossary = _build_correction_glossary(db)
    if glossary:
        system_prompt += "\n\n" + glossary

    # Fetch raw transcript segments
    rows = db.execute("""
        SELECT id, speaker_label, raw_text, confidence
        FROM transcripts
        WHERE communication_id = ? AND raw_text IS NOT NULL
        ORDER BY start_time
    """, (communication_id,)).fetchall()

    if not rows:
        logger.info("[%s] No transcript segments to clean", communication_id[:8])
        return {"segments_cleaned": 0, "total_cost_usd": 0.0}

    segments = [dict(r) for r in rows]
    total_cost = 0.0
    total_cleaned = 0
    total_input_tokens = 0
    total_output_tokens = 0
    proposed_title = None

    # Process in batches
    for batch_start in range(0, len(segments), CLEANUP_BATCH_SIZE):
        batch = segments[batch_start:batch_start + CLEANUP_BATCH_SIZE]
        batch_ids = {seg["id"] for seg in batch}

        user_prompt = _build_batch_payload(batch)

        response = await call_llm(
            db=db,
            communication_id=communication_id,
            stage="cleaning",
            model=haiku_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
        )

        total_cost += response.usage.cost_usd
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Parse and apply
        cleaned_map, batch_title = _parse_cleanup_response(response.text, batch_ids)

        # Use proposed title from first batch (most informative)
        if batch_start == 0 and batch_title:
            proposed_title = batch_title

        for seg_id, cleaned_text in cleaned_map.items():
            db.execute(
                "UPDATE transcripts SET cleaned_text = ? WHERE id = ?",
                (cleaned_text, seg_id),
            )
            total_cleaned += 1

        # For segments that didn't get cleaned (parse failure), copy raw_text as fallback
        for seg in batch:
            if seg["id"] not in cleaned_map:
                db.execute(
                    "UPDATE transcripts SET cleaned_text = ? WHERE id = ?",
                    (seg["raw_text"], seg["id"]),
                )
                total_cleaned += 1
                logger.debug(
                    "[%s] Segment %s: cleanup miss, using raw text",
                    communication_id[:8], seg["id"][:8],
                )

        db.commit()

        logger.info(
            "[%s] Cleanup batch %d-%d: %d/%d cleaned ($%.4f)",
            communication_id[:8],
            batch_start, batch_start + len(batch),
            len(cleaned_map), len(batch),
            response.usage.cost_usd,
        )

    # Write proposed title if communication has no title yet
    if proposed_title:
        row = db.execute(
            "SELECT title FROM communications WHERE id = ?",
            (communication_id,),
        ).fetchone()
        current_title = row["title"] if row else None
        if not current_title or current_title.strip() == "":
            db.execute(
                "UPDATE communications SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (proposed_title, communication_id),
            )
            db.commit()
            logger.info("[%s] Title set from cleanup: %s", communication_id[:8], proposed_title)

    logger.info(
        "[%s] Cleanup complete: %d segments, %d in + %d out tokens, $%.4f",
        communication_id[:8], total_cleaned,
        total_input_tokens, total_output_tokens, total_cost,
    )

    return {
        "segments_cleaned": total_cleaned,
        "segments_total": len(segments),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_cost_usd": round(total_cost, 6),
    }
