import React, { useState, useEffect, useCallback } from 'react';
import {
  ScrollText,
  Activity,
  AlertOctagon,
  CheckCircle2,
  AlertTriangle,
  Info,
  RefreshCw,
  Trash2,
  Download,
  Search,
  ChevronDown,
  ChevronRight,
  Radio,
  Send,
  Zap,
  Moon,
  Users,
  Layers,
  Clock,
  X
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { EventLog, EventLogSummary, RtspStatus } from '../../types';
import { useToast } from '../Toast';

type CategoryFilter = 'all' | 'motion' | 'detection' | 'webhook' | 'mqtt' | 'error' | 'system';
type LevelFilter = 'all' | 'info' | 'success' | 'warning' | 'error';
type RefreshInterval = 0 | 3000 | 5000 | 10000;

function formatTimeAgo(tsString: string): string {
  try {
    const d = new Date(tsString.endsWith('Z') ? tsString : `${tsString}Z`);
    const diffSec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
    if (diffSec < 5) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return tsString;
  }
}

function formatFullDate(tsString: string): string {
  try {
    const d = new Date(tsString.endsWith('Z') ? tsString : `${tsString}Z`);
    return d.toLocaleString();
  } catch {
    return tsString;
  }
}

export const EventsTab: React.FC = () => {
  const { showToast } = useToast();

  // State
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<EventLogSummary | null>(null);
  const [rtspStatus, setRtspStatus] = useState<RtspStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filters & Pagination
  const [selectedCategory, setSelectedCategory] = useState<CategoryFilter>('all');
  const [selectedLevel, setSelectedLevel] = useState<LevelFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [autoRefresh, setAutoRefresh] = useState<RefreshInterval>(3000);

  // UI state
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [previewThumbnail, setPreviewThumbnail] = useState<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Fetch Event Logs
  const fetchLogs = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    else setIsRefreshing(true);

    try {
      const offset = (page - 1) * pageSize;
      const params = new URLSearchParams();
      params.set('limit', String(pageSize));
      params.set('offset', String(offset));
      if (selectedCategory !== 'all') params.set('category', selectedCategory);
      if (selectedLevel !== 'all') params.set('level', selectedLevel);
      if (debouncedSearch) params.set('search', debouncedSearch);

      const res = await apiFetch<{ total: number; logs: EventLog[] }>(`/api/v1/events/logs?${params.toString()}`);
      setLogs(res.logs || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      if (!silent) {
        showToast(err.message || 'Failed to fetch event logs', 'error');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [page, pageSize, selectedCategory, selectedLevel, debouncedSearch, showToast]);

  // Fetch Telemetry Summary & RTSP Status
  const fetchTelemetry = useCallback(async () => {
    try {
      const [sumData, rtspData] = await Promise.all([
        apiFetch<EventLogSummary>('/api/v1/events/summary').catch(() => null),
        apiFetch<RtspStatus>('/api/v1/rtsp/status').catch(() => null),
      ]);
      if (sumData) setSummary(sumData);
      if (rtspData) setRtspStatus(rtspData);
    } catch {
      // Ignore background telemetry errors
    }
  }, []);

  // Initial load and filter change
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    fetchTelemetry();
  }, [fetchTelemetry]);

  // Auto-refresh timer
  useEffect(() => {
    if (autoRefresh === 0) return;
    const interval = setInterval(() => {
      fetchLogs(true);
      fetchTelemetry();
    }, autoRefresh);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogs, fetchTelemetry]);

  // Actions
  const handleClearLogs = async () => {
    setIsClearing(true);
    try {
      const body = selectedCategory !== 'all' ? { category: selectedCategory } : {};
      await apiFetch('/api/v1/events/logs', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      showToast(
        selectedCategory !== 'all' ? `Cleared '${selectedCategory}' events` : 'All event logs cleared',
        'success'
      );
      setShowClearModal(false);
      fetchLogs();
      fetchTelemetry();
    } catch (err: any) {
      showToast(err.message || 'Failed to clear logs', 'error');
    } finally {
      setIsClearing(false);
    }
  };

  const handleExportJson = () => {
    const params = new URLSearchParams();
    if (selectedCategory !== 'all') params.set('category', selectedCategory);
    if (selectedLevel !== 'all') params.set('level', selectedLevel);
    window.open(`/api/v1/events/export?${params.toString()}`, '_blank');
  };

  // Category Icon & Color Mapping
  const getCategoryMeta = (category: string, eventType: string) => {
    switch (category) {
      case 'motion':
        if (eventType === 'motion_idle') {
          return {
            label: 'Idle Mode',
            icon: <Moon size={14} />,
            color: '#94a3b8',
            bg: 'rgba(148, 163, 184, 0.12)',
            border: 'rgba(148, 163, 184, 0.3)',
          };
        }
        return {
          label: 'Motion Active',
          icon: <Zap size={14} />,
          color: '#38bdf8',
          bg: 'rgba(56, 189, 248, 0.12)',
          border: 'rgba(56, 189, 248, 0.35)',
        };
      case 'detection':
        if (eventType === 'detection_matched') {
          return {
            label: 'Face Matched',
            icon: <Users size={14} />,
            color: '#10b981',
            bg: 'rgba(16, 185, 129, 0.12)',
            border: 'rgba(16, 185, 129, 0.35)',
          };
        }
        return {
          label: 'Unrecognized',
          icon: <AlertTriangle size={14} />,
          color: '#f59e0b',
          bg: 'rgba(245, 158, 11, 0.12)',
          border: 'rgba(245, 158, 11, 0.35)',
        };
      case 'webhook':
        return {
          label: eventType === 'webhook_received' ? 'Protect Webhook' : 'Outgoing Webhook',
          icon: <Send size={14} />,
          color: '#818cf8',
          bg: 'rgba(129, 140, 248, 0.12)',
          border: 'rgba(129, 140, 248, 0.35)',
        };
      case 'mqtt':
        return {
          label: 'MQTT Broadcast',
          icon: <Radio size={14} />,
          color: '#fb923c',
          bg: 'rgba(251, 146, 60, 0.12)',
          border: 'rgba(251, 146, 60, 0.35)',
        };
      case 'error':
        return {
          label: 'Error',
          icon: <AlertOctagon size={14} />,
          color: '#f43f5e',
          bg: 'rgba(244, 63, 94, 0.15)',
          border: 'rgba(244, 63, 94, 0.4)',
        };
      case 'system':
      default:
        return {
          label: 'System',
          icon: <Activity size={14} />,
          color: '#a78bfa',
          bg: 'rgba(167, 139, 250, 0.12)',
          border: 'rgba(167, 139, 250, 0.3)',
        };
    }
  };

  const getLevelBadge = (level: string) => {
    switch (level) {
      case 'error':
        return { text: 'ERROR', color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.15)', icon: <AlertOctagon size={12} /> };
      case 'warning':
        return { text: 'WARN', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)', icon: <AlertTriangle size={12} /> };
      case 'success':
        return { text: 'SUCCESS', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)', icon: <CheckCircle2 size={12} /> };
      case 'info':
      default:
        return { text: 'INFO', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)', icon: <Info size={12} /> };
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 1. Header Banner & Telemetry Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))',
        gap: '1rem',
      }}>
        {/* Stream Motion State Card */}
        <div className="glass-panel" style={{ padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '0.05em' }}>
              Motion Gating State
            </span>
            <div style={{
              width: '28px', height: '28px', borderRadius: '8px',
              background: rtspStatus?.motion_detected ? 'rgba(56, 189, 248, 0.15)' : 'rgba(148, 163, 184, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: rtspStatus?.motion_detected ? '#38bdf8' : '#94a3b8'
            }}>
              {rtspStatus?.motion_detected ? <Zap size={16} /> : <Moon size={16} />}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <span style={{
              width: '10px', height: '10px', borderRadius: '50%',
              background: rtspStatus?.motion_detected ? '#38bdf8' : '#94a3b8',
              boxShadow: rtspStatus?.motion_detected ? '0 0 10px #38bdf8' : 'none',
              display: 'inline-block',
            }} />
            <span style={{ fontSize: '1.2rem', fontWeight: 800, color: rtspStatus?.motion_detected ? '#38bdf8' : '#cbd5e1' }}>
              {rtspStatus?.is_running
                ? (rtspStatus.motion_detected ? 'Active Motion' : 'Idle (Motionless)')
                : 'Stream Stopped'}
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {rtspStatus?.motion_gating_enabled ? 'CPU saving motion gating enabled' : 'Continuous inference active'}
          </div>
        </div>

        {/* Detections Today Card */}
        <div
          className="glass-panel"
          style={{ padding: '1.25rem', cursor: 'pointer', transition: 'all 0.2s ease' }}
          onClick={() => { setSelectedCategory('detection'); setPage(1); }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '0.05em' }}>
              Detections Today
            </span>
            <div style={{
              width: '28px', height: '28px', borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#10b981'
            }}>
              <Users size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981', lineHeight: 1.1 }}>
            {summary?.detections_today ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Recognized & unrecognized faces
          </div>
        </div>

        {/* Broadcasts Today Card */}
        <div
          className="glass-panel"
          style={{ padding: '1.25rem', cursor: 'pointer', transition: 'all 0.2s ease' }}
          onClick={() => { setSelectedCategory('webhook'); setPage(1); }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '0.05em' }}>
              Broadcasts Dispatched
            </span>
            <div style={{
              width: '28px', height: '28px', borderRadius: '8px',
              background: 'rgba(129, 140, 248, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#818cf8'
            }}>
              <Send size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#818cf8', lineHeight: 1.1 }}>
            {summary?.broadcasts_today ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Webhook POSTs & MQTT publishes
          </div>
        </div>

        {/* 24h Errors Card */}
        <div
          className="glass-panel"
          style={{
            padding: '1.25rem',
            cursor: 'pointer',
            borderColor: (summary?.error_count_24h || 0) > 0 ? 'rgba(244, 63, 94, 0.4)' : undefined
          }}
          onClick={() => { setSelectedLevel('error'); setPage(1); }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '0.05em' }}>
              Errors (Past 24h)
            </span>
            <div style={{
              width: '28px', height: '28px', borderRadius: '8px',
              background: (summary?.error_count_24h || 0) > 0 ? 'rgba(244, 63, 94, 0.2)' : 'rgba(16, 185, 129, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: (summary?.error_count_24h || 0) > 0 ? '#f43f5e' : '#10b981'
            }}>
              {(summary?.error_count_24h || 0) > 0 ? <AlertOctagon size={16} /> : <CheckCircle2 size={16} />}
            </div>
          </div>
          <div style={{
            fontSize: '1.8rem',
            fontWeight: 800,
            color: (summary?.error_count_24h || 0) > 0 ? '#f43f5e' : '#10b981',
            lineHeight: 1.1
          }}>
            {summary?.error_count_24h ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {(summary?.error_count_24h || 0) > 0 ? 'Click to inspect failure logs' : 'All systems operating cleanly'}
          </div>
        </div>
      </div>

      {/* 2. Control Toolbar: Filters, Search, Auto-Refresh & Actions */}
      <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1rem',
        }}>
          {/* Category Tabs */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            overflowX: 'auto',
            paddingBottom: '0.25rem',
            maxWidth: '100%',
          }}>
            {[
              { id: 'all', label: 'All Events', icon: <Layers size={14} /> },
              { id: 'motion', label: 'Motion & Idle', icon: <Zap size={14} /> },
              { id: 'detection', label: 'Detections', icon: <Users size={14} /> },
              { id: 'webhook', label: 'Webhooks', icon: <Send size={14} /> },
              { id: 'mqtt', label: 'MQTT', icon: <Radio size={14} /> },
              { id: 'error', label: 'Errors', icon: <AlertOctagon size={14} /> },
              { id: 'system', label: 'System', icon: <Activity size={14} /> },
            ].map((cat) => {
              const isActive = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => { setSelectedCategory(cat.id as CategoryFilter); setPage(1); }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    padding: '0.45rem 0.85rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: '1px solid',
                    borderColor: isActive ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.08)',
                    background: isActive ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.3) 0%, rgba(99, 102, 241, 0.1) 100%)' : 'rgba(255, 255, 255, 0.03)',
                    color: isActive ? '#fff' : 'var(--text-muted)',
                    transition: 'all 0.15s ease',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {cat.icon}
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>

          {/* Action Buttons: Export & Clear */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem' }}
              onClick={handleExportJson}
              title="Download event logs as JSON"
            >
              <Download size={14} />
              <span>Export</span>
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem', color: '#f43f5e' }}
              onClick={() => setShowClearModal(true)}
              title="Clear event logs"
            >
              <Trash2 size={14} />
              <span>Clear</span>
            </button>
          </div>
        </div>

        {/* Secondary Toolbar: Level filter, Search bar, and Auto-refresh control */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '0.75rem'
        }}>
          {/* Search Input */}
          <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: '380px' }}>
            <Search size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search event messages, persons, cameras..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '0.45rem 2rem 0.45rem 2.2rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                background: 'rgba(9, 13, 22, 0.6)',
                color: '#fff',
                fontSize: '0.825rem',
                outline: 'none',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute', right: '0.6rem', top: '50%', transform: 'translateY(-50%)',
                  background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer'
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Level Filter Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>Severity:</span>
            <select
              value={selectedLevel}
              onChange={(e) => { setSelectedLevel(e.target.value as LevelFilter); setPage(1); }}
              style={{
                padding: '0.4rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                background: 'rgba(9, 13, 22, 0.6)',
                color: 'var(--text-main)',
                fontSize: '0.8rem',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="all">All Levels</option>
              <option value="info">Info</option>
              <option value="success">Success</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </div>

          {/* Live Auto-Refresh & Manual Refresh */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>Refresh:</span>
              <select
                value={autoRefresh}
                onChange={(e) => setAutoRefresh(Number(e.target.value) as RefreshInterval)}
                style={{
                  padding: '0.4rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  background: 'rgba(9, 13, 22, 0.6)',
                  color: 'var(--text-main)',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value={3000}>Live (3s)</option>
                <option value={5000}>5s</option>
                <option value={10000}>10s</option>
                <option value={0}>Paused</option>
              </select>
            </div>

            <button
              className="btn btn-secondary"
              style={{ padding: '0.45rem', borderRadius: 'var(--radius-sm)' }}
              onClick={() => { fetchLogs(true); fetchTelemetry(); }}
              title="Refresh now"
              disabled={isRefreshing}
            >
              <RefreshCw size={14} className={isRefreshing ? 'spin' : ''} />
            </button>
          </div>
        </div>
      </div>

      {/* 3. Event Log Feed */}
      <div className="glass-panel" style={{ padding: '0.5rem', overflow: 'hidden' }}>
        {isLoading && logs.length === 0 ? (
          <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <RefreshCw size={28} className="spin" style={{ margin: '0 auto 1rem', color: 'var(--accent-primary)' }} />
            <div>Loading event logs...</div>
          </div>
        ) : logs.length === 0 ? (
          <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <ScrollText size={36} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
            <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.25rem' }}>
              No Events Recorded Yet
            </div>
            <div style={{ fontSize: '0.85rem', maxWidth: '400px', margin: '0 auto' }}>
              {debouncedSearch || selectedCategory !== 'all' || selectedLevel !== 'all'
                ? 'No events match the current filter criteria. Try resetting filters.'
                : 'Operational events like motion gating, detections, webhooks, and MQTT broadcasts will appear here in real-time.'}
            </div>
            {(debouncedSearch || selectedCategory !== 'all' || selectedLevel !== 'all') && (
              <button
                className="btn btn-secondary"
                style={{ marginTop: '1rem', padding: '0.45rem 1rem' }}
                onClick={() => {
                  setSelectedCategory('all');
                  setSelectedLevel('all');
                  setSearchQuery('');
                  setPage(1);
                }}
              >
                Reset All Filters
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {logs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              const catMeta = getCategoryMeta(log.category, log.event_type);
              const lvlMeta = getLevelBadge(log.level);
              const thumbUrl = log.details?.thumbnail_url || (log.details?.thumbnail ? `/api/v1/thumbnails/${log.details.thumbnail}` : null);

              return (
                <div
                  key={log.id}
                  className="glass-card"
                  style={{
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden',
                    borderColor: isExpanded ? 'var(--border-accent)' : undefined,
                    transition: 'all 0.15s ease',
                  }}
                >
                  {/* Main Event Row */}
                  <div
                    onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                    style={{
                      padding: '0.75rem 1rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.85rem',
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                  >
                    {/* Expand Chevron */}
                    <div style={{ color: 'var(--text-dim)', display: 'flex', alignItems: 'center' }}>
                      {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    </div>

                    {/* Category Badge */}
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      padding: '0.2rem 0.55rem',
                      borderRadius: 'var(--radius-xs)',
                      background: catMeta.bg,
                      color: catMeta.color,
                      border: `1px solid ${catMeta.border}`,
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      whiteSpace: 'nowrap',
                      minWidth: '115px',
                    }}>
                      {catMeta.icon}
                      <span>{catMeta.label}</span>
                    </div>

                    {/* Level Pill */}
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      padding: '0.15rem 0.45rem',
                      borderRadius: 'var(--radius-xs)',
                      background: lvlMeta.bg,
                      color: lvlMeta.color,
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      letterSpacing: '0.04em',
                    }}>
                      {lvlMeta.icon}
                      <span>{lvlMeta.text}</span>
                    </div>

                    {/* Message */}
                    <div style={{ flex: 1, fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-main)', wordBreak: 'break-word' }}>
                      {log.message}
                    </div>

                    {/* Optional Thumbnail preview */}
                    {thumbUrl && (
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          setPreviewThumbnail(thumbUrl);
                        }}
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '6px',
                          overflow: 'hidden',
                          border: '1px solid var(--border-accent)',
                          flexShrink: 0,
                          cursor: 'zoom-in',
                        }}
                        title="Click to zoom face crop"
                      >
                        <img src={thumbUrl} alt="Crop" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      </div>
                    )}

                    {/* Timestamp */}
                    <div
                      style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-dim)',
                        whiteSpace: 'nowrap',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}
                      title={formatFullDate(log.timestamp)}
                    >
                      <Clock size={12} />
                      <span>{formatTimeAgo(log.timestamp)}</span>
                    </div>
                  </div>

                  {/* Expanded Details Drawer */}
                  {isExpanded && (
                    <div style={{
                      borderTop: '1px solid var(--border-subtle)',
                      background: 'rgba(9, 13, 22, 0.4)',
                      padding: '1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.75rem',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-dim)', letterSpacing: '0.05em' }}>
                          Payload Details & Metadata
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                          ID: <code style={{ color: 'var(--accent-sky)' }}>{log.id}</code> · Recorded: {formatFullDate(log.timestamp)}
                        </span>
                      </div>

                      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        {thumbUrl && (
                          <div style={{
                            width: '90px',
                            height: '90px',
                            borderRadius: '8px',
                            overflow: 'hidden',
                            border: '1px solid var(--border-accent)',
                            flexShrink: 0
                          }}>
                            <img src={thumbUrl} alt="Detection" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          </div>
                        )}
                        <pre style={{
                          flex: 1,
                          minWidth: '260px',
                          background: 'rgba(0, 0, 0, 0.4)',
                          padding: '0.75rem',
                          borderRadius: '8px',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          fontSize: '0.75rem',
                          color: '#e2e8f0',
                          overflowX: 'auto',
                          fontFamily: 'monospace',
                          lineHeight: 1.4
                        }}>
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* 4. Pagination Footer */}
        {total > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
            padding: '1rem 0.5rem 0.5rem',
            borderTop: '1px solid var(--border-subtle)',
            marginTop: '0.5rem',
          }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
              Showing {Math.min((page - 1) * pageSize + 1, total)} to {Math.min(page * pageSize, total)} of {total} events
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                style={{
                  padding: '0.3rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                  background: 'rgba(9, 13, 22, 0.6)',
                  color: 'var(--text-main)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value={25}>25 / page</option>
                <option value={50}>50 / page</option>
                <option value={100}>100 / page</option>
              </select>

              <button
                className="btn btn-secondary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>

              <span style={{ fontSize: '0.8rem', color: 'var(--text-main)', padding: '0 0.25rem' }}>
                Page {page} of {totalPages}
              </span>

              <button
                className="btn btn-secondary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Clearing Logs */}
      {showClearModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '1rem',
        }}>
          <div className="glass-panel" style={{
            maxWidth: '440px',
            width: '100%',
            padding: '1.75rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <div style={{
                width: '38px', height: '38px', borderRadius: '10px',
                background: 'rgba(244, 63, 94, 0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#f43f5e'
              }}>
                <Trash2 size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 800 }}>Clear Event Logs</h3>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {selectedCategory !== 'all' ? `Clearing only '${selectedCategory}' category events` : 'Clearing all recorded logs'}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '1.5rem' }}>
              Are you sure you want to clear these event logs? This will purge historical operational records from SQLite. Core household models and persons will remain unaffected.
            </p>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowClearModal(false)}
                disabled={isClearing}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleClearLogs}
                disabled={isClearing}
              >
                {isClearing ? 'Clearing...' : 'Yes, Clear Logs'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Full Thumbnail Zoom Modal */}
      {previewThumbnail && (
        <div
          onClick={() => setPreviewThumbnail(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(10px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            cursor: 'zoom-out',
            padding: '2rem',
          }}
        >
          <div style={{ maxWidth: '400px', maxHeight: '400px', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--border-accent)', boxShadow: '0 20px 50px rgba(0,0,0,0.8)' }}>
            <img src={previewThumbnail} alt="Face Preview" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
        </div>
      )}
    </div>
  );
};
