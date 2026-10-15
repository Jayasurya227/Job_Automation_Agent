import React, { useState, useEffect } from 'react';
import { 
  Globe, 
  Shield, 
  Eye, 
  EyeOff, 
  Save, 
  CheckCircle2, 
  AlertTriangle,
  Mail,
  Send,
  Zap,
  HelpCircle,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { api } from '../api';

export default function AccountsSettings({ notify }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [testingSmtp, setTestingSmtp] = useState(false);
  const [smtpTestResult, setSmtpTestResult] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  const [portals, setPortals] = useState({
    naukri: { username: '', password: '', status: 'unconfigured', has_password: false }
  });

  const [smtp, setSmtp] = useState({
    sender_email: '',
    sender_name: 'Rayavaram Jayasurya',
    app_password: '',
    daily_limit: 12,
    enabled: true,
    has_password: false,
    status: 'unconfigured'
  });

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await api.getSettings();
      if (data.portals) {
        setPortals({
          naukri: {
            username: data.portals.naukri?.username || '',
            password: data.portals.naukri?.password || '',
            status: data.portals.naukri?.status || 'unconfigured',
            has_password: Boolean(data.portals.naukri?.has_password)
          }
        });
      }
      if (data.smtp) {
        setSmtp({
          sender_email: data.smtp.sender_email || '',
          sender_name: data.smtp.sender_name || 'Rayavaram Jayasurya',
          app_password: data.smtp.app_password || '',
          daily_limit: data.smtp.daily_limit || 12,
          enabled: data.smtp.enabled ?? true,
          has_password: Boolean(data.smtp.has_password),
          status: (data.smtp.sender_email && data.smtp.has_password) ? 'connected' : 'unconfigured'
        });
      }
    } catch (err) {
      if (notify) notify('Failed to load account settings: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleTestSmtp = async () => {
    if (!smtp.sender_email || !smtp.sender_email.includes('@')) {
      if (notify) notify('Please enter a valid Gmail address first.', 'error');
      return;
    }
    if (!smtp.app_password && !smtp.has_password) {
      if (notify) notify('Please enter your 16-character Google App Password.', 'error');
      return;
    }

    setTestingSmtp(true);
    setSmtpTestResult(null);
    try {
      const res = await api.testSMTP({
        host: 'smtp.gmail.com',
        port: 587,
        sender_email: smtp.sender_email.trim(),
        app_password: smtp.app_password ? smtp.app_password.replace(/\s+/g, '') : undefined
      });
      setSmtpTestResult({ success: true, message: res.message || 'Gmail SMTP connection verified!' });
      if (notify) notify('Gmail SMTP connection verified successfully!', 'success');
    } catch (err) {
      const msg = err.message || 'SMTP authentication failed. Check your App Password.';
      setSmtpTestResult({ success: false, message: msg });
      if (notify) notify('SMTP test failed: ' + msg, 'error');
    } finally {
      setTestingSmtp(false);
    }
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    try {
      setSaving(true);
      const payload = {
        portals: {
          naukri: { username: portals.naukri.username, password: portals.naukri.password }
        },
        smtp: {
          sender_email: smtp.sender_email.trim(),
          sender_name: smtp.sender_name.trim(),
          app_password: smtp.app_password.replace(/\s+/g, ''),
          daily_limit: parseInt(smtp.daily_limit) || 12,
          enabled: smtp.enabled
        }
      };

      const res = await api.updateSettings(payload);
      if (notify) notify('Credentials and Gmail outreach settings saved securely!', 'success');
      
      if (res.settings) {
        if (res.settings.portals) {
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
        if (res.settings.smtp) {
          setSmtp(prev => ({
            ...prev,
            app_password: res.settings.smtp?.app_password || '',
            has_password: Boolean(res.settings.smtp?.has_password),
            status: (res.settings.smtp?.sender_email && res.settings.smtp?.has_password) ? 'connected' : 'unconfigured'
          }));
        }
      }
    } catch (err) {
      if (notify) notify('Error saving credentials: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
        Loading credentials configuration...
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '820px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '70px' }}>
      
      {/* Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
            Accounts & Outreach Settings
          </h1>
          <span className="badge badge-indigo" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Shield size={11} /> 100% Local Storage
          </span>
        </div>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
          Configure your Naukri login for 1-Click apply, and your Gmail account for manual recruiter cold outreach.
        </p>
      </div>

      {/* Security Banner */}
      <div style={{
        padding: '14px 18px',
        borderRadius: '10px',
        background: 'rgba(99, 102, 241, 0.08)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        fontSize: '0.83rem',
        color: 'var(--text-secondary)',
        lineHeight: 1.5
      }}>
        <Shield size={20} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ color: 'var(--text-main)' }}>Strictly Local Security:</strong> Your passwords are saved strictly on your local machine in <code>backend/data/account_settings.json</code>. They are <strong>never</strong> transmitted to third parties or cloud servers.
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {/* CARD 1: NAUKRI.COM PORTAL CREDENTIALS */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Globe size={18} color="#ff7555" />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Naukri.com Credentials
              </h2>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              1-Click Automated Portal Apply
            </span>
          </div>

          <div style={{
            padding: '20px',
            borderRadius: '10px',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 117, 85, 0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '1.3rem' }}>🇮🇳</span>
                <div>
                  <span style={{ fontWeight: 700, fontSize: '0.98rem', color: '#ff7555' }}>Naukri.com</span>
                  <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)' }}>Primary Indian Job Board</span>
                </div>
              </div>
              <span className={`badge ${portals.naukri.status === 'connected' ? 'badge-emerald' : 'badge-amber'}`} style={{ fontSize: '0.72rem' }}>
                {portals.naukri.status === 'connected' ? 'Configured' : 'Needs Setup'}
              </span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '5px' }}>
                Registered Email / Username
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
                Naukri Account Password
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
                  style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', background: 'rgba(255, 117, 85, 0.06)', padding: '10px 12px', borderRadius: '6px', border: '1px solid rgba(255, 117, 85, 0.15)' }}>
              💡 <strong>Automated 1-Click:</strong> The agent uses this session to auto-fill Easy Apply applications without asking for passwords.
            </div>
          </div>
        </div>

        {/* CARD 2: GMAIL COLD OUTREACH CREDENTIALS */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Mail size={18} color="var(--primary-light)" />
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Gmail Outreach Configuration (SMTP)
              </h2>
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Direct Recruiter Emailing
            </span>
          </div>

          <div style={{
            padding: '20px',
            borderRadius: '10px',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '1.3rem' }}>✉️</span>
                <div>
                  <span style={{ fontWeight: 700, fontSize: '0.98rem', color: 'var(--primary-light)' }}>Google Workspace / Gmail</span>
                  <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)' }}>Delivers personalized emails directly from your Gmail address</span>
                </div>
              </div>
              <span className={`badge ${smtp.status === 'connected' ? 'badge-emerald' : 'badge-amber'}`} style={{ fontSize: '0.72rem' }}>
                {smtp.status === 'connected' ? 'Configured' : 'Needs Setup'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '5px' }}>
                  Your Gmail Address
                </label>
                <input
                  type="email"
                  className="input-field"
                  placeholder="e.g. rayavaramjayasurya@gmail.com"
                  value={smtp.sender_email}
                  onChange={(e) => setSmtp({ ...smtp, sender_email: e.target.value })}
                  style={{ width: '100%', fontSize: '0.85rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: '5px' }}>
                  Sender Display Name
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Rayavaram Jayasurya"
                  value={smtp.sender_name}
                  onChange={(e) => setSmtp({ ...smtp, sender_name: e.target.value })}
                  style={{ width: '100%', fontSize: '0.85rem' }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  16-Character Google App Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowHelp(!showHelp)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--primary-light)',
                    fontSize: '0.74rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: 0
                  }}
                >
                  <HelpCircle size={12} /> {showHelp ? 'Hide guide' : 'How to get App Password?'}
                </button>
              </div>

              <div style={{ position: 'relative' }}>
                <input
                  type={showSmtpPassword ? 'text' : 'password'}
                  className="input-field"
                  placeholder="e.g. abcd efgh ijkl mnop"
                  value={smtp.app_password}
                  onChange={(e) => setSmtp({ ...smtp, app_password: e.target.value })}
                  style={{ width: '100%', fontSize: '0.85rem', paddingRight: '36px', fontFamily: 'monospace' }}
                />
                <button
                  type="button"
                  onClick={() => setShowSmtpPassword(!showSmtpPassword)}
                  style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  {showSmtpPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Quick Helper Accordion */}
            {showHelp && (
              <div style={{
                background: 'rgba(99, 102, 241, 0.06)',
                border: '1px solid rgba(99, 102, 241, 0.2)',
                borderRadius: '8px',
                padding: '14px',
                fontSize: '0.78rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.6
              }}>
                <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                  Quick 60-Second Setup for Google App Password:
                </div>
                <ol style={{ margin: 0, paddingLeft: '18px' }}>
                  <li>Go to your Google Account: <a href="https://myaccount.google.com/security" target="_blank" rel="noreferrer" style={{ color: 'var(--cyan-light)', textDecoration: 'underline' }}>myaccount.google.com/security</a></li>
                  <li>Ensure <strong>2-Step Verification</strong> is turned ON.</li>
                  <li>Search for <strong>"App passwords"</strong> (or go to <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{ color: 'var(--cyan-light)', textDecoration: 'underline' }}>myaccount.google.com/apppasswords</a>).</li>
                  <li>Create a new app name called <code>Job Agent</code> and click <strong>Create</strong>.</li>
                  <li>Copy the 16-character code (e.g. <code>abcd efgh ijkl mnop</code>) and paste it above!</li>
                </ol>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', paddingTop: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  Daily Safe Limit:
                </label>
                <select
                  value={smtp.daily_limit}
                  onChange={(e) => setSmtp({ ...smtp, daily_limit: parseInt(e.target.value) })}
                  className="input-field"
                  style={{ width: '85px', fontSize: '0.82rem', padding: '4px 8px' }}
                >
                  <option value={5}>5 / day</option>
                  <option value={10}>10 / day</option>
                  <option value={12}>12 / day (Recommended)</option>
                  <option value={15}>15 / day</option>
                </select>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  (Prevents spam flag)
                </span>
              </div>

              {/* Test Connection Button */}
              <button
                type="button"
                onClick={handleTestSmtp}
                disabled={testingSmtp}
                className="btn btn-secondary btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem' }}
              >
                {testingSmtp ? <Loader2 size={13} className="spin" /> : <Zap size={13} color="var(--primary-light)" />}
                <span>{testingSmtp ? 'Testing Login...' : 'Test Connection'}</span>
              </button>
            </div>

            {/* Test result status badge */}
            {smtpTestResult && (
              <div style={{
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.76rem',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: smtpTestResult.success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                border: `1px solid ${smtpTestResult.success ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
                color: smtpTestResult.success ? 'var(--emerald-light)' : 'var(--rose-light)'
              }}>
                {smtpTestResult.success ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                <span>{smtpTestResult.message}</span>
              </div>
            )}
          </div>
        </div>

        {/* Global Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            type="submit"
            disabled={saving}
            className="btn btn-primary"
            style={{ fontSize: '0.88rem', padding: '10px 26px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            <span>{saving ? 'Saving...' : 'Save All Credentials'}</span>
          </button>
        </div>

      </form>
    </div>
  );
}
