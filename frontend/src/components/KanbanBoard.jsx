import React, { useState } from 'react';
import { getJobApplyClassification, openExternalJobLink } from '../utils/jobClassification';
import {
  Building2,
  MapPin,
  Calendar,
  FileText,
  Trash2,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Inbox,
  Zap,
  Check,
  CheckCircle,
  Briefcase,
  Loader2,
  Clock,
  Archive
} from 'lucide-react';

const COLUMNS = [
  {
    id: 'Saved',
    title: 'Discovered Jobs',
    subtitle: 'Found & Screened by Agent',
    color: 'var(--cyan)',
    glow: 'rgba(6, 182, 212, 0.4)',
    badgeClass: 'badge-cyan'
  },
  {
    id: 'Applied',
    title: 'Applied Jobs',
    subtitle: 'Submitted to Employer',
    color: 'var(--emerald)',
    glow: 'rgba(16, 185, 129, 0.4)',
    badgeClass: 'badge-emerald'
  },
];

// Helper to generate consistent gradient & initials from company name
function getCompanyStyle(companyName = '') {
  const clean = companyName.trim() || 'Company';
  const parts = clean.split(/\s+/);
  const initials = parts.length > 1
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : clean.slice(0, 2).toUpperCase();

  // Hash company name to pick from curated gradient palettes
  let hash = 0;
  for (let i = 0; i < clean.length; i++) hash = clean.charCodeAt(i) + ((hash << 5) - hash);
  const palettes = [
    { bg: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)', text: '#fff' },
    { bg: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)', text: '#fff' },
    { bg: 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)', text: '#fff' },
    { bg: 'linear-gradient(135deg, #ec4899 0%, #be185d 100%)', text: '#fff' },
    { bg: 'linear-gradient(135deg, #10b981 0%, #047857 100%)', text: '#fff' },
    { bg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', text: '#fff' },
  ];
  const chosen = palettes[Math.abs(hash) % palettes.length];
  return { initials, ...chosen };
}

export default function KanbanBoard({
  jobs,
  statusFilter = 'All',
  onSelectJob,
  onStatusChange,
  onDeleteJob,
  onApplyJob,
  applyingJobId = null,
  maxDaily = 7
}) {
  const [confirmApplyJob, setConfirmApplyJob] = useState(null);

  // Calculate high-match jobs waiting in reserve in Archived pool
  const reserveJobs = jobs.filter(
    (j) => j.status === 'Archived' && (j.match_score || 0) >= 70
  );
  const reserveCount = reserveJobs.length;

  // Determine displayed columns based on active dropdown selection
  let activeColumns = [];

  if (statusFilter === 'All') {
    activeColumns = [
      {
        id: 'Saved',
        title: 'Discovered Jobs',
        subtitle: 'Found & Screened by Agent (≥ 70% Match)',
        color: 'var(--cyan)',
        glow: 'rgba(6, 182, 212, 0.4)',
        badgeClass: 'badge-cyan',
        filterFn: (j) => j.status !== 'Applied',
      },
      {
        id: 'Applied',
        title: 'Applied Jobs',
        subtitle: `Submitted to Employer (Max ${maxDaily}/day)`,
        color: 'var(--emerald)',
        glow: 'rgba(16, 185, 129, 0.4)',
        badgeClass: 'badge-emerald',
        filterFn: (j) => j.status === 'Applied',
      },
    ];
  } else if (statusFilter === 'Saved') {
    activeColumns = [
      {
        id: 'Saved',
        title: '🔍 Discovered Jobs',
        subtitle: 'Found & Screened by Agent (≥ 70% Match)',
        color: 'var(--cyan)',
        glow: 'rgba(6, 182, 212, 0.4)',
        badgeClass: 'badge-cyan',
        filterFn: (j) => j.status !== 'Applied',
      },
    ];
  } else if (statusFilter === 'Ready') {
    activeColumns = [
      {
        id: 'Ready',
        title: '⭐ Review',
        subtitle: '75%+ Matches • External Company Sites & Manual Action',
        color: 'var(--cyan)',
        glow: 'rgba(6, 182, 212, 0.4)',
        badgeClass: 'badge-cyan',
        filterFn: (j) => j.status === 'Ready',
      },
    ];
  } else if (statusFilter === 'Applied') {
    activeColumns = [
      {
        id: 'Applied',
        title: '⚡ Applied Jobs',
        subtitle: `Submitted to Employer (Max ${maxDaily}/day)`,
        color: 'var(--emerald)',
        glow: 'rgba(16, 185, 129, 0.4)',
        badgeClass: 'badge-emerald',
        filterFn: (j) => j.status === 'Applied',
      },
    ];
  } else if (statusFilter === 'Archived') {
    activeColumns = [
      {
        id: 'Archived',
        title: '📁 Archive',
        subtitle: 'Reserve Pool (70% - 74% Backup Leads)',
        color: '#8b5cf6',
        glow: 'rgba(139, 92, 246, 0.4)',
        badgeClass: 'badge-purple',
        filterFn: (j) => j.status === 'Archived',
      },
    ];
  } else {
    activeColumns = [
      {
        id: statusFilter,
        title: `${statusFilter} Jobs`,
        subtitle: `Jobs filtered by ${statusFilter}`,
        color: 'var(--primary)',
        glow: 'rgba(99, 102, 241, 0.4)',
        badgeClass: 'badge-primary',
        filterFn: (j) => j.status === statusFilter,
      },
    ];
  }

  return (
    <div
      className="kanban-board-grid"
      style={activeColumns.length === 1 ? { gridTemplateColumns: '1fr', maxWidth: '850px', margin: '0 auto' } : {}}
    >
      {activeColumns.map((col) => {
        const isDiscoveredCol = col.id === 'Saved';
        const colJobs = jobs.filter(col.filterFn);
        // Discovered Jobs showcases all qualifying high-match opportunities
        const displayedJobs = isDiscoveredCol
          ? [...colJobs].sort((a, b) => (b.match_score || 0) - (a.match_score || 0) || b.id - a.id)
          : colJobs;

        return (
          <div
            key={col.id}
            style={{
              background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.75) 0%, rgba(240, 250, 242, 0.55) 100%)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              border: '1.8px solid #ffffff',
              borderRadius: '22px',
              display: 'flex',
              flexDirection: 'column',
              minHeight: '440px',
              minWidth: 0,
              overflow: 'hidden',
              boxShadow: 'var(--shadow-md), 0 4px 16px rgba(15, 40, 20, 0.06)',
            }}
          >
            {/* Column Header */}
            <div className="kanban-column-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                <div style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: col.color,
                  boxShadow: `0 0 12px ${col.glow}`,
                  flexShrink: 0
                }} />
                <div style={{ minWidth: 0 }}>
                  <div
                    className="kanban-column-title"
                    style={{
                      fontSize: '0.92rem',
                      fontWeight: 800,
                      color: 'var(--text-main)',
                      letterSpacing: '-0.01em',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {col.title}
                  </div>
                  <div className="kanban-column-subtitle" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {col.subtitle}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className={`badge ${col.badgeClass || 'badge-cyan'}`} style={{ fontSize: '0.75rem', padding: '3px 10px', flexShrink: 0 }}>
                  {displayedJobs.length} {displayedJobs.length === 1 ? 'Job' : 'Jobs'}
                </span>
              </div>
            </div>

            {/* Column Job Cards List */}
            <div style={{
              padding: '12px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              flex: 1,
              minWidth: 0,
            }}>

              {displayedJobs.length === 0 ? (
                <div style={{
                  padding: '48px 16px',
                  textAlign: 'center',
                  color: 'var(--text-dim)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px',
                  border: '1px dashed rgba(15, 23, 42, 0.14)',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.35)',
                  margin: '8px 0',
                }}>
                  <div style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '12px',
                    background: 'rgba(15, 23, 42, 0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                  }}>
                    <Inbox size={22} strokeWidth={1.5} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      No jobs in {col.title}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {col.id === 'Saved' ? 'Jobs discovered by the AI agent will appear here' : 'Jobs you have applied to will appear here'}
                    </div>
                  </div>
                </div>
              ) : (
                displayedJobs.map((job, idx) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    ranking={isDiscoveredCol ? idx + 1 : null}
                    onSelect={(tab) => onSelectJob(job.id, tab)}
                    onStatusChange={(newStatus) => onStatusChange(job.id, newStatus)}
                    onDelete={() => onDeleteJob(job.id)}
                    onApply={() => onApplyJob && onApplyJob(job)}
                    onMarkApplied={() => setConfirmApplyJob(job)}
                    isApplying={applyingJobId === job.id}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}

      {/* Option 2: "Did you apply?" Confirmation Modal */}
      {confirmApplyJob && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            backgroundColor: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
          onClick={() => setConfirmApplyJob(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '20px',
              border: '1.5px solid rgba(255, 255, 255, 0.8)',
              boxShadow: '0 20px 40px -8px rgba(15, 23, 42, 0.25), 0 0 1px 1px rgba(0, 0, 0, 0.05)',
              maxWidth: '440px',
              width: '100%',
              padding: '24px',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header with CheckCircle icon */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div
                style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#047857',
                  flexShrink: 0,
                }}
              >
                <CheckCircle size={22} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.08rem', fontWeight: 700, color: 'var(--text-main)' }}>
                  Did you apply?
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  Confirm manual application submission
                </p>
              </div>
            </div>

            {/* Job Details Box */}
            <div
              style={{
                background: 'rgba(15, 23, 42, 0.03)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '12px 14px',
                marginBottom: '16px',
              }}
            >
              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '3px' }}>
                {confirmApplyJob.job_title}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontWeight: 600 }}>{confirmApplyJob.company_name}</span>
                {confirmApplyJob.location && <span>• {confirmApplyJob.location}</span>}
              </div>
            </div>

            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '20px' }}>
              Have you submitted your application for this job? Clicking <strong>Yes</strong> will move this card into your <strong>Applied Jobs</strong> column.
            </p>

            {/* Action Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setConfirmApplyJob(null)}
                className="btn btn-secondary btn-sm"
                style={{
                  padding: '7px 14px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  borderRadius: '10px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onStatusChange(confirmApplyJob.id, 'Applied');
                  setConfirmApplyJob(null);
                }}
                className="btn btn-primary btn-sm"
                style={{
                  padding: '7px 16px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #10b981 0%, #047857 100%)',
                  border: 'none',
                  color: '#ffffff',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)',
                }}
              >
                <Check size={14} strokeWidth={2.5} />
                <span>Yes, Mark as Applied</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function JobCard({ job, ranking, onSelect, onStatusChange, onDelete, onApply, onMarkApplied, isApplying = false }) {
  const score = job.match_score;
  const isHighMatch = score !== null && score >= 80;
  const isMedMatch = score !== null && score >= 60 && score < 80;
  const scoreColor = isHighMatch ? 'var(--emerald)' : isMedMatch ? 'var(--amber)' : 'var(--rose)';
  const scoreBg = isHighMatch
    ? 'rgba(16, 185, 129, 0.12)'
    : isMedMatch ? 'rgba(245, 158, 11, 0.12)' : 'rgba(244, 63, 94, 0.12)';

  const edgeColor = isHighMatch ? 'var(--emerald)' : job.status === 'Applied' ? 'var(--emerald)' : 'var(--cyan)';
  const companyStyle = getCompanyStyle(job.company_name);

  const { isExternal: isExternalJob, is1Click: isExplicit1Click } = getJobApplyClassification(job);

  return (
    <div
      className="job-card-interactive"
      style={{ '--card-edge-color': edgeColor }}
      onClick={() => onSelect && onSelect('overview')}
    >
      {/* Top Bar: Company Avatar + Name & Platform Badge */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px', marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
          <div
            className="company-avatar"
            style={{ background: companyStyle.bg, color: companyStyle.text }}
          >
            {companyStyle.initials}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{
              fontSize: '0.82rem',
              fontWeight: 700,
              color: 'var(--text-secondary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {job.company_name}
            </div>
            {job.location && (
              <div style={{
                fontSize: '0.72rem',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}>
                <MapPin size={11} style={{ flexShrink: 0 }} /> {job.location}
              </div>
            )}
          </div>
        </div>

        {/* Portal & Source Tag + Showcase Ranking */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
          {ranking && (
            <span
              className="badge"
              style={{
                background: 'rgba(6, 182, 212, 0.14)',
                border: '1px solid rgba(6, 182, 212, 0.35)',
                color: 'var(--cyan)',
                fontSize: '0.66rem',
                padding: '2px 7px',
                fontWeight: 700,
                flexShrink: 0
              }}
            >
              #{ranking} Top Pick
            </span>
          )}
          {job.portal_name?.toLowerCase() === 'indeed' ? (
            <span
              className="badge"
              style={{
                background: 'rgba(6, 182, 212, 0.12)',
                border: '1px solid rgba(6, 182, 212, 0.35)',
                color: 'var(--cyan)',
                fontSize: '0.66rem',
                padding: '2px 7px',
                fontWeight: 600,
                flexShrink: 0
              }}
            >
              🌐 Indeed
            </span>
          ) : (
            <span
              className="badge"
              style={{
                background: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                color: 'var(--primary-light)',
                fontSize: '0.66rem',
                padding: '2px 7px',
                fontWeight: 600,
                flexShrink: 0
              }}
            >
              🇮🇳 {job.portal_name || 'Naukri'}
            </span>
          )}
        </div>
      </div>

      {/* Main Job Title */}
      <h3
        className="job-card-title"
        style={{
          fontSize: '0.94rem',
          fontWeight: 700,
          color: 'var(--text-main)',
          marginBottom: '8px',
          lineHeight: 1.35,
          letterSpacing: '-0.01em',
          wordBreak: 'break-word',
        }}
      >
        {job.job_title}
      </h3>

      {/* ATS Match Score & AI Evaluation Pill */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
        {score !== null ? (
          <div
            className="match-score-pill"
            style={{
              background: scoreBg,
              border: `1px solid ${scoreColor}`,
              color: scoreColor,
            }}
          >
            <Sparkles size={12} />
            <span>{score}% Match</span>
          </div>
        ) : (
          <span className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)', fontSize: '0.68rem' }}>
            Unscored
          </span>
        )}

        {job.recommendation && (
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            background: 'rgba(15, 23, 42, 0.04)',
            padding: '2px 8px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)'
          }}>
            {job.recommendation.toUpperCase() === 'APPLY'
              ? (score >= 80 ? '⭐ Recommended' : '🎯 Strong Fit')
              : job.recommendation}
          </span>
        )}

      </div>

      {/* Card Action Controls Footer */}
      <div
        className={`card-action-controls-footer ${job.status === 'Applied' ? 'footer-applied' : 'footer-unapplied'}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Status Badge / Pill styled uniformly like Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', minWidth: 0, flexShrink: 0 }}>
          {job.status === 'Applied' ? (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#047857',
                borderRadius: '8px',
                padding: '5px 9px',
                fontSize: '0.74rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
                flexShrink: 0
              }}
              title="Application submitted to employer"
            >
              <CheckCircle size={12} color="#047857" />
              <span>Applied</span>
            </div>
          ) : isExternalJob ? (
            <div
              style={{
                background: 'rgba(234, 179, 8, 0.12)',
                border: '1px solid rgba(234, 179, 8, 0.3)',
                color: '#b45309',
                borderRadius: '8px',
                padding: '5px 9px',
                fontSize: '0.74rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
                flexShrink: 0
              }}
              title="External company site (direct apply required)"
            >
              <ExternalLink size={12} color="#b45309" />
              <span>External</span>
            </div>
          ) : (
            <div
              style={{
                background: 'rgba(6, 182, 212, 0.12)',
                border: '1px solid rgba(6, 182, 212, 0.3)',
                color: '#0891b2',
                borderRadius: '8px',
                padding: '5px 9px',
                fontSize: '0.74rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
                flexShrink: 0
              }}
              title="1-Click Apply Ready"
            >
              <Zap size={12} color="#0891b2" />
              <span>1-Click</span>
            </div>
          )}
        </div>

        {/* Action Buttons Row */}
        <div className="card-action-buttons-row" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {job.status !== 'Applied' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (isExternalJob) {
                  // Direct open in new tab for external company postings
                  if (job.job_url) {
                    openExternalJobLink(job.job_url);
                  }
                  return;
                }
                // Native 1-Click Apply
                if (onApply) {
                  onApply(job);
                } else if (job.job_url) {
                  openExternalJobLink(job.job_url);
                }
              }}
              disabled={!isExternalJob && isApplying}
              className="btn btn-primary btn-sm card-btn-apply"
              style={{
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 600,
                borderRadius: '8px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                minHeight: '32px'
              }}
              title={isExternalJob ? "Open external company site in new tab" : "Open Easy Apply job on portal in new tab"}
            >
              {isExternalJob ? (
                <ExternalLink size={14} color="#ffffff" />
              ) : (
                <Zap size={14} color="#ffffff" />
              )}
              <span>{isExternalJob ? 'Apply ↗' : 'Apply'}</span>
            </button>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect('overview');
            }}
            className="btn btn-secondary btn-sm card-btn-inspect"
            style={{
              padding: '6px 11px',
              fontSize: '0.78rem',
              fontWeight: 600,
              borderRadius: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minHeight: '32px'
            }}
          >
            Inspect <ChevronRight size={13} />
          </button>

          {job.status !== 'Applied' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMarkApplied && onMarkApplied(job);
              }}
              className="btn btn-sm card-btn-mark"
              style={{
                padding: '6px 10px',
                borderRadius: '8px',
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                color: '#047857',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '32px',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#10b981';
                e.currentTarget.style.color = '#ffffff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(16, 185, 129, 0.12)';
                e.currentTarget.style.color = '#047857';
              }}
              title="Did you apply? Click to mark as applied"
            >
              <Check size={14} strokeWidth={2.5} />
            </button>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm(`Delete ${job.job_title} at ${job.company_name}?`)) {
                onDelete();
              }
            }}
            className="btn btn-danger-ghost btn-sm card-btn-delete"
            style={{
              padding: '6px 10px',
              borderRadius: '8px',
              minHeight: '32px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title="Delete Job"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
