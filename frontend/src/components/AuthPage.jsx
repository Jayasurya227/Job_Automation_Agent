import React, { useState } from 'react';
import { 
  Bot, 
  User, 
  Mail,
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  ShieldCheck, 
  KeyRound, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle,
  X,
  Loader2,
  RefreshCw
} from 'lucide-react';
import { api, setAuthToken } from '../api';

export default function AuthPage({ onLogin }) {
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  
  // Registration & Login Fields - Blank by default (credentials appear on tap/click)
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Forgot Password Modal State
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotStep, setForgotStep] = useState(1); // 1 = Request OTP, 2 = Verify OTP & Reset
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotOtp, setForgotOtp] = useState('');
  const [forgotNewPassword, setForgotNewPassword] = useState('');
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [forgotSubmitting, setForgotSubmitting] = useState(false);
  const [devOtpPreview, setDevOtpPreview] = useState(null);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setError('');

    const cleanEmail = email.trim().toLowerCase();
    const cleanPassword = password.trim();

    if (authMode === 'register' && !fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }
    if (!cleanPassword) {
      setError('Please enter your password.');
      return;
    }
    if (cleanPassword.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    setIsSubmitting(true);

    try {
      let res;
      if (authMode === 'login') {
        res = await api.login(cleanEmail, cleanPassword);
      } else {
        res = await api.register(fullName.trim(), cleanEmail, cleanPassword);
      }

      // Handle remember email preference
      if (rememberMe) {
        localStorage.setItem('agent_remembered_email', cleanEmail);
      } else {
        localStorage.removeItem('agent_remembered_email');
      }

      // Save JWT token
      if (res.access_token) {
        setAuthToken(res.access_token);
      }

      onLogin(res.user);
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenForgotModal = () => {
    setForgotEmail('');
    setForgotStep(1);
    setForgotOtp('');
    setForgotNewPassword('');
    setForgotConfirmPassword('');
    setForgotError('');
    setForgotSuccess(false);
    setDevOtpPreview(null);
    setShowForgotModal(true);
  };

  const handleRequestOtp = async (e) => {
    if (e) e.preventDefault();
    setForgotError('');
    if (!forgotEmail.trim()) {
      setForgotError('Please enter your registered email address.');
      return;
    }

    setForgotSubmitting(true);
    try {
      const res = await api.requestPasswordResetOtp(forgotEmail.trim().toLowerCase());
      if (res.dev_otp_preview) {
        setDevOtpPreview(res.dev_otp_preview);
      }
      setForgotStep(2);
    } catch (err) {
      setForgotError(err.message || 'Could not send verification OTP. Verify your email.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  const handleVerifyOtpAndReset = async (e) => {
    if (e) e.preventDefault();
    setForgotError('');

    if (!forgotOtp.trim() || forgotOtp.trim().length !== 6) {
      setForgotError('Please enter the 6-digit OTP sent to your email.');
      return;
    }
    if (!forgotNewPassword.trim() || forgotNewPassword.trim().length < 6) {
      setForgotError('New password must be at least 6 characters.');
      return;
    }
    if (forgotNewPassword !== forgotConfirmPassword) {
      setForgotError('New passwords do not match.');
      return;
    }

    setForgotSubmitting(true);
    try {
      await api.verifyOtpAndResetPassword(
        forgotEmail.trim().toLowerCase(),
        forgotOtp.trim(),
        forgotNewPassword.trim()
      );
      setForgotSuccess(true);
      setPassword(forgotNewPassword);
      setTimeout(() => {
        setShowForgotModal(false);
        setForgotSuccess(false);
      }, 2500);
    } catch (err) {
      setForgotError(err.message || 'Invalid or expired OTP. Please check your code.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  return (
    <div className="auth-page-wrapper">
      {/* Dynamic Background visual layer */}
      <div className="ai-office-bg-container">
        <div className="ai-office-image" />
        <div className="ai-holo-glow" />
        <div className="ai-office-overlay" />
      </div>

      {/* Main Frosted Glass Authentication Card - Attached to Top and Bottom */}
      <div className="auth-card glass-panel-elevated">
        {/* Header / Brand identity matching screenshot */}
        <div className="auth-header">
          <div className="auth-logo-badge">
            <Bot size={24} color="#ffffff" />
          </div>
          <div className="badge badge-indigo auth-agent-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Sparkles size={11} />
            <span>Autonomous Job Agent</span>
          </div>
          <h1 className="auth-title">Welcome to Career AI</h1>
          <p className="auth-subtitle">
            {authMode === 'login' 
              ? 'Sign in with your credentials to access your autonomous job discovery & application pipeline.'
              : 'Create an account to start your personalized autonomous job discovery & application pipeline.'}
          </p>
        </div>

        {/* Mode Switcher Tabs */}
        <div style={{
          display: 'flex',
          background: 'rgba(255, 255, 255, 0.55)',
          borderRadius: '12px',
          padding: '3px',
          marginBottom: '12px',
          border: '1px solid rgba(255, 255, 255, 0.85)',
          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.04)'
        }}>
          <button
            type="button"
            onClick={() => { 
              setAuthMode('login'); 
              setError('');
              setPassword('');
            }}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '9px',
              border: 'none',
              background: authMode === 'login' ? 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)' : 'transparent',
              color: authMode === 'login' ? '#ffffff' : '#475569',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: authMode === 'login' ? '0 2px 8px rgba(79, 70, 229, 0.28)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { 
              setAuthMode('register'); 
              setError('');
              setFullName('');
              setEmail('');
              setPassword('');
            }}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '9px',
              border: 'none',
              background: authMode === 'register' ? 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)' : 'transparent',
              color: authMode === 'register' ? '#ffffff' : '#475569',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: authMode === 'register' ? '0 2px 8px rgba(79, 70, 229, 0.28)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            Create Account
          </button>
        </div>

        {/* Error message banner */}
        {error && (
          <div className="auth-error-banner" style={{ marginBottom: '10px', padding: '8px 12px', fontSize: '0.8rem' }}>
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          {/* Full Name for Registration */}
          {authMode === 'register' && (
            <div className="auth-field-group" style={{ marginBottom: '10px' }}>
              <label htmlFor="auth-full-name" className="auth-label">
                Full Name
              </label>
              <div className="auth-input-container">
                <User size={15} className="auth-input-icon" />
                <input
                  id="auth-full-name"
                  type="text"
                  className="form-input auth-input"
                  placeholder="e.g. Rayavaram Jayasurya"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  required
                />
              </div>
            </div>
          )}

          {/* Email Address */}
          <div className="auth-field-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="auth-email" className="auth-label">
              Email Address
            </label>
            <div className="auth-input-container">
              <Mail size={15} className="auth-input-icon" />
              <input
                id="auth-email"
                type="email"
                className="form-input auth-input"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username email"
                required
              />
            </div>
          </div>

          {/* Password Field with Eye Toggle */}
          <div className="auth-field-group auth-password-group" style={{ marginBottom: '12px' }}>
            <label htmlFor="auth-password" className="auth-label">
              Password
            </label>
            <div className="auth-input-container">
              <Lock size={15} className="auth-input-icon" />
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input auth-input auth-input-password"
                placeholder={authMode === 'login' ? 'Enter your password' : 'Create password (min 6 characters)'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                required
              />
              <button
                type="button"
                id="auth-toggle-password-btn"
                className="auth-password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? 'Hide password' : 'Show password'}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Actions Row: Remember Me & Forgot Password (Only in Login mode) */}
          {authMode === 'login' && (
            <div className="auth-actions-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <label className="auth-checkbox-label" style={{ display: 'flex', alignItems: 'center', gap: '7px', cursor: 'pointer', fontSize: '13px', color: '#64748b', userSelect: 'none' }}>
                <input
                  type="checkbox"
                  id="auth-remember-me"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{ accentColor: '#4f46e5', width: '15px', height: '15px', cursor: 'pointer' }}
                />
                Remember email
              </label>

              <button
                type="button"
                id="auth-forgot-password-link"
                className="auth-link-btn"
                onClick={handleOpenForgotModal}
                style={{ background: 'none', border: 'none', color: '#4f46e5', cursor: 'pointer', fontSize: '13px', fontWeight: 600 }}
              >
                Forgot Password?
              </button>
            </div>
          )}

          {/* Primary Action Button - Olive Green Pill Button Matching Screenshot */}
          <button
            type="submit"
            id="auth-submit-btn"
            className="auth-submit-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={17} className="animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <>
                <span>{authMode === 'login' ? 'Sign In & Open Dashboard' : 'Create Account & Unlock'}</span>
                <ArrowRight size={17} />
              </>
            )}
          </button>
        </form>

        {/* Security watermark footer */}
        <div className="auth-security-footer" style={{ marginTop: '12px', textAlign: 'center', fontSize: '12px', color: '#527853', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontWeight: 600 }}>
          <ShieldCheck size={14} color="#4a6c27" />
          <span>100% Local Device Storage • Zero Cloud Tracking</span>
        </div>
      </div>

      {/* Forgot Password Modal with 6-digit Email OTP */}
      {showForgotModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <div className="glass-panel-elevated modal-content" style={{ maxWidth: '420px', width: '100%', padding: '24px', borderRadius: '16px', background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <KeyRound size={20} color="#818cf8" />
                <h3 style={{ margin: 0, fontSize: '18px', color: '#f8fafc' }}>
                  {forgotStep === 1 ? 'Reset Password via OTP' : 'Enter 6-Digit OTP'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowForgotModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {forgotError && (
              <div className="auth-error-banner" style={{ marginBottom: '14px' }}>
                <AlertCircle size={15} />
                <span>{forgotError}</span>
              </div>
            )}

            {forgotSuccess ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#10b981' }}>
                <CheckCircle2 size={40} style={{ margin: '0 auto 12px' }} />
                <h4 style={{ margin: '0 0 6px', color: '#f8fafc' }}>Password Reset Successful!</h4>
                <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8' }}>Your new password has been saved. Closing...</p>
              </div>
            ) : forgotStep === 1 ? (
              /* Step 1: Request OTP by Email */
              <form onSubmit={handleRequestOtp} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
                  Enter your registered email address. We will send a secure 6-digit OTP code valid for 10 minutes.
                </p>

                <div className="auth-field-group">
                  <label className="auth-label">Registered Email</label>
                  <input
                    type="email"
                    className="form-input auth-input"
                    placeholder="name@example.com"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    autoComplete="email"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={forgotSubmitting}
                  style={{ width: '100%', padding: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                >
                  {forgotSubmitting ? <Loader2 size={16} className="animate-spin" /> : 'Send 6-Digit OTP'}
                </button>
              </form>
            ) : (
              /* Step 2: Verify OTP & Input New Password */
              <form onSubmit={handleVerifyOtpAndReset} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
                  We sent a 6-digit code to <strong>{forgotEmail}</strong>.
                </p>

                {devOtpPreview && (
                  <div style={{ background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '10px 14px', borderRadius: '8px', fontSize: '12px', color: '#c7d2fe' }}>
                    <strong>OTP Code:</strong> <span style={{ fontSize: '16px', letterSpacing: '3px', fontWeight: 'bold', color: '#ffffff' }}>{devOtpPreview}</span> (Valid for 10 mins)
                  </div>
                )}

                <div className="auth-field-group">
                  <label className="auth-label">6-Digit OTP Code</label>
                  <input
                    type="text"
                    maxLength={6}
                    className="form-input auth-input"
                    placeholder="e.g. 123456"
                    value={forgotOtp}
                    onChange={(e) => setForgotOtp(e.target.value)}
                    style={{ letterSpacing: '4px', fontSize: '18px', textAlign: 'center', fontWeight: 'bold' }}
                    required
                  />
                </div>

                <div className="auth-field-group">
                  <label className="auth-label">New Password</label>
                  <input
                    type="password"
                    className="form-input auth-input"
                    placeholder="Minimum 6 characters"
                    value={forgotNewPassword}
                    onChange={(e) => setForgotNewPassword(e.target.value)}
                    required
                  />
                </div>

                <div className="auth-field-group">
                  <label className="auth-label">Confirm New Password</label>
                  <input
                    type="password"
                    className="form-input auth-input"
                    placeholder="Re-enter new password"
                    value={forgotConfirmPassword}
                    onChange={(e) => setForgotConfirmPassword(e.target.value)}
                    required
                  />
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setForgotStep(1)}
                    style={{ flex: 1, padding: '10px' }}
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={forgotSubmitting}
                    style={{ flex: 2, padding: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                  >
                    {forgotSubmitting ? <Loader2 size={16} className="animate-spin" /> : 'Reset Password'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
