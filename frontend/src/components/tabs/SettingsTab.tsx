import React, { useState, useEffect } from 'react';
import {
  Settings,
  Sliders,
  Bell,
  Database,
  Save,
  RotateCcw,
  History,
  ArrowUpRight,
  Zap
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { SystemSettings, MigrationStatus } from '../../types';
import { useToast } from '../Toast';

interface SettingsTabProps {
  onSettingsSaved?: () => void;
}

export const SettingsTab: React.FC<SettingsTabProps> = ({ onSettingsSaved }) => {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Recognition Settings State
  const [faceDetectorType, setFaceDetectorType] = useState('yolov8_face');
  const [detectionConfidence, setDetectionConfidence] = useState(0.6);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.45);
  const [detSize, setDetSize] = useState(320);
  const [ortThreads, setOrtThreads] = useState(8);
  const [maxSamples, setMaxSamples] = useState(25);
  const [trackWindowSeconds, setTrackWindowSeconds] = useState(15);
  const [motionGatingEnabled, setMotionGatingEnabled] = useState(true);
  const [motionThreshold, setMotionThreshold] = useState(0.015);

  // Notification Thresholds
  const [notificationThreshold, setNotificationThreshold] = useState(0.65);
  const [notifyOnUnknown, setNotifyOnUnknown] = useState(true);
  const [unknownMinConfidence, setUnknownMinConfidence] = useState(0.7);
  const [webhookOnlyKnown, setWebhookOnlyKnown] = useState(true);
  const [mqttOnlyKnown, setMqttOnlyKnown] = useState(true);

  // Migration Telemetry & Rollback State
  const [migrationStatus, setMigrationStatus] = useState<MigrationStatus | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState('1.0.0');
  const [migrating, setMigrating] = useState(false);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const [settingsRes, migrationRes] = await Promise.all([
        apiFetch<SystemSettings>('/api/v1/settings'),
        apiFetch<MigrationStatus>('/api/v1/settings/migrations')
      ]);

      if (settingsRes.face_detector_type) setFaceDetectorType(settingsRes.face_detector_type);
      if (settingsRes.detection_confidence !== undefined) setDetectionConfidence(settingsRes.detection_confidence);
      if (settingsRes.similarity_threshold !== undefined) setSimilarityThreshold(settingsRes.similarity_threshold);
      if (settingsRes.det_size !== undefined) setDetSize(settingsRes.det_size);
      if (settingsRes.ort_num_threads !== undefined) setOrtThreads(settingsRes.ort_num_threads);
      if (settingsRes.max_samples_per_person !== undefined) setMaxSamples(settingsRes.max_samples_per_person);
      if (settingsRes.unrecognized_track_window_seconds !== undefined) setTrackWindowSeconds(settingsRes.unrecognized_track_window_seconds);
      if (settingsRes.rtsp_motion_gating_enabled !== undefined) setMotionGatingEnabled(settingsRes.rtsp_motion_gating_enabled);
      if (settingsRes.rtsp_motion_threshold !== undefined) setMotionThreshold(settingsRes.rtsp_motion_threshold);

      if (settingsRes.notification_threshold !== undefined) setNotificationThreshold(settingsRes.notification_threshold);
      if (settingsRes.notify_on_unknown !== undefined) setNotifyOnUnknown(settingsRes.notify_on_unknown);
      if (settingsRes.unknown_min_confidence !== undefined) setUnknownMinConfidence(settingsRes.unknown_min_confidence);
      if (settingsRes.webhook_only_known_faces !== undefined) setWebhookOnlyKnown(settingsRes.webhook_only_known_faces);
      if (settingsRes.mqtt_only_known_faces !== undefined) setMqttOnlyKnown(settingsRes.mqtt_only_known_faces);

      setMigrationStatus(migrationRes);
    } catch (err: any) {
      showToast(err.message || 'Failed to load system settings', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: Partial<SystemSettings> = {
        face_detector_type: faceDetectorType,
        detection_confidence: detectionConfidence,
        similarity_threshold: similarityThreshold,
        det_size: detSize,
        ort_num_threads: ortThreads,
        max_samples_per_person: maxSamples,
        unrecognized_track_window_seconds: trackWindowSeconds,
        rtsp_motion_gating_enabled: motionGatingEnabled,
        rtsp_motion_threshold: motionThreshold,
        notification_threshold: notificationThreshold,
        notify_on_unknown: notifyOnUnknown,
        unknown_min_confidence: unknownMinConfidence,
        webhook_only_known_faces: webhookOnlyKnown,
        mqtt_only_known_faces: mqttOnlyKnown
      };

      await apiFetch('/api/v1/settings', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      showToast('Settings saved to database and applied to live runtime!', 'success');
      onSettingsSaved?.();
    } catch (err: any) {
      showToast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleRollForward = async () => {
    setMigrating(true);
    try {
      const res = await apiFetch<{ status: string; applied_count: number; message: string }>('/api/v1/settings/migrations/forward', {
        method: 'POST',
        body: JSON.stringify({})
      });
      showToast(res.message || `Applied ${res.applied_count} forward migrations`, 'success');
      const updated = await apiFetch<MigrationStatus>('/api/v1/settings/migrations');
      setMigrationStatus(updated);
    } catch (err: any) {
      showToast(err.message || 'Roll forward failed', 'error');
    } finally {
      setMigrating(false);
    }
  };

  const handleRollback = async () => {
    if (!confirm(`Confirm non-destructive schema rollback to version '${rollbackTarget}'? A backup will be taken automatically.`)) {
      return;
    }

    setMigrating(true);
    try {
      const res = await apiFetch<{ status: string; reverted_count: number; message: string }>('/api/v1/settings/migrations/rollback', {
        method: 'POST',
        body: JSON.stringify({ target_version: rollbackTarget })
      });
      showToast(res.message || `Rolled back ${res.reverted_count} migrations safely`, 'info');
      const updated = await apiFetch<MigrationStatus>('/api/v1/settings/migrations');
      setMigrationStatus(updated);
    } catch (err: any) {
      showToast(err.message || 'Rollback failed', 'error');
    } finally {
      setMigrating(false);
    }
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'rgba(99, 102, 241, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent-primary)'
          }}>
            <Settings size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>System &amp; Engine Settings</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Tune face detection thresholds, notification dispatch policies, and manage database schema migrations
            </p>
          </div>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={fetchSettings}
          disabled={loading}
        >
          <RotateCcw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Reload Settings</span>
        </button>
      </div>

      <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1.5rem' }}>
          {/* Card 1: Face Recognition & Engine Optimization */}
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <Sliders size={18} color="var(--accent-primary)" />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Inference &amp; Recognition Tuning</h3>
            </div>

            {/* Face Detection Engine Selection */}
            <div>
              <label className="form-label">Face Detector Engine</label>
              <select
                className="form-input"
                value={faceDetectorType}
                onChange={e => setFaceDetectorType(e.target.value)}
              >
                <option value="yolov8_face">YOLOv8-Face (Dual-Stage, Best False-Positive Filter)</option>
                <option value="scrfd">SCRFD (InsightFace Default RetinaFace)</option>
              </select>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                YOLOv8-Face specializes in eliminating false detections (foliage, hubcaps, headlights) on outdoor cameras while passing landmarks to ArcFace.
              </span>
            </div>

            {/* Detection Confidence */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Face Detection Confidence</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{Math.round(detectionConfidence * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                value={detectionConfidence}
                onChange={e => setDetectionConfidence(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Minimum RetinaFace confidence before a face crop is processed.
              </span>
            </div>

            {/* Similarity Threshold */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Match Similarity Threshold</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{Math.round(similarityThreshold * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                value={similarityThreshold}
                onChange={e => setSimilarityThreshold(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Cosine similarity required to classify a face as a registered household member.
              </span>
            </div>

            {/* Detection Size */}
            <div>
              <label className="form-label">Detector Input Resolution</label>
              <select
                className="form-input"
                value={detSize}
                onChange={e => setDetSize(parseInt(e.target.value, 10))}
              >
                <option value={320}>320px — Low-Latency (~20-50ms CPU)</option>
                <option value={480}>480px — Balanced Quality</option>
                <option value={640}>640px — High-Resolution (Small / Distant Faces)</option>
              </select>
            </div>

            {/* Thread Count */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>ONNX Runtime CPU Threads</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{ortThreads} Cores</span>
              </div>
              <input
                type="range"
                min="1"
                max="32"
                step="1"
                value={ortThreads}
                onChange={e => setOrtThreads(parseInt(e.target.value, 10))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Number of CPU threads allocated for ONNX matrix operations.
              </span>
            </div>

            {/* Max Samples Per Person */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Max Samples Per Member</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{maxSamples} embeddings</span>
              </div>
              <input
                type="range"
                min="5"
                max="100"
                step="5"
                value={maxSamples}
                onChange={e => setMaxSamples(parseInt(e.target.value, 10))}
                style={{ width: '100%' }}
              />
            </div>

            {/* Unrecognized Face Aggregation Window */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Review Aggregation Window</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{trackWindowSeconds} seconds</span>
              </div>
              <input
                type="range"
                min="5"
                max="60"
                step="5"
                value={trackWindowSeconds}
                onChange={e => setTrackWindowSeconds(parseInt(e.target.value, 10))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Sliding timeframe to combine unknown face detections into a single highest-confidence review item.
              </span>
            </div>

            {/* Real-time Stream Motion Gating */}
            <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginTop: '0.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Zap size={16} color="var(--accent-emerald)" />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Real-Time Motion Gating</span>
                </div>
                <input
                  type="checkbox"
                  checked={motionGatingEnabled}
                  onChange={e => setMotionGatingEnabled(e.target.checked)}
                />
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: motionGatingEnabled ? '0.75rem' : 0 }}>
                Skips deep face neural network inference on motionless camera scenes, saving over 90% CPU usage.
              </span>

              {motionGatingEnabled && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <label className="form-label" style={{ margin: 0, fontSize: '0.8rem' }}>Motion Sensitivity</label>
                    <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{(motionThreshold * 100).toFixed(1)}% pixels</span>
                  </div>
                  <input
                    type="range"
                    min="0.005"
                    max="0.05"
                    step="0.002"
                    value={motionThreshold}
                    onChange={e => setMotionThreshold(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                    Pixel difference ratio required to trigger inference (default: 1.5%).
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Card 2: Notification & Alert Thresholds */}
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <Bell size={18} color="var(--accent-amber)" />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Notification &amp; Alert Routing</h3>
            </div>

            {/* Notification Threshold */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Dispatch Confidence / Similarity Threshold</label>
                <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{Math.round(notificationThreshold * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                value={notificationThreshold}
                onChange={e => setNotificationThreshold(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Minimum confidence or similarity before dispatching an outgoing webhook/notification alert.
              </span>
            </div>

            {/* Unknown face alert toggle */}
            <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Notify on Unrecognized Visitors</span>
                <input
                  type="checkbox"
                  checked={notifyOnUnknown}
                  onChange={e => setNotifyOnUnknown(e.target.checked)}
                />
              </label>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                When enabled, arrivals that do not match any known household member emit unknown person alerts.
              </span>

              {notifyOnUnknown && (
                <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>Unknown Detection Confidence Cutoff</span>
                    <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{Math.round(unknownMinConfidence * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="0.95"
                    step="0.05"
                    value={unknownMinConfidence}
                    onChange={e => setUnknownMinConfidence(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>
              )}
            </div>

            {/* Webhook Only Known Faces */}
            <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', marginBottom: '0.35rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Webhook Only Known Faces</span>
                <input
                  type="checkbox"
                  checked={webhookOnlyKnown}
                  onChange={e => setWebhookOnlyKnown(e.target.checked)}
                />
              </label>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Restricts outgoing webhook events exclusively to verified household members.
              </span>
            </div>

            {/* MQTT Only Known Faces */}
            <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', marginBottom: '0.35rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>MQTT Only Known Faces</span>
                <input
                  type="checkbox"
                  checked={mqttOnlyKnown}
                  onChange={e => setMqttOnlyKnown(e.target.checked)}
                />
              </label>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Restricts MQTT detection events exclusively to verified household members.
              </span>
            </div>

            <div style={{ marginTop: 'auto', paddingTop: '1rem' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
                style={{ width: '100%' }}
              >
                <Save size={16} />
                <span>{saving ? 'Saving...' : 'Save All Settings'}</span>
              </button>
            </div>
          </div>
        </div>
      </form>

      {/* Database Schema Migrations & Non-Destructive Versioning */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Database size={20} color="var(--accent-sky)" />
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Database Schema Migrations</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Non-destructive versioning with automatic atomic snapshots and bidirectional roll forward / rollback
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRollForward}
              disabled={migrating}
            >
              <ArrowUpRight size={14} />
              <span>Apply Latest (Roll Forward)</span>
            </button>
          </div>
        </div>

        {/* Migration Telemetry Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <div className="glass-card" style={{ padding: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Current Schema Version</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono, monospace' }}>
              {migrationStatus ? migrationStatus.current_app_version : '...'}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Target App Version</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-sky)', fontFamily: 'JetBrains Mono, monospace' }}>
              {migrationStatus ? migrationStatus.target_app_version : '...'}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Applied Migrations</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
              {migrationStatus ? migrationStatus.applied_count : '...'}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Database Backups Available</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-purple)' }}>
              {migrationStatus ? migrationStatus.backups_count : '...'}
            </div>
          </div>
        </div>

        {/* Rollback Control Card */}
        <div style={{
          padding: '1.25rem',
          borderRadius: 'var(--radius-md)',
          background: 'rgba(239, 68, 68, 0.05)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <History size={16} color="var(--accent-rose)" />
            <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>Roll Back Schema Version</span>
          </div>

          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
            In the event of rolling back a server container to an earlier build, roll back the database schema safely to match your target build.
            Preserves core household members and vectors, and creates an atomic SQLite snapshot prior to rolling back.
          </p>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ width: '200px' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Target version (e.g. 1.0.0)"
                value={rollbackTarget}
                onChange={e => setRollbackTarget(e.target.value)}
                style={{ height: '36px', fontSize: '0.85rem' }}
              />
            </div>

            <button
              className="btn btn-secondary btn-sm"
              style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: 'var(--accent-rose)' }}
              onClick={handleRollback}
              disabled={migrating || !rollbackTarget.trim()}
            >
              <RotateCcw size={14} className={migrating ? 'animate-spin' : ''} />
              <span>{migrating ? 'Processing...' : `Execute Safe Rollback to v${rollbackTarget}`}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
