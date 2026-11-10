import React from 'react';
import { 
  ShieldAlert, 
  X, 
  Sliders, 
  Check 
} from 'lucide-react';

export default function QuotaModal({ 
  isOpen, 
  onClose, 
  appliedCount = 7, 
  maxDailyLimit = 7,
  onOpenSettings 
}) {
  if (!isOpen) return null;

  return (
    <div 
      className="modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        animation: 'fadeIn 0.2s ease-out'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div 
        className="quota-modal-card"
        style={{
          background: 'var(--bg-card, #ffffff)',
          color: 'var(--text-main, #0f172a)',
          borderRadius: '20px',
          border: '1px solid var(--border-card, rgba(226, 232, 240, 0.8))',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.05)',
          maxWidth: '440px',
          width: '100%',
          padding: '26px 22px 22px 22px',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          animation: 'scaleUp 0.2s ease-out'
        }}
      >
        {/* Top-Right ✕ Cancel / Close Button */}
        <button
          type="button"
          id="quota-modal-close-btn"
          onClick={onClose}
          aria-label="Close safety alert"
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: 'none',
            background: 'rgba(0, 0, 0, 0.05)',
            color: 'var(--text-muted, #64748b)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.15s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.12)';
            e.currentTarget.style.color = '#dc2626';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)';
            e.currentTarget.style.color = 'var(--text-muted, #64748b)';
          }}
        >
          <X size={18} strokeWidth={2.4} />
        </button>

        {/* Header with Icon, Brand Eyebrow & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div 
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '13px',
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.25) 100%)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#d97706',
              flexShrink: 0,
              boxShadow: '0 0 16px rgba(245, 158, 11, 0.18)'
            }}
          >
            <ShieldAlert size={25} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '2px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#059669', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                🤖 Job Automation Agent
              </span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, color: 'var(--text-main, #0f172a)', letterSpacing: '-0.02em' }}>
              Daily Limit Reached
            </h2>
          </div>
        </div>

        {/* Progress Tracker Card */}
        <div 
          style={{
            background: 'rgba(248, 250, 252, 0.85)',
            border: '1px solid rgba(226, 232, 240, 0.9)',
            borderRadius: '14px',
            padding: '13px 15px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>
              Today's Submissions:
            </span>
            <span style={{ fontWeight: 800, fontFamily: 'var(--font-mono, monospace)', color: '#047857' }}>
              {appliedCount} / {maxDailyLimit} Completed
            </span>
          </div>

          {/* 100% Full Safety Bar */}
          <div 
            style={{
              width: '100%',
              height: '8px',
              background: 'rgba(226, 232, 240, 0.8)',
              borderRadius: '999px',
              overflow: 'hidden'
            }}
          >
            <div 
              style={{
                width: '100%',
                height: '100%',
                background: 'linear-gradient(90deg, #10b981 0%, #059669 100%)',
                borderRadius: '999px'
              }}
            />
          </div>
        </div>

        {/* Simple & Clean 1-Line Message (Zero Heavy Jargon) */}
        <div 
          style={{
            fontSize: '0.86rem',
            lineHeight: 1.55,
            color: 'var(--text-secondary, #475569)',
            background: 'rgba(241, 245, 249, 0.65)',
            border: '1px solid rgba(226, 232, 240, 0.85)',
            borderRadius: '12px',
            padding: '12px 14px'
          }}
        >
          You've reached your daily limit of <strong>{maxDailyLimit} jobs</strong>. Auto-apply is paused for today and will resume tomorrow.
        </div>

        {/* Action Buttons */}
        <div 
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            marginTop: '2px'
          }}
        >
          <button
            type="button"
            id="quota-modal-confirm-btn"
            onClick={onClose}
            className="btn btn-primary"
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '0.88rem',
              fontWeight: 700,
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              border: 'none',
              color: '#ffffff',
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            <Check size={16} strokeWidth={2.4} />
            <span>Got It</span>
          </button>

          {onOpenSettings && (
            <button
              type="button"
              id="quota-modal-settings-btn"
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
              style={{
                width: '100%',
                padding: '9px',
                fontSize: '0.8rem',
                fontWeight: 600,
                borderRadius: '10px',
                background: 'transparent',
                border: '1px solid var(--border-card, rgba(226, 232, 240, 0.8))',
                color: 'var(--text-muted, #64748b)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--text-main, #0f172a)';
                e.currentTarget.style.borderColor = 'var(--primary, #6366f1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-muted, #64748b)';
                e.currentTarget.style.borderColor = 'var(--border-card, rgba(226, 232, 240, 0.8))';
              }}
            >
              <Sliders size={14} />
              <span>Change Limit</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
