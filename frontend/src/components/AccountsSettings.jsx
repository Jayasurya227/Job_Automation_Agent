import React, { useState, useEffect } from 'react';
import { 
  Globe, 
  Shield, 
  Eye, 
  EyeOff, 
  Save, 
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Key
} from 'lucide-react';
import { api } from '../api';

export default function AccountsSettings({ notify }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [launchingSession, setLaunchingSession] = useState(false);
  const [refreshingSession, setRefreshingSession] = useState(false);

  const [sessionInfo, setSessionInfo] = useState({
    connected: false,
    status: 'unconfigured',
    message: 'Checking persistent session...',
  });

  const [portals, setPortals] = useState({
    naukri: { username: '', password: '', status: 'unconfigured', has_password: false }
  });

  const loadSettingsAndSession = async () => {
    try {
      setLoading(true);
      const [settingsData, sessionData] = await Promise.allSettled([
        api.getSettings(),
        api.getNaukriSessionStatus()
      ]);

      if (settingsData.status === 'fulfilled' && settingsData.value?.portals) {
        setPortals({
          naukri: {
            username: settingsData.value.portals.naukri?.username || '',
            password: settingsData.value.portals.naukri?.password || '',
            status: settingsData.value.portals.naukri?.status || 'unconfigured',
            has_password: Boolean(settingsData.value.portals.naukri?.has_password)
          }
        });
      }

      if (sessionData.status === 'fulfilled' && sessionData.value) {
        setSessionInfo(sessionData.value);
      }
    } catch (err) {
      if (notify) notify('Failed to load account settings: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const checkSessionStatus = async (showToast = false) => {
    try {
      setRefreshingSession(true);
      const res = await api.getNaukriSessionStatus();
      setSessionInfo(res);
      if (showToast && notify) {
        if (res.connected) {
          notify('Naukri session is active and ready!', 'success');
        } else {
          notify('No active persistent session detected yet.', 'warning');
        }
      }
    } catch (err) {
      if (showToast && notify) notify('Error checking session: ' + err.message, 'error');
    } finally {
      setRefreshingSession(false);
    }
  };

  const handleLaunchSession = async () => {
    try {
      setLaunchingSession(true);
      const res = await api.launchNaukriSession();
      if (notify) {
        notify(res.message || 'Launched Chrome window! Log into Naukri and press Enter in the terminal.', 'info');
      }
      
      // Poll session status every 4 seconds for 40 seconds
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        try {
          const statusRes = await api.getNaukriSessionStatus();
          setSessionInfo(statusRes);
          if (statusRes.connected || attempts >= 10) {
            clearInterval(interval);
            setLaunchingSession(false);
            if (statusRes.connected && notify) {
              notify('🎉 Naukri session successfully captured and verified!', 'success');
            }
          }
        } catch {
          if (attempts >= 10) {
            clearInterval(interval);
            setLaunchingSession(false);
          }
        }
      }, 4000);

    } catch (err) {
      setLaunchingSession(false);
      if (notify) notify('Failed to launch login session: ' + err.message, 'error');
    }
  };

  useEffect(() => {
    loadSettingsAndSession();
  }, []);

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    try {
      setSaving(true);
      const payload = {
        portals: {
          naukri: { username: portals.naukri.username, password: portals.naukri.password }
        }
      };

      const res = await api.updateSettings(payload);
      if (notify) notify('Portal credentials saved securely!', 'success');
      
      if (res.settings && res.settings.portals) {
        setPortals(prev => ({
          ...prev,
          naukri: {
            ...prev.naukri,
            password: res.settings.portals.naukri?.password || '',
            status: res.settings.portals.naukri?.status || 'unconfigured',
            has_password: Boolean(res.settings.portals.naukri?.has_password)
          }
        }));
      }
    } catch (err) {
      if (notify) notify('Error saving credentials: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="accounts-settings-container" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        <Loader2 size={24} className="spin" style={{ margin: '0 auto 12px' }} />
        <div>Loading credentials &amp; session status...</div>
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
          Connect real Naukri accounts safely via persistent browser session cookies to bypass OTP and anti-bot blocks.
        </p>
      </div>

      {/* Security Banner */}
      <div className="portal-security-banner">
        <Shield size={20} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ color: 'var(--text-main)' }}>Zero Risk Persistent Session:</strong> We never submit your raw credentials via automated headless bots. Real browser profiles are stored strictly on your local disk at <code>backend/data/browser_session/</code>.
        </div>
      </div>

      {/* CARD 1: RECOMMENDED - ONE-CLICK SAFE BROWSER SESSION LOGIN */}
      <div className="glass-panel portal-card" style={{ border: '1px solid rgba(99, 102, 241, 0.35)', background: 'linear-gradient(180deg, rgba(99, 102, 241, 0.04) 0%, rgba(15, 23, 42, 0.02) 100%)' }}>
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
            <span className={`badge ${sessionInfo.connected ? 'badge-emerald' : 'badge-amber'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              {sessionInfo.connected ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
              {sessionInfo.connected ? 'Session Connected' : 'Needs Login'}
            </span>
            <button
              type="button"
              onClick={() => checkSessionStatus(true)}
              disabled={refreshingSession}
              className="btn btn-secondary"
              title="Refresh session status"
              style={{ padding: '6px 10px', fontSize: '0.78rem' }}
            >
              <RefreshCw size={13} className={refreshingSession ? 'spin' : ''} />
            </button>
          </div>
        </div>

        <div className="portal-session-banner" style={{
          background: sessionInfo.connected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)',
          border: `1px solid ${sessionInfo.connected ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: sessionInfo.connected ? 'var(--emerald)' : 'var(--amber)' }}>
            {sessionInfo.connected ? '🟢 Naukri Persistent Browser Session is Active' : '🟡 Session Not Initialized'}
          </div>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {sessionInfo.connected
              ? 'Your authenticated session cookies are stored locally. The agent can auto-apply to Naukri 1-Click jobs autonomously with zero password prompts.'
              : 'Naukri requires a one-time human authentication (to solve any SMS/WhatsApp OTP). Click the button below to launch Chrome on your PC, log into your account, and save your session permanently.'}
          </p>
        </div>

        <div className="portal-actions-footer">
          <button
            type="button"
            onClick={handleLaunchSession}
            disabled={launchingSession}
            className="portal-launch-btn"
          >
            {launchingSession ? <Loader2 size={16} className="spin" /> : <ExternalLink size={16} />}
            <span>{launchingSession ? 'Waiting for Login & Confirmation...' : 'Launch One-Time Chrome Login (OTP / CAPTCHA)'}</span>
          </button>

          <span className="portal-path-indicator">
            Path: <code>backend/data/browser_session/</code>
          </span>
        </div>
      </div>

      {/* CARD 2: OPTIONAL BACKUP CREDENTIALS */}
      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="glass-panel portal-card">
          <div className="portal-card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Key size={18} color="var(--primary-light)" />
              <h2 className="portal-card-h2">
                Backup Account Credentials (Optional)
              </h2>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Used for pre-filling login forms
            </span>
          </div>

          <div className="portal-credentials-box">
            <div>
              <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '5px' }}>
                Naukri Registered Email / Username
              </label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. your_naukri_id@email.com"
                value={portals.naukri.username}
                onChange={(e) => setPortals({
                  ...portals,
                  naukri: { ...portals.naukri, username: e.target.value }
                })}
                style={{ width: '100%', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '5px' }}>
                Naukri Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input-field"
                  placeholder="Enter account password"
                  value={portals.naukri.password}
                  onChange={(e) => setPortals({
                    ...portals,
                    naukri: { ...portals.naukri, password: e.target.value }
                  })}
                  style={{ width: '100%', fontSize: '0.85rem', paddingRight: '36px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Global Save Button */}
        <div className="portal-save-row">
          <button
            type="submit"
            disabled={saving}
            className="btn btn-secondary"
            style={{ fontSize: '0.88rem', padding: '10px 24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            <span>{saving ? 'Saving...' : 'Save Backup Credentials'}</span>
          </button>
        </div>

      </form>
    </div>
  );
}
