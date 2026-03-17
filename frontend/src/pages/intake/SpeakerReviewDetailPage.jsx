import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import {
  getConversation,
  getSpeakerSuggestions,
  listTrackerPeople,
  resolvePersonNames,
  assignSpeaker,
  confirmSpeakers,
  discardConversation,
  speakerSampleUrl,
  audioClipUrl,
  editTranscriptSegment,
} from "../../api/intake";

// Color palette for speaker labels
var SPEAKER_COLORS = [
  { bg: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.3)", text: "#60a5fa", dot: "#3b82f6" },
  { bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.3)", text: "#a78bfa", dot: "#8b5cf6" },
  { bg: "rgba(52,211,153,0.12)", border: "rgba(52,211,153,0.3)", text: "#34d399", dot: "#10b981" },
  { bg: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.3)", text: "#fbbf24", dot: "#f59e0b" },
  { bg: "rgba(248,113,113,0.12)", border: "rgba(248,113,113,0.3)", text: "#f87171", dot: "#ef4444" },
  { bg: "rgba(56,189,248,0.12)", border: "rgba(56,189,248,0.3)", text: "#38bdf8", dot: "#0ea5e9" },
  { bg: "rgba(244,114,182,0.12)", border: "rgba(244,114,182,0.3)", text: "#f472b6", dot: "#ec4899" },
  { bg: "rgba(163,230,53,0.12)", border: "rgba(163,230,53,0.3)", text: "#a3e635", dot: "#84cc16" },
];

function getSpeakerColor(label, labels) {
  var idx = labels.indexOf(label);
  return SPEAKER_COLORS[idx >= 0 ? idx % SPEAKER_COLORS.length : 0];
}

function formatTime(seconds) {
  if (seconds == null) return "--";
  var m = Math.floor(seconds / 60);
  var s = Math.round(seconds % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export default function SpeakerReviewDetailPage() {
  var { id } = useParams();
  var navigate = useNavigate();

  var [data, setData] = useState(null);
  var [suggestions, setSuggestions] = useState({});
  var [personNames, setPersonNames] = useState({});
  var [trackerPeople, setTrackerPeople] = useState([]);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [saving, setSaving] = useState(false);
  var [playingClip, setPlayingClip] = useState(null);
  var audioRef = useRef(null);

  // Speaker assignment state: { [label]: { tracker_person_id, name } }
  var [assignments, setAssignments] = useState({});
  var [dropdownLabel, setDropdownLabel] = useState(null);
  var [searchQuery, setSearchQuery] = useState("");
  // Editing transcript
  var [editingSegment, setEditingSegment] = useState(null);
  var [editText, setEditText] = useState("");

  var load = useCallback(async function() {
    setLoading(true);
    setError(null);
    try {
      var [convData, sugg, people] = await Promise.all([
        getConversation(id),
        getSpeakerSuggestions(id).catch(function() { return {}; }),
        listTrackerPeople({ limit: 200 }),
      ]);
      setData(convData);
      setSuggestions(sugg);
      setTrackerPeople(people);

      // Resolve person names for voiceprint suggestions
      var allPersonIds = new Set();
      Object.values(sugg).forEach(function(arr) {
        if (Array.isArray(arr)) {
          arr.forEach(function(s) { if (s.tracker_person_id) allPersonIds.add(s.tracker_person_id); });
        }
      });
      // Also from existing confirmed mappings in transcript
      if (convData.transcript) {
        convData.transcript.forEach(function(seg) {
          if (seg.tracker_person_id) allPersonIds.add(seg.tracker_person_id);
        });
      }
      if (allPersonIds.size > 0) {
        var names = await resolvePersonNames([...allPersonIds]);
        setPersonNames(names);
      }

      // Pre-populate assignments from existing confirmed mappings
      var existing = {};
      if (convData.transcript) {
        convData.transcript.forEach(function(seg) {
          if (seg.tracker_person_id && seg.speaker_label && !existing[seg.speaker_label]) {
            var resolved = personNames[seg.tracker_person_id] || { full_name: seg.tracker_person_id.slice(0, 8) };
            existing[seg.speaker_label] = {
              tracker_person_id: seg.tracker_person_id,
              name: resolved.full_name,
            };
          }
        });
      }
      setAssignments(existing);
    } catch (err) {
      setError(err.message || "Failed to load conversation");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(function() { load(); }, [load]);

  // Once personNames loads, update assignments that were set before names resolved
  useEffect(function() {
    if (Object.keys(personNames).length === 0) return;
    setAssignments(function(prev) {
      var updated = Object.assign({}, prev);
      var changed = false;
      Object.keys(updated).forEach(function(label) {
        var a = updated[label];
        var resolved = personNames[a.tracker_person_id];
        if (resolved && resolved.full_name && a.name !== resolved.full_name) {
          updated[label] = Object.assign({}, a, { name: resolved.full_name });
          changed = true;
        }
      });
      return changed ? updated : prev;
    });
  }, [personNames]);

  // Search tracker people with debounce
  useEffect(function() {
    if (!dropdownLabel) return;
    if (searchQuery.length < 2) {
      listTrackerPeople({ limit: 50 }).then(setTrackerPeople).catch(function() {});
      return;
    }
    var timer = setTimeout(function() {
      listTrackerPeople({ search: searchQuery, limit: 30 }).then(setTrackerPeople).catch(function() {});
    }, 250);
    return function() { clearTimeout(timer); };
  }, [searchQuery, dropdownLabel]);

  // Extract unique speaker labels
  var speakerLabels = data && data.transcript
    ? [...new Set(data.transcript.map(function(s) { return s.speaker_label; }))]
    : [];

  // Audio
  var playClip = function(conversationId, start, end) {
    var key = start + "-" + end;
    if (playingClip === key && audioRef.current) { audioRef.current.pause(); setPlayingClip(null); return; }
    if (audioRef.current) audioRef.current.pause();
    var audio = new Audio(audioClipUrl(conversationId, start, end));
    audio.onended = function() { setPlayingClip(null); };
    audio.onerror = function() { setPlayingClip(null); };
    audio.play();
    audioRef.current = audio;
    setPlayingClip(key);
  };

  var playSpeakerSample = function(label) {
    var key = "sample-" + label;
    if (playingClip === key && audioRef.current) { audioRef.current.pause(); setPlayingClip(null); return; }
    if (audioRef.current) audioRef.current.pause();
    var audio = new Audio(speakerSampleUrl(id, label));
    audio.onended = function() { setPlayingClip(null); };
    audio.onerror = function() { setPlayingClip(null); };
    audio.play();
    audioRef.current = audio;
    setPlayingClip(key);
  };

  // Assignment
  var handleAssign = async function(label, personId, personName) {
    try {
      await assignSpeaker({
        conversation_id: id,
        speaker_label: label,
        tracker_person_id: personId,
      });
      setAssignments(function(prev) {
        var next = Object.assign({}, prev);
        next[label] = { tracker_person_id: personId, name: personName };
        return next;
      });
      setDropdownLabel(null);
      setSearchQuery("");
    } catch (err) {
      alert("Failed to assign speaker: " + err.message);
    }
  };

  // Transcript editing
  var handleSaveEdit = async function() {
    if (!editingSegment) return;
    try {
      await editTranscriptSegment(editingSegment, editText);
      setData(function(prev) {
        return Object.assign({}, prev, {
          transcript: prev.transcript.map(function(s) {
            return s.id === editingSegment ? Object.assign({}, s, { text: editText }) : s;
          }),
        });
      });
      setEditingSegment(null);
    } catch (err) {
      alert("Failed to save edit: " + err.message);
    }
  };

  // Confirm / Discard
  var handleConfirm = async function() {
    var unassigned = speakerLabels.filter(function(l) { return !assignments[l]; });
    if (unassigned.length > 0) {
      if (!window.confirm(unassigned.length + " speaker(s) not assigned: " + unassigned.join(", ") + ". Confirm anyway?")) return;
    }
    setSaving(true);
    try {
      await confirmSpeakers(id);
      navigate("/intake/speaker-review");
    } catch (err) { alert("Failed to confirm: " + err.message); }
    finally { setSaving(false); }
  };

  var handleDiscard = async function() {
    if (!window.confirm("Discard this conversation? This cannot be undone.")) return;
    setSaving(true);
    try {
      await discardConversation(id);
      navigate("/intake/speaker-review");
    } catch (err) { alert("Failed to discard: " + err.message); }
    finally { setSaving(false); }
  };

  // ── Render ──

  if (loading) {
    return (<div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.dim }}>Loading conversation...</div>);
  }
  if (error) {
    return (
      <div style={{ padding: "28px 32px" }}>
        <div style={{ padding: "16px 20px", background: "#450a0a", border: "1px solid #7f1d1d", borderRadius: 8, color: "#fca5a5", fontSize: 14 }}>
          {error}
          <button onClick={load} style={{ marginLeft: 12, background: "none", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}>Retry</button>
        </div>
      </div>
    );
  }
  if (!data) return null;

  var conv = data.conversation;
  var transcript = data.transcript;
  var allAssigned = speakerLabels.every(function(l) { return assignments[l]; });

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1100 }}>
      {/* Back + header */}
      <div style={{ marginBottom: 20 }}>
        <button onClick={function() { navigate("/intake/speaker-review"); }}
          style={{ background: "none", border: "none", color: theme.text.dim, cursor: "pointer", fontSize: 12, padding: 0, marginBottom: 10, display: "flex", alignItems: "center", gap: 4 }}>
          &lsaquo; Back to Speaker Review
        </button>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          {conv.title || "Recording " + conv.id.slice(0, 8)}
        </h1>
        <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 4 }}>
          {conv.source && <span style={{ textTransform: "capitalize" }}>{conv.source}</span>}
          {conv.created_at && <span style={{ marginLeft: 12 }}>{new Date(conv.created_at).toLocaleString()}</span>}
          {conv.duration_seconds && <span style={{ marginLeft: 12 }}>{formatTime(conv.duration_seconds)}</span>}
        </div>
      </div>

      {/* Speaker Cards */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
          Speakers ({speakerLabels.length})
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {speakerLabels.map(function(label) {
            var color = getSpeakerColor(label, speakerLabels);
            var assignment = assignments[label];
            var labelSuggestions = (suggestions[label] || []).map(function(s) {
              var resolved = personNames[s.tracker_person_id] || {};
              return Object.assign({}, s, { name: resolved.full_name || s.tracker_person_id.slice(0, 8), title: resolved.title, org_name: resolved.org_name });
            });
            var segCount = transcript.filter(function(s) { return s.speaker_label === label; }).length;
            var isDropdownOpen = dropdownLabel === label;

            return (
              <div key={label} style={{ background: color.bg, border: "1px solid " + color.border, borderRadius: 10, padding: "12px 16px", minWidth: 220, position: "relative" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: color.dot }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: color.text }}>{label}</span>
                  <span style={{ fontSize: 11, color: theme.text.dim }}>({segCount} seg)</span>
                  <button onClick={function() { playSpeakerSample(label); }} title="Play speaker sample"
                    style={{ marginLeft: "auto", background: "none", border: "1px solid " + color.border, borderRadius: 4, color: color.text, cursor: "pointer", padding: "2px 6px", fontSize: 11 }}>
                    {playingClip === "sample-" + label ? "\u23f9" : "\u25b6"} Sample
                  </button>
                </div>

                {assignment ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>{assignment.name}</span>
                    <button onClick={function() {
                      setAssignments(function(prev) { var next = Object.assign({}, prev); delete next[label]; return next; });
                      setDropdownLabel(label);
                    }} style={{ background: "none", border: "none", color: theme.text.dim, cursor: "pointer", fontSize: 11, textDecoration: "underline" }}>Change</button>
                  </div>
                ) : (
                  <div>
                    {labelSuggestions.length > 0 && !isDropdownOpen && (
                      <div style={{ marginBottom: 6 }}>
                        {labelSuggestions.slice(0, 3).map(function(s) {
                          return (
                            <button key={s.tracker_person_id} onClick={function() { handleAssign(label, s.tracker_person_id, s.name); }}
                              style={{ display: "block", width: "100%", textAlign: "left", background: "rgba(255,255,255,0.05)", border: "1px solid " + theme.border.subtle, borderRadius: 6, padding: "6px 10px", cursor: "pointer", marginBottom: 4, color: theme.text.secondary, fontSize: 12 }}>
                              <span style={{ fontWeight: 600 }}>{s.name}</span>
                              {s.title && <span style={{ marginLeft: 6, color: theme.text.dim, fontSize: 10 }}>{s.title}</span>}
                              <span style={{ float: "right", fontSize: 10, color: theme.text.dim }}>{Math.round(s.confidence * 100)}%</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                    <button onClick={function() { setDropdownLabel(isDropdownOpen ? null : label); setSearchQuery(""); }}
                      style={{ background: "rgba(255,255,255,0.06)", border: "1px solid " + theme.border.subtle, borderRadius: 6, padding: "6px 10px", cursor: "pointer", color: theme.text.muted, fontSize: 12, width: "100%", textAlign: "left" }}>
                      {isDropdownOpen ? "Cancel" : "Assign speaker..."}
                    </button>
                  </div>
                )}

                {/* Dropdown — Tracker people */}
                {isDropdownOpen && (
                  <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 20, background: theme.bg.card, border: "1px solid " + theme.border.default, borderRadius: 8, marginTop: 4, maxHeight: 300, overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}>
                    <div style={{ padding: "8px 10px", borderBottom: "1px solid " + theme.border.subtle }}>
                      <input autoFocus placeholder="Search people..." value={searchQuery}
                        onChange={function(e) { setSearchQuery(e.target.value); }}
                        style={{ width: "100%", background: theme.bg.input, border: "1px solid " + theme.border.subtle, borderRadius: 5, padding: "6px 8px", color: theme.text.primary, fontSize: 12, outline: "none" }}
                        onFocus={function(e) { e.target.style.borderColor = theme.border.active; }}
                        onBlur={function(e) { e.target.style.borderColor = theme.border.subtle; }} />
                    </div>
                    <div style={{ maxHeight: 220, overflowY: "auto", padding: "4px 0" }}>
                      {trackerPeople.map(function(p) {
                        return (
                          <button key={p.id} onClick={function() { handleAssign(label, p.id, p.full_name); }}
                            style={{ display: "block", width: "100%", textAlign: "left", background: "transparent", border: "none", cursor: "pointer", padding: "7px 12px", color: theme.text.secondary, fontSize: 12, transition: "background 0.1s" }}
                            onMouseEnter={function(e) { e.currentTarget.style.background = "rgba(59,130,246,0.1)"; }}
                            onMouseLeave={function(e) { e.currentTarget.style.background = "transparent"; }}>
                            <span style={{ fontWeight: 600 }}>{p.full_name}</span>
                            {p.title && <span style={{ marginLeft: 8, color: theme.text.dim, fontSize: 11 }}>{p.title}</span>}
                            {p.org_name && <span style={{ marginLeft: 6, color: theme.text.dim, fontSize: 11 }}>({p.org_name})</span>}
                          </button>
                        );
                      })}
                      {trackerPeople.length === 0 && (
                        <div style={{ padding: "10px 12px", color: theme.text.dim, fontSize: 12 }}>No matching people in Tracker</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Transcript */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
          Transcript ({transcript.length} segments)
        </div>
        <div style={{ background: theme.bg.card, borderRadius: 10, border: "1px solid " + theme.border.subtle, overflow: "hidden" }}>
          {transcript.map(function(seg, idx) {
            var color = getSpeakerColor(seg.speaker_label, speakerLabels);
            var assignment = assignments[seg.speaker_label];
            var isEditing = editingSegment === seg.id;
            var clipKey = seg.start_time + "-" + seg.end_time;
            return (
              <div key={seg.id || idx} style={{ display: "flex", gap: 12, padding: "10px 16px", borderBottom: idx < transcript.length - 1 ? "1px solid " + theme.border.subtle : "none", alignItems: "flex-start" }}>
                <div style={{ width: 60, flexShrink: 0, textAlign: "right", paddingTop: 2 }}>
                  <button onClick={function() { playClip(id, seg.start_time, seg.end_time); }}
                    style={{ background: "none", border: "none", cursor: "pointer", color: playingClip === clipKey ? theme.accent.blue : theme.text.dim, fontSize: 11, fontFamily: theme.font.mono, padding: 0 }}
                    title="Play this segment">
                    {playingClip === clipKey ? "\u23f9" : "\u25b6"} {formatTime(seg.start_time)}
                  </button>
                </div>
                <div style={{ width: 110, flexShrink: 0, paddingTop: 2 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, color: color.text }}>
                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: color.dot }} />
                    {assignment ? assignment.name : seg.speaker_label}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {isEditing ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <textarea autoFocus value={editText} onChange={function(e) { setEditText(e.target.value); }}
                        style={{ flex: 1, background: theme.bg.input, border: "1px solid " + theme.border.active, borderRadius: 5, padding: "6px 8px", color: theme.text.primary, fontSize: 13, lineHeight: 1.5, resize: "vertical", minHeight: 40, fontFamily: "inherit" }} />
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        <button onClick={handleSaveEdit} style={{ background: theme.accent.blue, border: "none", borderRadius: 4, color: "#fff", cursor: "pointer", fontSize: 11, padding: "4px 8px" }}>Save</button>
                        <button onClick={function() { setEditingSegment(null); }} style={{ background: "none", border: "1px solid " + theme.border.subtle, borderRadius: 4, color: theme.text.dim, cursor: "pointer", fontSize: 11, padding: "4px 8px" }}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 13, lineHeight: 1.55, color: theme.text.secondary, cursor: "pointer" }}
                      onClick={function() { setEditingSegment(seg.id); setEditText(seg.text); }} title="Click to edit">
                      {seg.text}
                      {seg.user_corrected && <span style={{ marginLeft: 6, fontSize: 9, color: theme.text.dim, fontStyle: "italic" }}>edited</span>}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Action bar */}
      <div style={{ display: "flex", gap: 12, justifyContent: "space-between", alignItems: "center", padding: "16px 20px", background: theme.bg.card, borderRadius: 10, border: "1px solid " + theme.border.subtle }}>
        <div style={{ fontSize: 12, color: theme.text.dim }}>
          {Object.keys(assignments).length}/{speakerLabels.length} speakers assigned
          {allAssigned && <span style={{ marginLeft: 8, color: theme.accent.green, fontWeight: 600 }}>All assigned</span>}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={handleDiscard} disabled={saving}
            style={{ padding: "9px 18px", borderRadius: 7, border: "1px solid " + theme.border.subtle, background: "transparent", color: theme.text.dim, cursor: "pointer", fontSize: 13, fontWeight: 500 }}>
            Discard
          </button>
          <button onClick={handleConfirm} disabled={saving}
            style={{ padding: "9px 22px", borderRadius: 7, border: "none",
              background: allAssigned ? "linear-gradient(135deg, #16a34a, #22c55e)" : "linear-gradient(135deg, #1e40af, #3b82f6)",
              color: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 600, opacity: saving ? 0.6 : 1 }}>
            {saving ? "Saving..." : allAssigned ? "Confirm Speakers" : "Confirm (partial)"}
          </button>
        </div>
      </div>
    </div>
  );
}
