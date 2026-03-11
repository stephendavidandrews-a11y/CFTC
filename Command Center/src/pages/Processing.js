import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

function ProcessingStep({ title, description, buttonText, onRun, running, result, color }) {
  const bgColor = color === 'green' ? '#14532d' : color === 'amber' ? '#422006' : '#172554';
  const textColor = color === 'green' ? '#4ade80' : color === 'amber' ? '#fbbf24' : '#60a5fa';
  const borderColor = color === 'green' ? '#166534' : color === 'amber' ? '#92400e' : '#1e3a5f';

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 14 }}>{title}</div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{description}</div>
        </div>
        <button onClick={onRun} disabled={running} style={{
          padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: bgColor, color: textColor, border: `1px solid ${borderColor}`,
          cursor: running ? 'wait' : 'pointer', opacity: running ? 0.6 : 1,
          fontFamily: 'var(--font-sans)',
        }}>
          {running ? 'Processing...' : buttonText}
        </button>
      </div>
      {result && (
        <div style={{
          marginTop: 12, padding: 12, borderRadius: 6,
          background: '#0f172a', border: '1px solid #1e293b',
        }}>
          <pre style={{ fontSize: 11, color: '#94a3b8', whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'var(--font-mono)' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function Processing() {
  const [docket, setDocket] = useState('');
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState(null);
  const [running, setRunning] = useState({});
  const [results, setResults] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    api.getRules().then(data => {
      const r = data.rules || data || [];
      r.sort((a, b) => (b.total_comments || 0) - (a.total_comments || 0));
      setRules(r);
      if (r.length > 0) setDocket(r[0].docket_number);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (docket) refreshStats();
  }, [docket]);

  const refreshStats = async () => {
    try {
      const data = await api.getStats(docket);
      setStats(data);
    } catch (e) { /* ignore */ }
  };

  const runStep = async (key, fn) => {
    setRunning(r => ({ ...r, [key]: true }));
    try {
      const result = await fn();
      setResults(r => ({ ...r, [key]: result }));
      refreshStats();
    } catch (e) {
      setResults(r => ({ ...r, [key]: { error: e.message } }));
    }
    setRunning(r => ({ ...r, [key]: false }));
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 className="page-title">AI Processing</h2>
          <p className="page-desc">Run AI-powered analysis on comment letters</p>
        </div>
        <button onClick={() => navigate('/comments')} style={{
          background: 'none', border: '1px solid #1e293b', color: '#64748b',
          padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)',
        }}>← Back to Dashboard</button>
      </div>

      {/* Docket selector */}
      <div className="card" style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 8 }}>
          Select Docket
        </label>
        <select
          value={docket}
          onChange={e => setDocket(e.target.value)}
          style={{
            width: '100%', padding: '10px 14px', borderRadius: 8,
            background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
            fontSize: 13, fontFamily: 'var(--font-sans)', cursor: 'pointer',
          }}
        >
          {rules.map(r => (
            <option key={r.docket_number} value={r.docket_number}>
              {r.docket_number} — {r.title} ({r.total_comments || 0} comments)
            </option>
          ))}
        </select>
      </div>

      {/* Current stats */}
      {stats && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Current Status — {docket}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16 }}>
            {[
              { l: 'Total', v: stats.total_comments, c: '#e2e8f0' },
              { l: 'Tier 1', v: stats.tier_1_count, c: '#3b82f6' },
              { l: 'Tier 2', v: stats.tier_2_count, c: '#a78bfa' },
              { l: 'Tier 3', v: stats.tier_3_count, c: '#64748b' },
              { l: 'Form Letters', v: stats.form_letter_count, c: '#c084fc' },
              { l: 'Unclassified', v: stats.unclassified_count, c: '#475569' },
            ].map((s, i) => (
              <div key={i}>
                <div style={{ fontSize: 11, color: '#475569' }}>{s.l}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: s.c }}>{s.v}</div>
              </div>
            ))}
          </div>
          <div style={{ borderTop: '1px solid #1e293b', marginTop: 12, paddingTop: 12, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {[
              { l: 'Support', v: stats.support_count, c: '#22c55e' },
              { l: 'Oppose', v: stats.oppose_count, c: '#ef4444' },
              { l: 'Mixed', v: stats.mixed_count, c: '#f59e0b' },
              { l: 'Neutral', v: stats.neutral_count, c: '#64748b' },
            ].map((s, i) => (
              <div key={i}>
                <div style={{ fontSize: 11, color: '#475569' }}>{s.l}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: s.c }}>{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Processing Steps */}
      <div style={{ marginBottom: 8, fontWeight: 600, color: '#e2e8f0', fontSize: 14 }}>Processing Pipeline</div>

      <ProcessingStep
        title="Step 1: Detect Form Letters"
        description="Fast text fingerprinting to identify duplicate/form letter campaigns. Free — no API cost."
        buttonText="Detect Form Letters"
        color="green"
        running={running.formLetters}
        result={results.formLetters}
        onRun={() => runStep('formLetters', () => api.detectFormLetters(docket))}
      />

      <ProcessingStep
        title="Step 2: AI Tier Classification"
        description="Uses Claude Sonnet to classify comments into Tier 1/2/3, assign sentiment, and detect commenter types. ~$0.01-0.03 per batch of 50."
        buttonText="Run AI Tiering (batch 50)"
        color="amber"
        running={running.aiTier}
        result={results.aiTier}
        onRun={() => runStep('aiTier', () => api.aiTier(docket, 50))}
      />

      <ProcessingStep
        title="Step 3a: Summarize Tier 1 (Opus)"
        description="Uses Claude Opus for deep structured summaries of critical comments. ~$0.30 per comment."
        buttonText="Summarize Tier 1 (batch 10)"
        running={running.sumT1}
        result={results.sumT1}
        onRun={() => runStep('sumT1', () => api.aiSummarize(docket, 1, 10))}
      />

      <ProcessingStep
        title="Step 3b: Summarize Tier 2 (Sonnet)"
        description="Executive summaries for substantive comments. ~$0.01 per comment."
        buttonText="Summarize Tier 2 (batch 50)"
        running={running.sumT2}
        result={results.sumT2}
        onRun={() => runStep('sumT2', () => api.aiSummarize(docket, 2, 50))}
      />

      <ProcessingStep
        title="Step 3c: Summarize Tier 3 (Sonnet)"
        description="Brief summaries for standard comments. ~$0.005 per comment."
        buttonText="Summarize Tier 3 (batch 200)"
        color="green"
        running={running.sumT3}
        result={results.sumT3}
        onRun={() => runStep('sumT3', () => api.aiSummarize(docket, 3, 200))}
      />
    </div>
  );
}
