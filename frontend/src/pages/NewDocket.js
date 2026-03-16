import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function NewDocket() {
  const [releaseId, setReleaseId] = useState('');
  const [releases, setReleases] = useState([]);
  const [year, setYear] = useState(0);
  const [search, setSearch] = useState('');
  const [log, setLog] = useState([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.browseCftcReleases(year).then(data => {
      setReleases(data.releases || []);
    }).catch(() => {});
  }, [year]);

  const addLog = (msg) => setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);

  const runPipeline = async () => {
    if (!releaseId) return;
    setRunning(true);
    setDone(false);
    setLog([]);

    try {
      // Step 1: Add docket
      addLog(`Adding docket ${releaseId}...`);
      const addResult = await api.addDocket(releaseId);
      addLog(`Added: ${addResult.message}`);
      const docket = `CFTC-RELEASE-${releaseId.replace('CFTC-RELEASE-', '')}`;

      // Step 2: Fetch comments
      addLog('Fetching comments from CFTC portal...');
      const fetchResult = await api.fetchComments(docket);
      addLog(`Fetched: ${fetchResult.message}`);

      // Step 3: Extract text
      addLog('Extracting text from PDFs...');
      let remaining = 1;
      while (remaining > 0) {
        const extractResult = await api.extractText(docket, 20);
        addLog(`Extracted: ${extractResult.message}`);
        remaining = extractResult.remaining || 0;
      }
      addLog('Text extraction complete.');

      setDone(true);
      addLog('Pipeline complete! You can now run AI processing from the AI Processing page.');
    } catch (e) {
      addLog(`Error: ${e.message}`);
    }
    setRunning(false);
  };

  const filtered = releases.filter(r =>
    !search || r.title?.toLowerCase().includes(search.toLowerCase()) ||
    String(r.release_id).includes(search)
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 className="page-title">+ New Docket</h2>
          <p className="page-desc">Add a new rulemaking docket to track and analyze</p>
        </div>
        <button onClick={() => navigate('/comments')} style={{
          background: 'none', border: '1px solid #1e293b', color: '#64748b',
          padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)',
        }}>← Back to Dashboard</button>
      </div>

      {/* Manual entry */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}>Enter Release ID</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="e.g. 7512 or CFTC-RELEASE-7512"
            value={releaseId}
            onChange={e => setReleaseId(e.target.value)}
            style={{
              flex: 1, padding: '10px 14px', borderRadius: 8,
              background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
              fontSize: 13, fontFamily: 'var(--font-sans)',
            }}
          />
          <button onClick={runPipeline} disabled={running || !releaseId} style={{
            padding: '10px 20px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: '#14532d', color: '#4ade80', border: '1px solid #166534',
            cursor: running ? 'wait' : 'pointer', opacity: running || !releaseId ? 0.5 : 1,
            fontFamily: 'var(--font-sans)',
          }}>
            {running ? 'Running...' : 'Add & Ingest'}
          </button>
        </div>
      </div>

      {/* Activity log */}
      {log.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 8 }}>Activity Log</div>
          <div style={{
            background: '#0f172a', borderRadius: 6, padding: 12,
            maxHeight: 300, overflowY: 'auto',
            fontFamily: 'var(--font-mono)', fontSize: 11, color: '#94a3b8',
            lineHeight: 1.8,
          }}>
            {log.map((l, i) => (
              <div key={i} style={{ color: l.includes('Error') ? '#ef4444' : l.includes('complete') ? '#4ade80' : '#94a3b8' }}>{l}</div>
            ))}
          </div>
          {done && (
            <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
              <button onClick={() => navigate('/comments/processing')} style={{
                padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: '#172554', color: '#60a5fa', border: '1px solid #1e3a5f',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}>Run AI Processing →</button>
              <button onClick={() => navigate('/comments')} style={{
                padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: '#1f2937', color: '#94a3b8', border: '1px solid #374151',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}>View Dashboard</button>
            </div>
          )}
        </div>
      )}

      {/* Browse releases */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="card-title">Browse CFTC Releases</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              placeholder="Search releases..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                padding: '6px 10px', borderRadius: 6, background: '#0f172a',
                border: '1px solid #1e293b', color: '#e2e8f0', fontSize: 12, width: 180,
              }}
            />
            <select value={year} onChange={e => setYear(Number(e.target.value))} style={{
              padding: '6px 10px', borderRadius: 6, background: '#0f172a',
              border: '1px solid #1e293b', color: '#e2e8f0', fontSize: 12,
            }}>
              <option value="0">Current</option>
              {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {filtered.map(r => (
            <div key={r.release_id} style={{
              padding: '10px 12px', borderBottom: '1px solid #1e293b',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              fontSize: 12,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, color: '#e2e8f0' }}>{r.title}</div>
                <div style={{ color: '#475569', marginTop: 2 }}>
                  #{r.release_id} {r.fr_citation && `· ${r.fr_citation}`} {r.closing_date && `· Closes ${r.closing_date}`}
                </div>
              </div>
              <button onClick={() => setReleaseId(String(r.release_id))} style={{
                padding: '4px 12px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                background: '#172554', color: '#60a5fa', border: '1px solid #1e3a5f',
                cursor: 'pointer',
              }}>Select</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
