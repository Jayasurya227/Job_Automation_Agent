import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api';

export default function AccountsSettings({ notify }) {
  const [loading, setLoading] = useState(true);

  // Naukri session state
  const [launchingNaukriSession, setLaunchingNaukriSession] = useState(false);
  const [refreshingNaukriSession, setRefreshingNaukriSession] = useState(false);
  const [naukriSessionInfo, setNaukriSessionInfo] = useState({
    connected: false,
    status: 'unconfigured',
    message: 'Checking persistent session...',
  });

  // Indeed session state
  const [launchingIndeedSession, setLaunchingIndeedSession] = useState(false);
  const [refreshingIndeedSession, setRefreshingIndeedSession] = useState(false);
  const [indeedSessionInfo, setIndeedSessionInfo] = useState({
    connected: false,
    status: 'unconfigured',
    message: 'Checking persistent session...',
  });

  const loadSessions = async () => {
    try {
      setLoading(true);
      const [naukriData, indeedData] = await Promise.all([
        api.getNaukriSessionStatus().catch(() => null),
        api.getIndeedSessionStatus().catch(() => null),
      ]);
      if (naukriData) setNaukriSessionInfo(naukriData);
      if (indeedData) setIndeedSessionInfo(indeedData);
    } catch (err) {
      if (notify) notify('Failed to load portal session status: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const checkNaukriStatus = async (showToast = false) => {
    try {
      setRefreshingNaukriSession(true);
      const res = await api.getNaukriSessionStatus();
      setNaukriSessionInfo(res);
      if (showToast && notify) {
        if (res.connected) {
          notify('Naukri session is active and verified!', 'success');
        } else {
          notify('No active Naukri persistent session detected yet.', 'warning');
        }
      }
    } catch (err) {
      if (showToast && notify) notify('Error checking Naukri session: ' + err.message, 'error');
    } finally {
      setRefreshingNaukriSession(false);
    }
  };

  const checkIndeedStatus = async (showToast = false) => {
    try {
      setRefreshingIndeedSession(true);
      const res = await api.getIndeedSessionStatus();
      setIndeedSessionInfo(res);
      if (showToast && notify) {
        if (res.connected) {
          notify('Indeed session is active and verified!', 'success');
        } else {
          notify('No active Indeed persistent session detected yet.', 'warning');
        }
      }
    } catch (err) {
      if (showToast && notify) notify('Error checking Indeed session: ' + err.message, 'error');
    } finally {
      setRefreshingIndeedSession(false);
    }
  };


  const handleLaunchNaukriSession = async () => {
    try {
      setLaunchingNaukriSession(true);
      const res = await api.launchNaukriSession();
      if (notify) {
        notify(res.message || 'Launched Chrome window! Log into Naukri and press Enter in the terminal.', 'info');
      }
      
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        try {
          const statusRes = await api.getNaukriSessionStatus();
          setNaukriSessionInfo(statusRes);
          if (statusRes.connected || attempts >= 10) {
            clearInterval(interval);
            setLaunchingNaukriSession(false);
            if (statusRes.connected && notify) {
              notify('🎉 Naukri session successfully captured and verified!', 'success');
            }
          }
        } catch {
          if (attempts >= 10) {
            clearInterval(interval);
            setLaunchingNaukriSession(false);
          }
        }
      }, 4000);

    } catch (err) {
      setLaunchingNaukriSession(false);
      if (notify) notify('Failed to launch Naukri session: ' + err.message, 'error');
    }
  };

  const handleLaunchIndeedSession = async () => {
    try {
      setLaunchingIndeedSession(true);
      const res = await api.launchIndeedSession();
      if (notify) {
        notify(res.message || 'Launched Chrome window! Log into Indeed and press Enter in the terminal.', 'info');
      }
      
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        try {
          const statusRes = await api.getIndeedSessionStatus();
          setIndeedSessionInfo(statusRes);
          if (statusRes.connected || attempts >= 10) {
            clearInterval(interval);
            setLaunchingIndeedSession(false);
            if (statusRes.connected && notify) {
              notify('🎉 Indeed session successfully captured and verified!', 'success');
            }
          }
        } catch {
          if (attempts >= 10) {
            clearInterval(interval);
            setLaunchingIndeedSession(false);
          }
        }
      }, 4000);

    } catch (err) {
      setLaunchingIndeedSession(false);
      if (notify) notify('Failed to launch Indeed session: ' + err.message, 'error');
    }
  };


  useEffect(() => {
    loadSessions();
  }, []);

  if (loading) {
    return (
      <div className="accounts-settings-container" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        <Loader2 size={24} className="spin" style={{ margin: '0 auto 12px' }} />
        <div>Loading persistent portal sessions...</div>
      </div>
    );
  }

  return (
    <div className="accounts-settings-container">
      
      {/* Header */}
      <div className="portal-header-wrapper">
        <div className="portal-title-row">
          <h1 className="portal-page-title">
            Portal Accounts &amp; Session Manager
          </h1>
          <span className="badge badge-indigo" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
            <Shield size={11} /> 100% Local Storage
          </span>
        </div>
        <p className="portal-page-subtitle">
          Connect real Naukri, Indeed, and Instahyre accounts safely via persistent browser session cookies to bypass OTP and anti-bot blocks without storing passwords.
        </p>
      </div>

      {/* Security Banner */}
      <div className="portal-security-banner">
        <Shield size={20} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ color: 'var(--text-main)' }}>Zero-Password Persistent Sessions:</strong> No account passwords are saved or stored. Real authenticated browser profiles and cookies are kept strictly in isolated local vaults on your disk (<code>browser_session/</code>, <code>indeed_session/</code>, and <code>instahyre_session/</code>).
        </div>
      </div>

      {/* CARD 1: NAUKRI 1-CLICK SAFE LOGIN SESSION */}
      <div className="glass-panel portal-card" style={{ border: '1.8px solid #ffffff', boxShadow: 'var(--shadow-md)' }}>
        <div className="portal-card-header">
          <div className="portal-card-title-group">
            <span style={{ fontSize: '1.4rem', lineHeight: 1 }}>🇮🇳</span>
            <div className="portal-card-title-text">
              <div className="portal-card-heading-badge">
                <h2 className="portal-card-h2">
                  Naukri.com Safe 1-Click Login Session
                </h2>
                <span className="badge badge-purple" style={{ fontSize: '0.68rem', padding: '2px 8px' }}>
                  Recommended
                </span>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Persistent Chrome profile for OTP &amp; Captcha verification
              </span>
            </div>
          </div>

          <div className="portal-status-actions">
            <span className={`badge ${naukriSessionInfo.connected ? 'badge-emerald' : 'badge-amber'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              {naukriSessionInfo.connected ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
              {naukriSessionInfo.connected ? 'Session Connected' : 'Needs Login'}
            </span>
            <button
              type="button"
              onClick={() => checkNaukriStatus(true)}
              disabled={refreshingNaukriSession}
              className="btn btn-secondary"
              title="Refresh Naukri session status"
              style={{ padding: '6px 10px', fontSize: '0.78rem' }}
            >
              <RefreshCw size={13} className={refreshingNaukriSession ? 'spin' : ''} />
            </button>
          </div>
        </div>

        <div className="portal-session-banner" style={{
          background: naukriSessionInfo.connected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)',
          border: `1px solid ${naukriSessionInfo.connected ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: naukriSessionInfo.connected ? 'var(--emerald)' : 'var(--amber)' }}>
            {naukriSessionInfo.connected ? '🟢 Naukri Persistent Browser Session is Active' : '🟡 Naukri Session Not Initialized'}
          </div>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {naukriSessionInfo.connected
              ? 'Your authenticated session cookies are stored locally. The agent can auto-apply to Naukri 1-Click jobs autonomously with zero password prompts.'
              : 'Naukri requires a one-time human authentication (to solve any SMS/WhatsApp OTP). Click the button below to launch Chrome on your PC, log into your account, and save your session permanently.'}
          </p>
        </div>

        <div className="portal-actions-footer">
          <button
            type="button"
            onClick={handleLaunchNaukriSession}
            disabled={launchingNaukriSession}
            className="portal-launch-btn"
          >
            {launchingNaukriSession ? <Loader2 size={16} className="spin" /> : <ExternalLink size={16} />}
            <span>{launchingNaukriSession ? 'Waiting for Login & Confirmation...' : 'Launch One-Time Chrome Login (Naukri)'}</span>
          </button>

          <span className="portal-path-indicator">
            Path: <code>backend/data/browser_session/</code>
          </span>
        </div>
      </div>

      {/* CARD 2: INDEED 1-CLICK SAFE LOGIN SESSION */}
      <div className="glass-panel portal-card" style={{ border: '1.8px solid #ffffff', boxShadow: 'var(--shadow-md)' }}>
        <div className="portal-card-header">
          <div className="portal-card-title-group">
            <span style={{ fontSize: '1.4rem', lineHeight: 1 }}>🌐</span>
            <div className="portal-card-title-text">
              <div className="portal-card-heading-badge">
                <h2 className="portal-card-h2">
                  Indeed.com Safe 1-Click Login Session
                </h2>
                <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '2px 8px' }}>
                  Easily Apply
                </span>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Persistent Chrome profile for Indeed "Easily Apply" authentication &amp; bot protection
              </span>
            </div>
          </div>

          <div className="portal-status-actions">
            <span className={`badge ${indeedSessionInfo.connected ? 'badge-emerald' : 'badge-amber'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              {indeedSessionInfo.connected ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
              {indeedSessionInfo.connected ? 'Session Connected' : 'Needs Login'}
            </span>
            <button
              type="button"
              onClick={() => checkIndeedStatus(true)}
              disabled={refreshingIndeedSession}
              className="btn btn-secondary"
              title="Refresh Indeed session status"
              style={{ padding: '6px 10px', fontSize: '0.78rem' }}
            >
              <RefreshCw size={13} className={refreshingIndeedSession ? 'spin' : ''} />
            </button>
          </div>
        </div>

        <div className="portal-session-banner" style={{
          background: indeedSessionInfo.connected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)',
          border: `1px solid ${indeedSessionInfo.connected ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: indeedSessionInfo.connected ? 'var(--emerald)' : 'var(--amber)' }}>
            {indeedSessionInfo.connected ? '🟢 Indeed Persistent Browser Session is Active' : '🟡 Indeed Session Not Initialized'}
          </div>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {indeedSessionInfo.connected
              ? 'Your authenticated session cookies are stored locally in an isolated directory. The agent can auto-apply to Indeed "Easily Apply" jobs autonomously with zero password prompts.'
              : 'Indeed requires a one-time human authentication (email OTP or Google sign-in). Click the button below to launch Chrome on your PC, log into your account once, and save your cookies permanently.'}
          </p>
        </div>

        <div className="portal-actions-footer">
          <button
            type="button"
            onClick={handleLaunchIndeedSession}
            disabled={launchingIndeedSession}
            className="portal-launch-btn"
          >
            {launchingIndeedSession ? <Loader2 size={16} className="spin" /> : <ExternalLink size={16} />}
            <span>{launchingIndeedSession ? 'Waiting for Login & Confirmation...' : 'Launch One-Time Chrome Login (Indeed)'}</span>
          </button>

          <span className="portal-path-indicator">
            Path: <code>backend/data/indeed_session/</code>
          </span>
        </div>
      </div>

    </div>
  );
}
