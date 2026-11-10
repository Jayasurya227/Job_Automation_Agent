import React from 'react';
import { 
  Sparkles, 
  Send, 
  Compass, 
  Archive 
} from 'lucide-react';

export default function StatsBar({ metrics, backendStatus }) {
  const totalJobs = metrics?.total_jobs || 0;
  const appliedCount = metrics?.applied_count || 0;
  const readyCount = metrics?.ready_to_apply_count || 0;
  const discoveredCount = Math.max(0, totalJobs - appliedCount);
  const reserveCount = Math.max(0, totalJobs - appliedCount - readyCount);
  const avgAts = metrics?.average_match_score ? `${Math.round(metrics.average_match_score)}%` : '--';

  return (
    <div style={{ width: '100%', marginBottom: '6px' }}>
      {/* 4 Premium Glassmorphic Metric Tiles */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '14px',
        width: '100%',
      }}>
        {/* Card 1: ATS Match Rate */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--emerald)', '--stat-glow': 'rgba(16, 185, 129, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Average ATS Match
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {avgAts}
              </span>
              <span className="badge badge-emerald" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                High Tier
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Resume alignment with JD
            </span>
          </div>
          <div className="stat-icon-wrapper">
            <Sparkles size={22} color="#047857" />
          </div>
        </div>

        {/* Card 2: Discovered Jobs */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--cyan)', '--stat-glow': 'rgba(6, 182, 212, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Discovered Jobs
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0e7490', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {discoveredCount}
              </span>
              <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                ≥ 70% Match
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Total screened by agent
            </span>
          </div>
          <div className="stat-icon-wrapper">
            <Compass size={22} color="#0e7490" />
          </div>
        </div>

        {/* Card 3: Applied Jobs */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--primary)', '--stat-glow': 'rgba(99, 102, 241, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Applied Jobs
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: '#37501e', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {appliedCount}
              </span>
              <span className="badge badge-indigo" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                Max {metrics?.max_daily_apps || 7}/day
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Submitted to employers
            </span>
          </div>
          <div className="stat-icon-wrapper">
            <Send size={22} color="#4a6b28" />
          </div>
        </div>

        {/* Card 4: Reserve Pool (70-74%) */}
        <div className="stat-card" style={{ '--stat-accent': '#a855f7', '--stat-glow': 'rgba(168, 85, 247, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Reserve Pool
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: '#6b21a8', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {reserveCount}
              </span>
              <span className="badge badge-purple" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                70% – 74%
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Backup leads in Archive
            </span>
          </div>
          <div className="stat-icon-wrapper">
            <Archive size={22} color="#7e22ce" />
          </div>
        </div>
      </div>
    </div>
  );
}
