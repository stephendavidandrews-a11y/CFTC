/**
 * Composite priority scoring for matters.
 * Used by MattersPage (sort), TodayPage (top-7 priority actions), and any
 * future view that needs a single "how urgent is this matter?" number.
 *
 * Scoring breakdown:
 *   Priority weight        : critical=100, important=60, strategic=30
 *   Pending decision       : +25
 *   Deadline proximity     : overdue=+50, <=3d=+40, <=7d=+25, <=14d=+10
 *   Staleness (>14 days)   : +15  (stale matters need attention)
 */
export function matterRankScore(m) {
  let score = 0;
  // Priority weight
  if (m.priority === "critical this week") score += 100;
  else if (m.priority === "important this month") score += 60;
  else if (m.priority === "strategic / slow burn") score += 30;
  // Pending decision
  if (m.pending_decision && m.pending_decision.trim()) score += 25;
  // Deadline proximity (next 7 days = high, next 14 = medium)
  const deadline = m.work_deadline || m.external_deadline || m.decision_deadline;
  if (deadline) {
    const daysUntil = (new Date(deadline) - Date.now()) / (1000 * 60 * 60 * 24);
    if (daysUntil < 0) score += 50; // overdue
    else if (daysUntil <= 3) score += 40;
    else if (daysUntil <= 7) score += 25;
    else if (daysUntil <= 14) score += 10;
  }
  // Staleness penalty (newer = higher)
  if (m.updated_at) {
    const daysSinceUpdate = (Date.now() - new Date(m.updated_at).getTime()) / (1000 * 60 * 60 * 24);
    if (daysSinceUpdate > 14) score += 15; // stale matters need attention
  }
  return score;
}
