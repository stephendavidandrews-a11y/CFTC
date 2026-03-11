import React, { useState, useEffect } from 'react';
import { api } from '../api';

function ProcessingStep({ title, description, buttonText, onRun, running, result, variant }) {
  const btnBase = "px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors";
  const btnColor = variant === 'green' ? 'bg-green-600 hover:bg-green-700'
    : variant === 'amber' ? 'bg-amber-600 hover:bg-amber-700'
    : 'bg-blue-600 hover:bg-blue-700';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        </div>
        <button onClick={onRun} disabled={running} className={`${btnBase} ${btnColor}`}>
          {running ? 'Processing...' : buttonText}
        </button>
      </div>
      {result && (
        <div className="mt-4 bg-gray-50 rounded-lg p-4">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-auto max-h-60">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function Processing() {
  const [docket, setDocket] = useState('CFTC-RELEASE-7512');
  const [stats, setStats] = useState(null);
  const [running, setRunning] = useState({});
  const [results, setResults] = useState({});

  useEffect(() => {
    refreshStats();
  }, [docket]);

  const refreshStats = async () => {
    try {
      const data = await api.getStats(docket);
      setStats(data);
    } catch (e) {
      console.error(e);
    }
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
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">AI Processing</h1>
        <p className="text-gray-500 mt-1">Run AI-powered analysis on comment letters</p>
      </div>

      {/* Docket selector */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700">Docket Number:</label>
          <input
            type="text"
            value={docket}
            onChange={e => setDocket(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64"
          />
          <button onClick={refreshStats} className="text-sm text-blue-600 hover:text-blue-800">
            Refresh Stats
          </button>
        </div>
      </div>

      {/* Current stats */}
      {stats && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-3">Current Status — {docket}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div>
              <div className="text-xs text-gray-400">Total</div>
              <div className="text-lg font-bold text-gray-900">{stats.total_comments}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Tier 1</div>
              <div className="text-lg font-bold text-red-600">{stats.tier_1_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Tier 2</div>
              <div className="text-lg font-bold text-amber-600">{stats.tier_2_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Tier 3</div>
              <div className="text-lg font-bold text-green-600">{stats.tier_3_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Form Letters</div>
              <div className="text-lg font-bold text-purple-600">{stats.form_letter_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Unclassified</div>
              <div className="text-lg font-bold text-gray-500">{stats.unclassified_count}</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-gray-400">Support</div>
              <div className="text-sm font-semibold text-green-600">{stats.support_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Oppose</div>
              <div className="text-sm font-semibold text-red-600">{stats.oppose_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Mixed</div>
              <div className="text-sm font-semibold text-amber-600">{stats.mixed_count}</div>
            </div>
            <div>
              <div className="text-xs text-gray-400">Neutral</div>
              <div className="text-sm font-semibold text-gray-600">{stats.neutral_count}</div>
            </div>
          </div>
        </div>
      )}

      {/* Processing Steps */}
      <div className="space-y-4">
        <h2 className="font-semibold text-gray-900">Processing Pipeline</h2>

        <ProcessingStep
          title="Step 1: Detect Form Letters"
          description="Fast text fingerprinting to identify duplicate/form letter campaigns. Free — no API cost."
          buttonText="Detect Form Letters"
          variant="green"
          running={running.formLetters}
          result={results.formLetters}
          onRun={() => runStep('formLetters', () => api.detectFormLetters(docket))}
        />

        <ProcessingStep
          title="Step 2: AI Tier Classification"
          description="Uses Claude Sonnet to classify comments into Tier 1/2/3, assign sentiment, and detect commenter types. ~$0.01-0.03 per batch of 50."
          buttonText="Run AI Tiering (batch 50)"
          variant="amber"
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
          variant="green"
          running={running.sumT3}
          result={results.sumT3}
          onRun={() => runStep('sumT3', () => api.aiSummarize(docket, 3, 200))}
        />
      </div>
    </div>
  );
}
