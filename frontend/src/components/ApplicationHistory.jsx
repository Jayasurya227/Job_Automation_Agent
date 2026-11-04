import React, { useState, useEffect, useCallback } from 'react';
import { 
  History, 
  Calendar, 
  Check, 
  Compass, 
  Send, 
  Sparkles, 
  ExternalLink, 
  ShieldCheck, 
  Clock, 
  Search,
  RotateCw,
  Eye
} from 'lucide-react';
import { api } from '../api';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

// Helper to generate consistent gradient & initials from company name
function getCompanyStyle(companyName = '') {
  const clean = companyName.trim() || 'Company';
  const parts = clean.split(/\s+/);
  const initials = parts.length > 1
    ? (parts[0][0] + parts[1][0]).toUpperCase()
    : clean.slice(0, 2).toUpperCase();

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

function formatDate(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch {
    return isoStr;
  }
}

export default function ApplicationHistory({ onSelectJob, notify }) {
  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1); // 1-12

  const [loading, setLoading] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [availableMonths, setAvailableMonths] = useState([]);

  // Load history data for chosen month & year
  const loadHistory = useCallback(async (yr, mo) => {
    try {
      setLoading(true);
      const data = await api.getJobsHistory(yr, mo);
      setHistoryData(data);
      if (data?.available_months?.length) {
        setAvailableMonths(data.available_months);
      }
    } catch (err) {
      console.error('Failed to load application history:', err);
      if (notify) notify(`Failed to load history: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadHistory(selectedYear, selectedMonth);
  }, [loadHistory, selectedYear, selectedMonth]);

  const handleApplyFilter = (e) => {
    e?.preventDefault();
    loadHistory(selectedYear, selectedMonth);
    if (notify) {
      notify(`Loaded history for ${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}`, 'info');
    }
  };

  const discoveredJobs = historyData?.discovered_jobs || [];
  const appliedJobs = historyData?.applied_jobs || [];
  const discoveredCount = historyData?.discovered_count ?? discoveredJobs.length;
  const appliedCount = historyData?.applied_count ?? appliedJobs.length;
  const monthName = historyData?.month_name || `${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}`;

  return (
    <div className="application-history-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Header Banner */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.85)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid var(--border-card)',
        borderRadius: '14px',
        padding: '18px 22px',
        boxShadow: '0 4px 16px rgba(15, 23, 42, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(91, 132, 51, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary)'
            }}>
              <History size={22} />
            </div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', margin: 0, letterSpacing: '-0.02em' }}>
                Application History & Archive
              </h2>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Full audit trail of all discovered and applied jobs. Active dashboard keeps a rolling 7-day window.
              </p>
            </div>
          </div>

          {/* Trust & Safety Badges */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '4px 10px',
              borderRadius: '20px',
              background: 'rgba(16, 185, 129, 0.12)',
              color: '#065f46',
              border: '1px solid rgba(16, 185, 129, 0.25)'
            }}>
              <ShieldCheck size={13} />
              Deduplication Protected
            </span>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '4px 10px',
              borderRadius: '20px',
              background: 'rgba(6, 182, 212, 0.12)',
              color: '#0e7490',
              border: '1px solid rgba(6, 182, 212, 0.25)'
            }}>
              <Clock size={13} />
              Rolling 7-Day Active Lifespan
            </span>
          </div>
        </div>

        {/* Month & Year Selection Bar */}
        <form onSubmit={handleApplyFilter} style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border-subtle)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Calendar size={15} color="var(--primary)" />
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                Filter Period:
              </span>
            </div>

            {/* Month Dropdown */}
            <select
              id="history-month-select"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(parseInt(e.target.value, 10))}
              style={{
                fontSize: '0.82rem',
                fontWeight: 600,
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border-card)',
                background: '#ffffff',
                color: 'var(--text-main)',
                cursor: 'pointer'
              }}
            >
              {MONTH_NAMES.map((m, idx) => (
                <option key={m} value={idx + 1}>{m}</option>
              ))}
            </select>

            {/* Year Dropdown */}
            <select
              id="history-year-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value, 10))}
              style={{
                fontSize: '0.82rem',
                fontWeight: 600,
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border-card)',
                background: '#ffffff',
                color: 'var(--text-main)',
                cursor: 'pointer'
              }}
            >
              {[2026, 2025, 2024].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>

            {/* Tick Mark Confirmation Button */}
            <button
              type="submit"
              id="history-apply-btn"
              className="btn btn-primary"
              disabled={loading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                fontSize: '0.8rem',
                fontWeight: 700,
                borderRadius: '8px'
              }}
            >
              <Check size={15} />
              <span>View History</span>
            </button>

            <button
              type="button"
              onClick={() => loadHistory(selectedYear, selectedMonth)}
              title="Refresh month records"
              style={{
                background: 'transparent',
                border: '1px solid var(--border-card)',
                borderRadius: '8px',
                padding: '6px 10px',
                cursor: 'pointer',
                color: 'var(--text-muted)',
                display: 'inline-flex',
                alignItems: 'center'
              }}
            >
              <RotateCw size={14} className={loading ? 'spin' : ''} />
            </button>
          </div>

          {/* Quick Month Metrics Chips */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              fontSize: '0.78rem',
              fontWeight: 700,
              padding: '4px 10px',
              borderRadius: '8px',
              background: 'rgba(6, 182, 212, 0.1)',
              color: '#0891b2'
            }}>
              🔍 Discovered: <strong>{discoveredCount}</strong>
            </span>
            <span style={{
              fontSize: '0.78rem',
              fontWeight: 700,
              padding: '4px 10px',
              borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.1)',
              color: '#059669'
            }}>
              ⚡ Applied: <strong>{appliedCount}</strong>
            </span>
          </div>
        </form>
      </div>

      {/* 2. Two-Sided Side-by-Side Columns */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
        gap: '20px',
        alignItems: 'start'
      }}>
        {/* COLUMN 1: DISCOVERED JOBS (LEFT SIDE) */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid var(--border-card)',
          borderRadius: '14px',
          padding: '18px',
          boxShadow: '0 4px 16px rgba(15, 23, 42, 0.04)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          {/* Column Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingBottom: '10px',
            borderBottom: '2px solid rgba(6, 182, 212, 0.2)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Compass size={18} color="#0891b2" />
              <h3 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
                Discovered Jobs
              </h3>
            </div>
            <span style={{
              fontSize: '0.74rem',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: 'rgba(6, 182, 212, 0.15)',
              color: '#0e7490'
            }}>
              {discoveredCount} in {monthName}
            </span>
          </div>

          {/* Job List */}
          {discoveredJobs.length === 0 ? (
            <div style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.84rem'
            }}>
              <Search size={32} style={{ margin: '0 auto 10px auto', opacity: 0.4 }} />
              <div>No discovered jobs recorded in {monthName}.</div>
              <div style={{ fontSize: '0.74rem', marginTop: '4px' }}>
                Select another month from the filter above.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {discoveredJobs.map((job) => {
                const style = getCompanyStyle(job.company_name);
                return (
                  <div
                    key={job.id}
                    style={{
                      background: '#ffffff',
                      border: '1px solid var(--border-card)',
                      borderRadius: '10px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  >
                    {/* Top Row: Avatar + Title & Company + Match Score */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', minWidth: 0 }}>
                        <div style={{
                          width: '34px',
                          height: '34px',
                          borderRadius: '8px',
                          background: style.bg,
                          color: style.text,
                          fontWeight: 800,
                          fontSize: '0.78rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0
                        }}>
                          {style.initials}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <h4 style={{
                            fontSize: '0.88rem',
                            fontWeight: 700,
                            color: 'var(--text-main)',
                            margin: 0,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }} title={job.job_title}>
                            {job.job_title}
                          </h4>
                          <div style={{
                            fontSize: '0.76rem',
                            color: 'var(--text-muted)',
                            marginTop: '2px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {job.company_name} • {job.location || 'Remote'}
                          </div>
                        </div>
                      </div>

                      {/* Match Score */}
                      {job.match_score !== null && (
                        <span style={{
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: job.match_score >= 80 ? 'rgba(16, 185, 129, 0.12)' : 'rgba(99, 102, 241, 0.12)',
                          color: job.match_score >= 80 ? '#059669' : '#4f46e5',
                          flexShrink: 0
                        }}>
                          {job.match_score}% Match
                        </span>
                      )}
                    </div>

                    {/* Meta Row: Portal & Discovered Date */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '0.72rem',
                      color: 'var(--text-secondary)',
                      paddingTop: '6px',
                      borderTop: '1px solid #f1f5f9'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          textTransform: 'uppercase',
                          fontWeight: 700,
                          fontSize: '0.64rem',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: '#f1f5f9',
                          color: '#475569'
                        }}>
                          {job.portal_name}
                        </span>
                        <span style={{ color: 'var(--text-muted)' }}>
                          📅 {formatDate(job.created_at)}
                        </span>
                      </div>

                      {/* Action Links */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {onSelectJob && (
                          <button
                            type="button"
                            onClick={() => onSelectJob(job.id)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--primary)',
                              fontWeight: 700,
                              fontSize: '0.72rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <Eye size={12} />
                            Inspect ↗
                          </button>
                        )}
                        {job.job_url && (
                          <a
                            href={job.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              color: 'var(--text-muted)',
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center'
                            }}
                            title="Open posting on job portal"
                          >
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* COLUMN 2: APPLIED JOBS (RIGHT SIDE) */}
        <div style={{
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid var(--border-card)',
          borderRadius: '14px',
          padding: '18px',
          boxShadow: '0 4px 16px rgba(15, 23, 42, 0.04)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          {/* Column Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingBottom: '10px',
            borderBottom: '2px solid rgba(16, 185, 129, 0.25)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Send size={18} color="#059669" />
              <h3 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', margin: 0 }}>
                Applied Jobs
              </h3>
            </div>
            <span style={{
              fontSize: '0.74rem',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#065f46'
            }}>
              {appliedCount} in {monthName}
            </span>
          </div>

          {/* Job List */}
          {appliedJobs.length === 0 ? (
            <div style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.84rem'
            }}>
              <Send size={32} style={{ margin: '0 auto 10px auto', opacity: 0.4 }} />
              <div>No applications submitted in {monthName}.</div>
              <div style={{ fontSize: '0.74rem', marginTop: '4px' }}>
                Select another month from the filter above.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {appliedJobs.map((job) => {
                const style = getCompanyStyle(job.company_name);
                return (
                  <div
                    key={job.id}
                    style={{
                      background: '#ffffff',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      borderRadius: '10px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  >
                    {/* Top Row: Avatar + Title & Company + Status & Score */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', minWidth: 0 }}>
                        <div style={{
                          width: '34px',
                          height: '34px',
                          borderRadius: '8px',
                          background: style.bg,
                          color: style.text,
                          fontWeight: 800,
                          fontSize: '0.78rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0
                        }}>
                          {style.initials}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <h4 style={{
                            fontSize: '0.88rem',
                            fontWeight: 700,
                            color: 'var(--text-main)',
                            margin: 0,
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }} title={job.job_title}>
                            {job.job_title}
                          </h4>
                          <div style={{
                            fontSize: '0.76rem',
                            color: 'var(--text-muted)',
                            marginTop: '2px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {job.company_name} • {job.location || 'Remote'}
                          </div>
                        </div>
                      </div>

                      {/* Status & Score */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
                        <span style={{
                          fontSize: '0.7rem',
                          fontWeight: 800,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#065f46'
                        }}>
                          ✓ Applied
                        </span>
                        {job.match_score !== null && (
                          <span style={{
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            color: 'var(--text-muted)'
                          }}>
                            {job.match_score}% Match
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Meta Row: Portal & Applied Date */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '0.72rem',
                      color: 'var(--text-secondary)',
                      paddingTop: '6px',
                      borderTop: '1px solid #f1f5f9'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          textTransform: 'uppercase',
                          fontWeight: 700,
                          fontSize: '0.64rem',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: 'rgba(16, 185, 129, 0.12)',
                          color: '#047857'
                        }}>
                          {job.portal_name}
                        </span>
                        <span style={{ color: '#047857', fontWeight: 600 }}>
                          ⚡ {formatDate(job.applied_at || job.created_at)}
                        </span>
                      </div>

                      {/* Action Links */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {onSelectJob && (
                          <button
                            type="button"
                            onClick={() => onSelectJob(job.id)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--primary)',
                              fontWeight: 700,
                              fontSize: '0.72rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <Eye size={12} />
                            Inspect ↗
                          </button>
                        )}
                        {job.job_url && (
                          <a
                            href={job.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              color: 'var(--text-muted)',
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center'
                            }}
                            title="Open posting on job portal"
                          >
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

