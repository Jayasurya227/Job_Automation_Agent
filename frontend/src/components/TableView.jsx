import React from 'react';
import { 
  Building2, 
  MapPin, 
  FileText, 
  Trash2, 
  ExternalLink, 
  ChevronRight, 
  Sparkles,
  Send
} from 'lucide-react';

export default function TableView({ 
  jobs, 
  onSelectJob, 
  onStatusChange, 
  onDeleteJob,
  onApplyJob
}) {
  return (
    <div className="glass-panel" style={{ overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{
              background: 'rgba(0, 0, 0, 0.25)',
              borderBottom: '1px solid var(--border-card)',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              <th style={{ padding: '12px 16px' }}>ATS Match</th>
              <th style={{ padding: '12px 16px' }}>Job & Company</th>
              <th style={{ padding: '12px 16px' }}>Portal</th>
              <th style={{ padding: '12px 16px' }}>Status</th>
              <th style={{ padding: '12px 16px' }}>Tailored Resume</th>
              <th style={{ padding: '12px 16px' }}>Added Date</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No tracked jobs found matching your filters.
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const score = job.match_score;
                const isHighMatch = score !== null && score >= 80;
                const isMedMatch = score !== null && score >= 60 && score < 80;
                const scoreColor = isHighMatch ? 'var(--emerald)' : isMedMatch ? 'var(--amber)' : 'var(--rose)';

                return (
                  <tr
                    key={job.id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      transition: 'background 0.15s ease',
                      cursor: 'pointer',
                    }}
                    onClick={() => onSelectJob(job.id)}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Score */}
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {score !== null ? (
                        <div style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          background: `rgba(${isHighMatch ? '16, 185, 129' : isMedMatch ? '245, 158, 11' : '244, 63, 94'}, 0.15)`,
                          border: `1px solid ${scoreColor}`,
                          color: scoreColor,
                          fontWeight: 800,
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.8rem',
                        }}>
                          <Sparkles size={12} /> {score}%
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-dim)' }}>--</span>
                      )}
                    </td>

                    {/* Job & Company */}
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '2px' }}>
                        {job.job_title}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        <Building2 size={12} color="var(--primary-light)" /> {job.company_name}
                        {job.location && <span style={{ color: 'var(--text-muted)' }}>• {job.location}</span>}
                      </div>
                    </td>

                    {/* Portal */}
                    <td style={{ padding: '12px 16px' }}>
                      <span className="badge badge-indigo" style={{ fontSize: '0.7rem' }}>
                        {job.portal_name || 'Manual'}
                      </span>
                    </td>

                    {/* Status */}
                    <td style={{ padding: '12px 16px' }} onClick={(e) => e.stopPropagation()}>
                      <select
                        value={job.status === 'Applied' ? 'Applied' : 'Saved'}
                        onChange={(e) => onStatusChange(job.id, e.target.value)}
                        className="form-select"
                        style={{ padding: '4px 8px', fontSize: '0.78rem', width: 'auto' }}
                      >
                        <option value="Saved">Discovered</option>
                        <option value="Applied">Applied</option>
                      </select>
                    </td>

                    {/* Tailored Resume */}
                    <td style={{ padding: '12px 16px' }}>
                      {job.tailored_resume_tex_path ? (
                        <span className="badge badge-cyan" style={{ fontSize: '0.7rem' }}>
                          <FileText size={11} /> LaTeX Ready
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>None</span>
                      )}
                    </td>

                    {/* Added Date */}
                    <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>

                    {/* Actions */}
                    <td style={{ padding: '12px 16px', textAlign: 'right', whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          onClick={() => onSelectJob(job.id)}
                          className="btn btn-secondary btn-sm"
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          Inspect <ChevronRight size={12} />
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete ${job.job_title} at ${job.company_name}?`)) {
                              onDeleteJob(job.id);
                            }
                          }}
                          className="btn btn-danger-ghost btn-sm"
                          style={{ padding: '5px' }}
                          title="Delete Job"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
