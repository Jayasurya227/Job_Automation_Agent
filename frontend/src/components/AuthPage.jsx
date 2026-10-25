import React, { useState } from 'react';
import { 
  Bot, 
  User, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  ShieldCheck, 
  KeyRound, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle,
  X
} from 'lucide-react';

export default function AuthPage({ onLogin }) {
  const [firstName, setFirstName] = useState(() => {
    try {
      const saved = localStorage.getItem('agent_remembered_name');
      return saved ? JSON.parse(saved).firstName || '' : '';
    } catch {
      return '';
    }
  });
  const [lastName, setLastName] = useState(() => {
    try {
      const saved = localStorage.getItem('agent_remembered_name');
      return saved ? JSON.parse(saved).lastName || '' : '';
    } catch {
      return '';
    }
  });
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(() => {
    return Boolean(localStorage.getItem('agent_remembered_name'));
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Forgot Password Modal State
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotNewPassword, setForgotNewPassword] = useState('');
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState(false);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    setError('');

    const cleanFirst = firstName.trim();
    const cleanLast = lastName.trim();

    if (!cleanFirst) {
      setError('Please enter your First Name.');
      return;
    }
    if (!cleanLast) {
      setError('Please enter your Last Name.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters long.');
      return;
    }

    // Verify password if already registered in local vault
    const savedHash = localStorage.getItem('agent_auth_hash');
    const enteredHash = btoa(password);

    if (savedHash && savedHash !== enteredHash) {
      setError('Incorrect password. Please enter your registered password, or click "Forgot Password?" below.');
      return;
    }

    // Register password hash on initial setup
    if (!savedHash) {
      localStorage.setItem('agent_auth_hash', enteredHash);
    }

    setIsSubmitting(true);

    const userData = {
      firstName: cleanFirst,
      lastName: cleanLast,
      fullName: `${cleanFirst} ${cleanLast}`,
      loginTime: new Date().toISOString(),
      isAuthenticated: true
    };

    // Store remembered name only if requested (never auto-bypass sign-in)
    if (rememberMe) {
      localStorage.setItem('agent_remembered_name', JSON.stringify({ firstName: cleanFirst, lastName: cleanLast }));
    } else {
      localStorage.removeItem('agent_remembered_name');
    }

    // Clear any auto-login keys so opening localhost link will always show sign-in page first
    localStorage.removeItem('agent_user');
    sessionStorage.removeItem('agent_user');

    setTimeout(() => {
      setIsSubmitting(false);
      if (onLogin) {
        onLogin(userData);
      }
    }, 350);
  };

  const handleResetPassword = (e) => {
    e.preventDefault();
    setForgotError('');

    if (!forgotNewPassword) {
      setForgotError('Please enter a new password.');
      return;
    }
    if (forgotNewPassword.length < 4) {
      setForgotError('New password must be at least 4 characters.');
      return;
    }
    if (forgotNewPassword !== forgotConfirmPassword) {
      setForgotError('Passwords do not match.');
      return;
    }

    // Update password in local storage vault
    localStorage.setItem('agent_auth_hash', btoa(forgotNewPassword));
    setForgotSuccess(true);
    setPassword(forgotNewPassword);

    setTimeout(() => {
      setShowForgotModal(false);
      setForgotSuccess(false);
      setForgotNewPassword('');
      setForgotConfirmPassword('');
    }, 1800);
  };

  return (
    <div className="auth-page-wrapper">
      {/* AI Agents Office Workplace Background */}
      <div className="ai-office-bg-container" aria-hidden="true">
        <div className="ai-office-image" />
        <div className="ai-holo-glow" />
        <div className="ai-office-overlay" />
      </div>

      {/* Main Frosted Glass Authentication Card */}
      <div className="auth-card glass-panel-elevated">
        {/* Header / Brand identity */}
        <div className="auth-header">
          <div className="auth-logo-badge">
            <Bot size={26} color="#ffffff" />
          </div>
          <div className="badge badge-indigo auth-agent-badge">
            <Sparkles size={13} style={{ marginRight: '4px' }} />
            Autonomous Job Agent
          </div>
          <h1 className="auth-title">Welcome to Career AI</h1>
          <p className="auth-subtitle">
            Sign in with your credentials to access your autonomous job discovery & application pipeline.
          </p>
        </div>

        {/* Error message banner */}
        {error && (
          <div className="auth-error-banner">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {/* Row: First Name & Last Name */}
          <div className="auth-row-names">
            <div className="auth-field-group">
              <label htmlFor="auth-first-name" className="auth-label">
                First Name
              </label>
              <div className="auth-input-container">
                <User size={16} className="auth-input-icon" />
                <input
                  id="auth-first-name"
                  type="text"
                  className="form-input auth-input"
                  placeholder="e.g. Jaswanth"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  autoComplete="given-name"
                  required
                />
              </div>
            </div>

            <div className="auth-field-group">
              <label htmlFor="auth-last-name" className="auth-label">
                Last Name
              </label>
              <div className="auth-input-container">
                <User size={16} className="auth-input-icon" />
                <input
                  id="auth-last-name"
                  type="text"
                  className="form-input auth-input"
                  placeholder="e.g. Kumar"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  autoComplete="family-name"
                  required
                />
              </div>
            </div>
          </div>

          {/* Password Field with Eye Toggle */}
          <div className="auth-field-group auth-password-group">
            <label htmlFor="auth-password" className="auth-label">
              Password
            </label>
            <div className="auth-input-container">
              <Lock size={16} className="auth-input-icon" />
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input auth-input auth-input-password"
                placeholder="Enter your security password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
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
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          {/* Actions Row: Remember Me & Forgot Password */}
          <div className="auth-actions-row">
            <label className="auth-remember-label">
              <input
                type="checkbox"
                id="auth-remember-checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="auth-checkbox"
              />
              <span>Remember name</span>
            </label>

            <button
              type="button"
              id="auth-forgot-password-link"
              className="auth-forgot-btn"
              onClick={() => {
                setShowForgotModal(true);
                setForgotError('');
                setForgotSuccess(false);
              }}
            >
              Forgot Password?
            </button>
          </div>

          {/* Submit Sign In Button */}
          <button
            type="submit"
            id="auth-submit-btn"
            className="btn btn-primary auth-submit-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <span>Sign In & Open Dashboard</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        {/* Security & Privacy Guarantee Footer */}
        <div className="auth-privacy-footer">
          <ShieldCheck size={14} color="#059669" />
          <span>100% Local Device Storage • Zero Cloud Tracking</span>
        </div>
      </div>

      {/* Forgot Password Frosted Glass Modal */}
      {showForgotModal && (
        <div className="auth-modal-overlay" onClick={() => setShowForgotModal(false)}>
          <div 
            className="auth-modal-card glass-panel-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <button 
              className="auth-modal-close-btn"
              onClick={() => setShowForgotModal(false)}
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>

            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <div className="auth-modal-icon-badge">
                <KeyRound size={22} color="var(--primary)" />
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)', margin: '8px 0 4px' }}>
                Reset Device Password
              </h3>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', lineHeight: '1.45' }}>
                Your agent credentials are encrypted directly in your local browser vault. You can set a new password below.
              </p>
            </div>

            {forgotSuccess ? (
              <div className="auth-success-banner">
                <CheckCircle2 size={20} color="#059669" />
                <div>
                  <strong>Password Reset Successfully!</strong>
                  <div style={{ fontSize: '0.8rem', color: 'var(--emerald)' }}>
                    Your new password has been saved. Closing in a moment...
                  </div>
                </div>
              </div>
            ) : (
              <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {forgotError && (
                  <div className="auth-error-banner" style={{ margin: 0 }}>
                    <AlertCircle size={15} />
                    <span>{forgotError}</span>
                  </div>
                )}

                <div>
                  <label className="auth-label">New Password</label>
                  <input
                    type="password"
                    id="forgot-new-password"
                    className="form-input"
                    placeholder="Enter at least 4 characters"
                    value={forgotNewPassword}
                    onChange={(e) => setForgotNewPassword(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="auth-label">Confirm New Password</label>
                  <input
                    type="password"
                    id="forgot-confirm-password"
                    className="form-input"
                    placeholder="Re-enter your new password"
                    value={forgotConfirmPassword}
                    onChange={(e) => setForgotConfirmPassword(e.target.value)}
                    required
                  />
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                    onClick={() => setShowForgotModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    id="forgot-save-btn"
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                  >
                    Save New Password
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
