import React, { useState, useEffect } from 'react';
import { 
  X, 
  MapPin, 
  DollarSign, 
  Sparkles, 
  Clock, 
  Building, 
  Trash2, 
  ExternalLink, 
  FileText, 
  Check, 
  Globe, 
  Share2, 
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileCheck,
  Zap
} from 'lucide-react';
import { api } from '../api';
import { getJobApplyClassification, openExternalJobLink } from '../utils/jobClassification';

export default function JobModal({ 
  jobId, 
  onClose, 
  onStatusChange, 
  onDelete, 
  notify,
  onApply,
  isApplying = false,
  initialTab = 'overview'
}) {
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(
    typeof initialTab === 'string' && ['overview', 'description'].includes(initialTab)
      ? initialTab
      : 'overview'
  );
  const [resumeData, setResumeData] = useState(null);
  const [notesText, setNotesText] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);

  useEffect(() => {
    if (typeof initialTab === 'string' && ['overview', 'description'].includes(initialTab)) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  useEffect(() => {
    if (!jobId) return;
    loadDetail();
  }, [jobId]);

  const loadDetail = async () => {
    setLoading(true);
    try {
      const data = await api.getJobDetail(jobId);
      setJob(data);
      setNotesText(data.notes || '');


    } catch (err) {
      notify('Failed to load job details: ' + err.message, 'error');
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const { isExternal: isExternalJob, is1Click: isExplicit1Click } = getJobApplyClassification(job);

  return (
    <div 
      className="modal-backdrop" 
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        backgroundColor: 'rgba(20, 45, 25, 0.35)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div 
        className="modal-container glass-panel job-modal-card" 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="job-modal-header">
          <div className="job-modal-header-info">
            <div className="job-modal-title-row">
              <span className="badge badge-indigo" style={{ fontSize: '0.72rem', flexShrink: 0 }}>
                {job?.portal_name || 'Naukri'}
              </span>
              <h2 className="job-modal-title">
                {job?.job_title || 'Job Details'}
              </h2>
            </div>
            {job && (
              <div className="job-modal-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Building size={13} color="var(--cyan-light)" /> {job.company_name}
                </span>
                {job.location && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <MapPin size={13} color="var(--rose-light)" /> {job.location}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="job-modal-header-actions">
            {job && (
              job.status === 'Applied' ? (
                <span className="badge badge-emerald" style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
                  <CheckCircle2 size={13} /> Applied
                </span>
              ) : isExternalJob ? (
                <span className="badge" style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(234, 179, 8, 0.12)', color: '#b45309', border: '1px solid rgba(234, 179, 8, 0.3)', flexShrink: 0 }}>
                  <ExternalLink size={13} /> External Portal
                </span>
              ) : (
                <span className="badge badge-cyan" style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
                  <Zap size={13} /> 1-Click Apply Ready
                </span>
              )
            )}

            <button
              onClick={onClose}
              title="Close modal"
              style={{
                background: 'rgba(15, 23, 42, 0.06)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '6px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Tabs Navigation */}
        <div className="job-modal-tabs-nav" style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(241, 245, 249, 0.75)',
          padding: '0 20px',
        }}>
          {[
            { id: 'overview', label: 'AI Match Analysis', shortLabel: 'AI Analysis', icon: Sparkles },
            { id: 'description', label: 'Full Job Description', shortLabel: 'Job Description', icon: Globe },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="job-modal-tab-btn"
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '7px',
                  padding: '12px 14px',
                  background: 'none',
                  border: 'none',
                  borderBottom: isActive ? '2px solid var(--primary)' : '2px solid transparent',
                  color: isActive ? 'var(--primary-light)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                <Icon size={15} />
                <span className="desktop-tab-label">{tab.label}</span>
                <span className="mobile-tab-label" style={{ display: 'none' }}>{tab.shortLabel}</span>
              </button>
            );
          })}
        </div>

        {/* Modal Body Content */}
        <div className="job-modal-body" style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              Loading job details...
            </div>
          ) : !job ? (
            <div style={{ color: 'var(--rose-light)' }}>Job not found.</div>
          ) : (
            <>
              {/* TAB 1: AI Match Analysis */}
              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div className="job-modal-skills-grid">
                    {/* Matching Skills */}
                    <div style={{
                      background: 'rgba(16, 185, 129, 0.05)',
                      border: '1px solid rgba(16, 185, 129, 0.2)',
                      borderRadius: '12px',
                      padding: '16px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--emerald)', flexShrink: 0 }} />
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--emerald-light)', margin: 0 }}>
                          Matching Candidate Skills ({job.matching_skills?.length || 0})
                        </h4>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {job.matching_skills && job.matching_skills.length > 0 ? (
                          job.matching_skills.map((s, idx) => (
                            <span key={idx} className="badge badge-emerald job-modal-skill-badge">
                              {s}
                            </span>
                          ))
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No direct matches identified.</span>
                        )}
                      </div>
                    </div>

                    {/* Missing Skills */}
                    <div style={{
                      background: 'rgba(244, 63, 94, 0.05)',
                      border: '1px solid rgba(244, 63, 94, 0.2)',
                      borderRadius: '12px',
                      padding: '16px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--rose)', flexShrink: 0 }} />
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--rose-light)', margin: 0 }}>
                          Missing Keywords / Skills ({job.missing_skills?.length || 0})
                        </h4>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {job.missing_skills && job.missing_skills.length > 0 ? (
                          job.missing_skills.map((s, idx) => (
                            <span key={idx} className="badge badge-rose job-modal-skill-badge">
                              {s}
                            </span>
                          ))
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--emerald-light)' }}>Zero skill gaps! Full overlap.</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Key Strengths */}
                  {job.key_strengths && job.key_strengths.length > 0 && (
                    <div style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '12px',
                      padding: '16px',
                    }}>
                      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '10px', marginTop: 0 }}>
                        Key Competitive Advantages
                      </h4>
                      <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.875rem', color: 'var(--text-secondary)', margin: 0 }}>
                        {job.key_strengths.map((str, idx) => (
                          <li key={idx}>{str}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Summary Reasoning */}
                  {job.summary_reasoning && (
                    <div style={{
                      background: 'rgba(99, 102, 241, 0.05)',
                      border: '1px solid rgba(99, 102, 241, 0.2)',
                      borderRadius: '12px',
                      padding: '16px',
                    }}>
                      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--primary-light)', marginBottom: '6px', marginTop: 0 }}>
                        AI Match Evaluation Reasoning
                      </h4>
                      <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                        {job.summary_reasoning}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: Full Job Description */}
              {activeTab === 'description' && (
                <div>
                  <div style={{
                    background: 'rgba(15, 23, 42, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '12px',
                    padding: '18px 20px',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '0.88rem',
                    color: 'var(--text-main)',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.65,
                    wordBreak: 'break-word',
                  }}>
                    {job.job_description || 'No detailed job description provided.'}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="job-modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            {job?.job_url && job?.status !== 'Applied' && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => {
                  if (isExternalJob) {
                    openExternalJobLink(job.job_url);
                  } else if (onApply) {
                    onClose();
                    onApply(job);
                  } else {
                    openExternalJobLink(job.job_url);
                  }
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  padding: '7px 14px'
                }}
              >
                {isExternalJob ? (
                  <>
                    <ExternalLink size={14} /> Open External Site ↗
                  </>
                ) : (
                  <>
                    <Zap size={14} /> 1-Click Apply
                  </>
                )}
              </button>
            )}
          </div>
          <button 
            type="button" 
            className="btn btn-secondary btn-sm job-modal-close-btn" 
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
