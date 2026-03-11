import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api';

function Badge({ className, children }) {
  return <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${className}`}>{children}</span>;
}

function Section({ title, children }) {
  if (!children) return null;
  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}

export default function CommentDetail() {
  const { documentId } = useParams();
  const [comment, setComment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getComment(documentId)
      .then(data => { setComment(data); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [documentId]);

  if (loading) return <div className="p-8 text-center text-gray-500">Loading comment...</div>;
  if (error) return <div className="text-red-600 p-4 bg-red-50 rounded-lg">Error: {error}</div>;
  if (!comment) return <div className="p-8 text-center text-gray-500">Comment not found.</div>;

  const structured = comment.ai_summary_structured || {};
  const tier = comment.tier || 3;
  const tierCls = tier === 1 ? 'tier-1' : tier === 2 ? 'tier-2' : 'tier-3';
  const sentCls = comment.sentiment?.toLowerCase() === 'support' ? 'sentiment-support'
    : comment.sentiment?.toLowerCase() === 'oppose' ? 'sentiment-oppose'
    : comment.sentiment?.toLowerCase() === 'mixed' ? 'sentiment-mixed'
    : 'sentiment-neutral';

  return (
    <div>
      {/* Back link */}
      <Link to="/comments" className="text-blue-600 hover:text-blue-800 text-sm mb-4 inline-block">
        ← Back to Comments
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              {comment.commenter_name || comment.commenter_organization || 'Anonymous Commenter'}
            </h1>
            {comment.commenter_organization && comment.commenter_name && (
              <p className="text-gray-500 mt-1">{comment.commenter_organization}</p>
            )}
            <p className="text-gray-400 text-sm mt-1">{comment.document_id}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={tierCls + ' border'}>Tier {tier}</Badge>
            <Badge className={sentCls}>{comment.sentiment || 'Unknown'}</Badge>
            {comment.is_form_letter && (
              <Badge className="bg-purple-100 text-purple-800">Form Letter</Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-4 border-t border-gray-100">
          <div>
            <div className="text-xs text-gray-400">Date Submitted</div>
            <div className="text-sm font-medium text-gray-700">{comment.submission_date || '—'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Pages</div>
            <div className="text-sm font-medium text-gray-700">{comment.page_count || '—'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Commenter Type</div>
            <div className="text-sm font-medium text-gray-700">
              {structured.commenter_type || comment.commenter_type || '—'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Source</div>
            {comment.regulations_gov_url ? (
              <a href={comment.regulations_gov_url} target="_blank" rel="noreferrer"
                className="text-sm text-blue-600 hover:text-blue-800">
                View on Regulations.gov
              </a>
            ) : (
              <span className="text-sm text-gray-700">—</span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* AI Summary */}
          {comment.ai_summary && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">AI Summary</h2>
              <p className="text-gray-700 leading-relaxed">{comment.ai_summary}</p>
            </div>
          )}

          {/* Tier 1: Key Arguments */}
          {tier === 1 && structured.key_arguments && structured.key_arguments.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Key Arguments</h2>
              <div className="space-y-4">
                {structured.key_arguments.map((arg, i) => (
                  <div key={i} className="border-l-4 border-blue-400 pl-4">
                    <h3 className="font-semibold text-gray-800">{i + 1}. {arg.topic}</h3>
                    {arg.sub_points && (
                      <ul className="mt-2 space-y-1">
                        {arg.sub_points.map((sp, j) => (
                          <li key={j} className="text-sm text-gray-600 flex items-start">
                            <span className="text-blue-400 mr-2 mt-0.5">•</span>
                            <span>{sp}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {arg.requested_action && (
                      <div className="mt-2 text-sm bg-blue-50 text-blue-700 px-3 py-2 rounded">
                        <span className="font-medium">Requested Action:</span> {arg.requested_action}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tier 1: Legal Challenges */}
          {tier === 1 && structured.legal_challenges && structured.legal_challenges.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Legal Challenges</h2>
              <div className="space-y-3">
                {structured.legal_challenges.map((lc, i) => (
                  <div key={i} className="flex items-start bg-red-50 rounded-lg p-3">
                    <div className="text-red-500 font-mono text-xs mr-3 mt-0.5 whitespace-nowrap min-w-[180px]">
                      {lc.citation}
                    </div>
                    <div className="text-sm text-gray-700">{lc.theory}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tier 1: Requested Changes */}
          {tier === 1 && structured.requested_changes && structured.requested_changes.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Requested Changes</h2>
              <div className="space-y-2">
                {structured.requested_changes.map((rc, i) => (
                  <div key={i} className="flex items-start">
                    <span className="text-amber-500 font-bold mr-2">{i + 1}.</span>
                    <span className="text-sm text-gray-700">{rc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tier 1: Key Quotes */}
          {tier === 1 && structured.key_quotes && structured.key_quotes.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Key Quotes</h2>
              <div className="space-y-3">
                {structured.key_quotes.map((q, i) => (
                  <blockquote key={i} className="border-l-4 border-gray-300 pl-4 italic text-gray-600">
                    "{q}"
                  </blockquote>
                ))}
              </div>
            </div>
          )}

          {/* Raw Comment Text (collapsible) */}
          <details className="bg-white rounded-xl shadow-sm border border-gray-200">
            <summary className="p-6 cursor-pointer text-lg font-semibold text-gray-900 hover:text-blue-600">
              Original Comment Text
            </summary>
            <div className="px-6 pb-6">
              <pre className="whitespace-pre-wrap text-sm text-gray-600 leading-relaxed max-h-[600px] overflow-y-auto">
                {comment.comment_text || 'No text available'}
              </pre>
            </div>
          </details>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Data & Evidence */}
          {tier === 1 && structured.data_evidence && structured.data_evidence.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Data & Evidence</h3>
              <div className="space-y-2">
                {structured.data_evidence.map((d, i) => (
                  <div key={i} className="text-sm text-gray-600 bg-gray-50 rounded p-2">{d}</div>
                ))}
              </div>
            </div>
          )}

          {/* Topics */}
          {structured.topics_tags && structured.topics_tags.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Topics</h3>
              <div className="flex flex-wrap gap-2">
                {structured.topics_tags.map((t, i) => (
                  <span key={i} className="bg-blue-50 text-blue-700 text-xs px-2.5 py-1 rounded-full">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* PDF Link */}
          {comment.original_pdf_url && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Attachments</h3>
              <a href={comment.original_pdf_url} target="_blank" rel="noreferrer"
                className="flex items-center text-blue-600 hover:text-blue-800 text-sm">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Download Original PDF
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
