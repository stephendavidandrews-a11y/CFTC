import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { useToastContext as useToast } from "../../contexts/ToastContext";
import {
  getSpeakerReviewDetail,
  linkSpeaker,
  createProvisionalPerson,
  skipSpeaker,
  rejectVoiceprintMatch,
  completeSpeakerReview,
  editTranscriptSegment,
  findSimilarCorrections,
  applyCorrections,
  unlinkSpeaker,
  mergeSpeakers,
} from "../../api/ai";
import ConfidenceIndicator from "../../components/shared/ConfidenceIndicator";
import PersonOrgResolver from "../../components/shared/PersonOrgResolver";

// ── Speaker colors (consistent per label) ─────────────────────────────────

const SPEAKER_COLORS = [
  "#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa",
  "#fb923c", "#22d3ee", "#f87171", "#a3e635", "#e879f9",
];

function speakerColor(label, speakers) {
  const idx = speakers.findIndex((s) => s.speaker_label === label);
  return SPEAKER_COLORS[idx % SPEAKER_COLORS.length];
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmtTime(s) {
  if (s == null) return "";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtDuration(s) {
  if (s == null) return "\u2014";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

// ── Voice Quality Badge ──────────────────────────────────────────────────

function VoiceQualityBadge({ quality }) {
  if (!quality) return null;

  const colors = {
    good: { bg: "rgba(74,222,128,0.12)", border: "rgba(74,222,128,0.3)", text: "#4ade80", icon: "✓" },
    fair: { bg: "rgba(250,204,21,0.12)", border: "rgba(250,204,21,0.3)", text: "#fbbf24", icon: "⚠" },
    poor: { bg: "rgba(248,113,113,0.12)", border: "rgba(248,113,113,0.3)", text: "#f87171", icon: "✖" },
  };
  const c = colors[quality.verdict] || colors.fair;

  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6,
      padding: "8px 10px", marginBottom: 8,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: c.text }}>{c.icon}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: c.text, textTransform: "uppercase" }}>
          Voice Quality: {quality.verdict}
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 10, color: theme.text.faint }}>
        {quality.hnr_db != null && (
          <span>HNR: <b style={{ color: quality.hnr_db >= 10 ? "#4ade80" : "#f87171" }}>{quality.hnr_db.toFixed(1)}dB</b></span>
        )}
        {quality.jitter != null && (
          <span>Jitter: <b style={{ color: quality.jitter <= 0.02 ? "#4ade80" : "#f87171" }}>{(quality.jitter * 100).toFixed(1)}%</b></span>
        )}
        {quality.shimmer != null && (
          <span>Shimmer: <b style={{ color: quality.shimmer <= 0.05 ? "#4ade80" : "#f87171" }}>{(quality.shimmer * 100).toFixed(1)}%</b></span>
        )}
        {quality.pitch_mean != null && (
          <span>Pitch: <b style={{ color: theme.text.muted }}>{Math.round(quality.pitch_mean)}Hz</b></span>
        )}
        {quality.f0_stddev_ratio != null && (
          <span>F0 var: <b style={{ color: quality.f0_stddev_ratio <= 0.4 ? "#4ade80" : "#f87171" }}>{(quality.f0_stddev_ratio * 100).toFixed(0)}%</b></span>
        )}
        {quality.speaking_rate_wpm != null && (
          <span>Rate: <b style={{ color: theme.text.muted }}>{Math.round(quality.speaking_rate_wpm)} wpm</b></span>
        )}
      </div>
      {quality.issues && quality.issues.length > 0 && (
        <div style={{ marginTop: 4, fontSize: 10, color: c.text }}>
          {quality.issues.join(" • ")}
        </div>
      )}
    </div>
  );
}

// ── Audio Player Bar ────────────────────────────────────────────────────────
// Spec 2B: play/pause, scrub bar, playback speed (1x, 1.5x, 2x)

function AudioPlayer({ audioRef, communicationId }) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnded = () => { setPlaying(false); setCurrentTime(0); };

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("durationchange", onDurationChange);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("durationchange", onDurationChange);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
  }, [audioRef]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) audio.pause();
    else audio.play().catch(() => {});
  };

  const handleScrub = (e) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Number(e.target.value);
  };

  const changeSpeed = (rate) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = rate;
    setPlaybackRate(rate);
  };

  const SPEEDS = [1, 1.5, 2];

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
      background: "rgba(255,255,255,0.03)", borderRadius: 6,
      border: "1px solid " + theme.border.subtle, marginBottom: 12,
    }}>
      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        style={{
          width: 30, height: 30, borderRadius: "50%",
          background: "rgba(59,130,246,0.15)", color: "#60a5fa",
          border: "1px solid rgba(59,130,246,0.3)",
          cursor: "pointer", fontSize: 12, display: "flex",
          alignItems: "center", justifyContent: "center",
        }}
      >
        {playing ? "\u23F8" : "\u25B6"}
      </button>

      {/* Current time */}
      <span style={{
        fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono,
        minWidth: 38, textAlign: "right",
      }}>
        {fmtTime(currentTime)}
      </span>

      {/* Scrub bar */}
      <input
        type="range"
        min={0}
        max={duration || 1}
        step={0.1}
        value={currentTime}
        onChange={handleScrub}
        style={{
          flex: 1, height: 4, cursor: "pointer",
          accentColor: "#3b82f6",
        }}
      />

      {/* Duration */}
      <span style={{
        fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono,
        minWidth: 38,
      }}>
        {fmtTime(duration)}
      </span>

      {/* Speed controls */}
      <div style={{ display: "flex", gap: 2 }}>
        {SPEEDS.map((rate) => (
          <button
            key={rate}
            onClick={() => changeSpeed(rate)}
            style={{
              padding: "2px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
              background: playbackRate === rate ? "rgba(59,130,246,0.2)" : "transparent",
              color: playbackRate === rate ? "#60a5fa" : theme.text.faint,
              border: playbackRate === rate
                ? "1px solid rgba(59,130,246,0.3)"
                : "1px solid transparent",
              cursor: "pointer",
            }}
          >
            {rate}x
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Speaker Card ────────────────────────────────────────────────────────────

function SpeakerCard({ speaker, color, communicationId, onUpdate, audioRef, segments, allSpeakers }) {
  const toast = useToast();
  const [showNewPerson, setShowNewPerson] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showMergeDropdown, setShowMergeDropdown] = useState(false);

  const handleLinkPerson = async (person) => {
    setBusy(true);
    try {
      // Warn on poor voice quality
      if (speaker.vocal_quality?.verdict === "poor") {
        const proceed = window.confirm(
          "Warning: Voice quality for this speaker is POOR (" +
          (speaker.vocal_quality.issues || []).join(", ") +
          "). Creating a voiceprint from poor audio may cause misidentification. Proceed anyway?"
        );
        if (!proceed) { setBusy(false); return; }
      }
      await linkSpeaker(communicationId, {
        participant_id: speaker.id,
        tracker_person_id: person.id,
        proposed_name: person.full_name,
        proposed_title: person.title,
        proposed_org: person.organization_name,
      });
      toast.success(`Linked ${speaker.speaker_label} to ${person.full_name}`);
      onUpdate();
    } catch (e) {
      toast.error(`Link failed: ${e.message}`);
    }
    setBusy(false);
  };

  const handleConfirmVoiceprint = async (candidate, matchLogId) => {
    setBusy(true);
    try {
      // Warn on poor voice quality
      if (speaker.vocal_quality?.verdict === "poor") {
        const proceed = window.confirm(
          "Warning: Voice quality for this speaker is POOR (" +
          (speaker.vocal_quality.issues || []).join(", ") +
          "). Creating a voiceprint from poor audio may cause misidentification. Proceed anyway?"
        );
        if (!proceed) { setBusy(false); return; }
      }
      await linkSpeaker(communicationId, {
        participant_id: speaker.id,
        tracker_person_id: candidate.tracker_person_id,
        voiceprint_match_log_id: matchLogId,
      });
      toast.success(`Confirmed voiceprint match for ${speaker.speaker_label}`);
      onUpdate();
    } catch (e) {
      toast.error(`Confirm failed: ${e.message}`);
    }
    setBusy(false);
  };

  const handleNewPerson = async (personData) => {
    setBusy(true);
    try {
      await createProvisionalPerson(communicationId, {
        participant_id: speaker.id,
        ...personData,
      });
      toast.success(`Created provisional person: ${personData.proposed_name}`);
      setShowNewPerson(false);
      onUpdate();
    } catch (e) {
      toast.error(`Create failed: ${e.message}`);
    }
    setBusy(false);
  };

  const handleSkip = async () => {
    setBusy(true);
    try {
      await skipSpeaker(communicationId, speaker.id);
      toast.info(`Skipped ${speaker.speaker_label}`);
      onUpdate();
    } catch (e) {
      toast.error(`Skip failed: ${e.message}`);
    }
    setBusy(false);
  };

  // Enhancement #4: Unlink a confirmed speaker
  const handleUnlink = async () => {
    setBusy(true);
    try {
      await unlinkSpeaker(communicationId, speaker.id);
      toast.info(`Unlinked ${speaker.speaker_label}`);
      onUpdate();
    } catch (e) {
      toast.error(`Unlink failed: ${e.message}`);
    }
    setBusy(false);
  };

  // Enhancement #5: Merge speakers
  const handleMerge = async (targetLabel) => {
    setBusy(true);
    setShowMergeDropdown(false);
    try {
      await mergeSpeakers(communicationId, targetLabel, [speaker.speaker_label]);
      toast.success(`Merged ${speaker.speaker_label} into ${targetLabel}`);
      onUpdate();
    } catch (e) {
      toast.error(`Merge failed: ${e.message}`);
    }
    setBusy(false);
  };

  // Enhancement #2: Play voice sample — 7-10 seconds minimum
  const handlePlaySample = () => {
    const audio = audioRef?.current;
    if (!audio) return;
    const speakerSegs = segments.filter((s) => s.speaker_label === speaker.speaker_label);
    if (speakerSegs.length === 0) return;

    const firstSeg = speakerSegs[0];
    const startTime = firstSeg.start_time || 0;
    const firstSegDuration = (firstSeg.end_time || startTime) - startTime;

    let sampleDuration;
    if (firstSegDuration >= 7) {
      // First segment alone is long enough
      sampleDuration = Math.min(15, firstSegDuration);
    } else {
      // Span multiple segments to get at least 7s (cap at 10s)
      sampleDuration = 10;
      // Find actual contiguous run duration
      let totalDur = 0;
      for (const seg of speakerSegs) {
        const segEnd = seg.end_time || (seg.start_time + 5);
        const segDur = segEnd - (seg.start_time || 0);
        totalDur += segDur;
        if (totalDur >= 10) break;
      }
      sampleDuration = Math.max(7, Math.min(10, totalDur));
    }

    audio.currentTime = startTime;
    audio.play().catch(() => {});

    // Auto-pause after the calculated duration
    const pauseAt = startTime + sampleDuration;
    const checkInterval = setInterval(() => {
      if (audio.currentTime >= pauseAt - 0.3 || audio.paused) {
        if (!audio.paused && audio.currentTime >= pauseAt - 0.3) {
          audio.pause();
        }
        clearInterval(checkInterval);
      }
    }, 200);
  };

  const statusIcon = speaker.confirmed
    ? (speaker.match_source === "provisional" ? "\uD83C\uDD95" : "\u2713")
    : "\u2753";
  const statusColor = speaker.confirmed
    ? (speaker.match_source === "provisional" ? "#fbbf24" : "#4ade80")
    : theme.text.faint;

  const isResolved = speaker.confirmed;
  const candidates = speaker.voiceprint_candidates || [];

  // Other speaker labels for merge dropdown (exclude self)
  const otherSpeakers = allSpeakers.filter((s) => s.speaker_label !== speaker.speaker_label);

  return (
    <div style={{
      background: theme.bg.card,
      border: `1px solid ${isResolved ? (speaker.match_source === "provisional" ? "rgba(250,204,21,0.3)" : "rgba(74,222,128,0.3)") : theme.border.subtle}`,
      borderRadius: 8, padding: 14, marginBottom: 10,
      borderLeft: `3px solid ${color}`,
      opacity: busy ? 0.6 : 1, pointerEvents: busy ? "none" : "auto",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color, fontWeight: 700, fontSize: 13 }}>{speaker.speaker_label}</span>
          <span style={{ fontSize: 11, color: theme.text.faint }}>
            {fmtDuration(speaker.speech_seconds)} speaking
          </span>
          {/* Play voice sample button */}
          <button
            onClick={handlePlaySample}
            title="Play 7-10s voice sample"
            style={{
              width: 22, height: 22, borderRadius: "50%",
              background: "rgba(96,165,250,0.12)", color: "#60a5fa",
              border: "1px solid rgba(96,165,250,0.25)",
              cursor: "pointer", fontSize: 10, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}
          >
            {"\u25B6"}
          </button>
        </div>
        <span style={{ color: statusColor, fontSize: 14, fontWeight: 700 }}>{statusIcon}</span>
      </div>

      {/* Sample utterances */}
      {speaker.sample_utterances?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          {speaker.sample_utterances.map((u, i) => (
            <div key={i} style={{
              fontSize: 11, color: theme.text.muted, lineHeight: 1.4,
              padding: "2px 0", borderLeft: `2px solid ${color}22`, paddingLeft: 8,
              marginBottom: 2,
            }}>
              "{u.length > 120 ? u.slice(0, 120) + "\u2026" : u}"
            </div>
          ))}
        </div>
      )}

      {/* Voice quality indicator */}
      {speaker.vocal_quality && <VoiceQualityBadge quality={speaker.vocal_quality} />}

      {/* Resolved state */}
      {isResolved && (
        <div style={{
          padding: "8px 10px", borderRadius: 6,
          background: speaker.match_source === "provisional"
            ? "rgba(250,204,21,0.08)"
            : speaker.match_source === "skipped"
              ? "rgba(156,163,175,0.08)"
              : "rgba(74,222,128,0.08)",
          fontSize: 12,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{ flex: 1 }}>
            {speaker.match_source === "provisional" && (
              <div>
                <span style={{ color: "#fbbf24", fontWeight: 600 }}>Provisional: </span>
                <span style={{ color: theme.text.primary }}>{speaker.proposed_name}</span>
                {speaker.proposed_title && <span style={{ color: theme.text.faint }}> {"\u2014"} {speaker.proposed_title}</span>}
                {speaker.proposed_org && <span style={{ color: theme.text.faint }}>, {speaker.proposed_org}</span>}
              </div>
            )}
            {speaker.match_source === "skipped" && (
              <span style={{ color: theme.text.faint }}>Skipped {"\u2014"} Sonnet will use raw speaker label</span>
            )}
            {speaker.match_source !== "provisional" && speaker.match_source !== "skipped" && speaker.tracker_person_id && (
              <div>
                <span style={{ color: "#4ade80", fontWeight: 600 }}>Linked: </span>
                <span style={{ color: theme.text.primary }}>{speaker.proposed_name || speaker.tracker_person_id}</span>
                {speaker.voiceprint_confidence != null && (
                  <span style={{ color: theme.text.faint, fontSize: 11 }}>
                    {" "}(voiceprint {Math.round(speaker.voiceprint_confidence * 100)}%)
                  </span>
                )}
              </div>
            )}
          </div>
          {/* Enhancement #4: Unlink button */}
          <button
            onClick={handleUnlink}
            title="Unlink this speaker and reset to unconfirmed"
            style={{
              padding: "3px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
              background: "rgba(239,68,68,0.1)", color: "#f87171",
              border: "1px solid rgba(239,68,68,0.25)",
              cursor: "pointer", marginLeft: 8,
            }}
          >
            Unlink
          </button>
        </div>
      )}

      {/* Unresolved: show voiceprint candidates + controls */}
      {!isResolved && (
        <>
          {/* Voiceprint candidates */}
          {candidates.length > 0 && (
            <div style={{
              background: "rgba(96,165,250,0.06)", padding: 10, borderRadius: 6,
              border: "1px solid rgba(96,165,250,0.15)", marginBottom: 8,
            }}>
              <div style={{ fontSize: 10, color: "#60a5fa", fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>
                Voiceprint Suggestions
              </div>
              {candidates.map((c, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "6px 0",
                  borderBottom: i < candidates.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ color: theme.text.primary, fontSize: 12, fontWeight: 500 }}>
                      {c.tracker_person_id.slice(0, 8)}{"\u2026"}
                    </span>
                    <div style={{ marginTop: 2 }}>
                      <ConfidenceIndicator
                        score={c.score}
                        size="bar"
                        showLabel
                        label={
                          c.confidence_label === "high_confidence" ? "Strong match" :
                          c.confidence_label === "medium_confidence" ? "Likely match" : "Possible match"
                        }
                      />
                    </div>
                  </div>
                  <button
                    onClick={() => handleConfirmVoiceprint(c, null)}
                    style={{
                      padding: "4px 10px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                      background: "rgba(74,222,128,0.15)", color: "#4ade80",
                      border: "1px solid rgba(74,222,128,0.3)", cursor: "pointer",
                    }}
                  >
                    Confirm
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Manual controls — using shared PersonOrgResolver pattern but keeping
              the speaker-review-specific flow (link vs new-person vs skip) */}
          <div style={{ marginTop: 6 }}>
            <PersonOrgResolver
              entityType="person"
              onLink={handleLinkPerson}
              onCreateNew={handleNewPerson}
              onSkip={handleSkip}
              showSkip={true}
            />
          </div>

          {/* Enhancement #5: Merge speakers button */}
          {otherSpeakers.length > 0 && (
            <div style={{ marginTop: 8, position: "relative" }}>
              <button
                onClick={() => setShowMergeDropdown(!showMergeDropdown)}
                style={{
                  padding: "4px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: "rgba(168,85,247,0.1)", color: "#a78bfa",
                  border: "1px solid rgba(168,85,247,0.25)",
                  cursor: "pointer",
                }}
              >
                Merge into{"\u2026"}
              </button>
              {showMergeDropdown && (
                <div style={{
                  position: "absolute", top: "100%", left: 0, zIndex: 20,
                  marginTop: 4, minWidth: 180,
                  background: theme.bg.card,
                  border: "1px solid " + theme.border.subtle,
                  borderRadius: 6, overflow: "hidden",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
                }}>
                  <div style={{
                    padding: "6px 10px", fontSize: 10, color: theme.text.faint,
                    fontWeight: 600, textTransform: "uppercase",
                    borderBottom: "1px solid " + theme.border.subtle,
                  }}>
                    Merge {speaker.speaker_label} into:
                  </div>
                  {otherSpeakers.map((other) => (
                    <button
                      key={other.speaker_label}
                      onClick={() => handleMerge(other.speaker_label)}
                      style={{
                        display: "flex", alignItems: "center", gap: 8,
                        width: "100%", padding: "8px 10px",
                        background: "transparent", color: theme.text.primary,
                        border: "none", borderBottom: "1px solid rgba(255,255,255,0.04)",
                        cursor: "pointer", fontSize: 12, textAlign: "left",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <span style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: speakerColor(other.speaker_label, allSpeakers),
                        flexShrink: 0,
                      }} />
                      <span style={{ fontWeight: 600 }}>{other.speaker_label}</span>
                      {other.proposed_name && (
                        <span style={{ color: theme.text.faint, fontSize: 11 }}>
                          ({other.proposed_name})
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function SpeakerReviewDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, refetch } = useApi(() => getSpeakerReviewDetail(id), [id]);
  const [completing, setCompleting] = useState(false);
  const [activeSegIdx, setActiveSegIdx] = useState(-1);
  const audioRef = useRef(null);
  const transcriptPanelRef = useRef(null);
  const speakerPanelRef = useRef(null);

  const stableRefetch = useCallback(async () => {
    const tScroll = transcriptPanelRef.current?.scrollTop || 0;
    const sScroll = speakerPanelRef.current?.scrollTop || 0;
    await refetch();
    requestAnimationFrame(() => {
      if (transcriptPanelRef.current) transcriptPanelRef.current.scrollTop = tScroll;
      if (speakerPanelRef.current) speakerPanelRef.current.scrollTop = sScroll;
    });
  }, [refetch]);
  const [editingSegId, setEditingSegId] = useState(null);
  const [editText, setEditText] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [propagation, setPropagation] = useState(null); // { correctionId, candidates, patternFrom, patternTo }
  const [selectedCandidates, setSelectedCandidates] = useState(new Set());
  const [applyingPropagation, setApplyingPropagation] = useState(false);

  const speakers = data?.speakers || [];
  const segments = data?.transcript_segments || [];
  const vpSummary = data?.voiceprint_summary;

  const confirmedCount = speakers.filter((s) => s.confirmed).length;
  const allDone = speakers.length > 0 && confirmedCount === speakers.length;

  // Enhancement #3: Build speaker name map for transcript display
  const speakerNameMap = useMemo(() => {
    const map = {};
    for (const s of speakers) {
      if (s.confirmed && s.proposed_name) {
        map[s.speaker_label] = s.proposed_name;
      }
    }
    return map;
  }, [speakers]);

  // Track which transcript segment is currently playing
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || segments.length === 0) return;

    const onTimeUpdate = () => {
      const t = audio.currentTime;
      const idx = segments.findIndex(
        (seg) => seg.start_time <= t && (seg.end_time == null || seg.end_time > t)
      );
      setActiveSegIdx(idx);
    };

    audio.addEventListener("timeupdate", onTimeUpdate);
    return () => audio.removeEventListener("timeupdate", onTimeUpdate);
  }, [segments]);

  // Click transcript line -> open inline edit
  const handleSegmentClick = useCallback((seg) => {
    if (editingSegId === seg.id) return; // already editing this one
    setEditingSegId(seg.id);
    setEditText(seg.text || "");
    setPropagation(null);
    setSelectedCandidates(new Set());
  }, [editingSegId]);

  const handleSaveEdit = async (segId) => {
    if (!editText.trim() || savingEdit) return;
    setSavingEdit(true);
    try {
      const result = await editTranscriptSegment(id, segId, editText.trim());
      if (result.changed && result.similar_count > 0) {
        // Show propagation option
        toast.success(`Saved. ${result.similar_count} similar segment${result.similar_count > 1 ? "s" : ""} found.`);
        // Load candidates
        const similar = await findSimilarCorrections(id, result.correction_id);
        setPropagation({
          correctionId: result.correction_id,
          candidates: similar.candidates || [],
          patternFrom: similar.pattern_from,
          patternTo: similar.pattern_to,
        });
        setSelectedCandidates(new Set());
      } else {
        toast.success("Saved correction.");
        setEditingSegId(null);
        setPropagation(null);
      }
      stableRefetch();
    } catch (e) {
      toast.error(`Save failed: ${e.message}`);
    }
    setSavingEdit(false);
  };

  const handleCancelEdit = () => {
    setEditingSegId(null);
    setEditText("");
    setPropagation(null);
    setSelectedCandidates(new Set());
  };

  const handleToggleCandidate = (transcriptId) => {
    setSelectedCandidates(prev => {
      const next = new Set(prev);
      if (next.has(transcriptId)) next.delete(transcriptId);
      else next.add(transcriptId);
      return next;
    });
  };

  const handleApplyPropagation = async () => {
    if (!propagation || selectedCandidates.size === 0) return;
    setApplyingPropagation(true);
    try {
      const corrections = propagation.candidates
        .filter(c => selectedCandidates.has(c.transcript_id))
        .map(c => ({ transcript_id: c.transcript_id, reviewed_text: c.suggested_text }));
      const result = await applyCorrections(id, propagation.correctionId, corrections);
      toast.success(`Applied correction to ${result.applied} segment${result.applied > 1 ? "s" : ""}.`);
      setEditingSegId(null);
      setPropagation(null);
      setSelectedCandidates(new Set());
      stableRefetch();
    } catch (e) {
      toast.error(`Apply failed: ${e.message}`);
    }
    setApplyingPropagation(false);
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeSpeakerReview(id);
      toast.success("Speaker review complete \u2014 enrichment started");
      navigate("/review/speakers");
    } catch (e) {
      toast.error(`Complete failed: ${e.message}`);
    }
    setCompleting(false);
  };

  const audioUrl = `/ai/api/communications/${id}/audio`;

  if (loading) {
    return (
      <div style={{ padding: "40px 32px", color: theme.text.faint }}>
        Loading speaker review...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "40px 32px" }}>
        <div style={{
          padding: "12px 16px", borderRadius: 8,
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          color: "#f87171", fontSize: 13,
        }}>
          Failed to load: {error.message || String(error)}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Hidden audio element */}
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      {/* Header */}
      <div style={{
        padding: "16px 24px", borderBottom: "1px solid " + theme.border.subtle,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <button
            onClick={() => navigate("/review/speakers")}
            style={{
              background: "none", border: "none", color: theme.text.faint,
              cursor: "pointer", fontSize: 12, padding: 0, marginBottom: 4,
            }}
          >
            {"\u2190"} Speaker Review Queue
          </button>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
            {data?.title || data?.original_filename || "Untitled"}
          </h1>
          <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 2 }}>
            {fmtDuration(data?.duration_seconds)} {"\u00b7"} {speakers.length} speakers
            {vpSummary && vpSummary.profiles_in_library > 0 && (
              <span> {"\u00b7"} {vpSummary.profiles_in_library} voice profiles in library</span>
            )}
          </div>
        </div>
      </div>

      {/* Split layout: 60% transcript, 40% speaker cards */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Transcript with audio player */}
        <div style={{
          width: "60%", overflowY: "auto", padding: "16px 20px",
          borderRight: "1px solid " + theme.border.subtle,
        }}>
          {/* Audio player bar */}
          <AudioPlayer audioRef={audioRef} communicationId={id} />

          <div style={{ fontSize: 11, color: theme.text.faint, fontWeight: 600, marginBottom: 12, textTransform: "uppercase" }}>
            Transcript {"\u2014"} click a line to edit
          </div>
          {segments.length === 0 && (
            <div style={{ color: theme.text.faint, fontSize: 13 }}>No transcript segments available.</div>
          )}
          {segments.map((seg, i) => {
            const col = speakerColor(seg.speaker_label, speakers);
            const isActive = i === activeSegIdx;
            const isEditing = editingSegId === seg.id;
            // Enhancement #3: Resolve speaker name from confirmed links
            const displayName = speakerNameMap[seg.speaker_label] || seg.speaker_label;
            return (
              <div
                key={seg.id || i}
                onClick={() => !isEditing && handleSegmentClick(seg)}
                style={{
                  display: "flex", gap: 10, marginBottom: 4, fontSize: 13, lineHeight: 1.5,
                  padding: "3px 6px", borderRadius: 4,
                  cursor: isEditing ? "default" : "text",
                  background: isEditing
                    ? "rgba(250,204,21,0.06)"
                    : isActive ? "rgba(59,130,246,0.08)" : "transparent",
                  border: isEditing
                    ? "1px solid rgba(250,204,21,0.25)"
                    : isActive ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
                  transition: "background 0.15s",
                  alignItems: "flex-start",
                }}
              >
                {/* Enhancement #1: Play button per segment */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    const a = audioRef.current;
                    if (a) {
                      a.currentTime = seg.start_time || 0;
                      a.play().catch(() => {});
                    }
                  }}
                  style={{
                    width: 18, height: 18, borderRadius: "50%", flexShrink: 0,
                    background: "transparent", color: isActive ? "#60a5fa" : "rgba(255,255,255,0.2)",
                    border: "1px solid " + (isActive ? "rgba(96,165,250,0.4)" : "rgba(255,255,255,0.1)"),
                    cursor: "pointer", fontSize: 8, display: "flex",
                    alignItems: "center", justifyContent: "center",
                    marginTop: 2, padding: 0,
                    transition: "color 0.15s, border-color 0.15s",
                  }}
                  title="Play from here"
                  onMouseEnter={(e) => { e.currentTarget.style.color = "#60a5fa"; e.currentTarget.style.borderColor = "rgba(96,165,250,0.4)"; }}
                  onMouseLeave={(e) => { if (i !== activeSegIdx) { e.currentTarget.style.color = "rgba(255,255,255,0.2)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; } }}
                >
                  {"\u25B6"}
                </button>
                <div style={{
                  minWidth: 44, color: isActive ? "#60a5fa" : theme.text.faint,
                  fontFamily: theme.font.mono, fontSize: 10, paddingTop: 3,
                  textAlign: "right",
                }}>
                  {fmtTime(seg.start_time)}
                </div>
                <div style={{
                  minWidth: 80, fontWeight: 600, color: col, fontSize: 11, paddingTop: 3,
                }}>
                  {displayName}
                </div>
                {isEditing ? (
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                    <textarea
                      autoFocus
                      rows={2}
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") { e.preventDefault(); handleCancelEdit(); }
                        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSaveEdit(seg.id); }
                      }}
                      style={{
                        width: "100%", fontSize: 13, lineHeight: 1.5,
                        color: theme.text.secondary,
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 4, padding: "4px 6px",
                        resize: "vertical", fontFamily: "inherit",
                        outline: "none",
                      }}
                    />
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleSaveEdit(seg.id); }}
                        disabled={savingEdit}
                        style={{
                          padding: "3px 10px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                          background: savingEdit ? "#374151" : "rgba(74,222,128,0.15)",
                          color: savingEdit ? "#6b7280" : "#4ade80",
                          border: savingEdit ? "1px solid #374151" : "1px solid rgba(74,222,128,0.3)",
                          cursor: savingEdit ? "not-allowed" : "pointer",
                        }}
                      >
                        {savingEdit ? "Saving..." : "Save"}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleCancelEdit(); }}
                        style={{
                          padding: "3px 10px", borderRadius: 4, fontSize: 11,
                          background: "transparent", color: theme.text.faint,
                          border: "1px solid " + theme.border.subtle, cursor: "pointer",
                        }}
                      >
                        Cancel
                      </button>
                      <span style={{ fontSize: 10, color: theme.text.faint }}>
                        Enter to save {"\u00b7"} Esc to cancel {"\u00b7"} Shift+Enter for newline
                      </span>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: theme.text.secondary, flex: 1 }}>
                    {seg.text}
                  </div>
                )}
              </div>
            );
          })}

          {/* Propagation panel */}
          {propagation && propagation.candidates.length > 0 && (
            <div style={{
              marginTop: 12, padding: 12, borderRadius: 8,
              background: "rgba(250,204,21,0.06)",
              border: "1px solid rgba(250,204,21,0.2)",
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#fbbf24", marginBottom: 8 }}>
                Similar corrections found
              </div>
              <div style={{ fontSize: 11, color: theme.text.faint, marginBottom: 10 }}>
                Pattern: <code style={{ background: "rgba(255,255,255,0.06)", padding: "1px 4px", borderRadius: 3 }}>
                  {propagation.patternFrom}
                </code>
                {" "}{"\u2192"}{" "}
                <code style={{ background: "rgba(255,255,255,0.06)", padding: "1px 4px", borderRadius: 3 }}>
                  {propagation.patternTo}
                </code>
              </div>
              <div style={{ maxHeight: 300, overflowY: "auto" }}>
                {propagation.candidates.map((c) => (
                  <label key={c.transcript_id} style={{
                    display: "flex", gap: 8, padding: "8px 6px", cursor: "pointer",
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                    alignItems: "flex-start",
                  }}>
                    <input
                      type="checkbox"
                      checked={selectedCandidates.has(c.transcript_id)}
                      onChange={() => handleToggleCandidate(c.transcript_id)}
                      style={{ marginTop: 3 }}
                    />
                    <div style={{ flex: 1, fontSize: 12 }}>
                      <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                        <span style={{ color: theme.text.faint, fontFamily: theme.font?.mono || "monospace", fontSize: 10 }}>
                          {fmtTime(c.start_time)}
                        </span>
                        <span style={{ color: theme.text.faint, fontSize: 10 }}>{c.speaker_label}</span>
                      </div>
                      <div style={{ color: "#f87171", textDecoration: "line-through", marginBottom: 2, lineHeight: 1.4 }}>
                        {c.current_text}
                      </div>
                      <div style={{ color: "#4ade80", lineHeight: 1.4 }}>
                        {c.suggested_text}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button
                  onClick={handleApplyPropagation}
                  disabled={selectedCandidates.size === 0 || applyingPropagation}
                  style={{
                    padding: "6px 14px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: selectedCandidates.size > 0 && !applyingPropagation ? "#fbbf24" : "#374151",
                    color: selectedCandidates.size > 0 && !applyingPropagation ? "#000" : "#6b7280",
                    border: "none",
                    cursor: selectedCandidates.size > 0 && !applyingPropagation ? "pointer" : "not-allowed",
                  }}
                >
                  {applyingPropagation ? "Applying..." : `Apply to ${selectedCandidates.size} selected`}
                </button>
                <button
                  onClick={() => { setPropagation(null); setEditingSegId(null); setSelectedCandidates(new Set()); }}
                  style={{
                    padding: "6px 14px", borderRadius: 4, fontSize: 11,
                    background: "transparent", color: theme.text.faint,
                    border: "1px solid " + theme.border.subtle, cursor: "pointer",
                  }}
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Speaker cards */}
        <div ref={speakerPanelRef} style={{ width: "40%", overflowY: "auto", padding: "16px 16px" }}>
          <div style={{ fontSize: 11, color: theme.text.faint, fontWeight: 600, marginBottom: 12, textTransform: "uppercase" }}>
            Speaker Mapping ({confirmedCount} / {speakers.length} confirmed)
          </div>
          {speakers.map((s) => (
            <SpeakerCard
              key={s.id}
              speaker={s}
              color={speakerColor(s.speaker_label, speakers)}
              communicationId={id}
              onUpdate={stableRefetch}
              audioRef={audioRef}
              segments={segments}
              allSpeakers={speakers}
            />
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        padding: "12px 24px",
        borderTop: "1px solid " + theme.border.subtle,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: theme.bg.card,
      }}>
        <span style={{ fontSize: 13, color: theme.text.muted }}>
          {confirmedCount} of {speakers.length} speakers confirmed
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => navigate("/review/speakers")}
            style={{
              padding: "8px 16px", borderRadius: 6, fontSize: 13,
              background: "transparent", color: theme.text.faint,
              border: "1px solid " + theme.border.subtle, cursor: "pointer",
            }}
          >
            Back to Queue
          </button>
          <button
            onClick={handleComplete}
            disabled={!allDone || completing}
            style={{
              padding: "8px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: allDone && !completing ? "#3b82f6" : "#374151",
              color: allDone && !completing ? "#fff" : "#6b7280",
              border: "none",
              cursor: allDone && !completing ? "pointer" : "not-allowed",
            }}
          >
            {completing ? "Completing..." : "Confirm All & Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
