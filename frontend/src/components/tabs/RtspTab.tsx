import React, { useState, useEffect } from 'react';
import {
  Radio,
  Play,
  Square,
  RefreshCw,
  Video,
  Activity,
  Bell,
  Cpu,
  Save,
  AlertTriangle,
  Wifi,
  WifiOff,
  ShieldCheck,
  Server,
  Zap
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { RtspStatus, SystemSettings } from '../../types';
import { useToast } from '../Toast';

export const RtspTab: React.FC = () => {
  const { showToast } = useToast();
  const [status, setStatus] = useState<RtspStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Form Configuration State
  const [url, setUrl] = useState('');
  const [cameraName, setCameraName] = useState('Front Porch');
  const [fps, setFps] = useState(2.0);
  const [cooldownSeconds, setCooldownSeconds] = useState(30);
  const [motionGatingEnabled, setMotionGatingEnabled] = useState(true);
  const [motionThreshold, setMotionThreshold] = useState(0.015);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookOnlyKnown, setWebhookOnlyKnown] = useState(true);
  const [mqttOnlyKnown, setMqttOnlyKnown] = useState(true);

  // MQTT Config
  const [mqttEnabled, setMqttEnabled] = useState(false);
  const [mqttHost, setMqttHost] = useState('');
  const [mqttPort, setMqttPort] = useState(1883);
  const [mqttTopic, setMqttTopic] = useState('home/security/faces');
  const [mqttUser, setMqttUser] = useState('');
  const [mqttPassword, setMqttPassword] = useState('');

  const [savingConfig, setSavingConfig] = useState(false);
  const [previewTimestamp, setPreviewTimestamp] = useState<number>(Date.now());
  const [previewError, setPreviewError] = useState(false);

  const fetchStatus = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await apiFetch<RtspStatus>('/api/v1/rtsp/status');
      if (res && typeof res === 'object') {
        setStatus(res);
        setPreviewTimestamp(Date.now());
        setPreviewError(false);
      }
    } catch (err: any) {
      if (!silent) showToast(err.message || 'Failed to fetch RTSP status', 'error');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchFullSettings = async () => {
    try {
      const res = await apiFetch<SystemSettings>('/api/v1/settings');
      if (res) {
        if (typeof res.rtsp_url === 'string') setUrl(res.rtsp_url);
        if (typeof res.rtsp_camera_name === 'string') setCameraName(res.rtsp_camera_name);
        if (typeof res.rtsp_fps === 'number' && !isNaN(res.rtsp_fps)) setFps(res.rtsp_fps);
        if (typeof res.rtsp_cooldown_seconds === 'number' && !isNaN(res.rtsp_cooldown_seconds)) {
          setCooldownSeconds(res.rtsp_cooldown_seconds);
        }
        if (typeof res.rtsp_motion_gating_enabled === 'boolean') {
          setMotionGatingEnabled(res.rtsp_motion_gating_enabled);
        }
        if (typeof res.rtsp_motion_threshold === 'number' && !isNaN(res.rtsp_motion_threshold)) {
          setMotionThreshold(res.rtsp_motion_threshold);
        }
        if (typeof res.rtsp_webhook_url === 'string') setWebhookUrl(res.rtsp_webhook_url);
        if (typeof res.webhook_only_known_faces === 'boolean') setWebhookOnlyKnown(res.webhook_only_known_faces);
        if (typeof res.mqtt_only_known_faces === 'boolean') setMqttOnlyKnown(res.mqtt_only_known_faces);

        setMqttEnabled(!!res.mqtt_enabled);
        if (typeof res.mqtt_host === 'string') setMqttHost(res.mqtt_host);
        if (typeof res.mqtt_port === 'number') setMqttPort(res.mqtt_port);
        if (typeof res.mqtt_topic === 'string') setMqttTopic(res.mqtt_topic);
        if (typeof res.mqtt_user === 'string') setMqttUser(res.mqtt_user);
        if (typeof res.mqtt_password === 'string') setMqttPassword(res.mqtt_password);
      }
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchFullSettings();

    // Poll status & preview while on this tab
    const interval = setInterval(() => {
      fetchStatus(true);
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const handleStartStream = async () => {
    setActionInProgress(true);
    try {
      await apiFetch('/api/v1/rtsp/start', { method: 'POST' });
      showToast('RTSP stream worker started', 'success');
      await fetchStatus();
    } catch (err: any) {
      showToast(err.message || 'Failed to start stream', 'error');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleStopStream = async () => {
    setActionInProgress(true);
    try {
      await apiFetch('/api/v1/rtsp/stop', { method: 'POST' });
      showToast('RTSP stream worker stopped', 'info');
      await fetchStatus();
    } catch (err: any) {
      showToast(err.message || 'Failed to stop stream', 'error');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingConfig(true);
    try {
      const payload = {
        url,
        camera_name: cameraName,
        fps,
        cooldown_seconds: cooldownSeconds,
        motion_gating_enabled: motionGatingEnabled,
        motion_threshold: motionThreshold,
        webhook_url: webhookUrl,
        webhook_only_known_faces: webhookOnlyKnown,
        mqtt_enabled: mqttEnabled,
        mqtt_host: mqttHost,
        mqtt_port: mqttPort,
        mqtt_topic: mqttTopic,
        mqtt_user: mqttUser || undefined,
        mqtt_password: mqttPassword || undefined,
        mqtt_only_known_faces: mqttOnlyKnown
      };

      await apiFetch('/api/v1/rtsp/config', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      showToast('RTSP & MQTT configuration saved and active!', 'success');
      await fetchStatus();
    } catch (err: any) {
      showToast(err.message || 'Failed to update configuration', 'error');
    } finally {
      setSavingConfig(false);
    }
  };

  const isRunning = status?.is_running ?? false;
  const isConnected = status?.is_connected ?? false;

  const actualFps = typeof status?.actual_fps === 'number'
    ? status.actual_fps
    : (typeof status?.fps_actual === 'number' ? status.fps_actual : 0.0);

  const targetFps = typeof status?.target_fps === 'number'
    ? status.target_fps
    : (typeof fps === 'number' ? fps : 2.0);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'rgba(236, 72, 153, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent-pink)'
          }}>
            <Radio size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>RTSP Stream &amp; MQTT Broker</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Real-time video ingestion, background inference thread, webhook alerts, and Home Assistant MQTT publishing
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {isRunning ? (
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleStopStream}
              disabled={actionInProgress}
              style={{ borderColor: 'var(--accent-rose)', color: 'var(--accent-rose)' }}
            >
              <Square size={14} />
              <span>Stop Stream</span>
            </button>
          ) : (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleStartStream}
              disabled={actionInProgress || !url.trim()}
            >
              <Play size={14} />
              <span>Start Stream</span>
            </button>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchStatus()}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Real-time Telemetry Status Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '1rem' }}>
        {/* Worker Status */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: isRunning ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
            color: isRunning ? 'var(--accent-emerald)' : 'var(--text-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Activity size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Stream Worker</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: isRunning ? 'var(--accent-emerald)' : '#fff' }}>
              {isRunning ? (isConnected ? 'Streaming Live' : 'Connecting...') : 'Stopped'}
            </div>
          </div>
        </div>

        {/* Sampling Speed */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-sky)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Cpu size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Actual Sampling FPS</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', fontFamily: 'JetBrains Mono, monospace' }}>
              {status ? `${actualFps.toFixed(1)} / ${targetFps.toFixed(1)} fps` : '0.0 fps'}
            </div>
          </div>
        </div>

        {/* Motion Gating / CPU Saver Telemetry */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: (status?.motion_gating_enabled ?? motionGatingEnabled)
              ? (status?.motion_detected ? 'rgba(56, 189, 248, 0.2)' : 'rgba(16, 185, 129, 0.15)')
              : 'rgba(100, 116, 139, 0.15)',
            color: (status?.motion_gating_enabled ?? motionGatingEnabled)
              ? (status?.motion_detected ? 'var(--accent-sky)' : 'var(--accent-emerald)')
              : 'var(--text-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Zap size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Motion Gating (CPU)</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
              {!isRunning
                ? (motionGatingEnabled ? 'Gating Armed' : 'Disabled')
                : (status?.motion_gating_enabled
                    ? (status.motion_detected ? 'Motion Detected' : 'Idle (CPU Saving)')
                    : 'Continuous (Always)')}
            </div>
          </div>
        </div>

        {/* MQTT Status */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: status?.mqtt?.connected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            color: status?.mqtt?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            {status?.mqtt?.connected ? <Wifi size={20} /> : <WifiOff size={20} />}
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MQTT Broker</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: status?.mqtt?.connected ? 'var(--accent-emerald)' : '#fff' }}>
              {status?.mqtt?.enabled
                ? (status.mqtt.connected ? 'Connected' : 'Disconnected')
                : 'Disabled'}
            </div>
          </div>
        </div>

        {/* Webhook Filter Policy */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <ShieldCheck size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Alert Filter</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
              {webhookOnlyKnown ? 'Known Faces Only' : 'All Faces'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Monitor & Configuration Form */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        {/* Live Camera Feed & Recent RTSP Event */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Live Preview Screen */}
          <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Video size={18} color="var(--accent-primary)" />
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Live Camera Feed ({cameraName})</h3>
              </div>
              {isRunning && (
                <div className="chip chip-success" style={{ fontSize: '0.65rem' }}>
                  <span className="pulsing-dot" /> LIVE
                </div>
              )}
            </div>

            <div style={{
              width: '100%',
              height: '300px',
              backgroundColor: '#070a10',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {isRunning && !previewError ? (
                <img
                  src={`/api/v1/rtsp/preview?t=${previewTimestamp}`}
                  alt="Live Camera Snapshot"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  onError={() => setPreviewError(true)}
                />
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '2rem' }}>
                  <Radio size={40} strokeWidth={1.5} style={{ margin: '0 auto 0.75rem' }} />
                  <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>
                    {isRunning ? 'Waiting for camera keyframe...' : 'Camera Stream is Idle'}
                  </div>
                  <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                    {isRunning ? 'Camera stream is connecting' : 'Click "Start Stream" above to begin real-time detection'}
                  </div>
                </div>
              )}
            </div>

            {status?.last_error && (
              <div style={{
                padding: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: 'var(--accent-rose)',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <AlertTriangle size={16} />
                <span>Last Stream Error: {status.last_error}</span>
              </div>
            )}
          </div>

          {/* Last Detection Summary Card */}
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Latest Real-Time Detection</h3>
            {status?.last_detection ? (
              <div className="glass-card" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                {status.last_detection.thumbnail_url && (
                  <img
                    src={status.last_detection.thumbnail_url}
                    alt="Detection face"
                    style={{ width: '54px', height: '54px', borderRadius: '10px', objectFit: 'cover' }}
                  />
                )}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>
                      {status.last_detection.person_name || 'Unknown Face'}
                    </span>
                    <span className={`chip ${status.last_detection.match ? 'chip-success' : 'chip-warning'}`} style={{ fontSize: '0.65rem' }}>
                      {status.last_detection.match
                        ? `${Math.round((status.last_detection.similarity ?? 0) * 100)}% match`
                        : 'Unknown'}
                    </span>
                    {status.last_detection.match && (
                      <span className={`chip ${status.last_detection.is_household !== false ? 'chip-success' : 'chip-purple'}`} style={{ fontSize: '0.65rem' }}>
                        {status.last_detection.is_household !== false ? 'Household' : 'Visitor'}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    {status.last_detection.timestamp
                      ? `Detected ${new Date(
                          typeof status.last_detection.timestamp === 'number' && status.last_detection.timestamp < 1e11
                            ? status.last_detection.timestamp * 1000
                            : status.last_detection.timestamp
                        ).toLocaleTimeString()}`
                      : 'Recently detected'}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textAlign: 'center', padding: '1.5rem 0' }}>
                No active detections registered on this stream session yet.
              </div>
            )}
          </div>
        </div>

        {/* Configuration Form */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Stream &amp; Alert Setup</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Configure camera connection string, sampling FPS, webhook dispatcher, and MQTT credentials
              </p>
            </div>
          </div>

          <form onSubmit={handleSaveConfig} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* RTSP Stream URL */}
            <div>
              <label className="form-label">RTSP Video Stream URL *</label>
              <input
                type="text"
                className="form-input"
                placeholder="rtsp://192.168.1.1:554/s0 or rtsps://..."
                value={url}
                onChange={e => setUrl(e.target.value)}
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                Supports UniFi Protect RTSP/RTSPS links, Reolink, Dahua, Hikvision, and standard IP cameras.
              </span>
            </div>

            {/* Camera Name */}
            <div>
              <label className="form-label">Camera Identifier Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="Front Porch G4 Pro"
                value={cameraName}
                onChange={e => setCameraName(e.target.value)}
              />
            </div>

            {/* Sliders: Sampling FPS & Cooldown */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <label className="form-label" style={{ margin: 0 }}>Sampling Rate</label>
                  <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>
                    {typeof fps === 'number' ? fps.toFixed(1) : Number(fps || 2).toFixed(1)} FPS
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="10.0"
                  step="0.5"
                  value={fps}
                  onChange={e => setFps(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <label className="form-label" style={{ margin: 0 }}>Alert Cooldown</label>
                  <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{cooldownSeconds}s</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="300"
                  step="5"
                  value={cooldownSeconds}
                  onChange={e => setCooldownSeconds(parseInt(e.target.value, 10))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {/* Motion Detection Gating Optimization Card */}
            <div style={{
              padding: '1rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Zap size={16} color="var(--accent-emerald)" />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Motion Detection Gating (CPU Saver)</span>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={motionGatingEnabled}
                    onChange={e => setMotionGatingEnabled(e.target.checked)}
                  />
                  <span style={{ color: '#fff', fontWeight: 500 }}>Enable Gating</span>
                </label>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Skips heavy deep-learning face inference when camera pixels are static, cutting idle CPU load by over 90%. Includes an automatic 10-second safety heartbeat to never miss still subjects.
              </div>

              {motionGatingEnabled && (
                <div style={{ marginTop: '0.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <label className="form-label" style={{ margin: 0, fontSize: '0.8rem' }}>Motion Sensitivity Threshold</label>
                    <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>
                      {(motionThreshold * 100).toFixed(1)}% pixels changed
                    </span>
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
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', display: 'block', marginTop: '3px' }}>
                    Lower percentage triggers on smaller movements (subtle head shifts); higher percentage requires larger body movement. Default: 1.5%.
                  </span>
                </div>
              )}
            </div>

            {/* Webhook Configuration Card */}
            <div style={{
              padding: '1rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Bell size={16} color="var(--accent-primary)" />
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Outgoing Webhook Notification</span>
              </div>

              <div>
                <label className="form-label">Webhook URL (Home Assistant / Node-RED / Discord)</label>
                <input
                  type="url"
                  className="form-input"
                  placeholder="http://homeassistant.local:8123/api/webhook/face-alert"
                  value={webhookUrl}
                  onChange={e => setWebhookUrl(e.target.value)}
                />
              </div>

              {/* Only Known Faces Checkbox */}
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                <input
                  type="checkbox"
                  checked={webhookOnlyKnown}
                  onChange={e => setWebhookOnlyKnown(e.target.checked)}
                />
                <span style={{ color: '#fff', fontWeight: 500 }}>Only send webhook for recognized known faces</span>
              </label>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                When enabled, unrecognized faces will not trigger downstream automation alerts or push notifications.
              </div>
            </div>

            {/* MQTT Configuration Card */}
            <div style={{
              padding: '1rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Server size={16} color="var(--accent-sky)" />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>MQTT Broker Integration</span>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={mqttEnabled}
                    onChange={e => setMqttEnabled(e.target.checked)}
                  />
                  <span>Enable MQTT</span>
                </label>
              </div>

              {mqttEnabled && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.25rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
                    <div>
                      <label className="form-label">Broker Host IP</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="192.168.1.50"
                        value={mqttHost}
                        onChange={e => setMqttHost(e.target.value)}
                        required={mqttEnabled}
                      />
                    </div>
                    <div>
                      <label className="form-label">Port</label>
                      <input
                        type="number"
                        className="form-input"
                        value={mqttPort}
                        onChange={e => setMqttPort(parseInt(e.target.value, 10))}
                        required={mqttEnabled}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="form-label">Topic</label>
                    <input
                      type="text"
                      className="form-input"
                      value={mqttTopic}
                      onChange={e => setMqttTopic(e.target.value)}
                      required={mqttEnabled}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div>
                      <label className="form-label">Username (Optional)</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="mosquitto"
                        value={mqttUser}
                        onChange={e => setMqttUser(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Password (Optional)</label>
                      <input
                        type="password"
                        className="form-input"
                        placeholder="••••••••"
                        value={mqttPassword}
                        onChange={e => setMqttPassword(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Only Known Faces Checkbox */}
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                    <input
                      type="checkbox"
                      checked={mqttOnlyKnown}
                      onChange={e => setMqttOnlyKnown(e.target.checked)}
                    />
                    <span style={{ color: '#fff', fontWeight: 500 }}>Only publish MQTT events for recognized known faces</span>
                  </label>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    When enabled, unrecognized faces will not be published to your MQTT topics.
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={savingConfig}
              style={{ marginTop: '0.5rem' }}
            >
              <Save size={16} />
              <span>{savingConfig ? 'Applying & Saving...' : 'Save Configuration'}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
