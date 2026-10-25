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
  FileCheck
} from 'lucide-react';
import { api } from '../api';

export default function JobModal({ 
  jobId, 
  onClose, 
  onStatusChange, 
  onDelete, 
  notify,
  onApply,
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

      // Load resume if available
      if (data.tailored_resume_tex_path) {
        try {
          const res = await api.getJobResume(jobId);
          setResumeData(res);
        } catch {
          // resume might not be generated yet
        }
      }
    } catch (err) {
      notify('Failed to load job details: ' + err.message, 'error');
      onClose();
    } finally {
      setLoading(false);
    }
  };

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
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div 
        className="modal-container glass-panel" 
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '840px',
          width: '94%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          borderRadius: '16px',
          border: '1px solid var(--border-subtle)',
          boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.35)',
          background: 'var(--bg-card-solid, #ffffff)',
          position: 'relative',
          zIndex: 10000,
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-card-solid, #ffffff)',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge badge-indigo" style={{ fontSize: '0.72rem' }}>
                {job?.portal_name || 'Naukri'}
              </span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
                {job?.job_title || 'Job Details'}
              </h2>
            </div>
            {job && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Building size={13} color="var(--cyan-light)" /> {job.company_name}
                </span>
                {job.location && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <MapPin size={13} color="var(--rose-light)" /> {job.location}
                  </span>
                )}
                {job.job_url && (
                  <a 
                    href={job.job_url} 
                    target="_blank" 
                    rel="noreferrer"
                    style={{ display: 'flex', alignItems: 'center', gap: '3px', color: 'var(--primary-light)', textDecoration: 'none' }}
                  >
                    Post Link <ExternalLink size={12} />
                  </a>
                )}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {job && (
              job.status === 'Applied' ? (
                <span className="badge badge-emerald" style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <CheckCircle2 size={13} /> Applied
                </span>
              ) : (
                <span className="badge badge-cyan" style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Sparkles size={13} /> Screened & Ready
                </span>
              )
            )}

            <button
              onClick={onClose}
              style={{
                background: 'rgba(15, 23, 42, 0.06)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '6px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Tabs Navigation */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(241, 245, 249, 0.75)',
          padding: '0 24px',
          overflowX: 'auto'
        }}>
          {[
            { id: 'overview', label: 'AI Match Analysis', icon: Sparkles },
            { id: 'description', label: 'Full Job Description', icon: Globe },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  padding: '12px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: isActive ? '2px solid var(--primary)' : '2px solid transparent',
                  color: isActive ? 'var(--primary-light)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                <Icon size={15} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Modal Body Content */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
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
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '16px',
                  }}>
                    {/* Matching Skills */}
                    <div style={{
                      background: 'rgba(16, 185, 129, 0.05)',
                      border: '1px solid rgba(16, 185, 129, 0.2)',
                      borderRadius: '12px',
                      padding: '16px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--emerald)' }} />
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--emerald-light)', margin: 0 }}>
                          Matching Candidate Skills ({job.matching_skills?.length || 0})
                        </h4>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {job.matching_skills && job.matching_skills.length > 0 ? (
                          job.matching_skills.map((s, idx) => (
                            <span key={idx} className="badge badge-emerald" style={{ fontSize: '0.78rem' }}>
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
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--rose)' }} />
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--rose-light)', margin: 0 }}>
                          Missing Keywords / Skills ({job.missing_skills?.length || 0})
                        </h4>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {job.missing_skills && job.missing_skills.length > 0 ? (
                          job.missing_skills.map((s, idx) => (
                            <span key={idx} className="badge badge-rose" style={{ fontSize: '0.78rem' }}>
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

              {/* TAB 3: Full Job Description */}
              {activeTab === 'description' && (
                <div>
                  <pre style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '10px',
                    padding: '16px',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '0.85rem',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.6,
                    maxHeight: '450px',
                    overflowY: 'auto',
                  }}>
                    {job.job_description}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(7, 10, 19, 0.5)',
        }}>
          {job && (
            <button
              className="btn btn-danger-ghost btn-sm"
              onClick={() => {
                if (window.confirm(`Delete ${job.job_title} at ${job.company_name} from database?`)) {
                  onDelete(job.id);
                  onClose();
                }
              }}
            >
              <Trash2 size={15} /> Delete Job Listing
            </button>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {job && (
              <button
                id="download-tailored-resume-btn"
                type="button"
                className="btn btn-emerald btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 16px' }}
                onClick={() => {
                  window.open(api.downloadTailoredResumePdfUrl(job.id), '_blank');
                  if (notify) notify('Compiling and downloading tailored PDF resume...', 'info');
                }}
              >
                <Download size={15} /> Download Resume (PDF)
              </button>
            )}

            <button className="btn btn-secondary btn-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
