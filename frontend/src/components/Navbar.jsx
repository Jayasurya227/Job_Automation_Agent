import React from 'react';
import { 
  Bot, 
  Layers, 
  Settings, 
  RefreshCw,
  LogOut,
  UserCheck
} from 'lucide-react';

export default function Navbar({ 
  activeTab, 
  setActiveTab, 
  backendStatus, 
  onRefresh, 
  loading,
  user,
  onLogout
}) {
  const userDisplayName = user?.fullName || (user?.firstName ? `${user.firstName} ${user.lastName || ''}`.trim() : 'User');
  const userInitials = (user?.firstName ? user.firstName[0] : 'U') + (user?.lastName ? user.lastName[0] : '');

  return (
    <header className="navbar-header">
      <div className="navbar-container" style={{
        maxWidth: '1440px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        boxSizing: 'border-box',
        width: '100%',
      }}>
        {/* Brand & System Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(99, 102, 241, 0.4)',
            flexShrink: 0
          }}>
            <Bot size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span className="navbar-brand-title" style={{
                fontSize: '1.05rem',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                background: 'linear-gradient(90deg, #0f172a 0%, #334155 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                Autonomous Job Agent
              </span>
              <div 
                className={`badge ${backendStatus === 'online' ? 'badge-emerald' : 'badge-rose'}`}
                style={{ fontSize: '0.68rem', padding: '2px 7px' }}
                title={backendStatus === 'online' ? 'FastAPI & SQLite Connected' : 'Connecting to Backend...'}
              >
                <span className={backendStatus === 'online' ? 'pulse-dot' : ''} style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor: backendStatus === 'online' ? '#10b981' : '#f43f5e'
                }} />
                {backendStatus === 'online' ? 'Online' : 'Offline'}
              </div>
            </div>
            <div className="navbar-brand-subtitle" style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              AI Career Command Center • 100% Autonomous Pipeline
            </div>
          </div>
        </div>

        {/* Tab Controls, User Session & Refresh */}
        <div className="navbar-actions-row">
          <div className="navbar-tabs-group" style={{
            display: 'flex',
            alignItems: 'center',
            background: 'rgba(15, 23, 42, 0.05)',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
          }}>
            <button
              id="tab-btn-pipeline"
              className="navbar-tab-btn"
              onClick={() => setActiveTab('pipeline')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '8px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: activeTab === 'pipeline' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'pipeline' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s ease',
              }}
            >
              <Layers size={16} />
              Pipeline
            </button>

            <button
              id="tab-btn-settings"
              className="navbar-tab-btn"
              onClick={() => setActiveTab('settings')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '8px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: activeTab === 'settings' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'settings' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s ease',
              }}
            >
              <Settings size={16} />
              Settings
            </button>
          </div>

          <button
            id="refresh-btn"
            className="btn btn-secondary btn-sm"
            onClick={onRefresh}
            disabled={loading}
            title="Refresh data"
            style={{ padding: '8px', flexShrink: 0 }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>

          {/* User Session Badge & Logout */}
          {user && (
            <div className="navbar-user-badge" id="navbar-user-profile-badge">
              <div className="navbar-user-avatar">
                {userInitials.toUpperCase()}
              </div>
              <span className="navbar-user-name" title={userDisplayName}>
                {user.firstName || 'User'}
              </span>
              {onLogout && (
                <button
                  id="navbar-logout-btn"
                  className="navbar-logout-btn"
                  onClick={onLogout}
                  title="Sign out / Switch user"
                  aria-label="Sign out"
                >
                  <LogOut size={14} />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
