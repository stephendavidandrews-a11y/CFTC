import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

const STEPS = [
  { key: 'add', label: 'Add Docket', description: 'Register docket in the system' },
  { key: 'fetch', label: 'Fetch Comments', description: 'Pull comments from CFTC' },
  { key: 'extract', label: 'Extract Text', description: 'Download PDFs and extract text' },
  { key: 'formLetters', label: 'Detect Form Letters', description: 'Identify duplicate campaigns' },
  { key: 'tier', label: 'AI Tier Classification', description: 'Classify into Tier 1/2/3' },
  { key: 'sumT1', label: 'Summarize Tier 1', description: 'Deep Opus summaries for critical comments' },
  { key: 'sumT2', label: 'Summarize Tier 2', description: 'Executive summaries' },
  { key: 'sumT3', label: 'Summarize Tier 3', description: 'Brief summaries' },
];

function StepIndicator({ step, currentStep, status }) {
  const idx = STEPS.findIndex(s => s.key === step.key);
  const currentIdx = STEPS.findIndex(s => s.key === currentStep);
  const isActive = step.key === currentStep;
  const isDone = status === 'done';
  const isError = status === 'error';
  const isPending = idx > currentIdx && !isDone;

  let bgColor = 'bg-gray-200 text-gray-500';
  if (isDone) bgColor = 'bg-green-500 text-white';
  if (isActive) bgColor = 'bg-blue-500 text-white animate-pulse';
  if (isError) bgColor = 'bg-red-500 text-white';

  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg ${isActive ? 'bg-blue-50 border border-blue-200' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${bgColor}`}>
        {isDone ? '✓' : isError ? '!' : idx + 1}
      </div>
      <div>
        <div className={`text-sm font-medium ${isActive ? 'text-blue-900' : isDone ? 'text-green-700' : 'text-gray-600'}`}>
          {step.label}
        </div>
        <div className="text-xs text-gray-400">{step.description}</div>
      </div>
    </div>
  );
}

export default function NewDocket() {
  const [docketInput, setDocketInput] = useState('');
  const [running, setRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(null);
  const [stepStatuses, setStepStatuses] = useState({});
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [releases, setReleases] = useState(null);
  const [selectedYear, setSelectedYear] = useState(0);
  const [showBrowser, setShowBrowser] = useState(false);
  const [existingDocket, setExistingDocket] = useState(null);
  const [checkingDocket, setCheckingDocket] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [allReleases, setAllReleases] = useState([]);
  const logsEndRef = useRef(null);
  const navigate = useNavigate();

  const log = (msg) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, `[${timestamp}] ${msg}`]);
  };

  const setStatus = (key, status) => {
    setStepStatuses(prev => ({ ...prev, [key]: status }));
  };

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Check if docket already exists when input changes
  useEffect(() => {
    const input = docketInput.trim();
    if (!input) { setExistingDocket(null); return; }

    // Clear immediately so stale warning doesn't persist
    setExistingDocket(null);
    const docketNumber = input.match(/^\d+$/) ? `CFTC-RELEASE-${input}` : input;
    setCheckingDocket(true);

    const timer = setTimeout(() => {
      api.getStats(docketNumber)
        .then(stats => {
          // Only show warning if docket actually has comments
          setExistingDocket(stats.total_comments > 0 ? stats : null);
          setCheckingDocket(false);
        })
        .catch(() => { setExistingDocket(null); setCheckingDocket(false); });
    }, 500);

    return () => clearTimeout(timer);
  }, [docketInput]);

  const browseReleases = async () => {
    setShowBrowser(true);
    try {
      const data = await api.browseCftcReleases(selectedYear);
      const r = data.releases || [];
      setAllReleases(r);
      setReleases(r);
    } catch (e) {
      log(`Error browsing releases: ${e.message}`);
    }
  };

  // Filter releases by search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setReleases(allReleases);
      return;
    }
    const q = searchQuery.toLowerCase();
    setReleases(allReleases.filter(r =>
      (r.title || '').toLowerCase().includes(q) ||
      (r.description || '').toLowerCase().includes(q) ||
      (r.category || '').toLowerCase().includes(q) ||
      (r.fr_citation || '').toLowerCase().includes(q) ||
      String(r.release_id).includes(q)
    ));
  }, [searchQuery, allReleases]);

  const runPipeline = async () => {
    if (!docketInput.trim()) return;
    setRunning(true);
    setError(null);
    setLogs([]);
    setStepStatuses({});
    const docket = docketInput.trim();

    try {
      // Step 1: Add docket
      setCurrentStep('add');
      log(`Adding docket ${docket}...`);
      const addResult = await api.addDocket(docket);
      log(`✓ ${addResult.message}`);
      setStatus('add', 'done');

      const docketNumber = addResult.message.match(/CFTC-RELEASE-\d+/)?.[0] || docket;

      // Step 2: Fetch comments
      setCurrentStep('fetch');
      log('Fetching comments from CFTC...');
      const fetchResult = await api.fetchComments(docketNumber);
      log(`✓ ${fetchResult.message}`);
      setStatus('fetch', 'done');

      // Step 3: Extract text (loop until done)
      setCurrentStep('extract');
      log('Extracting text from PDFs...');
      let extractRemaining = 1;
      let totalExtracted = 0;
      while (extractRemaining > 0) {
        const extractResult = await api.extractText(docketNumber, 50);
        totalExtracted += extractResult.processed;
        extractRemaining = extractResult.remaining;
        log(`  Extracted ${totalExtracted} so far, ${extractRemaining} remaining...`);
      }
      log(`✓ Text extraction complete (${totalExtracted} comments processed)`);
      setStatus('extract', 'done');

      // Step 4: Form letter detection
      setCurrentStep('formLetters');
      log('Detecting form letter campaigns...');
      const flResult = await api.detectFormLetters(docketNumber);
      log(`✓ Found ${flResult.form_letter_groups} campaigns (${flResult.form_letter_comments} comments), ${flResult.unique_comments} unique`);
      setStatus('formLetters', 'done');

      // Step 5: AI Tiering (loop until done)
      setCurrentStep('tier');
      log('Running AI tier classification...');
      let tierRemaining = 1;
      let totalTiered = 0;
      while (tierRemaining > 0) {
        const tierResult = await api.aiTier(docketNumber, 50);
        totalTiered += tierResult.processed;
        tierRemaining = tierResult.remaining;
        log(`  Tiered ${totalTiered} so far, ${tierRemaining} remaining (T1: ${tierResult.tier_1}, T2: ${tierResult.tier_2}, T3: ${tierResult.tier_3})...`);
      }
      log(`✓ Tiering complete (${totalTiered} comments classified)`);
      setStatus('tier', 'done');

      // Step 6: Summarize Tier 1 (Opus)
      setCurrentStep('sumT1');
      log('Generating Tier 1 summaries (Opus — this may take a while)...');
      let t1Remaining = 1;
      let t1Total = 0;
      while (t1Remaining > 0) {
        const result = await api.aiSummarize(docketNumber, 1, 10);
        t1Total += result.processed;
        t1Remaining = result.remaining;
        if (result.processed > 0) {
          log(`  Summarized ${t1Total} Tier 1 comments, ${t1Remaining} remaining...`);
        } else {
          t1Remaining = 0;
        }
      }
      log(`✓ Tier 1 summaries complete (${t1Total})`);
      setStatus('sumT1', 'done');

      // Step 7: Summarize Tier 2
      setCurrentStep('sumT2');
      log('Generating Tier 2 summaries (Sonnet)...');
      let t2Remaining = 1;
      let t2Total = 0;
      while (t2Remaining > 0) {
        const result = await api.aiSummarize(docketNumber, 2, 50);
        t2Total += result.processed;
        t2Remaining = result.remaining;
        if (result.processed > 0) {
          log(`  Summarized ${t2Total} Tier 2 comments, ${t2Remaining} remaining...`);
        } else {
          t2Remaining = 0;
        }
      }
      log(`✓ Tier 2 summaries complete (${t2Total})`);
      setStatus('sumT2', 'done');

      // Step 8: Summarize Tier 3
      setCurrentStep('sumT3');
      log('Generating Tier 3 summaries (Sonnet)...');
      let t3Remaining = 1;
      let t3Total = 0;
      while (t3Remaining > 0) {
        const result = await api.aiSummarize(docketNumber, 3, 200);
        t3Total += result.processed;
        t3Remaining = result.remaining;
        if (result.processed > 0) {
          log(`  Summarized ${t3Total} Tier 3 comments, ${t3Remaining} remaining...`);
        } else {
          t3Remaining = 0;
        }
      }
      log(`✓ Tier 3 summaries complete (${t3Total})`);
      setStatus('sumT3', 'done');

      // Done!
      setCurrentStep(null);
      log('');
      log('🎉 PIPELINE COMPLETE! All comments analyzed.');
      log(`View results on the Dashboard or export a briefing document.`);

    } catch (e) {
      setError(e.message);
      log(`✗ ERROR: ${e.message}`);
      if (currentStep) setStatus(currentStep, 'error');
    }

    setRunning(false);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Add New Docket</h1>
        <p className="text-gray-500 mt-1">Pull and analyze all comments for a CFTC rulemaking</p>
      </div>

      {/* Input */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          CFTC Release ID or Docket Number
        </label>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="e.g., 7624 or CFTC-RELEASE-7624"
            value={docketInput}
            onChange={e => setDocketInput(e.target.value)}
            disabled={running}
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            onKeyDown={e => e.key === 'Enter' && !running && runPipeline()}
          />
          <button
            onClick={runPipeline}
            disabled={running || !docketInput.trim()}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {running ? 'Processing...' : 'Start Analysis'}
          </button>
        </div>
        <div className="mt-3 flex items-center gap-4">
          <button
            onClick={browseReleases}
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            Browse CFTC releases
          </button>

        {/* Existing docket warning */}
        {existingDocket && !running && (
          <div className="flex-1 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-amber-800 font-medium text-sm">⚠️ This docket already exists</div>
                <div className="text-amber-700 text-xs mt-1">
                  {existingDocket.total_comments} comments | 
                  T1: {existingDocket.tier_1_count}, T2: {existingDocket.tier_2_count}, T3: {existingDocket.tier_3_count} | 
                  {existingDocket.tier1_summarized ? ' ✓ Summarized' : ' ✗ Not yet summarized'}
                </div>
                <div className="text-amber-600 text-xs mt-1">
                  {existingDocket.tier1_summarized
                    ? 'Re-running will skip already-processed comments (no extra API cost). Only new comments will be processed.'
                    : 'Comments exist but summarization hasn\'t been completed. Running will pick up where it left off.'}
                </div>
              </div>
              <button
                onClick={() => navigate(`/comments?docket=${existingDocket.docket_number}`)}
                className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded hover:bg-amber-200 whitespace-nowrap ml-3"
              >
                View on Dashboard
              </button>
            </div>
          </div>
        )}
          {showBrowser && (
            <div className="flex items-center gap-2">
              <select
                value={selectedYear}
                onChange={e => setSelectedYear(parseInt(e.target.value))}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                <option value={0}>Current / Upcoming</option>
                {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map(y => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <button
                onClick={browseReleases}
                className="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded"
              >
                Load
              </button>
            </div>
          )}
        </div>

        {/* Release browser */}
        {allReleases.length > 0 && (
          <div className="mt-4">
            <input
              type="text"
              placeholder="Search rules by name, keyword, or ID..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {releases.length === 0 ? (
              <div className="text-gray-400 text-sm text-center py-4">No rules match "{searchQuery}"</div>
            ) : (
            <div className="border border-gray-200 rounded-lg overflow-hidden max-h-60 overflow-y-auto">
              <div className="text-xs text-gray-400 px-3 py-1 bg-gray-50">{releases.length} result{releases.length !== 1 ? 's' : ''}</div>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">ID</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Title</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Type</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">FR Citation</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Closing</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {releases.map(r => (
                  <tr key={`${r.release_id}-${r.title}`} className="hover:bg-blue-50 cursor-pointer">
                    <td className="px-3 py-2 text-sm font-mono">{r.release_id}</td>
                    <td className="px-3 py-2 text-sm max-w-md">
                      <div className="font-medium">{r.title?.substring(0, 100)}</div>
                      {r.description && (
                        <div className="text-xs text-gray-400 mt-0.5">{r.description.substring(0, 150)}{r.description.length > 150 ? '...' : ''}</div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">{r.category}</td>
                    <td className="px-3 py-2 text-sm text-gray-500">{r.fr_citation}</td>
                    <td className="px-3 py-2 text-sm text-gray-500">{r.closing_date}</td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => { setDocketInput(String(r.release_id)); setShowBrowser(false); setSearchQuery(''); }}
                        className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200"
                      >
                        Select
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
            )}
          </div>
        )}
      </div>

      {/* Progress */}
      {(running || Object.keys(stepStatuses).length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          {/* Steps */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Pipeline Steps</h2>
            <div className="space-y-1">
              {STEPS.map(step => (
                <StepIndicator
                  key={step.key}
                  step={step}
                  currentStep={currentStep}
                  status={stepStatuses[step.key]}
                />
              ))}
            </div>
          </div>

          {/* Logs */}
          <div className="md:col-span-2 bg-gray-900 rounded-xl shadow-sm border border-gray-700 p-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Activity Log</h2>
            <div className="font-mono text-xs text-green-400 max-h-[500px] overflow-y-auto space-y-0.5">
              {logs.map((line, i) => (
                <div key={i} className={line.includes('ERROR') ? 'text-red-400' : line.includes('✓') ? 'text-green-300' : line.includes('🎉') ? 'text-yellow-300 text-sm font-bold' : ''}>
                  {line}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <div className="text-red-800 font-medium">Error</div>
          <div className="text-red-600 text-sm mt-1">{error}</div>
          <p className="text-red-500 text-xs mt-2">
            You can restart the pipeline — it will pick up where it left off (already-processed comments are skipped).
          </p>
        </div>
      )}

      {/* Done state */}
      {!running && stepStatuses.sumT3 === 'done' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
          <div className="text-green-800 font-bold text-lg mb-2">🎉 Analysis Complete!</div>
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
            >
              View Dashboard
            </button>
            <a
              href={`http://localhost:8000/api/v1/export/briefing/CFTC-RELEASE-${docketInput.replace('CFTC-RELEASE-', '')}`}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              download
            >
              📄 Export Briefing Doc
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
