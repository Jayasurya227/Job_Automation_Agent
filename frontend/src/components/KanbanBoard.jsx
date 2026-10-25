import React from 'react';
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
  Send,
  Zap,
  CheckCircle,
  Briefcase,
  Mail
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
  onSelectJob, 
  onStatusChange, 
  onDeleteJob,
  onApplyJob
}) {
  const getJobsByStatus = (status) => {
    return jobs.filter((j) => {
      if (status === 'Applied') return j.status === 'Applied';
      return j.status !== 'Applied';
    });
  };

  return (
    <div className="kanban-board-grid">
      {COLUMNS.map((col) => {
        const colJobs = getJobsByStatus(col.id);
        return (
          <div
            key={col.id}
            style={{
              background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.65) 0%, rgba(246, 249, 254, 0.5) 100%)',
              backdropFilter: 'blur(18px)',
              WebkitBackdropFilter: 'blur(18px)',
              border: '1px solid rgba(255, 255, 255, 0.9)',
              borderRadius: '16px',
              display: 'flex',
              flexDirection: 'column',
              minHeight: '440px',
              minWidth: 0,
              overflow: 'hidden',
              boxShadow: '0 8px 24px -4px rgba(15, 23, 42, 0.06), 0 2px 6px -1px rgba(15, 23, 42, 0.03)',
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
                  <div style={{ 
                    fontSize: '0.92rem', 
                    fontWeight: 800, 
                    color: 'var(--text-main)',
                    letterSpacing: '-0.01em',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {col.title}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {col.subtitle}
                  </div>
                </div>
              </div>
              <span className={`badge ${col.badgeClass}`} style={{ fontSize: '0.75rem', padding: '3px 10px', flexShrink: 0 }}>
                {colJobs.length} {colJobs.length === 1 ? 'Job' : 'Jobs'}
              </span>
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
              {colJobs.length === 0 ? (
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
                colJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onSelect={(tab) => onSelectJob(job.id, tab)}
                    onStatusChange={(newStatus) => onStatusChange(job.id, newStatus)}
                    onDelete={() => onDeleteJob(job.id)}
                    onApply={() => onApplyJob && onApplyJob(job)}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function JobCard({ job, onSelect, onStatusChange, onDelete, onApply }) {
  const score = job.match_score;
  const isHighMatch = score !== null && score >= 80;
  const isMedMatch = score !== null && score >= 60 && score < 80;
  const scoreColor = isHighMatch ? 'var(--emerald)' : isMedMatch ? 'var(--amber)' : 'var(--rose)';
  const scoreBg = isHighMatch 
    ? 'rgba(16, 185, 129, 0.12)' 
    : isMedMatch ? 'rgba(245, 158, 11, 0.12)' : 'rgba(244, 63, 94, 0.12)';
  
  const edgeColor = isHighMatch ? 'var(--emerald)' : job.status === 'Applied' ? 'var(--emerald)' : 'var(--cyan)';
  const companyStyle = getCompanyStyle(job.company_name);

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

        {/* Portal & Source Tag */}
        <span 
          className="badge" 
          style={{ 
            background: 'rgba(99, 102, 241, 0.12)', 
            border: '1px solid rgba(99, 102, 241, 0.3)', 
            color: 'var(--primary-light)',
            fontSize: '0.66rem', 
            padding: '2px 7px', 
            flexShrink: 0 
          }}
        >
          {job.portal_name || 'Naukri'}
        </span>
      </div>

      {/* Main Job Title */}
      <h3 style={{
        fontSize: '0.94rem',
        fontWeight: 700,
        color: 'var(--text-main)',
        marginBottom: '8px',
        lineHeight: 1.35,
        letterSpacing: '-0.01em',
        wordBreak: 'break-word',
      }}>
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
            background: 'rgba(255, 255, 255, 0.04)',
            padding: '2px 8px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.06)'
          }}>
            {job.recommendation}
          </span>
        )}

        {job.notes && job.notes.includes('[Outreach Sent') && (
          <span 
            className="badge badge-emerald" 
            onClick={(e) => {
              e.stopPropagation();
              onSelect('outreach');
            }}
            style={{ 
              fontSize: '0.68rem', 
              fontWeight: 600,
              padding: '2px 7px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              cursor: 'pointer'
            }}
            title="Click to view outreach history"
          >
            <Mail size={10} /> Emailed
          </span>
        )}
      </div>

      {/* Card Action Controls Footer */}
      <div 
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '10px',
          marginTop: '6px',
          minWidth: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
          {job.status === 'Applied' ? (
            <span className="badge badge-emerald" style={{ fontSize: '0.7rem', padding: '3px 8px' }}>
              <CheckCircle size={11} /> Applied
            </span>
          ) : (
            <span className="badge badge-cyan" style={{ fontSize: '0.7rem', padding: '3px 8px' }}>
              <Zap size={11} /> Queued
            </span>
          )}
        </div>

        {/* Action Buttons Row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect('outreach');
            }}
            className="btn btn-sm"
            style={{ 
              padding: '5px 10px', 
              fontSize: '0.75rem',
              fontWeight: 700,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              color: '#c2410c',
              background: 'rgba(234, 88, 12, 0.12)',
              border: '1.5px solid rgba(234, 88, 12, 0.5)',
              boxShadow: '0 1px 3px rgba(234, 88, 12, 0.15)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(234, 88, 12, 0.22)';
              e.currentTarget.style.borderColor = '#ea580c';
              e.currentTarget.style.color = '#9a3412';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(234, 88, 12, 0.12)';
              e.currentTarget.style.borderColor = 'rgba(234, 88, 12, 0.5)';
              e.currentTarget.style.color = '#c2410c';
            }}
            title="Preview & send recruiter email"
          >
            <Mail size={13} strokeWidth={2.4} color="#ea580c" /> Email
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect('overview');
            }}
            className="btn btn-secondary btn-sm"
            style={{ 
              padding: '5px 9px', 
              fontSize: '0.74rem',
              fontWeight: 600,
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
            }}
          >
            Inspect <ChevronRight size={12} />
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm(`Delete ${job.job_title} at ${job.company_name}?`)) {
                onDelete();
              }
            }}
            className="btn btn-danger-ghost btn-sm"
            style={{ padding: '5px 8px', borderRadius: '8px' }}
            title="Delete Job"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
