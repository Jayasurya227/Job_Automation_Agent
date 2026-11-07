import React, { useState, useEffect, useCallback, useRef } from 'react';
import Navbar from './components/Navbar';
import KanbanBoard from './components/KanbanBoard';
import ProfileEditor from './components/ProfileEditor';
import AccountsSettings from './components/AccountsSettings';
import ApplicationHistory from './components/ApplicationHistory';
import JobModal from './components/JobModal';
import Toast from './components/Toast';
import AuthPage from './components/AuthPage';
import { api } from './api';
import { 
  Search, 
  Filter, 
  AlertTriangle, 
  RefreshCw,
  User,
  Globe,
  Sparkles,
  Loader2,
  ChevronDown,
  ExternalLink,
  Clock,
  History
} from 'lucide-react';

export default function App() {
  // Always start unauthenticated so opening the localhost link opens the sign-in page first
  const [currentUser, setCurrentUser] = useState(null);

  // Clear legacy stored session from previous visits on mount
  useEffect(() => {
    try {
      localStorage.removeItem('agent_user');
      sessionStorage.removeItem('agent_user');
    } catch {
      // ignore
    }
  }, []);

  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline' | 'settings'
  const [settingsTab, setSettingsTab] = useState('profile'); // 'profile' | 'naukri'
  const [jobs, setJobs] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [profile, setProfile] = useState(null);
  const [backendStatus, setBackendStatus] = useState('online');
  const [loading, setLoading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJobTab, setSelectedJobTab] = useState('overview');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const filterDropdownRef = useRef(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [naukriSession, setNaukriSession] = useState(null);
  const [indeedSession, setIndeedSession] = useState(null);
  const [autopilotStatus, setAutopilotStatus] = useState(null);
  const [applyingJobId, setApplyingJobId] = useState(null);

  // Hourly Auto-Discovery State (9:00 AM – 9:00 PM)
  const [autoDiscoverEnabled, setAutoDiscoverEnabled] = useState(() => {
    try {
      const saved = localStorage.getItem('auto_discover_enabled');
      return saved !== null ? saved === 'true' : true;
    } catch {
      return true;
    }
  });
  const [countdownSeconds, setCountdownSeconds] = useState(3600);

  // Close custom filter dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (filterDropdownRef.current && !filterDropdownRef.current.contains(event.target)) {
        setIsFilterOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, []);

  const notify = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const handleLogin = useCallback((userData) => {
    setCurrentUser(userData);
    notify(`Welcome ${userData.firstName || 'User'}! Pipeline workspace unlocked.`, 'success');
  }, [notify]);

  const handleLogout = useCallback(() => {
    try {
      localStorage.removeItem('agent_user');
      sessionStorage.removeItem('agent_user');
    } catch (e) {
      console.error(e);
    }
    setCurrentUser(null);
    notify('Signed out from workspace.', 'info');
  }, [notify]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Health check determines true backend connectivity
      try {
        await api.checkHealth();
        setBackendStatus('online');
      } catch (healthErr) {
        console.warn('Backend health check unreachable:', healthErr);
        setBackendStatus('offline');
        return;
      }

      // 2. Fetch jobs, metrics, profile, session status & autopilot status using Promise.allSettled
      // Prevents a single dropped/delayed fetch on mobile networks from falsely marking the entire backend offline
      const [jobsRes, metricsRes, profileRes, naukriRes, indeedRes, autopilotRes] = await Promise.allSettled([
        api.getJobs(),
        api.getMetrics(),
        api.getProfile(),
        api.getNaukriSessionStatus(),
        api.getIndeedSessionStatus(),
        api.getAutopilotStatus(),
      ]);

      if (jobsRes.status === 'fulfilled' && jobsRes.value) {
        setJobs(jobsRes.value);
      }
      if (metricsRes.status === 'fulfilled' && metricsRes.value) {
        setMetrics(metricsRes.value);
      }
      if (profileRes.status === 'fulfilled' && profileRes.value) {
        setProfile(profileRes.value);
      }
      if (naukriRes.status === 'fulfilled' && naukriRes.value) {
        setNaukriSession(naukriRes.value);
      }
      if (indeedRes.status === 'fulfilled' && indeedRes.value) {
        setIndeedSession(indeedRes.value);
      }
      if (autopilotRes.status === 'fulfilled' && autopilotRes.value) {
        setAutopilotStatus(autopilotRes.value);
      }
      setBackendStatus('online');
    } catch (err) {
      console.error('Data sync failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Sync sessions & timetable status whenever returning to Pipeline tab
  useEffect(() => {
    if (activeTab === 'pipeline') {
      Promise.allSettled([
        api.getNaukriSessionStatus(),
        api.getAutopilotStatus(),
      ]).then(([naukriRes, autoRes]) => {
        if (naukriRes.status === 'fulfilled' && naukriRes.value) setNaukriSession(naukriRes.value);
        if (autoRes.status === 'fulfilled' && autoRes.value) setAutopilotStatus(autoRes.value);
      });
    }
  }, [activeTab]);

  // Periodic heartbeat tick to update timetable countdown and status
  useEffect(() => {
    const timer = setInterval(() => {
      api.getAutopilotStatus().then(res => {
        if (res) setAutopilotStatus(res);
      }).catch(() => {});
    }, 20000);
    return () => clearInterval(timer);
  }, []);

  // Dynamic Navigation Handler to redirect to Portal Accounts settings
  const handleRedirectToPortalSettings = useCallback(() => {
    setActiveTab('settings');
    setSettingsTab('naukri');
  }, []);

  // 1-Click Instant Autonomous Discovery (Bypasses popup modal, uses saved profile directly)
  const handleInstantDiscover = useCallback(async (isAutoTrigger = false) => {
    if (isDiscovering) return;

    // Reset hourly countdown timer timestamp on every run (manual or auto)
    try {
      localStorage.setItem('last_discover_timestamp', Date.now().toString());
    } catch {
      // ignore
    }
    setCountdownSeconds(3600);

    const savedRoles = profile?.preferences?.target_roles || profile?.target_roles || [];
    const rolesToSearch = savedRoles.length > 0 ? savedRoles.slice(0, 3) : ['Junior AI Engineer'];
    const savedLocs = profile?.preferences?.preferred_locations || profile?.target_locations || [];
    const locsToSearch = savedLocs.length > 0 ? savedLocs.slice(0, 2) : ['Hyderabad'];
    const freshness = profile?.preferences?.freshness_days ?? 1;
    const minScore = profile?.preferences?.min_match_score ?? 70;

    // 100% Naukri Auto-Pilot Engine
    const scheduledPortal = 'naukri';
    const scheduledPortalLabel = 'Naukri.com';

    setIsDiscovering(true);
    const rolesLabel = rolesToSearch.join(', ');
    const locsLabel = locsToSearch.join(', ');

    if (isAutoTrigger) {
      notify(`⏰ Scheduled Auto-Discovery: Agent is crawling fresh 24h jobs on ${scheduledPortalLabel} (${rolesLabel} in ${locsLabel})...`, 'info');
    } else {
      notify(`🚀 Agent launched! Crawling fresh 24h jobs on ${scheduledPortalLabel} across [${rolesLabel}] in [${locsLabel}]...`, 'info');
    }

    try {
      const result = await api.discoverJobs({
        search_terms: rolesToSearch,
        locations: locsToSearch,
        location: locsLabel,
        portals: [scheduledPortal],
        results_wanted: 8,
        freshness_days: freshness,
        min_match_score: minScore,
        max_process: 10,
      });

      await loadData();

      const savedCount = result?.new_jobs_saved ?? result?.high_matches_ready ?? 0;
      const autoApplied = result?.auto_applied_count ?? 0;
      const applyMsg = autoApplied > 0 ? ` (${autoApplied} auto-applied via 1-Click!)` : '';
      notify(`🎉 Discovery complete on ${scheduledPortalLabel} for [${rolesLabel}] in [${locsLabel}]! ${savedCount} high matches queued${applyMsg}.`, 'success');
    } catch (err) {
      console.error('Instant discovery error:', err);
      notify(`Discovery notice: ${err.message}`, 'error');
    } finally {
      setIsDiscovering(false);
    }
  }, [isDiscovering, profile, notify, loadData]);

  // Precision Hourly Auto-Discovery Timer (9:00 AM – 9:00 PM Office Hours)
  useEffect(() => {
    if (!currentUser) return;

    const tick = () => {
      const now = new Date();
      const currentHour = now.getHours();
      const isOfficeHours = currentHour >= 9 && currentHour < 21;

      if (!isOfficeHours) {
        // Outside office hours: countdown until 9:00 AM next morning
        let nextStart = new Date(now);
        if (currentHour >= 21) {
          nextStart.setDate(nextStart.getDate() + 1);
        }
        nextStart.setHours(9, 0, 0, 0);
        const diffSecs = Math.max(0, Math.floor((nextStart.getTime() - now.getTime()) / 1000));
        setCountdownSeconds(diffSecs);
        return;
      }

      // Inside Office Hours: check elapsed time since last run
      let lastRun = 0;
      try {
        lastRun = parseInt(localStorage.getItem('last_discover_timestamp') || '0', 10);
      } catch {
        lastRun = 0;
      }

      if (!lastRun) {
        lastRun = Date.now();
        try {
          localStorage.setItem('last_discover_timestamp', lastRun.toString());
        } catch {}
      }

      const elapsedSec = Math.floor((Date.now() - lastRun) / 1000);
      const remaining = Math.max(0, 3600 - elapsedSec);
      setCountdownSeconds(remaining);

      // Trigger if countdown reached 0, auto-discover is enabled, and not currently running
      if (remaining <= 0 && autoDiscoverEnabled && !isDiscovering) {
        try {
          localStorage.setItem('last_discover_timestamp', Date.now().toString());
        } catch {}
        setCountdownSeconds(3600);
        handleInstantDiscover(true);
      }
    };

    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [currentUser, autoDiscoverEnabled, isDiscovering, handleInstantDiscover]);

  useEffect(() => {
    if (!currentUser) return;
    loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [currentUser, loadData]);

  const handleStatusChange = async (jobId, newStatus) => {
    try {
      await api.updateJobStatus(jobId, newStatus);
      // Optimistic update
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: newStatus } : j))
      );
      // Reload metrics
      const newMetrics = await api.getMetrics();
      setMetrics(newMetrics);
      notify(`Job status updated to "${newStatus}"`, 'success');
    } catch (err) {
      notify('Failed to update status: ' + err.message, 'error');
    }
  };

  const handleDeleteJob = async (jobId) => {
    try {
      await api.deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
      const newMetrics = await api.getMetrics();
      setMetrics(newMetrics);
      notify('Job removed from pipeline and database', 'info');
    } catch (err) {
      notify('Failed to delete job: ' + err.message, 'error');
    }
  };

  const handle1ClickApply = async (job) => {
    if (!job || !job.id) return;
    if (applyingJobId) {
      notify('Another application is currently in progress. Please wait...', 'warning');
      return;
    }

    setApplyingJobId(job.id);
    notify(`⚡ Starting 1-Click Apply for "${job.job_title}" at ${job.company_name}...`, 'info');

    try {
      const res = await api.triggerApply(job.id, 'autonomous', job.portal_name || 'Naukri');
      
      if (res.status === 'SUBMITTED') {
        notify(`🎉 Successfully applied to "${job.job_title}" at ${job.company_name}!`, 'success');
        setJobs((prev) =>
          prev.map((j) => (j.id === job.id ? { ...j, status: 'Applied' } : j))
        );
        const newMetrics = await api.getMetrics();
        setMetrics(newMetrics);
      } else if (res.status === 'EXTERNAL_SITE') {
        notify(`⚠️ "${job.job_title}" redirects to an external company site. Skipping 1-Click apply for now.`, 'warning');
        setJobs((prev) =>
          prev.map((j) => (j.id === job.id ? { ...j, notes: 'External Company Portal: Direct application required.' } : j))
        );
      } else if (res.status === 'LOGIN_REQUIRED') {
        notify(`⚠️ Naukri session is disconnected or expired. Please re-authenticate in Settings > Portal Accounts.`, 'warning');
      } else if (res.status === 'ALREADY_APPLIED') {
        notify(`ℹ️ Already applied to "${job.job_title}" at ${job.company_name} on Naukri.`, 'info');
        setJobs((prev) =>
          prev.map((j) => (j.id === job.id ? { ...j, status: 'Applied' } : j))
        );
        const newMetrics = await api.getMetrics();
        setMetrics(newMetrics);
      } else {
        const errorMsg = res.execution_logs?.[res.execution_logs.length - 1] || res.status || 'Application not completed';
        notify(`Application notice: ${errorMsg}`, 'warning');
      }
    } catch (err) {
      console.error('1-Click Apply error:', err);
      notify(`1-Click Apply failed: ${err.message}`, 'error');
    } finally {
      setApplyingJobId(null);
    }
  };


  // Hourly Office Hours calculation and countdown formatter
  const currentHour = new Date().getHours();
  const isOfficeHours = currentHour >= 9 && currentHour < 21;

  const formatCountdown = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    if (m >= 60) {
      const h = Math.floor(m / 60);
      const remM = m % 60;
      return `${h}h ${remM}m`;
    }
    return `${m}m ${s < 10 ? '0' : ''}${s}s`;
  };

  // Filter jobs by search term and status
  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.job_title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      job.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (job.location && job.location.toLowerCase().includes(searchTerm.toLowerCase()));

    let matchesStatus = true;
    if (statusFilter === 'All') {
      matchesStatus = true;
    } else if (statusFilter === 'Ready') {
      matchesStatus = job.status === 'Ready';
    } else if (statusFilter === 'Applied') {
      matchesStatus = job.status === 'Applied';
    } else if (statusFilter === 'Archived') {
      matchesStatus = job.status === 'Archived';
    } else {
      matchesStatus = job.status === statusFilter;
    }

    return matchesSearch && matchesStatus;
  });

  const statusOptions = [
    { value: 'All', label: 'All Discovered', icon: '🌐', count: jobs.filter(j => j.status !== 'Applied').length },
    { value: 'Ready', label: 'Review (≥80%)', icon: '⭐', count: jobs.filter(j => j.status === 'Ready').length },
    { value: 'Applied', label: 'Applied', icon: '✅', count: jobs.filter(j => j.status === 'Applied').length },
    { value: 'Archived', label: 'Archive (70–79%)', icon: '📁', count: jobs.filter(j => j.status === 'Archived').length },
  ];
  const activeStatusOption = statusOptions.find(o => o.value === statusFilter) || statusOptions[0];

  // If user is not authenticated, show Amorphous Auth Gate
  if (!currentUser) {
    return (
      <>
        <AuthPage onLogin={handleLogin} />
        <Toast toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        backendStatus={backendStatus}
        onRefresh={loadData}
        loading={loading}
        user={currentUser}
        onLogout={handleLogout}
      />

      {/* Offline Alert Banner */}
      {backendStatus === 'offline' && (
        <div style={{
          background: 'rgba(244, 63, 94, 0.15)',
          borderBottom: '1px solid rgba(244, 63, 94, 0.3)',
          padding: '10px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          color: 'var(--rose-light)',
          fontSize: '0.85rem',
        }}>
          <AlertTriangle size={16} />
          <span>
            Backend engine is currently offline or unreachable at <code>http://localhost:8000</code>. Please ensure your FastAPI server is running.
          </span>
          <button 
            className="btn btn-secondary btn-sm" 
            onClick={loadData}
            style={{ padding: '3px 8px', fontSize: '0.75rem', borderColor: 'rgba(244, 63, 94, 0.4)' }}
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="main-content-layout">
        {/* TAB 1: PIPELINE BOARD */}
        {activeTab === 'pipeline' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* 1. Live Naukri Session Warning Banner (Strictly Shown ONLY on Expired or Not Connected) */}
            {(() => {
              if (naukriSession?.connected && !naukriSession?.expired) {
                return null;
              }
              const isExpired = Boolean(naukriSession?.expired);
              const title = isExpired ? 'Naukri Connection Lost (Expired)' : 'Naukri Account Not Connected';
              const desc = isExpired 
                ? `Your Naukri session has expired (${naukriSession?.age_days || 0}d old). Re-connect via Mobile OTP in Settings.`
                : 'Connect your registered mobile number via SMS OTP in Settings to start autonomous Naukri job applications.';
              const btnText = isExpired ? 'Re-connect Naukri (OTP)' : 'Connect Naukri (OTP)';

              return (
                <div className="naukri-session-warning-card">
                  <div className="session-warning-left">
                    <div className="session-warning-icon">
                      <AlertTriangle size={15} color="#b45309" />
                    </div>
                    <div className="session-warning-text">
                      <strong>{title}:</strong>{' '}
                      <span>{desc}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="session-reconnect-btn"
                    onClick={handleRedirectToPortalSettings}
                    title="Go to Settings > Portal Accounts"
                  >
                    <span>{btnText}</span>
                    <ExternalLink size={12} />
                  </button>
                </div>
              );
            })()}

            {/* 2. Sleek, Minimal Timetable Status Pill */}
            {(() => {
              const timeline = autopilotStatus?.timeline;
              if (!timeline) return null;

              const phase = timeline.phase || 'closed';
              const isWork = phase === 'work';
              const isBreak = phase === 'break';

              let pillText = '';
              let pillBadge = '';
              if (isWork) {
                pillText = `🚀 Searching Naukri (${timeline.slot_label || 'Active'})`;
                pillBadge = `Break in ${timeline.remaining_minutes || 0}m`;
              } else if (isBreak) {
                pillText = `💤 Resting Cooldown`;
                pillBadge = `Next scan in ${timeline.remaining_minutes || 0}m`;
              } else {
                pillText = `🌙 Standby (Office Hours: 9 AM – 9 PM)`;
                pillBadge = `Resumes 9:00 AM`;
              }

              return (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px',
                  padding: '4px 12px',
                  borderRadius: '20px',
                  background: isWork 
                    ? 'rgba(16, 185, 129, 0.08)' 
                    : (isBreak ? 'rgba(245, 158, 11, 0.08)' : 'rgba(255, 255, 255, 0.7)'),
                  border: `1px solid ${isWork ? 'rgba(16, 185, 129, 0.25)' : (isBreak ? 'rgba(245, 158, 11, 0.25)' : 'rgba(0, 0, 0, 0.08)')}`,
                  backdropFilter: 'blur(8px)',
                  width: 'fit-content',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: isWork ? '#065f46' : (isBreak ? '#92400e' : 'var(--text-secondary)'),
                  boxShadow: 'var(--shadow-sm)',
                  margin: '0 0 2px 0'
                }}>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <span>{pillText}</span>
                    {isWork && (
                      <span style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: '#10b981',
                        boxShadow: '0 0 6px #10b981',
                        display: 'inline-block'
                      }} />
                    )}
                  </div>
                  <span style={{
                    fontSize: '0.72rem',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: isWork ? 'rgba(16, 185, 129, 0.15)' : (isBreak ? 'rgba(245, 158, 11, 0.15)' : 'rgba(0, 0, 0, 0.05)'),
                    color: isWork ? '#047857' : (isBreak ? '#b45309' : 'var(--text-muted)'),
                    fontWeight: 700
                  }}>
                    {pillBadge}
                  </span>
                </div>
              );
            })()}

            {/* Pipeline Controls Bar */}
            <div className="pipeline-controls-bar">
              {/* Search Bar */}
              <div className="controls-search-box">
                <div style={{ position: 'relative', width: '100%' }}>
                  <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    id="search-input"
                    className="form-input search-input-styled"
                    placeholder="Search by title, company, or location..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>

              {/* Controls Actions Group */}
              <div className="controls-actions-group">
                {/* Custom Compact Glassmorphic Dropdown */}
                <div className="custom-status-dropdown-wrapper" ref={filterDropdownRef}>
                  <button
                    type="button"
                    id="status-filter-select"
                    className="custom-status-dropdown-trigger"
                    onClick={() => setIsFilterOpen(!isFilterOpen)}
                    aria-label="Filter jobs by status"
                  >
                    <span className="dropdown-trigger-content">
                      <span>{activeStatusOption.icon}</span>
                      <span>{activeStatusOption.label} ({activeStatusOption.count})</span>
                    </span>
                    <ChevronDown 
                      size={11} 
                      color="var(--text-muted)"
                      style={{
                        transform: isFilterOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease',
                        flexShrink: 0
                      }} 
                    />
                  </button>

                  {isFilterOpen && (
                    <div className="custom-status-dropdown-menu">
                      {statusOptions.map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          className={`custom-status-dropdown-item ${statusFilter === opt.value ? 'active' : ''}`}
                          onClick={() => {
                            setStatusFilter(opt.value);
                            setIsFilterOpen(false);
                          }}
                        >
                          <span className="dropdown-item-left">
                            <span className="dropdown-item-icon">{opt.icon}</span>
                            <span className="dropdown-item-label">{opt.label}</span>
                          </span>
                          <span className="dropdown-item-count">{opt.count}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Hourly Auto-Discovery Live Status & Quick Pause/Resume Pill */}
                <button
                  type="button"
                  id="auto-discover-status-pill"
                  className={`auto-discover-status-pill ${
                    isDiscovering
                      ? 'state-discovering'
                      : !autoDiscoverEnabled
                      ? 'state-paused'
                      : isOfficeHours
                      ? 'state-active'
                      : 'state-standby'
                  }`}
                  onClick={() => {
                    const nextVal = !autoDiscoverEnabled;
                    setAutoDiscoverEnabled(nextVal);
                    try { localStorage.setItem('auto_discover_enabled', nextVal.toString()); } catch {}
                    notify(nextVal ? '⏰ Hourly Auto-Discovery enabled (9:00 AM – 9:00 PM)' : '⏸️ Hourly Auto-Discovery paused', 'info');
                  }}
                  title={autoDiscoverEnabled ? "Auto-Discovery is active every 1 hour (9 AM - 9 PM). Click to pause." : "Auto-Discovery is paused. Click to resume."}
                >
                  <div className="pill-content-left">
                    <Clock size={13} className={isDiscovering ? 'spin' : ''} />
                    <span className="pill-title">
                      {isDiscovering
                        ? 'Auto-Crawl:'
                        : !autoDiscoverEnabled
                        ? 'Auto-Discovery:'
                        : isOfficeHours
                        ? 'Next Auto:'
                        : 'Standby:'}
                    </span>
                  </div>
                  <div className="pill-content-right">
                    <span className="pill-timer-badge">
                      {isDiscovering ? (
                        'Searching...'
                      ) : !autoDiscoverEnabled ? (
                        'PAUSED'
                      ) : isOfficeHours ? (
                        formatCountdown(countdownSeconds)
                      ) : (
                        `Resumes in ${formatCountdown(countdownSeconds)}`
                      )}
                    </span>
                    <span className="pill-status-tag">
                      {autoDiscoverEnabled ? (isOfficeHours ? 'ON' : 'SLEEP') : 'OFF'}
                    </span>
                  </div>
                </button>

                {/* 1-Click Instant Autonomous Discovery Trigger */}
                <button
                  id="trigger-discovery-btn"
                  className="btn btn-primary controls-discover-btn"
                  onClick={() => handleInstantDiscover(false)}
                  disabled={isDiscovering}
                  style={{
                    opacity: isDiscovering ? 0.85 : 1,
                    cursor: isDiscovering ? 'wait' : 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                  title="Discover fresh 24h jobs now, or wait for the hourly auto-tap"
                >
                  {isDiscovering ? (
                    <>
                      <Loader2 size={13} className="spin" />
                      <span>Searching...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={13} />
                      <span>Discover Jobs</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Board View */}
            <KanbanBoard
              jobs={filteredJobs}
              statusFilter={statusFilter}
              onSelectJob={(id, tab = 'overview') => {
                setSelectedJobId(id);
                setSelectedJobTab(typeof tab === 'string' ? tab : 'overview');
              }}
              onStatusChange={handleStatusChange}
              onDeleteJob={handleDeleteJob}
              onApplyJob={handle1ClickApply}
              applyingJobId={applyingJobId}
            />
          </div>
        )}


        {/* TAB 2: SETTINGS (PROFILE & NAUKRI ACCOUNTS UNIFIED) */}
        {activeTab === 'settings' && (
          <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Unified Settings Header & Navigation Toggle */}
            <div className="settings-header-wrapper">
              <div className="settings-title-section">
                <div className="settings-title-row">
                  <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
                    Settings
                  </h1>
                  {/* Mobile-only Application History pill button beside Settings */}
                  <button
                    type="button"
                    id="settings-tab-history-mobile-btn"
                    className="settings-history-mobile-btn"
                    onClick={() => setSettingsTab('history')}
                    style={{
                      background: settingsTab === 'history' ? 'var(--primary)' : 'rgba(255, 255, 255, 0.85)',
                      color: settingsTab === 'history' ? '#ffffff' : 'var(--text-main)',
                      border: settingsTab === 'history' ? '1px solid var(--primary)' : '1px solid var(--border-card)',
                    }}
                  >
                    <History 
                      size={18} 
                      strokeWidth={2.4}
                      className="settings-history-mobile-icon"
                      style={{ color: '#ea580c', stroke: '#ea580c' }}
                    />
                    <span>Application History</span>
                  </button>
                </div>
                <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                  Manage your candidate profile, master resume, and job portal credentials.
                </p>
              </div>

              {/* Sub-navigation buttons */}
              <div className="settings-subtabs-group">
                <button
                  id="settings-tab-profile-btn"
                  className="settings-subtab-btn"
                  onClick={() => setSettingsTab('profile')}
                  style={{
                    background: settingsTab === 'profile' ? 'var(--primary)' : 'transparent',
                    color: settingsTab === 'profile' ? '#ffffff' : 'var(--text-secondary)',
                  }}
                >
                  <User size={15} />
                  <span>Profile & Resume</span>
                </button>

                <button
                  id="settings-tab-naukri-btn"
                  className="settings-subtab-btn"
                  onClick={() => setSettingsTab('naukri')}
                  style={{
                    background: settingsTab === 'naukri' ? 'var(--primary)' : 'transparent',
                    color: settingsTab === 'naukri' ? '#ffffff' : 'var(--text-secondary)',
                  }}
                >
                  <Globe size={15} />
                  <span>Portal Accounts</span>
                </button>

                {/* Laptop-only 3rd tab in the unified group */}
                <button
                  id="settings-tab-history-btn"
                  className="settings-subtab-btn settings-subtab-history-desktop"
                  onClick={() => setSettingsTab('history')}
                  style={{
                    background: settingsTab === 'history' ? 'var(--primary)' : 'transparent',
                    color: settingsTab === 'history' ? '#ffffff' : 'var(--text-secondary)',
                  }}
                >
                  <History size={15} />
                  <span>Application History</span>
                </button>
              </div>
            </div>

            {/* Sub-view content */}
            {settingsTab === 'profile' ? (
              <ProfileEditor
                inline={true}
                notify={notify}
                onProfileUpdated={(updated) => setProfile(updated)}
              />
            ) : settingsTab === 'naukri' ? (
              <AccountsSettings notify={notify} />
            ) : (
              <ApplicationHistory
                notify={notify}
                onSelectJob={(jobId) => {
                  setSelectedJobId(jobId);
                  setSelectedJobTab('analysis');
                }}
              />
            )}
          </div>
        )}
      </main>

      {/* Detailed Inspection Modal */}
      {selectedJobId && (
        <JobModal
          jobId={selectedJobId}
          initialTab={selectedJobTab}
          onClose={() => setSelectedJobId(null)}
          onStatusChange={handleStatusChange}
          onDelete={handleDeleteJob}
          notify={notify}
          onApply={handle1ClickApply}
          isApplying={applyingJobId === selectedJobId}
        />
      )}

      {/* Floating Notifications */}
      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
