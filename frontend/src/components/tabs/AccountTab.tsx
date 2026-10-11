import React, { useState } from 'react';
import {
  KeyRound,
  Eye,
  EyeOff,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Globe,
  Fingerprint
} from 'lucide-react';
import type { User } from '../../types';
import { apiFetch } from '../../api';
import { useToast } from '../Toast';

interface AccountTabProps {
  user: User;
  onUserUpdated?: () => void;
}

export const AccountTab: React.FC<AccountTabProps> = ({ user, onUserUpdated }) => {
  const { showToast } = useToast();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMinLength = newPassword.length >= 8;
  const passwordsMatch = newPassword === confirmPassword && confirmPassword.length > 0;
  const canSubmit = currentPassword.length > 0 && isMinLength && passwordsMatch && !isLoading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsLoading(true);
    setError(null);

    try {
      await apiFetch('/api/v1/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });

      showToast('Administrator password updated successfully!', 'success');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      if (onUserUpdated) {
        onUserUpdated();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to update password');
      showToast(err.message || 'Failed to update password', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header Banner */}
      <div>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, margin: '0 0 0.35rem 0', color: 'var(--text-primary)' }}>
          Account & Security
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
          Manage administrator credentials, session authentication, and remote internet exposure safeguards.
        </p>
      </div>

      {/* Warning Banner if using default initial password */}
      {user.is_default_password && (
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '1rem',
          padding: '1.25rem 1.5rem',
          borderRadius: '14px',
          background: 'rgba(245, 158, 11, 0.12)',
          border: '1px solid rgba(245, 158, 11, 0.35)',
          color: '#fef3c7'
        }}>
          <AlertTriangle size={24} color="var(--accent-amber)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--accent-amber)', marginBottom: '0.25rem' }}>
              Default Administrator Password Detected
            </div>
            <div style={{ fontSize: '0.85rem', color: '#fde68a', lineHeight: 1.5 }}>
              Your server is currently configured with the default initial password (<code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px' }}>admin123</code>).
              Before exposing this server to the internet or public IP, please set a strong custom password below to secure your system.
            </div>
          </div>
        </div>
      )}

      {/* Two Column Grid: Password Form & Security Overview */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '1.5rem',
        alignItems: 'start'
      }}>
        {/* Change Password Card */}
        <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <KeyRound size={20} color="var(--brand-primary)" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Update Password
              </h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Salted bcrypt hash stored securely in SQLite
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            {/* Current Password */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Current Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showCurrent ? 'text' : 'password'}
                  className="input"
                  style={{ width: '100%', paddingRight: '2.5rem' }}
                  placeholder="••••••••••••"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent(!showCurrent)}
                  style={{
                    position: 'absolute',
                    right: '0.75rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* New Password */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                New Password (minimum 8 characters)
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showNew ? 'text' : 'password'}
                  className="input"
                  style={{ width: '100%', paddingRight: '2.5rem' }}
                  placeholder="••••••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  style={{
                    position: 'absolute',
                    right: '0.75rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {/* Character length indicator */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                marginTop: '0.4rem',
                fontSize: '0.75rem',
                color: isMinLength ? 'var(--accent-emerald)' : 'var(--text-muted)'
              }}>
                <CheckCircle2 size={12} color={isMinLength ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
                <span>At least 8 characters ({newPassword.length}/8)</span>
              </div>
            </div>

            {/* Confirm New Password */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Confirm New Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showConfirm ? 'text' : 'password'}
                  className="input"
                  style={{ width: '100%', paddingRight: '2.5rem' }}
                  placeholder="••••••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  style={{
                    position: 'absolute',
                    right: '0.75rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {confirmPassword.length > 0 && !passwordsMatch && (
                <div style={{ color: 'var(--accent-rose)', fontSize: '0.75rem', marginTop: '0.4rem' }}>
                  Passwords do not match
                </div>
              )}
            </div>

            {error && (
              <div style={{
                padding: '0.75rem',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.15)',
                color: 'var(--accent-rose)',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <AlertTriangle size={15} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={!canSubmit}
              style={{
                width: '100%',
                padding: '0.8rem',
                marginTop: '0.5rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
            >
              {isLoading ? (
                <>
                  <span className="spinner" style={{ width: '16px', height: '16px' }}></span>
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Lock size={16} />
                  <span>Update Administrator Password</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Security & Remote Hardening Information Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Identity Card */}
          <div className="glass-panel" style={{ padding: '1.5rem', borderRadius: '16px' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Fingerprint size={18} color="var(--brand-primary)" />
              <span>Current Session Identity</span>
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Username</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{user.username}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Role</span>
                <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>System Administrator</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Password Security</span>
                <span style={{ color: user.is_default_password ? 'var(--accent-amber)' : 'var(--accent-emerald)', fontWeight: 600 }}>
                  {user.is_default_password ? 'Default (Needs Update)' : 'Custom Password'}
                </span>
              </div>
            </div>
          </div>

          {/* Remote Exposure Checklist */}
          <div className="glass-panel" style={{ padding: '1.5rem', borderRadius: '16px' }}>
            <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Globe size={18} color="var(--accent-cyan)" />
              <span>Internet Exposure Checklist</span>
            </h3>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', lineHeight: 1.5, margin: '0 0 1rem 0' }}>
              Your server includes built-in safeguards for secure remote management:
            </p>

            <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.82rem', color: '#cbd5e1' }}>
              <li>
                <strong style={{ color: '#fff' }}>Brute-force Throttling:</strong> Failed logins are rate-limited per IP (5 attempts per 5 mins, 15m lockout).
              </li>
              <li>
                <strong style={{ color: '#fff' }}>Security Headers:</strong> HSTS, nosniff, SAMEORIGIN, and permissions policies are injected on every response.
              </li>
              <li>
                <strong style={{ color: '#fff' }}>HttpOnly Cookies:</strong> Session tokens are protected against client-side script inspection (XSS).
              </li>
              <li>
                <strong style={{ color: '#fff' }}>Recommended Reverse Proxy:</strong> When exposing to the internet, put FaceEngine behind Cloudflare Tunnel, Nginx Proxy Manager, or Caddy for automatic TLS/HTTPS.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
