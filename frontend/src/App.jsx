import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import KanbanBoard from './components/KanbanBoard';
import ProfileEditor from './components/ProfileEditor';
import AccountsSettings from './components/AccountsSettings';
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
  Globe
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
  const [toasts, setToasts] = useState([]);

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
      // 1. Health check
      await api.checkHealth();
      setBackendStatus('online');

      // 2. Fetch jobs, metrics & profile in parallel
      const [jobsData, metricsData, profileData] = await Promise.all([
        api.getJobs(),
        api.getMetrics(),
        api.getProfile().catch(() => null),
      ]);

      setJobs(jobsData);
      setMetrics(metricsData);
      if (profileData) setProfile(profileData);
    } catch (err) {
      console.error('Data sync failed:', err);
      setBackendStatus('offline');
    } finally {
      setLoading(false);
    }
  }, []);

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


  // Filter jobs by search term and status
  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.job_title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      job.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (job.location && job.location.toLowerCase().includes(searchTerm.toLowerCase()));

    // 'All' passes through; any specific status does an exact match against backend status value
    const matchesStatus = statusFilter === 'All' || job.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Pipeline Controls Bar */}
            <div className="pipeline-controls-bar">
              {/* Search Bar */}
              <div className="controls-search-box">
                <div style={{ position: 'relative', width: '100%' }}>
                  <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    id="search-input"
                    className="form-input"
                    style={{ paddingLeft: '36px' }}
                    placeholder="Search by title, company, or location..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>

              {/* Status Filter & View Toggle */}
              <div className="controls-filter-box">
                <select
                  id="status-filter-select"
                  className="form-select"
                  style={{ width: 'auto' }}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="All">All Jobs ({jobs.length})</option>
                  <option value="Saved">Saved ({jobs.filter(j => j.status === 'Saved').length})</option>
                  <option value="Tailored">Tailored ({jobs.filter(j => j.status === 'Tailored').length})</option>
                  <option value="Ready">Ready to Apply ({jobs.filter(j => j.status === 'Ready').length})</option>
                  <option value="Applied">Applied ({jobs.filter(j => j.status === 'Applied').length})</option>
                  <option value="Interview">Interview ({jobs.filter(j => j.status === 'Interview').length})</option>
                  <option value="Offer">Offer ({jobs.filter(j => j.status === 'Offer').length})</option>
                  <option value="Rejected">Rejected ({jobs.filter(j => j.status === 'Rejected').length})</option>
                  <option value="Archived">Archived ({jobs.filter(j => j.status === 'Archived').length})</option>
                </select>
              </div>
            </div>

            {/* Board View */}
            <KanbanBoard
              jobs={filteredJobs}
              onSelectJob={(id, tab = 'overview') => {
                setSelectedJobId(id);
                setSelectedJobTab(typeof tab === 'string' ? tab : 'overview');
              }}
              onStatusChange={handleStatusChange}
              onDeleteJob={handleDeleteJob}
            />
          </div>
        )}


        {/* TAB 2: SETTINGS (PROFILE & NAUKRI ACCOUNTS UNIFIED) */}
        {activeTab === 'settings' && (
          <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Unified Settings Header & Navigation Toggle */}
            <div className="settings-header-wrapper">
              <div>
                <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
                  Settings
                </h1>
                <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
                  Manage your candidate profile, master resume, and portal & outreach accounts.
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
                  <span>Accounts & Outreach</span>
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
            ) : (
              <AccountsSettings notify={notify} />
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
        />
      )}

      {/* Floating Notifications */}
      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
