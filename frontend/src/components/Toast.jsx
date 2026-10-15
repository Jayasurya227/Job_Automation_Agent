import React, { useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      maxWidth: '400px',
      pointerEvents: 'none',
    }}>
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  const isSuccess = toast.type === 'success';
  const isError = toast.type === 'error';

  return (
    <div
      style={{
        pointerEvents: 'auto',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '12px 16px',
        borderRadius: '10px',
        background: 'rgba(16, 24, 44, 0.95)',
        backdropFilter: 'blur(16px)',
        border: `1px solid ${isSuccess ? 'rgba(16, 185, 129, 0.4)' : isError ? 'rgba(244, 63, 94, 0.4)' : 'rgba(99, 102, 241, 0.4)'}`,
        boxShadow: '0 8px 30px rgba(0,0,0,0.6)',
        color: '#f8fafc',
        fontSize: '0.875rem',
        animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {isSuccess && <CheckCircle2 size={18} color="#10b981" style={{ flexShrink: 0 }} />}
      {isError && <AlertCircle size={18} color="#f43f5e" style={{ flexShrink: 0 }} />}
      {!isSuccess && !isError && <Info size={18} color="#6366f1" style={{ flexShrink: 0 }} />}

      <div style={{ flex: 1 }}>{toast.message}</div>

      <button
        onClick={() => onDismiss(toast.id)}
        style={{
          background: 'none',
          border: 'none',
          color: '#64748b',
          cursor: 'pointer',
          padding: '2px',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <X size={15} />
      </button>
    </div>
  );
}
