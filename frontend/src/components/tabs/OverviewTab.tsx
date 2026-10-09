import React from 'react';
import {
  Users,
  Database,
  Inbox,
  CheckCircle2,
  Cpu,
  ArrowRight,
  PlusCircle,
  FlaskConical,
  Radio,
  ExternalLink
} from 'lucide-react';
import type { SystemStats } from '../../types';
import type { TabId } from '../Header';

interface OverviewTabProps {
  stats: SystemStats | null;
  onNavigateTab: (tab: TabId) => void;
  onAddMember: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  stats,
  onNavigateTab,
  onAddMember,
}) => {
  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 4 Core Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
        {/* Total Members */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)'
          }}>
            <Users size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Household Members</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {stats ? stats.total_persons : '...'}
            </div>
          </div>
        </div>

        {/* Total Face Samples */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-sky)'
          }}>
            <Database size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Learned Embeddings</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {stats ? stats.total_samples : '...'}
            </div>
          </div>
        </div>

        {/* Unrecognized Faces Queue */}
        <div
          className="glass-panel"
          style={{
            padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem',
            cursor: 'pointer',
            borderColor: stats && stats.unrecognized_count > 0 ? 'rgba(245, 158, 11, 0.4)' : undefined
          }}
          onClick={() => onNavigateTab('review')}
        >
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-amber)'
          }}>
            <Inbox size={24} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Review Queue</span>
              {stats && stats.unrecognized_count > 0 && (
                <span className="chip chip-warning" style={{ fontSize: '0.65rem' }}>Action Needed</span>
              )}
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: stats && stats.unrecognized_count > 0 ? 'var(--accent-amber)' : '#fff', lineHeight: 1.1 }}>
              {stats ? stats.unrecognized_count : '...'}
            </div>
          </div>
        </div>

        {/* Recognition Accuracy */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-emerald)'
          }}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Accuracy Rate</div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)', lineHeight: 1.1 }}>
              {stats ? `${stats.accuracy_rate}%` : '...'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Overview Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {/* Recent Activity Feed */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Recent Detection Feed</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Latest camera arrivals and verified faces</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigateTab('review')}>
              View All <ArrowRight size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1 }}>
            {!stats || !stats.recent_activity || stats.recent_activity.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-dim)', fontSize: '0.875rem' }}>
                No recent face detections recorded yet. Stream camera or test via Sandbox.
              </div>
            ) : (
              stats.recent_activity.slice(0, 6).map(act => (
                <div
                  key={act.id}
                  className="glass-card"
                  style={{
                    padding: '0.75rem 1rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                  }}
                >
                  <img
                    src={act.thumbnail_url || `/api/v1/thumbnails/${act.thumbnail_path}`}
                    alt="Detection crop"
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '8px',
                      objectFit: 'cover',
                      border: `1px solid ${act.status === 'matched' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`
                    }}
                    onError={e => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#fff' }}>
                        {act.matched_name || 'Unrecognized Face'}
                      </span>
                      <span className={`chip ${act.status === 'matched' ? 'chip-success' : 'chip-warning'}`} style={{ fontSize: '0.65rem' }}>
                        {act.status === 'matched' ? `${Math.round((act.similarity || 0) * 100)}% match` : 'Unknown'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {act.camera_id || 'Front Door'} • {new Date(act.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Engine Telemetry & Quick Launch */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Quick Actions Panel */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '0.35rem' }}>Quick Actions</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
              Common administrative workflows and camera operations
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
              <button
                className="btn btn-primary"
                style={{ justifyContent: 'flex-start', padding: '0.85rem 1rem' }}
                onClick={onAddMember}
              >
                <PlusCircle size={18} />
                <span>Add Member</span>
              </button>

              <button
                className="btn btn-secondary"
                style={{ justifyContent: 'flex-start', padding: '0.85rem 1rem' }}
                onClick={() => onNavigateTab('sandbox')}
              >
                <FlaskConical size={18} />
                <span>Test Sandbox</span>
              </button>

              <button
                className="btn btn-secondary"
                style={{ justifyContent: 'flex-start', padding: '0.85rem 1rem' }}
                onClick={() => onNavigateTab('rtsp')}
              >
                <Radio size={18} />
                <span>Camera Stream</span>
              </button>
            </div>
          </div>

          {/* Vision Engine Architecture Card */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <Cpu size={20} color="var(--accent-primary)" />
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Inference Engine Telemetry</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ArcFace Buffalo_L &amp; RetinaFace CPU Pipeline</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Embedding Dimension</span>
                <span style={{ fontWeight: 600, fontFamily: 'JetBrains Mono, monospace' }}>512-D Normalized Vector</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Active Resolution Mode</span>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>320px Low-Latency (~20-50ms)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Unraid Thread Optimization</span>
                <span style={{ fontWeight: 600 }}>Active (8 Cores Reserved)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>API Documentation</span>
                <a
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: 'var(--accent-sky)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', textDecoration: 'none' }}
                >
                  Interactive Swagger <ExternalLink size={12} />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
