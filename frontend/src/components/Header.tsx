import React from 'react';
import {
  LayoutDashboard,
  Inbox,
  Users,
  FlaskConical,
  Radio,
  Settings,
  BookOpen,
  LogOut,
  UserCheck,
  ScrollText
} from 'lucide-react';
import type { User as UserType } from '../types';
import { getPathForTab } from '../router';

export type TabId = 'overview' | 'review' | 'persons' | 'sandbox' | 'rtsp' | 'events' | 'settings' | 'guide';

interface HeaderProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  unrecognizedCount: number;
  user: UserType;
  onLogout: () => void;
  engineReady?: boolean;
  detectorType?: string;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  unrecognizedCount,
  user,
  onLogout,
  engineReady = true,
  detectorType,
}) => {
  const navTabs: { id: TabId; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: 'overview', label: 'Dashboard', icon: <LayoutDashboard size={16} /> },
    {
      id: 'review',
      label: 'Review Queue',
      icon: <Inbox size={16} />,
      badge: unrecognizedCount > 0 ? unrecognizedCount : undefined,
    },
    { id: 'persons', label: 'Household', icon: <Users size={16} /> },
    { id: 'sandbox', label: 'Test Sandbox', icon: <FlaskConical size={16} /> },
    { id: 'rtsp', label: 'RTSP & MQTT', icon: <Radio size={16} /> },
    { id: 'events', label: 'Event Log', icon: <ScrollText size={16} /> },
    { id: 'settings', label: 'Settings', icon: <Settings size={16} /> },
    { id: 'guide', label: 'Integrations', icon: <BookOpen size={16} /> },
  ];

  return (
    <header className="glass-panel" style={{
      position: 'sticky',
      top: '1rem',
      zIndex: 100,
      margin: '0 auto 1.5rem',
      maxWidth: '1440px',
      borderRadius: 'var(--radius-lg)',
      padding: '0.75rem 1.25rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '1rem',
      flexWrap: 'wrap'
    }}>
      {/* Brand & Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <a
          href={getPathForTab('overview')}
          onClick={(e) => {
            if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
              e.preventDefault();
              onTabChange('overview');
            }
          }}
          style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer' }}
        >
          <img
            src="/favicon.png"
            alt="FaceEngine Logo"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              objectFit: 'cover',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.45)',
              border: '1px solid rgba(99, 102, 241, 0.35)'
            }}
          />
          <div>
            <div className="brand-title" style={{ fontSize: '1.1rem', fontWeight: 800, lineHeight: 1.1 }}>
              FaceEngine
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Household Vision
            </div>
          </div>
        </a>

        {/* Engine Readiness & Detector Engine Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <div className="chip chip-success" style={{ padding: '0.25rem 0.6rem' }}>
            <span className="pulsing-dot" />
            <span>{engineReady ? 'Engine Ready' : 'Warming Up'}</span>
          </div>
          {detectorType && (
            <a
              href={getPathForTab('settings')}
              className="chip chip-purple"
              style={{
                padding: '0.25rem 0.65rem',
                fontWeight: 600,
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                textDecoration: 'none',
              }}
              onClick={(e) => {
                if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
                  e.preventDefault();
                  onTabChange('settings');
                }
              }}
              title={`Active Detector Engine: ${detectorType === 'yolov8_face' ? 'YOLOv8-Face' : detectorType}. Click to configure in Settings.`}
            >
              <span>{detectorType === 'yolov8_face' ? 'YOLOv8-Face' : (detectorType === 'scrfd' ? 'SCRFD' : detectorType)}</span>
            </a>
          )}
        </div>
      </div>

      {/* Main Tabs Navigation */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', overflowX: 'auto', padding: '0.25rem 0' }}>
        {navTabs.map(tab => {
          const isActive = activeTab === tab.id;
          const href = getPathForTab(tab.id);
          return (
            <a
              key={tab.id}
              href={href}
              onClick={(e) => {
                if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
                  e.preventDefault();
                  onTabChange(tab.id);
                }
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.55rem 0.9rem',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
                fontWeight: isActive ? 700 : 500,
                color: isActive ? '#fff' : 'var(--text-muted)',
                background: isActive ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(147, 51, 234, 0.25) 100%)' : 'transparent',
                border: isActive ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                whiteSpace: 'nowrap',
                textDecoration: 'none',
              }}
              onMouseEnter={e => {
                if (!isActive) e.currentTarget.style.color = 'var(--text-main)';
              }}
              onMouseLeave={e => {
                if (!isActive) e.currentTarget.style.color = 'var(--text-muted)';
              }}
            >
              {tab.icon}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span style={{
                  background: 'var(--accent-amber)',
                  color: '#000',
                  fontSize: '0.65rem',
                  fontWeight: 800,
                  padding: '1px 6px',
                  borderRadius: '10px',
                  lineHeight: '1.2'
                }}>
                  {tab.badge}
                </span>
              )}
            </a>
          );
        })}
      </nav>

      {/* User Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div className="chip" style={{ background: 'rgba(255, 255, 255, 0.05)', color: '#cbd5e1' }}>
          <UserCheck size={14} color="var(--accent-emerald)" />
          <span>{user.username}</span>
        </div>

        <button
          onClick={onLogout}
          className="btn btn-secondary btn-sm"
          title="Sign out of administrative session"
          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
        >
          <LogOut size={14} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
};
