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
  Copy, 
  Globe, 
  Share2, 
  Download,
  Send,
  Paperclip,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Mail,
  XCircle,
  FileCheck,
  ZoomIn,
  Edit3,
  Eye
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
    typeof initialTab === 'string' && ['overview', 'outreach', 'description'].includes(initialTab)
      ? initialTab
      : 'overview'
  );
  const [resumeData, setResumeData] = useState(null);
  const [copiedSubject, setCopiedSubject] = useState(false);
  const [copiedBody, setCopiedBody] = useState(false);
  const [notesText, setNotesText] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);

  useEffect(() => {
    if (typeof initialTab === 'string' && ['overview', 'outreach', 'description'].includes(initialTab)) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  // Outreach & SMTP State
  const [recipientEmail, setRecipientEmail] = useState('');
  const [customSubject, setCustomSubject] = useState('');
  const [customBody, setCustomBody] = useState('');
  const [attachResume, setAttachResume] = useState(true);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailSentResult, setEmailSentResult] = useState(null);
  // Gmail-style UI state
  const [editingBody, setEditingBody] = useState(false);
  const [editingSubject, setEditingSubject] = useState(false);
  const [editingRecipient, setEditingRecipient] = useState(false);
  const [resumeZoomed, setResumeZoomed] = useState(false);

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
      setRecipientEmail(data.detected_email || '');
      setCustomSubject(data.cold_email_subject || `Application: ${data.job_title} - Rayavaram Jayasurya`);
      setCustomBody(data.cold_email_body || '');
      setAttachResume(true);
      setEmailSentResult(null);

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

  const handleSendEmail = async () => {
    if (!recipientEmail || !recipientEmail.trim() || !recipientEmail.includes('@')) {
      notify('Please enter a valid recipient email address (e.g. careers@company.com)', 'error');
      return;
    }

    setSendingEmail(true);
    setEmailSentResult(null);
    try {
      const res = await api.sendColdEmail({
        job_id: job.id,
        recipient_email: recipientEmail.trim(),
        subject: customSubject || job.cold_email_subject,
        body: customBody || job.cold_email_body,
        resume_pdf_path: attachResume ? (job.tailored_resume_pdf_path || 'data/uploaded_resume.pdf') : null
      });

      setEmailSentResult(res);
      notify(`Email successfully dispatched to ${res.recipient}! (Sent today: ${res.daily_sent}/${res.daily_limit})`, 'success');

      // Append audit log entry to notes and persist
      const timestamp = new Date().toLocaleDateString();
      const resumeNote = res.resume_attached ? ' [PDF Resume Attached]' : '';
      const emailLog = `\n[${timestamp}] Cold outreach dispatched to ${res.recipient}${resumeNote} via Gmail SMTP.`;
      const updatedNotes = (notesText || '') + emailLog;
      setNotesText(updatedNotes);
      try {
        await api.updateJobStatus(job.id, job.status, updatedNotes);
        if (onStatusChange) onStatusChange(job.id, job.status, updatedNotes);
      } catch {
        // silent fail on note update
      }
    } catch (err) {
      notify(`Failed to send email: ${err.message}`, 'error');
    } finally {
      setSendingEmail(false);
    }
  };

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text);
    if (type === 'subject') {
      setCopiedSubject(true);
      setTimeout(() => setCopiedSubject(false), 2000);
    } else if (type === 'body') {
      setCopiedBody(true);
      setTimeout(() => setCopiedBody(false), 2000);
    }
    notify('Copied to clipboard!', 'info');
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
            { id: 'outreach', label: '✉️ Email Recruiter (Outreach)', icon: Mail },
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

              {/* TAB 2: Email Recruiter — Gmail-Style View */}
              {activeTab === 'outreach' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>

                  {/* ── Sent Banner ── */}
                  {job.notes?.includes('[Outreach Sent') && (
                    <div style={{
                      padding: '10px 16px',
                      marginBottom: '16px',
                      borderRadius: '10px',
                      background: 'rgba(16, 185, 129, 0.08)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      display: 'flex', alignItems: 'center', gap: '10px',
                      fontSize: '0.83rem', color: '#059669'
                    }}>
                      <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
                      <span><strong>Outreach already sent</strong> for this position. You can send again below.</span>
                    </div>
                  )}

                  {/* ════════════════════════════════════════
                       GMAIL-STYLE EMAIL COMPOSE CARD
                  ════════════════════════════════════════ */}
                  <div style={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: '12px',
                    boxShadow: '0 2px 12px rgba(15,23,42,0.08)',
                    overflow: 'hidden',
                    fontFamily: 'Google Sans, Roboto, Arial, sans-serif',
                  }}>

                    {/* ── Gmail Subject Bar ── */}
                    <div style={{
                      padding: '14px 20px 12px',
                      borderBottom: '1px solid #f1f5f9',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', minWidth: '38px' }}>Sub:</span>
                        {editingSubject ? (
                          <input
                            autoFocus
                            type="text"
                            value={customSubject}
                            onChange={(e) => setCustomSubject(e.target.value)}
                            onBlur={() => setEditingSubject(false)}
                            style={{
                              flex: 1, border: 'none', outline: 'none',
                              fontSize: '1rem', fontWeight: 700, color: '#0f172a',
                              background: 'transparent', fontFamily: 'inherit'
                            }}
                          />
                        ) : (
                          <span
                            onClick={() => setEditingSubject(true)}
                            title="Click to edit subject"
                            style={{
                              flex: 1, fontSize: '1rem', fontWeight: 700,
                              color: '#0f172a', cursor: 'text',
                            }}
                          >
                            {customSubject || `Application for ${job.job_title} Role`}
                          </span>
                        )}
                        <Edit3
                          size={14}
                          style={{ color: '#94a3b8', cursor: 'pointer', flexShrink: 0 }}
                          onClick={() => setEditingSubject(true)}
                          title="Edit subject"
                        />
                      </div>
                    </div>

                    {/* ── Gmail Sender Row ── */}
                    <div style={{
                      padding: '12px 20px 10px',
                      borderBottom: '1px solid #f1f5f9',
                      display: 'flex', alignItems: 'flex-start', gap: '12px'
                    }}>
                      {/* Avatar */}
                      <div style={{
                        width: '38px', height: '38px', borderRadius: '50%',
                        background: 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: '#ffffff', fontSize: '0.85rem', fontWeight: 700,
                        flexShrink: 0, boxShadow: '0 2px 6px rgba(99,102,241,0.35)'
                      }}>
                        RJ
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                          <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a' }}>
                            Rayavaram Jayasurya
                          </span>
                          <span style={{ fontSize: '0.72rem', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                            {new Date().toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px' }}>
                          {'<rayavaramjayasurya@gmail.com>'}
                        </div>

                        {/* Recipient line */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                          <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>to</span>
                          {editingRecipient ? (
                            <input
                              autoFocus
                              type="email"
                              value={recipientEmail}
                              onChange={(e) => setRecipientEmail(e.target.value)}
                              onBlur={() => setEditingRecipient(false)}
                              placeholder="careers@company.com"
                              style={{
                                border: 'none', outline: 'none', borderBottom: '1.5px solid #6366f1',
                                fontSize: '0.78rem', color: '#334155',
                                background: 'transparent', fontFamily: 'inherit',
                                padding: '1px 0', minWidth: '200px'
                              }}
                            />
                          ) : (
                            <span
                              onClick={() => setEditingRecipient(true)}
                              title="Click to edit recipient email"
                              style={{
                                fontSize: '0.78rem', fontWeight: 600,
                                color: recipientEmail ? '#334155' : '#ef4444',
                                cursor: 'text',
                                borderBottom: '1px dashed #cbd5e1',
                                paddingBottom: '1px'
                              }}
                            >
                              {recipientEmail || (job.detected_email ? job.detected_email : '⚠ Enter recruiter email...')}
                            </span>
                          )}
                          <Edit3
                            size={11}
                            style={{ color: '#cbd5e1', cursor: 'pointer' }}
                            onClick={() => setEditingRecipient(true)}
                            title="Edit recipient"
                          />
                        </div>
                      </div>
                    </div>

                    {/* ── Email Body ── */}
                    <div style={{ padding: '18px 20px 10px' }}>
                      {editingBody ? (
                        <textarea
                          autoFocus
                          rows={10}
                          value={customBody}
                          onChange={(e) => setCustomBody(e.target.value)}
                          style={{
                            width: '100%', border: 'none', outline: 'none',
                            resize: 'vertical', fontSize: '0.875rem',
                            lineHeight: 1.75, color: '#1e293b',
                            fontFamily: 'Google Sans, Roboto, Arial, sans-serif',
                            background: 'transparent',
                          }}
                        />
                      ) : (
                        <pre
                          onClick={() => setEditingBody(true)}
                          title="Click to edit email body"
                          style={{
                            margin: 0, padding: 0,
                            fontFamily: 'Google Sans, Roboto, Arial, sans-serif',
                            fontSize: '0.875rem', lineHeight: 1.75,
                            color: '#1e293b', whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word', cursor: 'text',
                          }}
                        >
                          {customBody}
                        </pre>
                      )}

                      {/* Edit / Preview toggle */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                        <button
                          onClick={() => setEditingBody(!editingBody)}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            fontSize: '0.72rem', color: '#94a3b8',
                            display: 'flex', alignItems: 'center', gap: '4px'
                          }}
                        >
                          {editingBody ? <><Eye size={12} /> Preview</> : <><Edit3 size={12} /> Edit Body</>}
                        </button>
                      </div>
                    </div>

                    {/* ── Attachment Section ── */}
                    <div style={{
                      borderTop: '1px solid #f1f5f9',
                      padding: '14px 20px 16px',
                    }}>
                      <div style={{
                        fontSize: '0.72rem', fontWeight: 600,
                        color: '#64748b', marginBottom: '12px',
                        display: 'flex', alignItems: 'center', gap: '6px'
                      }}>
                        <Paperclip size={13} />
                        1 attachment
                        <span style={{ color: '#cbd5e1' }}>•</span>
                        <span style={{ color: '#94a3b8' }}>Scanned by Gmail ✓</span>
                      </div>

                      {/* PDF Attachment Card */}
                      <div
                        onClick={() => setResumeZoomed(true)}
                        title="Click to preview resume"
                        style={{
                          display: 'inline-flex',
                          flexDirection: 'column',
                          width: '160px',
                          borderRadius: '10px',
                          border: '1px solid #e2e8f0',
                          overflow: 'hidden',
                          cursor: 'pointer',
                          boxShadow: '0 1px 6px rgba(15,23,42,0.10)',
                          transition: 'box-shadow 0.15s ease, transform 0.15s ease',
                          userSelect: 'none',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.boxShadow = '0 4px 16px rgba(15,23,42,0.18)';
                          e.currentTarget.style.transform = 'translateY(-2px)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.boxShadow = '0 1px 6px rgba(15,23,42,0.10)';
                          e.currentTarget.style.transform = 'translateY(0)';
                        }}
                      >
                        {/* Thumbnail preview */}
                        <div style={{
                          height: '110px',
                          background: 'linear-gradient(160deg, #f8fafc 0%, #e2e8f0 100%)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          position: 'relative', overflow: 'hidden',
                        }}>
                          {/* Simulated resume doc lines */}
                          <div style={{ padding: '10px 12px', width: '100%' }}>
                            <div style={{ fontSize: '0.6rem', fontWeight: 800, color: '#1e293b', marginBottom: '4px', textAlign: 'center' }}>Rayavaram Jayasurya</div>
                            <div style={{ fontSize: '0.45rem', color: '#64748b', textAlign: 'center', marginBottom: '6px' }}>+91 9381744883 • rayavaramjayasurya@gmail.com</div>
                            {[90, 75, 80, 65, 85, 70].map((w, i) => (
                              <div key={i} style={{
                                height: '4px', borderRadius: '2px', marginBottom: '3px',
                                background: i === 0 ? '#4f46e5' : '#cbd5e1',
                                width: w + '%', opacity: i === 0 ? 1 : 0.7
                              }} />
                            ))}
                          </div>
                          {/* Zoom hint overlay */}
                          <div style={{
                            position: 'absolute', top: '6px', right: '6px',
                            background: 'rgba(99,102,241,0.85)', borderRadius: '50%',
                            width: '22px', height: '22px',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}>
                            <ZoomIn size={11} color="#fff" />
                          </div>
                        </div>

                        {/* Card footer */}
                        <div style={{
                          background: '#f8fafc',
                          borderTop: '1px solid #e2e8f0',
                          padding: '6px 8px',
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          gap: '4px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', minWidth: 0 }}>
                            <div style={{
                              background: '#dc2626', color: '#fff', fontSize: '0.5rem',
                              fontWeight: 800, padding: '1px 4px', borderRadius: '3px',
                              flexShrink: 0, letterSpacing: '0.03em'
                            }}>PDF</div>
                            <span style={{
                              fontSize: '0.6rem', color: '#334155', fontWeight: 600,
                              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                            }}>JAI Resume.pdf</span>
                          </div>
                          <a
                            href={api.downloadMasterResumePdfUrl()}
                            download
                            onClick={(e) => e.stopPropagation()}
                            title="Download Resume PDF"
                            style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              width: '20px', height: '20px', borderRadius: '4px',
                              background: 'rgba(99,102,241,0.1)',
                              color: '#6366f1', flexShrink: 0, textDecoration: 'none'
                            }}
                          >
                            <Download size={11} />
                          </a>
                        </div>
                      </div>
                    </div>

                    {/* ── Gmail-Style Action Buttons ── */}
                    <div style={{
                      borderTop: '1px solid #f1f5f9',
                      padding: '14px 20px',
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', gap: '12px',
                      flexWrap: 'wrap',
                      background: '#f8fafc'
                    }}>
                      <button
                        type="button"
                        onClick={() => setActiveTab('overview')}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: '7px',
                          padding: '9px 18px', borderRadius: '20px',
                          border: '1.5px solid #e2e8f0',
                          background: '#ffffff', color: '#475569',
                          fontSize: '0.84rem', fontWeight: 600, cursor: 'pointer',
                          fontFamily: 'inherit', transition: 'all 0.15s'
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = '#ffffff'; }}
                      >
                        <XCircle size={15} /> Discard
                      </button>

                      <button
                        type="button"
                        onClick={handleSendEmail}
                        disabled={sendingEmail}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: '8px',
                          padding: '10px 24px', borderRadius: '20px',
                          border: 'none',
                          background: sendingEmail
                            ? '#94a3b8'
                            : 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)',
                          color: '#ffffff',
                          fontSize: '0.88rem', fontWeight: 700, cursor: sendingEmail ? 'not-allowed' : 'pointer',
                          fontFamily: 'inherit',
                          boxShadow: sendingEmail ? 'none' : '0 4px 14px rgba(99,102,241,0.4)',
                          transition: 'all 0.15s'
                        }}
                        onMouseEnter={(e) => { if (!sendingEmail) e.currentTarget.style.boxShadow = '0 6px 20px rgba(99,102,241,0.55)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = sendingEmail ? 'none' : '0 4px 14px rgba(99,102,241,0.4)'; }}
                      >
                        {sendingEmail ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={15} />}
                        <span>{sendingEmail ? 'Sending...' : 'Send via Gmail'}</span>
                      </button>
                    </div>
                  </div>

                  {/* ════════════════════════════════════════
                       RESUME ZOOM FULLSCREEN MODAL
                  ════════════════════════════════════════ */}
                  {resumeZoomed && (
                    <div
                      onClick={() => setResumeZoomed(false)}
                      style={{
                        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                        background: 'rgba(15,23,42,0.82)', backdropFilter: 'blur(10px)',
                        zIndex: 99999,
                        display: 'flex', flexDirection: 'column',
                        alignItems: 'center', justifyContent: 'center',
                        padding: '20px'
                      }}
                    >
                      <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          background: '#fff', borderRadius: '14px',
                          width: '100%', maxWidth: '680px',
                          maxHeight: '88vh', overflow: 'auto',
                          boxShadow: '0 30px 80px rgba(0,0,0,0.5)',
                          display: 'flex', flexDirection: 'column'
                        }}
                      >
                        {/* Zoom header */}
                        <div style={{
                          padding: '14px 20px',
                          borderBottom: '1px solid #e2e8f0',
                          display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between',
                          background: '#f8fafc'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{
                              background: '#dc2626', color: '#fff', fontSize: '0.6rem',
                              fontWeight: 800, padding: '2px 6px', borderRadius: '4px'
                            }}>PDF</div>
                            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0f172a' }}>JAI Resume.pdf</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <a
                              href={api.downloadMasterResumePdfUrl()}
                              download
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '5px',
                                padding: '6px 14px', borderRadius: '8px',
                                background: '#eff6ff', border: '1px solid #bfdbfe',
                                color: '#3b82f6', fontSize: '0.78rem', fontWeight: 600,
                                textDecoration: 'none'
                              }}
                            >
                              <Download size={13} /> Download PDF
                            </a>
                            <button
                              onClick={() => setResumeZoomed(false)}
                              style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                color: '#64748b', padding: '4px',
                                display: 'flex', alignItems: 'center', borderRadius: '6px'
                              }}
                            >
                              <X size={18} />
                            </button>
                          </div>
                        </div>

                        {/* Zoom body — embed PDF via iframe */}
                        <iframe
                          src={`${api.downloadMasterResumePdfUrl()}#toolbar=0`}
                          title="Resume Preview"
                          style={{
                            width: '100%',
                            flex: 1,
                            minHeight: '520px',
                            border: 'none',
                          }}
                        />
                      </div>
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
