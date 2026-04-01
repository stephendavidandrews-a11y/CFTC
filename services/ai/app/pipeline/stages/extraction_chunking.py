"""Transcript chunking for long recordings.

When a transcript exceeds the model's context budget, this module splits it
into overlapping chunks, each small enough for a single extraction call.
After extraction, results from all chunks are merged and deduplicated.

Used by extraction.py — all other extraction modules are unaffected.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_INPUT_TOKENS = 135_000  # Leave 64K for output + 1K buffer
OVERLAP_SECONDS = 60  # Seconds of overlap between adjacent chunks


def estimate_tokens(text: str) -> int:
    """Conservative token estimate: ~3 chars per token for JSON-heavy content."""
    return len(text) // 3


def fetch_transcript_segments(db, communication_id: str) -> list[dict]:
    """Fetch all transcript segments for a communication."""
    rows = db.execute(
        """
        SELECT id, speaker_label, start_time, end_time,
               reviewed_text, cleaned_text, raw_text
        FROM transcripts
        WHERE communication_id = ?
        ORDER BY start_time
    """,
        (communication_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _segment_token_cost(seg: dict) -> int:
    """Estimate token cost of one transcript segment (text + JSON overhead)."""
    text = (
        seg.get("reviewed_text")
        or seg.get("cleaned_text")
        or seg.get("raw_text")
        or ""
    )
    return estimate_tokens(text) + 30  # ~30 tokens for JSON keys/formatting


def chunk_transcript_segments(
    segments: list[dict],
    max_transcript_tokens: int,
    topic_boundaries: Optional[list[float]] = None,
) -> list[list[dict]]:
    """Split transcript segments into chunks that fit within token budget.

    Each segment's token cost is estimated from its text content.
    Splits prefer topic boundaries when available.
    Adjacent chunks overlap by OVERLAP_SECONDS.

    Returns list of segment lists (each list is one chunk).
    If everything fits in one chunk, returns [segments] unchanged.
    """
    if not segments:
        return [segments]

    seg_tokens = [_segment_token_cost(seg) for seg in segments]
    total_tokens = sum(seg_tokens)

    if total_tokens <= max_transcript_tokens:
        return [segments]

    # Build preferred split indices from topic boundaries
    preferred_splits = set()
    if topic_boundaries:
        for boundary_time in topic_boundaries:
            for i, seg in enumerate(segments):
                if seg.get("start_time", 0) >= boundary_time and i > 0:
                    preferred_splits.add(i)
                    break

    chunks = []
    chunk_start = 0

    while chunk_start < len(segments):
        running_tokens = 0
        chunk_end = chunk_start

        while chunk_end < len(segments):
            if running_tokens + seg_tokens[chunk_end] > max_transcript_tokens:
                break
            running_tokens += seg_tokens[chunk_end]
            chunk_end += 1

        if chunk_end == chunk_start:
            # Single segment exceeds budget — include it anyway
            chunk_end = chunk_start + 1

        # Snap to a preferred split point if one exists within 80-100% of chunk
        min_end = max(chunk_start + 1, int(chunk_end * 0.8))
        for candidate in range(chunk_end, min_end - 1, -1):
            if candidate in preferred_splits:
                chunk_end = candidate
                break

        chunks.append(segments[chunk_start:chunk_end])

        # Next chunk starts with overlap
        if chunk_end < len(segments):
            overlap_start = chunk_end
            end_time = segments[chunk_end].get("start_time", 0)
            for i in range(chunk_end - 1, max(chunk_start, chunk_end - 20), -1):
                seg_start = segments[i].get("start_time", 0)
                if end_time - seg_start >= OVERLAP_SECONDS:
                    overlap_start = i
                    break
            chunk_start = overlap_start
        else:
            break

    logger.info(
        "Transcript chunked into %d parts (%d segments, %d est tokens)",
        len(chunks),
        len(segments),
        total_tokens,
    )
    return chunks


def get_topic_boundaries(db, communication_id: str) -> Optional[list[float]]:
    """Extract topic boundary timestamps from enrichment data."""
    row = db.execute(
        "SELECT topic_segments_json FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row or not row["topic_segments_json"]:
        return None
    try:
        td = json.loads(row["topic_segments_json"])
        topics = td.get("topics", [])
        return [t["start_time"] for t in topics if t.get("start_time")]
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def merge_chunked_results(
    chunk_results: list,
    communication_id: str,
    full_context: dict,
    policy: dict,
    db,
) -> tuple:
    """Merge extraction results from multiple chunks.

    Returns (merged_extraction, merged_processed, total_usage).
    """
    from app.pipeline.stages.extraction_models import (
        ExtractionOutput,
    )
    from app.pipeline.stages.extraction_postprocess import _post_process

    all_bundles = []
    all_suppressed = []
    all_associations = []
    summaries = []
    total_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "processing_seconds": 0.0,
    }

    for result in chunk_results:
        if not result.success:
            continue
        ud = result.usage_data or {}
        total_usage["input_tokens"] += ud.get("input_tokens", 0)
        total_usage["output_tokens"] += ud.get("output_tokens", 0)
        total_usage["cost_usd"] += ud.get("cost_usd", 0.0)
        total_usage["processing_seconds"] += ud.get("processing_seconds", 0.0)

        if result.parsed_output:
            all_bundles.extend(result.parsed_output.bundles)
            all_suppressed.extend(result.parsed_output.suppressed_observations or [])
            all_associations.extend(result.parsed_output.matter_associations or [])
            if result.parsed_output.extraction_summary:
                summaries.append(result.parsed_output.extraction_summary)

    # Merge bundles by target_matter_id — deduplicate items
    merged_by_matter = {}
    for bundle in all_bundles:
        key = bundle.target_matter_id or bundle.target_matter_title or "unknown"
        if key not in merged_by_matter:
            merged_by_matter[key] = bundle
        else:
            existing = merged_by_matter[key]
            existing_sigs = set()
            for item in existing.items:
                sig = (
                    getattr(item, "item_type", ""),
                    (getattr(item, "title", None) or
                     (item.proposed_data or {}).get("title", "") or "")[:60].lower(),
                )
                existing_sigs.add(sig)

            for item in bundle.items:
                sig = (
                    getattr(item, "item_type", ""),
                    (getattr(item, "title", None) or
                     (item.proposed_data or {}).get("title", "") or "")[:60].lower(),
                )
                if sig not in existing_sigs:
                    existing.items.append(item)
                    existing_sigs.add(sig)

    # Deduplicate matter_associations by matter_id
    seen_assoc = set()
    deduped_associations = []
    for assoc in all_associations:
        if assoc.matter_id not in seen_assoc:
            deduped_associations.append(assoc)
            seen_assoc.add(assoc.matter_id)

    merged_extraction = ExtractionOutput(
        communication_id=communication_id,
        extraction_summary=" | ".join(summaries) if summaries else "Chunked extraction",
        bundles=list(merged_by_matter.values()),
        suppressed_observations=all_suppressed,
        matter_associations=deduped_associations,
    )

    # Post-process the merged result
    processed = _post_process(
        merged_extraction,
        full_context,
        policy,
        db,
        communication_id,
    )

    return merged_extraction, processed, total_usage
