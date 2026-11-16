import React, { useState, useEffect } from 'react';
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
  RefreshCw,
  Check,
  Globe,
  Target
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

  // Forgot Password Modal State (3-Step Enterprise Recovery Journey)
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotStep, setForgotStep] = useState(1); // 1 = Email, 2 = Verify OTP Only, 3 = Set New Password
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotOtp, setForgotOtp] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [forgotNewPassword, setForgotNewPassword] = useState('');
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState('');
  const [showForgotNewPassword, setShowForgotNewPassword] = useState(false);
  const [showForgotConfirmPassword, setShowForgotConfirmPassword] = useState(false);
  const [forgotError, setForgotError] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [forgotSubmitting, setForgotSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Countdown timer for OTP resend cooldown
  useEffect(() => {
    let timer;
    if (resendCooldown > 0) {
      timer = setInterval(() => {
        setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [resendCooldown]);

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
    setForgotEmail(email.trim() || '');
    setForgotStep(1);
    setForgotOtp('');
    setResetToken('');
    setForgotNewPassword('');
    setForgotConfirmPassword('');
    setShowForgotNewPassword(false);
    setShowForgotConfirmPassword(false);
    setForgotError('');
    setForgotSuccess(false);
    setResendCooldown(0);
    setShowForgotModal(true);
  };

  // Step 1: Request OTP by entering registered email
  const handleRequestOtp = async (e) => {
    if (e) e.preventDefault();
    setForgotError('');
    const cleanEmail = forgotEmail.trim().toLowerCase();
    if (!cleanEmail) {
      setForgotError('Please enter your registered email address.');
      return;
    }

    setForgotSubmitting(true);
    try {
      await api.requestPasswordResetOtp(cleanEmail);
      setForgotStep(2);
      setForgotOtp('');
      setResendCooldown(30);
    } catch (err) {
      setForgotError(err.message || 'Could not send verification OTP. Please verify your email.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  // Resend OTP in Step 2 with cooldown timer
  const handleResendOtp = async () => {
    if (resendCooldown > 0 || forgotSubmitting) return;
    setForgotError('');
    setForgotSubmitting(true);
    try {
      await api.requestPasswordResetOtp(forgotEmail.trim().toLowerCase());
      setForgotOtp('');
      setResendCooldown(30);
    } catch (err) {
      setForgotError(err.message || 'Failed to resend OTP. Please try again.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  // Step 2: Verify 6-digit numeric OTP ONLY (Transitions to Step 3 on success)
  const handleVerifyOtp = async (e) => {
    if (e) e.preventDefault();
    setForgotError('');

    const cleanOtp = forgotOtp.replace(/\D/g, '').trim();
    if (cleanOtp.length !== 6) {
      setForgotError('Please enter the full 6-digit verification code.');
      return;
    }

    setForgotSubmitting(true);
    try {
      const res = await api.verifyOtpOnly(forgotEmail.trim().toLowerCase(), cleanOtp);
      if (res && res.reset_token) {
        setResetToken(res.reset_token);
      }
      // OTP verified successfully! Advance to Step 3: Set New Password
      setForgotStep(3);
      setForgotError('');
    } catch (err) {
      setForgotError(err.message || 'Invalid or expired OTP. Please check your code or request a fresh one.');
    } finally {
      setForgotSubmitting(false);
    }
  };

  // Step 3: Set New Password & Confirm Password (After OTP is proven valid)
  const handleSetNewPassword = async (e) => {
    if (e) e.preventDefault();
    setForgotError('');

    const cleanNewPass = forgotNewPassword.trim();
    const cleanConfirmPass = forgotConfirmPassword.trim();

    if (!cleanNewPass || cleanNewPass.length < 6) {
      setForgotError('New password must be at least 6 characters.');
      return;
    }
    if (cleanNewPass !== cleanConfirmPass) {
      setForgotError('New passwords do not match. Please verify.');
      return;
    }

    setForgotSubmitting(true);
    try {
      await api.setNewPassword(
        forgotEmail.trim().toLowerCase(),
        resetToken,
        cleanNewPass
      );
      setForgotSuccess(true);
      // Automatically pre-fill on login form for seamless user sign in
      setEmail(forgotEmail.trim().toLowerCase());
      setPassword(cleanNewPass);
      setTimeout(() => {
        setShowForgotModal(false);
        setForgotSuccess(false);
        setForgotStep(1);
      }, 2200);
    } catch (err) {
      setForgotError(err.message || 'Failed to update password. Please try again.');
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

      {/* Split Screen Container (Laptop: 50/50 Showcase Split, Mobile: Centered Card) */}
      <div className="auth-split-container">
        {/* Left Column: Frosted Glass Authentication Card */}
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

      {/* Right Column: Hero Capability Showcase (Laptop View Only) */}
      <div className="auth-showcase-panel">
        <div className="showcase-top-badge">
          <Sparkles size={14} color="#4f46e5" />
          <span>Autonomous Career Cockpit</span>
        </div>

        <h2 className="showcase-hero-title">
          Land High-Match Roles <br />
          <span className="showcase-gradient-text">On 100% Auto-Pilot</span>
        </h2>

        <p className="showcase-hero-desc">
          Your 24/7 autonomous career command center. Continuous stealth discovery across Naukri &amp; Indeed with verified Claude 3.5 ATS scoring.
        </p>

        {/* 3D Glassmorphic Visual Showcase with Live HUD Badges */}
        <div className="showcase-hero-visual-container">
          <div className="showcase-image-wrapper">
            <img 
              src="/job-automation-hero.png" 
              alt="Autonomous Job Application AI Agent" 
              className="showcase-hero-image"
              loading="eager"
            />
            <div className="showcase-image-overlay-glow"></div>
          </div>

          {/* Floating Glassmorphic Badges - Compact Corner Pills */}
          <div className="floating-badge badge-auto-applied">
            <div className="floating-badge-icon badge-icon-emerald">
              <CheckCircle2 size={13} />
            </div>
            <div className="floating-badge-text">
              <span className="badge-title">Auto-Pilot Successfully</span>
            </div>
          </div>

          <div className="floating-badge badge-ats-match">
            <div className="floating-badge-icon badge-icon-indigo">
              <Target size={13} />
            </div>
            <div className="floating-badge-text">
              <span className="badge-title">95% ATS Score</span>
            </div>
          </div>

          <div className="floating-badge badge-portals">
            <div className="floating-badge-icon badge-icon-cyan">
              <Globe size={13} />
            </div>
            <div className="floating-badge-text">
              <span className="badge-title">Active Sync</span>
            </div>
          </div>
        </div>

        <div className="showcase-live-strip">
          <div className="showcase-pulse-indicator">
            <span className="pulse-ping"></span>
            <span className="pulse-dot"></span>
          </div>
          <span className="showcase-status-label">Production Autonomous Engine Active</span>
          <div className="showcase-tags-divider">•</div>
          <span className="showcase-tags-list">FastAPI • Playwright • Claude 3.5 • SQLite</span>
        </div>
      </div>
    </div>

      {/* Forgot Password Modal - Real-World 3-Step Verification Journey */}
      {showForgotModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <div className="glass-panel-elevated modal-content" style={{ maxWidth: '440px', width: '100%', padding: '26px', borderRadius: '18px', background: '#131b2e', border: '1px solid rgba(255,255,255,0.15)', boxShadow: '0 20px 40px rgba(0,0,0,0.6)' }}>
            
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <KeyRound size={22} color="#818cf8" />
                <h3 style={{ margin: 0, fontSize: '18px', color: '#f8fafc', fontWeight: 600 }}>
                  {forgotStep === 1 && 'Reset Password'}
                  {forgotStep === 2 && 'Enter 6-Digit OTP'}
                  {forgotStep === 3 && 'Create New Password'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowForgotModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>

            {/* 3-Step Visual Progress Indicator */}
            {!forgotSuccess && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: forgotStep >= 1 ? '#818cf8' : '#64748b', fontWeight: forgotStep === 1 ? 700 : 500 }}>
                  <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: forgotStep > 1 ? '#10b981' : (forgotStep === 1 ? '#818cf8' : '#334155'), color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 'bold' }}>
                    {forgotStep > 1 ? '✓' : '1'}
                  </span>
                  <span>Email</span>
                </div>
                <div style={{ height: '1px', flex: 1, margin: '0 8px', background: forgotStep >= 2 ? '#818cf8' : 'rgba(255,255,255,0.1)' }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: forgotStep >= 2 ? '#818cf8' : '#64748b', fontWeight: forgotStep === 2 ? 700 : 500 }}>
                  <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: forgotStep > 2 ? '#10b981' : (forgotStep === 2 ? '#818cf8' : '#334155'), color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 'bold' }}>
                    {forgotStep > 2 ? '✓' : '2'}
                  </span>
                  <span>Verify OTP</span>
                </div>
                <div style={{ height: '1px', flex: 1, margin: '0 8px', background: forgotStep >= 3 ? '#818cf8' : 'rgba(255,255,255,0.1)' }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: forgotStep >= 3 ? '#818cf8' : '#64748b', fontWeight: forgotStep === 3 ? 700 : 500 }}>
                  <span style={{ width: '18px', height: '18px', borderRadius: '50%', background: forgotStep === 3 ? '#818cf8' : '#334155', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 'bold' }}>
                    3
                  </span>
                  <span>New Password</span>
                </div>
              </div>
            )}

            {/* Error Banner */}
            {forgotError && (
              <div className="auth-error-banner" style={{ marginBottom: '14px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                <AlertCircle size={16} />
                <span>{forgotError}</span>
              </div>
            )}

            {/* Success State */}
            {forgotSuccess ? (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: '#10b981' }}>
                <CheckCircle2 size={46} style={{ margin: '0 auto 14px', color: '#10b981' }} />
                <h4 style={{ margin: '0 0 8px', color: '#f8fafc', fontSize: '18px', fontWeight: 600 }}>Password Reset Successful!</h4>
                <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
                  Your password has been securely updated. Automatically closing to sign in...
                </p>
              </div>
            ) : forgotStep === 1 ? (
              /* ============================================================== */
              /* STEP 1: Enter Email & Request OTP                              */
              /* ============================================================== */
              <form onSubmit={handleRequestOtp} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
                  Enter your registered account email. We will send a single-use 6-digit OTP code to verify your identity.
                </p>

                <div className="auth-field-group">
                  <label className="auth-label" style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '6px', display: 'block' }}>Registered Email</label>
                  <div style={{ position: 'relative' }}>
                    <Mail size={16} color="#64748b" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      type="email"
                      className="form-input auth-input"
                      placeholder="name@example.com"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      autoComplete="email"
                      required
                      style={{ paddingLeft: '38px', width: '100%', boxSizing: 'border-box' }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={forgotSubmitting}
                  style={{ width: '100%', padding: '12px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 600, fontSize: '14px', cursor: forgotSubmitting ? 'not-allowed' : 'pointer' }}
                >
                  {forgotSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Sending OTP...</span>
                    </>
                  ) : (
                    <>
                      <span>Send 6-Digit OTP</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </form>
            ) : forgotStep === 2 ? (
              /* ============================================================== */
              /* STEP 2: Dedicated 6-Digit OTP Verification Screen (Numbers Only)*/
              /* ============================================================== */
              <form onSubmit={handleVerifyOtp} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5 }}>
                  We sent a 6-digit verification code to <strong style={{ color: '#f8fafc' }}>{forgotEmail}</strong>.
                  Check your inbox and enter the code below:
                </div>

                <div className="auth-field-group">
                  <label className="auth-label" style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '8px', display: 'block', textAlign: 'center' }}>
                    Enter 6-Digit Verification Code
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    autoFocus
                    className="form-input auth-input"
                    placeholder="• • • • • •"
                    value={forgotOtp}
                    onChange={(e) => setForgotOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    style={{
                      letterSpacing: '8px',
                      fontSize: '24px',
                      textAlign: 'center',
                      fontWeight: 'bold',
                      fontFamily: 'monospace',
                      padding: '12px 16px',
                      width: '100%',
                      boxSizing: 'border-box',
                      borderRadius: '10px'
                    }}
                    required
                  />
                  <div style={{ textAlign: 'center', marginTop: '6px', fontSize: '11px', color: '#64748b' }}>
                    Digits only (0–9) • Typing or Pasting supported
                  </div>
                </div>

                {/* Resend OTP Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', padding: '0 4px' }}>
                  <span style={{ color: '#94a3b8' }}>Didn't receive code?</span>
                  {resendCooldown > 0 ? (
                    <span style={{ color: '#64748b', fontWeight: 500 }}>
                      Resend in {resendCooldown}s
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={forgotSubmitting}
                      style={{ background: 'none', border: 'none', color: '#818cf8', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                    >
                      Resend New OTP
                    </button>
                  )}
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setForgotStep(1);
                      setForgotOtp('');
                      setForgotError('');
                    }}
                    style={{ flex: 1, padding: '11px', borderRadius: '10px', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', color: '#cbd5e1', cursor: 'pointer' }}
                  >
                    Change Email
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={forgotSubmitting || forgotOtp.replace(/\D/g, '').length !== 6}
                    style={{ flex: 2, padding: '11px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 600, cursor: (forgotSubmitting || forgotOtp.replace(/\D/g, '').length !== 6) ? 'not-allowed' : 'pointer', opacity: forgotOtp.replace(/\D/g, '').length === 6 ? 1 : 0.6 }}
                  >
                    {forgotSubmitting ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        <span>Verifying...</span>
                      </>
                    ) : (
                      <>
                        <span>Verify OTP</span>
                        <ArrowRight size={16} />
                      </>
                    )}
                  </button>
                </div>
              </form>
            ) : (
              /* ============================================================== */
              /* STEP 3: Set New Password (Only Accessible After OTP Verified)  */
              /* ============================================================== */
              <form onSubmit={handleSetNewPassword} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <div style={{ padding: '8px 12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '8px', color: '#6ee7b7', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Check size={14} color="#10b981" />
                  <span>OTP verified for <strong>{forgotEmail}</strong>. Create your new password:</span>
                </div>

                <div className="auth-field-group">
                  <label className="auth-label" style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '6px', display: 'block' }}>New Password</label>
                  <div style={{ position: 'relative' }}>
                    <Lock size={16} color="#64748b" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      type={showForgotNewPassword ? 'text' : 'password'}
                      className="form-input auth-input"
                      placeholder="Minimum 6 characters"
                      value={forgotNewPassword}
                      onChange={(e) => setForgotNewPassword(e.target.value)}
                      required
                      style={{ paddingLeft: '38px', paddingRight: '40px', width: '100%', boxSizing: 'border-box' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowForgotNewPassword(!showForgotNewPassword)}
                      style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}
                    >
                      {showForgotNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div className="auth-field-group">
                  <label className="auth-label" style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '6px', display: 'block' }}>Confirm New Password</label>
                  <div style={{ position: 'relative' }}>
                    <Lock size={16} color="#64748b" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      type={showForgotConfirmPassword ? 'text' : 'password'}
                      className="form-input auth-input"
                      placeholder="Re-enter new password"
                      value={forgotConfirmPassword}
                      onChange={(e) => setForgotConfirmPassword(e.target.value)}
                      required
                      style={{ paddingLeft: '38px', paddingRight: '40px', width: '100%', boxSizing: 'border-box' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowForgotConfirmPassword(!showForgotConfirmPassword)}
                      style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}
                    >
                      {showForgotConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Match indicator */}
                {forgotNewPassword && forgotConfirmPassword && (
                  <div style={{ fontSize: '12px', color: forgotNewPassword === forgotConfirmPassword ? '#10b981' : '#f87171', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    {forgotNewPassword === forgotConfirmPassword ? '✓ Passwords match' : '✕ Passwords do not match'}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={forgotSubmitting}
                  style={{ width: '100%', padding: '12px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 600, fontSize: '14px', marginTop: '6px', cursor: forgotSubmitting ? 'not-allowed' : 'pointer' }}
                >
                  {forgotSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Updating Password...</span>
                    </>
                  ) : (
                    <>
                      <span>Save & Update Password</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
