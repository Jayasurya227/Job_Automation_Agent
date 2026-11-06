import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Smartphone,
  Laptop,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  KeyRound,
  RotateCcw,
} from 'lucide-react';
import { api } from '../api';

export default function AccountsSettings({ notify }) {
  const [loading, setLoading] = useState(true);

  // Dual-mode selection for Naukri
  const [naukriMode, setNaukriMode] = useState('mobile'); // 'mobile' | 'laptop'
  const [mobileLoginType, setMobileLoginType] = useState('password'); // 'password' | 'otp'
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isConnectingMobile, setIsConnectingMobile] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);

  // Dual-mode selection for Indeed (Step 5)
  const [indeedMode, setIndeedMode] = useState('mobile'); // 'mobile' | 'laptop'
  const [indeedLoginType, setIndeedLoginType] = useState('code'); // 'code' | 'password'
  const [indeedIdentifier, setIndeedIdentifier] = useState('');
  const [indeedPassword, setIndeedPassword] = useState('');
  const [showIndeedPassword, setShowIndeedPassword] = useState(false);
  const [isConnectingIndeedMobile, setIsConnectingIndeedMobile] = useState(false);
  const [isIndeedReconnecting, setIsIndeedReconnecting] = useState(false);

  // OTP Modal State (Unified for Naukri & Indeed)
  const [activePortal, setActivePortal] = useState('naukri'); // 'naukri' | 'indeed'
  const [otpModalOpen, setOtpModalOpen] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [otpValue, setOtpValue] = useState('');
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [otpError, setOtpError] = useState('');

  // Laptop Naukri session state
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

  // Laptop Chrome launcher for Naukri
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

  // Laptop Chrome launcher for Indeed
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

  // Mobile Connect Handler for Naukri
  const handleMobileConnect = async (e) => {
    if (e) e.preventDefault();
    if (!identifier.trim()) {
      if (notify) notify('Please enter your Naukri email or 10-digit mobile number.', 'warning');
      return;
    }
    if (mobileLoginType === 'password' && !password.trim()) {
      if (notify) notify('Please enter your account password.', 'warning');
      return;
    }

    try {
      setIsConnectingMobile(true);
      setActivePortal('naukri');
      const res = await api.connectNaukriMobile({
        identifier: identifier.trim(),
        password: mobileLoginType === 'password' ? password : null,
        use_otp: mobileLoginType === 'otp',
      });

      if (res.status === 'OTP_REQUIRED') {
        setActiveSessionId(res.session_id);
        setActivePortal('naukri');
        setOtpModalOpen(true);
        setOtpValue('');
        setOtpError('');
        if (notify) notify(res.message || 'Verification OTP sent to your phone!', 'info');
      } else if (res.status === 'SUCCESS') {
        if (notify) notify(res.message || '🎉 Naukri account connected successfully!', 'success');
        setIsReconnecting(false);
        checkNaukriStatus(false);
      } else {
        if (notify) notify(res.message || 'Failed to connect. Please verify your credentials.', 'error');
      }
    } catch (err) {
      if (notify) notify('Connection error: ' + err.message, 'error');
    } finally {
      setIsConnectingMobile(false);
    }
  };

  // Mobile Connect Handler for Indeed (Step 5)
  const handleIndeedMobileConnect = async (e) => {
    if (e) e.preventDefault();
    if (!indeedIdentifier.trim()) {
      if (notify) notify('Please enter your Indeed email or phone number.', 'warning');
      return;
    }
    if (indeedLoginType === 'password' && !indeedPassword.trim()) {
      if (notify) notify('Please enter your Indeed password.', 'warning');
      return;
    }

    try {
      setIsConnectingIndeedMobile(true);
      setActivePortal('indeed');
      const res = await api.connectIndeedMobile({
        identifier: indeedIdentifier.trim(),
        password: indeedLoginType === 'password' ? indeedPassword : null,
        use_code: indeedLoginType === 'code',
      });

      if (res.status === 'OTP_REQUIRED') {
        setActiveSessionId(res.session_id);
        setActivePortal('indeed');
        setOtpModalOpen(true);
        setOtpValue('');
        setOtpError('');
        if (notify) notify(res.message || 'Verification code sent to your email or phone!', 'info');
      } else if (res.status === 'SUCCESS') {
        if (notify) notify(res.message || '🎉 Indeed account connected successfully!', 'success');
        setIsIndeedReconnecting(false);
        checkIndeedStatus(false);
      } else {
        if (notify) notify(res.message || 'Failed to connect Indeed. Please verify your credentials.', 'error');
      }
    } catch (err) {
      if (notify) notify('Indeed connection error: ' + err.message, 'error');
    } finally {
      setIsConnectingIndeedMobile(false);
    }
  };

  // Unified Mobile OTP / Verification Code Handler
  const handleVerifyOtp = async (e) => {
    if (e) e.preventDefault();
    if (!otpValue.trim() || otpValue.trim().length < 4) {
      setOtpError('Please enter a valid verification code.');
      return;
    }

    try {
      setIsVerifyingOtp(true);
      setOtpError('');
      let res;
      if (activePortal === 'indeed') {
        res = await api.verifyIndeedMobileOtp({
          session_id: activeSessionId,
          code: otpValue.trim(),
        });
      } else {
        res = await api.verifyNaukriMobileOtp({
          session_id: activeSessionId,
          otp: otpValue.trim(),
        });
      }

      if (res.status === 'SUCCESS') {
        const portalLabel = activePortal === 'indeed' ? 'Indeed' : 'Naukri';
        if (notify) notify(res.message || `🎉 ${portalLabel} session successfully verified!`, 'success');
        setOtpModalOpen(false);
        setActiveSessionId(null);
        setOtpValue('');
        if (activePortal === 'indeed') {
          setIsIndeedReconnecting(false);
          checkIndeedStatus(true);
        } else {
          setIsReconnecting(false);
          checkNaukriStatus(true);
        }
      } else {
        setOtpError(res.message || 'Verification failed. Please re-enter the code.');
        if (notify) notify(res.message || 'Invalid verification code.', 'error');
      }
    } catch (err) {
      setOtpError(err.message || 'Failed to verify code.');
      if (notify) notify('Verification error: ' + err.message, 'error');
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  // Cancel Mobile Session
  const handleCancelMobileSession = async () => {
    if (activeSessionId) {
      try {
        if (activePortal === 'indeed') {
          await api.cancelIndeedMobileSession(activeSessionId);
        } else {
          await api.cancelNaukriMobileSession(activeSessionId);
        }
      } catch {
        // ignore
      }
    }
    setActiveSessionId(null);
    setOtpModalOpen(false);
    setOtpValue('');
    setOtpError('');
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
          Connect real Naukri, Indeed, and job portal accounts safely via persistent browser session cookies to bypass OTP and anti-bot blocks without storing passwords.
        </p>
      </div>

      {/* Security Banner */}
      <div className="portal-security-banner">
        <Shield size={20} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ color: 'var(--text-main)' }}>Zero-Password Persistent Sessions:</strong> Passwords are never permanently stored. Real authenticated browser profiles and cookies are kept strictly in isolated local vaults on your disk (<code>browser_session/</code> and <code>indeed_session/</code>).
        </div>
      </div>

      {/* CARD 1: NAUKRI 1-CLICK SAFE LOGIN SESSION (DUAL-MODE) */}
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

        {/* DUAL-MODE SELECTOR TOGGLE BAR */}
        <div className="portal-mode-toggle-bar">
          <button
            type="button"
            className={`portal-mode-pill ${naukriMode === 'mobile' ? 'active' : ''}`}
            onClick={() => { setNaukriMode('mobile'); setIsReconnecting(false); }}
          >
            <Smartphone size={15} />
            <span>Mobile Login (OTP)</span>
            <span className="portal-pill-badge">Direct on Phone</span>
          </button>
          <button
            type="button"
            className={`portal-mode-pill ${naukriMode === 'laptop' ? 'active' : ''}`}
            onClick={() => setNaukriMode('laptop')}
          >
            <Laptop size={15} />
            <span>Laptop Browser</span>
          </button>
        </div>

        {/* MODE 1: MOBILE LOGIN (OTP) */}
        {naukriMode === 'mobile' && (
          <div>
            {/* If Connected and NOT re-connecting: show clean active banner */}
            {naukriSessionInfo.connected && !isReconnecting ? (
              <div>
                <div className="portal-session-banner" style={{
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--emerald)' }}>
                    🟢 Naukri Persistent Browser Session is Active
                  </div>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Your authenticated session cookies are active. The agent can auto-apply to Naukri 1-Click jobs autonomously with zero password prompts.
                  </p>
                </div>

                <div className="portal-actions-footer">
                  <button
                    type="button"
                    onClick={() => setIsReconnecting(true)}
                    className="portal-reconnect-btn"
                  >
                    <RotateCcw size={14} />
                    <span>Re-connect / Refresh Mobile Session</span>
                  </button>

                  <span className="portal-path-indicator">
                    Vault: <code>backend/data/browser_session/</code>
                  </span>
                </div>
              </div>
            ) : (
              /* Mobile Credentials & OTP Form */
              <form onSubmit={handleMobileConnect} className="portal-mobile-form">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    {isReconnecting ? '🔄 Re-connect Naukri Account' : '📱 Connect Naukri via Mobile'}
                  </div>
                  {isReconnecting && (
                    <button
                      type="button"
                      onClick={() => setIsReconnecting(false)}
                      style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: '0.75rem', cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  )}
                </div>

                {/* Sub-mode selector: Password vs Direct OTP */}
                <div className="portal-type-toggle">
                  <button
                    type="button"
                    className={`portal-type-btn ${mobileLoginType === 'password' ? 'active' : ''}`}
                    onClick={() => setMobileLoginType('password')}
                  >
                    <KeyRound size={13} />
                    <span>Email &amp; Password</span>
                  </button>
                  <button
                    type="button"
                    className={`portal-type-btn ${mobileLoginType === 'otp' ? 'active' : ''}`}
                    onClick={() => setMobileLoginType('otp')}
                  >
                    <Smartphone size={13} />
                    <span>Direct Mobile OTP</span>
                  </button>
                </div>

                {/* Field 1: Email or Mobile */}
                <div className="portal-form-field">
                  <label className="portal-field-label">
                    <span>{mobileLoginType === 'password' ? 'Naukri Email or Mobile Number' : 'Registered 10-Digit Mobile Number'}</span>
                  </label>
                  <div className="portal-input-container">
                    {mobileLoginType === 'password' ? (
                      <Mail size={16} className="portal-input-icon" />
                    ) : (
                      <Smartphone size={16} className="portal-input-icon" />
                    )}
                    <input
                      type={mobileLoginType === 'otp' ? 'tel' : 'text'}
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder={mobileLoginType === 'password' ? 'e.g. name@gmail.com or 9876543210' : 'e.g. 9876543210'}
                      className="portal-text-input"
                      required
                      autoComplete="username"
                    />
                  </div>
                </div>

                {/* Field 2: Password (Only for password flow) */}
                {mobileLoginType === 'password' && (
                  <div className="portal-form-field">
                    <label className="portal-field-label">
                      <span>Naukri Account Password</span>
                    </label>
                    <div className="portal-input-container">
                      <Lock size={16} className="portal-input-icon" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="portal-text-input"
                        required
                        autoComplete="current-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="portal-password-toggle"
                        title={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>
                )}

                <div className="portal-form-note">
                  <ShieldCheck size={14} color="#ea580c" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>
                    <strong>Zero-Password Storage:</strong> Credentials are used exclusively for one-time headless session verification and are never stored on disk.
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={isConnectingMobile}
                  className="portal-launch-btn"
                  style={{ width: '100%', marginTop: '4px' }}
                >
                  {isConnectingMobile ? <Loader2 size={16} className="spin" /> : <Smartphone size={16} />}
                  <span>{isConnectingMobile ? 'Connecting to Naukri... Please wait' : 'Connect Naukri via OTP'}</span>
                </button>
              </form>
            )}
          </div>
        )}

        {/* MODE 2: LAPTOP BROWSER LOGIN (EXISTING INTACT FLOW) */}
        {naukriMode === 'laptop' && (
          <div>
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
        )}
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

        {/* DUAL-MODE SELECTOR TOGGLE BAR FOR INDEED */}
        <div className="portal-mode-toggle-bar">
          <button
            type="button"
            className={`portal-mode-pill ${indeedMode === 'mobile' ? 'active' : ''}`}
            onClick={() => { setIndeedMode('mobile'); setIsIndeedReconnecting(false); }}
          >
            <Smartphone size={15} />
            <span>Mobile Login (OTP / Code)</span>
            <span className="portal-pill-badge">Direct on Phone</span>
          </button>
          <button
            type="button"
            className={`portal-mode-pill ${indeedMode === 'laptop' ? 'active' : ''}`}
            onClick={() => setIndeedMode('laptop')}
          >
            <Laptop size={15} />
            <span>Laptop Browser</span>
          </button>
        </div>

        {/* MODE 1: INDEED MOBILE LOGIN */}
        {indeedMode === 'mobile' && (
          <div>
            {/* If Connected and NOT re-connecting: show clean active banner */}
            {indeedSessionInfo.connected && !isIndeedReconnecting ? (
              <div>
                <div className="portal-session-banner" style={{
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--emerald)' }}>
                    🟢 Indeed Persistent Browser Session is Active
                  </div>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Your authenticated session cookies are active. The agent can auto-apply to Indeed "Easily Apply" jobs autonomously with zero password prompts.
                  </p>
                </div>

                <div className="portal-actions-footer">
                  <button
                    type="button"
                    onClick={() => setIsIndeedReconnecting(true)}
                    className="portal-reconnect-btn"
                  >
                    <RotateCcw size={14} />
                    <span>Re-connect / Refresh Indeed Mobile Session</span>
                  </button>

                  <span className="portal-path-indicator">
                    Vault: <code>backend/data/indeed_session/</code>
                  </span>
                </div>
              </div>
            ) : (
              /* Mobile Credentials & Code Form for Indeed */
              <form onSubmit={handleIndeedMobileConnect} className="portal-mobile-form">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    {isIndeedReconnecting ? '🔄 Re-connect Indeed Account' : '📱 Connect Indeed via Mobile'}
                  </div>
                  {isIndeedReconnecting && (
                    <button
                      type="button"
                      onClick={() => setIsIndeedReconnecting(false)}
                      style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: '0.75rem', cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  )}
                </div>

                {/* Sub-mode selector: Code vs Password */}
                <div className="portal-type-toggle">
                  <button
                    type="button"
                    className={`portal-type-btn ${indeedLoginType === 'code' ? 'active' : ''}`}
                    onClick={() => setIndeedLoginType('code')}
                  >
                    <Smartphone size={13} />
                    <span>Direct Login Code (Passwordless)</span>
                  </button>
                  <button
                    type="button"
                    className={`portal-type-btn ${indeedLoginType === 'password' ? 'active' : ''}`}
                    onClick={() => setIndeedLoginType('password')}
                  >
                    <KeyRound size={13} />
                    <span>Email &amp; Password</span>
                  </button>
                </div>

                {/* Field 1: Email or Phone */}
                <div className="portal-form-field">
                  <label className="portal-field-label">
                    <span>{indeedLoginType === 'password' ? 'Indeed Email Address or Phone' : 'Registered Indeed Email or Phone'}</span>
                  </label>
                  <div className="portal-input-container">
                    <Mail size={16} className="portal-input-icon" />
                    <input
                      type="text"
                      value={indeedIdentifier}
                      onChange={(e) => setIndeedIdentifier(e.target.value)}
                      placeholder="e.g. name@gmail.com or 9876543210"
                      className="portal-text-input"
                      required
                      autoComplete="username"
                    />
                  </div>
                </div>

                {/* Field 2: Password (Only for password flow) */}
                {indeedLoginType === 'password' && (
                  <div className="portal-form-field">
                    <label className="portal-field-label">
                      <span>Indeed Account Password</span>
                    </label>
                    <div className="portal-input-container">
                      <Lock size={16} className="portal-input-icon" />
                      <input
                        type={showIndeedPassword ? 'text' : 'password'}
                        value={indeedPassword}
                        onChange={(e) => setIndeedPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="portal-text-input"
                        required
                        autoComplete="current-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowIndeedPassword(!showIndeedPassword)}
                        className="portal-password-toggle"
                        title={showIndeedPassword ? 'Hide password' : 'Show password'}
                      >
                        {showIndeedPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    </div>
                  </div>
                )}

                <div className="portal-form-note">
                  <ShieldCheck size={14} color="#0284c7" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>
                    <strong>Zero-Password Storage:</strong> Credentials are used exclusively for one-time headless session verification and are never stored on disk.
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={isConnectingIndeedMobile}
                  className="portal-launch-btn"
                  style={{ width: '100%', marginTop: '4px' }}
                >
                  {isConnectingIndeedMobile ? <Loader2 size={16} className="spin" /> : <Smartphone size={16} />}
                  <span>{isConnectingIndeedMobile ? 'Connecting to Indeed... Please wait' : 'Connect Indeed via Code'}</span>
                </button>
              </form>
            )}
          </div>
        )}

        {/* MODE 2: INDEED LAPTOP BROWSER LOGIN (FALLBACK) */}
        {indeedMode === 'laptop' && (
          <div>
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
        )}
      </div>

      {/* STEP 4/5: INTERACTIVE OTP / CODE MODAL POPUP (UNIFIED FOR NAUKRI & INDEED) */}
      {otpModalOpen && (
        <div className="portal-otp-overlay">
          <div className="portal-otp-dialog">
            <div className="portal-otp-icon-wrapper" style={{ background: activePortal === 'indeed' ? 'rgba(2, 132, 199, 0.1)' : 'rgba(234, 88, 12, 0.1)', color: activePortal === 'indeed' ? '#0284c7' : '#ea580c' }}>
              <ShieldCheck size={30} />
            </div>

            <div>
              <h3 className="portal-otp-title">
                {activePortal === 'indeed' ? 'Indeed Verification Code' : 'Naukri Verification Code'}
              </h3>
              <p className="portal-otp-subtitle">
                {activePortal === 'indeed'
                  ? 'Enter the 6-digit verification code sent to your Indeed registered email or phone to complete your connection.'
                  : 'Enter the 6-digit OTP code sent to your registered mobile phone or WhatsApp to complete your connection.'}
              </p>
            </div>

            {otpError && (
              <div style={{
                padding: '8px 12px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#dc2626',
                fontSize: '0.78rem',
                textAlign: 'center'
              }}>
                {otpError}
              </div>
            )}

            <form onSubmit={handleVerifyOtp} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <input
                type="text"
                value={otpValue}
                onChange={(e) => setOtpValue(e.target.value.replace(/\s+/g, '').slice(0, 8))}
                placeholder="• • • • • •"
                maxLength={8}
                className="portal-otp-input-field"
                autoFocus
                required
              />

              <div className="portal-otp-actions">
                <button
                  type="submit"
                  disabled={isVerifyingOtp || otpValue.length < 4}
                  className="portal-otp-verify-btn"
                >
                  {isVerifyingOtp ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
                  <span>{isVerifyingOtp ? 'Verifying Code... Please wait' : 'Verify & Complete Connection'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleCancelMobileSession}
                  className="portal-otp-cancel-btn"
                >
                  Cancel &amp; Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
