import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldCheck, 
  Send, 
  CheckCircle2, 
  XCircle, 
  Sparkles, 
  FileText, 
  ExternalLink, 
  Eye, 
  Building2, 
  MapPin, 
  ChevronDown, 
  ChevronUp, 
  AlertCircle,
  Loader2,
  Terminal
} from 'lucide-react';
import { api } from '../api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export default function ApplicationModal({ 
  job, 
  isOpen, 
  onClose, 
  onApplicationComplete,
  notify 
}) {
  const [currentStep, setCurrentStep] = useState('initializing'); // 'initializing' | 'review_gateway' | 'submitting' | 'submitted' | 'rejected'
  const [threadId, setThreadId] = useState(null);
  const [workflowState, setWorkflowState] = useState(null);
  const [reviewSnapshotUrl, setReviewSnapshotUrl] = useState(null);
  const [confirmationSnapshotUrl, setConfirmationSnapshotUrl] = useState(null);
  const [screeningAnswers, setScreeningAnswers] = useState({});
  const [executionLogs, setExecutionLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const [showAnswers, setShowAnswers] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectPrompt, setShowRejectPrompt] = useState(false);
  const [isZoomed, setIsZoomed] = useState(false);
  const [liveEvents, setLiveEvents] = useState([]);
  const [activeWorkflowStep, setActiveWorkflowStep] = useState(null);
  const [liveStatusText, setLiveStatusText] = useState('Initializing application environment...');

  useEffect(() => {
    let unsubscribe = null;
    if (isOpen && job) {
      setLiveEvents([]);
      setActiveWorkflowStep('start');
      setLiveStatusText('Connecting to real-time workflow engine...');

      unsubscribe = api.subscribeToEvents(`workflow:${job.id}`, (eventData) => {
        if (eventData?.step) {
          setActiveWorkflowStep(eventData.step);
          if (eventData.message) {
            setLiveStatusText(eventData.message);
            setLiveEvents((prev) => [
              ...prev,
              {
                timestamp: eventData.timestamp || new Date().toLocaleTimeString(),
                step: eventData.step,
                status: eventData.status,
                message: eventData.message,
              },
            ]);
          }
        }
      });

      startWorkflow();
    } else {
      resetState();
    }
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [isOpen, job]);

  const resetState = () => {
    setCurrentStep('initializing');
    setThreadId(null);
    setWorkflowState(null);
    setReviewSnapshotUrl(null);
    setConfirmationSnapshotUrl(null);
    setScreeningAnswers({});
    setExecutionLogs([]);
    setLiveEvents([]);
    setActiveWorkflowStep(null);
    setLiveStatusText('Initializing application environment...');
    setShowLogs(false);
    setShowAnswers(false);
    setIsSubmitting(false);
    setShowRejectPrompt(false);
    setIsZoomed(false);
  };

  const startWorkflow = async () => {
    setCurrentStep('initializing');
    try {
      const res = await api.triggerApply(job.id, 'assisted', job.portal_name || 'LinkedIn Easy Apply');
      setThreadId(res.thread_id);
      setWorkflowState(res.status);
      setExecutionLogs(res.execution_logs || []);

      if (res.is_interrupted) {
        // Paused at Human Review Gateway
        setCurrentStep('review_gateway');
        if (res.review_snapshot_url) {
          setReviewSnapshotUrl(`${API_BASE}${res.review_snapshot_url}`);
        }
        if (res.interrupt_payload?.screening_answers) {
          setScreeningAnswers(res.interrupt_payload.screening_answers);
        }
        notify?.('Assisted Application paused at Human Review Gateway for inspection.', 'info');
      } else if (res.status === 'SUBMITTED') {
        setCurrentStep('submitted');
        if (res.confirmation_snapshot_url) {
          setConfirmationSnapshotUrl(`${API_BASE}${res.confirmation_snapshot_url}`);
        }
      }
    } catch (err) {
      console.error('Workflow trigger failed:', err);
      notify?.('Failed to initiate application workflow: ' + err.message, 'error');
      setCurrentStep('error');
    }
  };

  const handleApproveAndSubmit = async () => {
    if (!threadId) return;
    setIsSubmitting(true);
    try {
      const res = await api.resumeWorkflow(threadId, true);
      setWorkflowState(res.status);
      setExecutionLogs(res.execution_logs || []);

      if (res.status === 'SUBMITTED') {
        setCurrentStep('submitted');
        if (res.confirmation_snapshot_url) {
          setConfirmationSnapshotUrl(`${API_BASE}${res.confirmation_snapshot_url}`);
        }
        notify?.(`Application for ${job.job_title} successfully submitted!`, 'success');
        onApplicationComplete?.(job.id, 'Applied');
      }
    } catch (err) {
      console.error('Resume submission failed:', err);
      notify?.('Submission error: ' + err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRejectApplication = async () => {
    if (!threadId) return;
    setIsSubmitting(true);
    try {
      const res = await api.resumeWorkflow(threadId, false, rejectionReason || 'Candidate skipped');
      setWorkflowState(res.status);
      setExecutionLogs(res.execution_logs || []);
      setCurrentStep('rejected');
      notify?.('Application skipped by candidate.', 'info');
      onApplicationComplete?.(job.id, 'Saved');
    } catch (err) {
      console.error('Rejection failed:', err);
      notify?.('Action error: ' + err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !job) return null;

  const score = job.match_score ?? 85;
  const isHighMatch = score >= 80;
  const scoreColor = isHighMatch ? 'var(--emerald)' : 'var(--amber)';

  const stepRank = {
    start: 0,
    evaluate: 1,
    tailor: 2,
    prepare_form: 3,
    review_gateway: 4,
    submit: 5,
  };
  const currentRank = stepRank[activeWorkflowStep] || (currentStep === 'review_gateway' ? 4 : currentStep === 'submitted' ? 5 : 0);

  const stepsList = [
    { 
      id: 'eval', 
      label: 'Match Evaluation', 
      done: currentRank > 1 || currentStep === 'review_gateway' || currentStep === 'submitted', 
      active: activeWorkflowStep === 'evaluate' || (currentStep === 'initializing' && (!activeWorkflowStep || activeWorkflowStep === 'start'))
    },
    { 
      id: 'tailor', 
      label: 'ATS Resume Tailoring', 
      done: currentRank > 2 || currentStep === 'review_gateway' || currentStep === 'submitted', 
      active: activeWorkflowStep === 'tailor' 
    },
    { 
      id: 'form', 
      label: 'Form Auto-Fill', 
      done: currentRank > 3 || currentStep === 'review_gateway' || currentStep === 'submitted', 
      active: activeWorkflowStep === 'prepare_form' 
    },
    { 
      id: 'review', 
      label: 'Review Gateway', 
      done: currentStep === 'submitted' || currentStep === 'rejected', 
      active: currentStep === 'review_gateway' 
    },
    { 
      id: 'submit', 
      label: 'Submission', 
      done: currentStep === 'submitted', 
      active: currentStep === 'submitting' || activeWorkflowStep === 'submit' 
    }
  ];

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'var(--surface-overlay)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        animation: 'fadeIn 0.2s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && currentStep !== 'submitting') {
          onClose();
        }
      }}
    >
      <div 
        style={{
          background: 'var(--surface-card)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid var(--border-card)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: isZoomed ? '1100px' : '820px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          transition: 'max-width 0.25s ease',
        }}
      >
        {/* MODAL HEADER */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.7) 0%, rgba(255, 255, 255, 0.3) 100%)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(56, 189, 248, 0.15))',
              border: '1px solid rgba(16, 185, 129, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--emerald)',
            }}>
              <Send size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  Easy Apply Gateway
                </h3>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  background: 'rgba(99, 102, 241, 0.15)',
                  color: 'var(--primary-light)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                }}>
                  <ShieldCheck size={12} /> Assisted Mode
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                <Building2 size={13} color="var(--primary-light)" />
                <span style={{ fontWeight: 600 }}>{job.company_name}</span>
                <span style={{ color: 'var(--text-muted)' }}>&bull;</span>
                <span>{job.job_title}</span>
                {job.location && <span style={{ color: 'var(--text-muted)' }}>&bull; {job.location}</span>}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              borderRadius: '8px',
              background: `rgba(${isHighMatch ? '16, 185, 129' : '245, 158, 11'}, 0.15)`,
              border: `1px solid ${scoreColor}`,
              color: scoreColor,
              fontWeight: 800,
              fontSize: '0.85rem',
            }}>
              <Sparkles size={13} /> {score}% Fit
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                color: 'var(--text-secondary)',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* STEPPER PROGRESS BAR */}
        <div style={{
          padding: '12px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(0, 0, 0, 0.25)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}>
            {stepsList.map((st, i) => (
              <div 
                key={st.id} 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.74rem',
                  fontWeight: st.active ? 800 : st.done ? 600 : 500,
                  color: st.active ? 'var(--primary-light)' : st.done ? 'var(--emerald)' : 'var(--text-dim)',
                }}
              >
                <div style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.65rem',
                  fontWeight: 800,
                  background: st.done ? 'rgba(16, 185, 129, 0.2)' : st.active ? 'rgba(99, 102, 241, 0.3)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${st.done ? 'var(--emerald)' : st.active ? 'var(--primary)' : 'var(--border-subtle)'}`,
                  color: st.done ? 'var(--emerald)' : st.active ? '#fff' : 'var(--text-dim)',
                }}>
                  {st.done ? '✓' : i + 1}
                </div>
                <span>{st.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* MODAL BODY */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* STATE 1: INITIALIZING / FORM FILLING IN PROGRESS (WITH LIVE SSE STREAM) */}
          {currentStep === 'initializing' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '10px 0' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ position: 'relative', width: '60px', height: '60px', margin: '0 auto 16px' }}>
                  <Loader2 size={60} className="spin" color="var(--primary-light)" style={{ position: 'absolute', inset: 0 }} />
                  <div style={{
                    position: 'absolute',
                    inset: '14px',
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%)',
                  }} />
                </div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '1.15rem', color: 'var(--text-main)', fontWeight: 800 }}>
                  Assisted Workflow in Progress
                </h4>
                <p style={{ margin: 0, color: 'var(--primary-light)', fontSize: '0.9rem', fontWeight: 600 }}>
                  {liveStatusText}
                </p>
              </div>

              {/* LIVE REAL-TIME SSE EVENT STREAM TERMINAL */}
              <div style={{
                background: 'rgba(5, 8, 22, 0.85)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                borderRadius: '12px',
                padding: '16px',
                fontFamily: 'monospace',
                fontSize: '0.78rem',
                maxHeight: '220px',
                overflowY: 'auto',
                boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.5)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '6px' }}>
                  <span style={{ color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--emerald)', display: 'inline-block', boxShadow: '0 0 8px var(--emerald)' }} />
                    LIVE SSE STREAM
                  </span>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.72rem' }}>
                    workflow:{job.id}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {liveEvents.length === 0 ? (
                    <div style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                      Streaming real-time execution steps from backend...
                    </div>
                  ) : (
                    liveEvents.map((ev, idx) => (
                      <div key={idx} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', lineHeight: '1.4' }}>
                        <span style={{ color: 'var(--primary-light)', opacity: 0.8 }}>[{ev.timestamp}]</span>
                        <span style={{ 
                          color: ev.status === 'completed' ? 'var(--emerald)' : ev.status === 'running' ? 'var(--amber)' : ev.status === 'paused' ? 'var(--cyan)' : '#e2e8f0',
                          flex: 1
                        }}>
                          {ev.message}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STATE 2: REVIEW GATEWAY (HUMAN-IN-THE-LOOP INSPECTION) */}
          {currentStep === 'review_gateway' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {/* Assisted Shield Notice */}
              <div style={{
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: '10px',
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}>
                <ShieldCheck size={22} color="var(--emerald)" style={{ flexShrink: 0 }} />
                <div style={{ fontSize: '0.82rem', lineHeight: '1.4' }}>
                  <strong style={{ color: 'var(--emerald)' }}>Human-in-the-Loop Review Gateway:</strong> Execution is safely paused.
                  Inspect the auto-filled form snapshot below. The application will ONLY be submitted upon your explicit approval.
                </div>
              </div>

              {/* Visual Snapshot Card */}
              {reviewSnapshotUrl && (
                <div style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid var(--border-card)',
                  borderRadius: '12px',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '10px 16px',
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.78rem',
                    color: 'var(--text-secondary)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Eye size={14} color="var(--primary-light)" />
                      <span>Live Playwright Form Snapshot</span>
                    </div>
                    <button
                      onClick={() => setIsZoomed(!isZoomed)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--primary-light)',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        fontWeight: 600,
                      }}
                    >
                      {isZoomed ? 'Shrink Preview' : 'Expand Preview'}
                    </button>
                  </div>
                  <div style={{
                    padding: '12px',
                    display: 'flex',
                    justifyContent: 'center',
                    background: 'var(--bg-secondary)',
                    borderRadius: '10px',
                  }}>
                    <img 
                      src={reviewSnapshotUrl} 
                      alt="Form Review Snapshot" 
                      style={{
                        maxWidth: '100%',
                        borderRadius: '8px',
                        border: '1px solid var(--border-subtle)',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
                        maxHeight: isZoomed ? '600px' : '360px',
                        objectFit: 'contain',
                      }} 
                    />
                  </div>
                </div>
              )}

              {/* Staged Form Answers Accordion */}
              <div style={{
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '10px',
                overflow: 'hidden',
              }}>
                <button
                  onClick={() => setShowAnswers(!showAnswers)}
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: 'transparent',
                    border: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    color: 'var(--text-main)',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={15} color="var(--accent-cyan)" />
                    <span>Candidate Staged Q&A Answers ({Object.keys(screeningAnswers).length} fields verified)</span>
                  </div>
                  {showAnswers ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {showAnswers && (
                  <div style={{
                    padding: '12px 16px',
                    borderTop: '1px solid var(--border-subtle)',
                    background: 'rgba(0, 0, 0, 0.2)',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                    gap: '12px',
                    fontSize: '0.78rem',
                  }}>
                    {Object.entries(screeningAnswers).map(([k, v]) => (
                      <div key={k} style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle)',
                      }}>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'capitalize', marginBottom: '2px' }}>
                          {k.replace(/_/g, ' ')}
                        </div>
                        <div style={{ color: 'var(--text-main)', fontWeight: 600, wordBreak: 'break-word' }}>
                          {typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v || '--')}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Reject / Skip prompt if toggled */}
              {showRejectPrompt && (
                <div style={{
                  background: 'rgba(244, 63, 94, 0.1)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  borderRadius: '10px',
                  padding: '14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--rose-light)', fontWeight: 700 }}>
                    Please provide an optional skip reason:
                  </div>
                  <input
                    className="form-input"
                    placeholder="e.g. Salary too low, non-preferred location, mismatch"
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    style={{ fontSize: '0.8rem', padding: '8px 12px' }}
                  />
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '4px' }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setShowRejectPrompt(false)}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={handleRejectApplication}
                      disabled={isSubmitting}
                    >
                      Confirm Skip
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STATE 3: SUBMITTED CONFIRMATION */}
          {currentStep === 'submitted' && (
            <div style={{ textAlign: 'center', padding: '30px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: 'rgba(16, 185, 129, 0.15)',
                border: '2px solid var(--emerald)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--emerald)',
                marginBottom: '16px',
              }}>
                <CheckCircle2 size={36} />
              </div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '1.3rem', color: '#fff', fontWeight: 800 }}>
                Application Submitted!
              </h3>
              <p style={{ margin: '0 0 20px 0', color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '460px' }}>
                Your verified candidate application for <strong>{job.job_title}</strong> at <strong>{job.company_name}</strong> was submitted and marked as <strong>Applied</strong> in your database.
              </p>

              {confirmationSnapshotUrl && (
                <div style={{
                  marginBottom: '20px',
                  borderRadius: '10px',
                  overflow: 'hidden',
                  border: '1px solid var(--border-card)',
                  maxWidth: '520px',
                }}>
                  <div style={{ padding: '6px 12px', background: 'rgba(0,0,0,0.3)', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Submission Confirmation Receipt
                  </div>
                  <img src={confirmationSnapshotUrl} alt="Confirmation Receipt" style={{ width: '100%', display: 'block' }} />
                </div>
              )}
            </div>
          )}

          {/* STATE 4: REJECTED / SKIPPED */}
          {currentStep === 'rejected' && (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <div style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'rgba(244, 63, 94, 0.12)',
                border: '2px solid var(--rose)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--rose)',
                margin: '0 auto 16px',
              }}>
                <XCircle size={32} />
              </div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                Application Skipped
              </h3>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                You chose to skip submitting this role. The job remains safely archived in your tracker.
              </p>
            </div>
          )}

          {/* AUDIT LOG DRAWER */}
          {executionLogs.length > 0 && (
            <div style={{
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              overflow: 'hidden',
            }}>
              <button
                onClick={() => setShowLogs(!showLogs)}
                style={{
                  width: '100%',
                  padding: '8px 14px',
                  background: 'transparent',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  color: 'var(--text-muted)',
                  fontSize: '0.74rem',
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Terminal size={12} />
                  <span>LangGraph Audit Trail ({executionLogs.length} events)</span>
                </div>
                {showLogs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>

              {showLogs && (
                <div style={{
                  padding: '10px 14px',
                  borderTop: '1px solid var(--border-subtle)',
                  background: '#070a0e',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.72rem',
                  lineHeight: '1.5',
                  color: 'var(--accent-cyan)',
                  maxHeight: '140px',
                  overflowY: 'auto',
                }}>
                  {executionLogs.map((log, idx) => (
                    <div key={idx} style={{ marginBottom: '4px' }}>&gt; {log}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* MODAL FOOTER ACTION BAR */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(0, 0, 0, 0.25)',
        }}>
          {currentStep === 'review_gateway' ? (
            <>
              <button
                className="btn btn-danger-ghost"
                onClick={() => setShowRejectPrompt(true)}
                disabled={isSubmitting}
                style={{ fontSize: '0.85rem' }}
              >
                <XCircle size={15} />
                <span>Skip Role</span>
              </button>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  className="btn btn-secondary"
                  onClick={onClose}
                  disabled={isSubmitting}
                  style={{ fontSize: '0.85rem' }}
                >
                  Inspect Later
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleApproveAndSubmit}
                  disabled={isSubmitting}
                  style={{
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    borderColor: '#10b981',
                    boxShadow: '0 4px 16px rgba(16, 185, 129, 0.3)',
                    fontSize: '0.85rem',
                    fontWeight: 800,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={15} className="spin" />
                      <span>Submitting Application...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      <span>Approve & Submit Application</span>
                    </>
                  )}
                </button>
              </div>
            </>
          ) : currentStep === 'submitted' || currentStep === 'rejected' ? (
            <div style={{ display: 'flex', width: '100%', justifyContent: 'flex-end' }}>
              <button
                className="btn btn-primary"
                onClick={onClose}
                style={{ minWidth: '110px' }}
              >
                Done
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', width: '100%', justifyContent: 'flex-end' }}>
              <button
                className="btn btn-secondary"
                onClick={onClose}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
