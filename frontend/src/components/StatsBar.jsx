import React from 'react';
import { 
  Sparkles, 
  Send, 
  Compass, 
  Bot, 
  Zap, 
  CheckCircle2, 
  ArrowUpRight,
  ShieldCheck,
  Cpu
} from 'lucide-react';

export default function StatsBar({ metrics, backendStatus, profile }) {
  const totalJobs = metrics?.total_jobs || 0;
  const appliedCount = metrics?.applied_count || 0;
  const discoveredCount = Math.max(0, totalJobs - appliedCount);
  const avgAts = metrics?.average_match_score ? `${Math.round(metrics.average_match_score)}%` : '--';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '8px' }}>
      {/* Live AI Status & Intelligence Ticker */}
      <div className="ai-activity-banner">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '9999px',
            padding: '3px 10px',
          }}>
            <span className="pulse-dot" />
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--emerald-light)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Autonomous AI Active
            </span>
          </div>

          <span className="ai-ticker-text">
            <Cpu size={14} color="var(--cyan)" />
            <span>Target Portal: <strong style={{ color: 'var(--text-main)' }}>Naukri.com</strong></span>
            <span style={{ opacity: 0.4 }}>•</span>
            <span>Profile: <strong style={{ color: 'var(--text-main)' }}>{profile?.name || 'Resume Loaded'}</strong></span>
            <span style={{ opacity: 0.4 }}>•</span>
            <span>Role: <strong style={{ color: 'var(--text-main)' }}>{profile?.target_roles?.[0] || 'Junior AI Engineer'}</strong></span>
          </span>
        </div>
      </div>

      {/* 4 Premium Glassmorphic Metric Tiles */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '14px',
        width: '100%',
      }}>
        {/* Card 1: ATS Match Rate */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--emerald)', '--stat-glow': 'rgba(16, 185, 129, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
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
          <div className="stat-icon-wrapper" style={{ background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
            <Sparkles size={22} color="var(--emerald-light)" />
          </div>
        </div>

        {/* Card 2: Discovered Jobs */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--cyan)', '--stat-glow': 'rgba(6, 182, 212, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Discovered Jobs
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--cyan-light)', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {discoveredCount}
              </span>
              <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                Discovered
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Ready for autonomous apply
            </span>
          </div>
          <div className="stat-icon-wrapper" style={{ background: 'rgba(6, 182, 212, 0.12)', border: '1px solid rgba(6, 182, 212, 0.25)' }}>
            <Compass size={22} color="var(--cyan-light)" />
          </div>
        </div>

        {/* Card 3: Applied Jobs */}
        <div className="stat-card" style={{ '--stat-accent': 'var(--primary)', '--stat-glow': 'rgba(99, 102, 241, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Applied Jobs
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--primary-light)', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {appliedCount}
              </span>
              <span className="badge badge-indigo" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                Applied
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Submitted to employers
            </span>
          </div>
          <div className="stat-icon-wrapper" style={{ background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.25)' }}>
            <Send size={22} color="var(--primary-light)" />
          </div>
        </div>

        {/* Card 4: Autonomous Engine Status */}
        <div className="stat-card" style={{ '--stat-accent': '#a855f7', '--stat-glow': 'rgba(168, 85, 247, 0.2)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Agent Engine
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, color: '#c084fc', letterSpacing: '-0.03em', fontFamily: 'var(--font-mono)' }}>
                {backendStatus === 'online' ? '100% Ready' : 'Offline'}
              </span>
              <span className="badge badge-purple" style={{ fontSize: '0.68rem', padding: '1px 6px' }}>
                Playwright AI
              </span>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              Real-time browser automation
            </span>
          </div>
          <div className="stat-icon-wrapper" style={{ background: 'rgba(168, 85, 247, 0.12)', border: '1px solid rgba(168, 85, 247, 0.25)' }}>
            <Bot size={22} color="#c084fc" />
          </div>
        </div>
      </div>
    </div>
  );
}
