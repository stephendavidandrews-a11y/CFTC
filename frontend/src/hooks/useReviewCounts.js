import { useState, useEffect, useCallback } from "react";

/**
 * Fetches review pipeline stage counts from /ai/api/health.
 * Polls on mount + every 60s. Falls back gracefully if AI service is down.
 */
export default function useReviewCounts() {
  const [counts, setCounts] = useState(null);

  const fetchCounts = useCallback(async () => {
    try {
      const res = await fetch("/ai/api/health");
      if (!res.ok) return;
      const data = await res.json();
      const q = data.queue || {};
      setCounts({
        speakers: (q.awaiting_speaker_review || 0) + (q.speaker_review_in_progress || 0),
        participants: (q.awaiting_participant_review || 0) + (q.participant_review_in_progress || 0)
                    + (q.awaiting_association_review || 0) + (q.association_review_in_progress || 0),
        bundles: (q.awaiting_bundle_review || 0) + (q.bundle_review_in_progress || 0),
        commit: q.reviewed || 0,
      });
    } catch {
      setCounts(null);
    }
  }, []);

  useEffect(() => {
    fetchCounts();
    const interval = setInterval(fetchCounts, 60000);
    return () => clearInterval(interval);
  }, [fetchCounts]);

  return counts;
}
