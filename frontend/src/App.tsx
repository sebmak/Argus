import React, { useState, useEffect, useCallback } from 'react';
import { apiFetch, onAuthError } from './api';
import type { User, SystemStats } from './types';
import { ToastProvider, useToast } from './components/Toast';
import { LoginGate } from './components/LoginGate';
import { Header, type TabId } from './components/Header';
import { OverviewTab } from './components/tabs/OverviewTab';
import { ReviewTab } from './components/tabs/ReviewTab';
import { PersonsTab } from './components/tabs/PersonsTab';
import { SandboxTab } from './components/tabs/SandboxTab';
import { RtspTab } from './components/tabs/RtspTab';
import { SettingsTab } from './components/tabs/SettingsTab';
import { GuideTab } from './components/tabs/GuideTab';
import { EventsTab } from './components/tabs/EventsTab';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ScanFace } from 'lucide-react';

const MainAppContent: React.FC = () => {
  const { showToast } = useToast();
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [openAddMemberModal, setOpenAddMemberModal] = useState(false);

  // 1. Initial Authentication Check via Cookie
  const checkSession = useCallback(async () => {
    try {
      const userData = await apiFetch<User>('/api/v1/auth/me');
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setIsInitializing(false);
    }
  }, []);

  // 2. Fetch Global System Telemetry & Statistics
  const fetchStats = useCallback(async () => {
    try {
      const statsData = await apiFetch<SystemStats>('/api/v1/stats');
      setStats(statsData);
    } catch {
      // Ignored if unauthenticated or offline
    }
  }, []);

  useEffect(() => {
    checkSession();

    // Register 401 Interceptor: If any call fails with 401, drop session to show LoginGate
    const unsubscribe = onAuthError(() => {
      setUser(null);
    });

    return () => unsubscribe();
  }, [checkSession]);

  useEffect(() => {
    if (user) {
      fetchStats();

      // Poll telemetry every 8 seconds
      const timer = setInterval(() => {
        fetchStats();
      }, 8000);

      return () => clearInterval(timer);
    }
  }, [user, fetchStats]);

  const handleLogout = async () => {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST' });
      setUser(null);
      showToast('Signed out successfully', 'info');
    } catch (err: any) {
      setUser(null);
    }
  };

  // Boot Splash while verifying existing HttpOnly session cookie
  if (isInitializing) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        background: 'radial-gradient(circle at 50% 30%, #1e1b4b 0%, #090d16 70%)',
        color: '#cbd5e1'
      }}>
        <div style={{
          width: '56px', height: '56px', borderRadius: '16px',
          background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff',
          boxShadow: '0 0 30px rgba(99, 102, 241, 0.4)'
        }}>
          <ScanFace size={32} />
        </div>
        <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>Connecting to Household Vision Engine...</div>
      </div>
    );
  }

  // Authentication Gate: Enforce access restriction unless authenticated
  if (!user) {
    return (
      <LoginGate
        onLoginSuccess={(loggedUser) => {
          setUser(loggedUser);
          showToast(`Welcome back, ${loggedUser.username}!`, 'success');
          fetchStats();
        }}
      />
    );
  }

  return (
    <div style={{ minHeight: '100vh', paddingBottom: '3rem' }}>
      {/* Sticky App Header */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        unrecognizedCount={stats?.unrecognized_count || 0}
        user={user}
        onLogout={handleLogout}
        engineReady={true}
        detectorType={stats?.face_detector_type}
      />

      {/* Main Tab Content Container */}
      <main className="container">
        <ErrorBoundary fallbackTitle={`Error loading ${activeTab.toUpperCase()} tab`}>
          {activeTab === 'overview' && (
            <OverviewTab
              stats={stats}
              onNavigateTab={setActiveTab}
              onAddMember={() => {
                setActiveTab('persons');
                setOpenAddMemberModal(true);
              }}
            />
          )}

          {activeTab === 'review' && (
            <ReviewTab
              onAssignmentComplete={fetchStats}
            />
          )}

          {activeTab === 'persons' && (
            <PersonsTab
              onRefreshStats={fetchStats}
              openAddModal={openAddMemberModal}
              onCloseAddModal={() => setOpenAddMemberModal(false)}
            />
          )}

          {activeTab === 'sandbox' && (
            <SandboxTab />
          )}

          {activeTab === 'rtsp' && (
            <RtspTab />
          )}

          {activeTab === 'events' && (
            <EventsTab />
          )}

          {activeTab === 'settings' && (
            <SettingsTab onSettingsSaved={fetchStats} />
          )}

          {activeTab === 'guide' && (
            <GuideTab />
          )}
        </ErrorBoundary>
      </main>
    </div>
  );
};

export default function App() {
  return (
    <ToastProvider>
      <MainAppContent />
    </ToastProvider>
  );
}
