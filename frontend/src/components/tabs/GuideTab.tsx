import React, { useState } from 'react';
import {
  BookOpen,
  Copy,
  Check,
  ExternalLink,
  Shield,
  Radio
} from 'lucide-react';
import { useToast } from '../Toast';

export const GuideTab: React.FC = () => {
  const { showToast } = useToast();
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    showToast('Copied to clipboard', 'info');
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const webhookUrl = `${window.location.origin}/api/v1/protect/webhook`;

  const unifiPayloadSample = `{
  "type": "smart_detect_zone",
  "camera": {
    "name": "Front Porch G4 Pro",
    "id": "camera_front_door_01"
  },
  "smartDetectTypes": ["person"],
  "event": {
    "id": "evt_9823491283",
    "thumbnail": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "metadata": {
      "personName": "Sebastian Makinson"
    }
  }
}`;

  const haWebhookYaml = `# Home Assistant automation: Send UniFi Protect snapshot to FaceEngine
alias: "UniFi Protect -> FaceEngine Ingestion"
description: "Pushes Protect smart detection snapshots to train or verify household members"
trigger:
  - platform: state
    entity_id: binary_sensor.front_door_person_detected
    to: "on"
action:
  - service: rest_command.face_engine_ingest
    data:
      camera_name: "Front Door"
      person_name: "{{ trigger.to_state.attributes.person | default('Unknown') }}"
      image: "{{ state_attr('camera.front_door', 'entity_picture') }}"`;

  const haMqttYaml = `# Home Assistant MQTT Sensor Configuration (configuration.yaml)
mqtt:
  sensor:
    - name: "FaceEngine Last Detected Member"
      state_topic: "home/security/faces"
      value_template: "{{ value_json.person_name }}"
      icon: "mdi:account-badge"
    - name: "FaceEngine Detection Similarity"
      state_topic: "home/security/faces"
      value_template: "{{ (value_json.similarity * 100) | round(1) }}"
      unit_of_measurement: "%"
      icon: "mdi:percent"`;

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'rgba(168, 85, 247, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent-purple)'
          }}>
            <BookOpen size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Integration &amp; API Guide</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Connect UniFi Protect, Home Assistant, RTSP cameras, and MQTT automations
            </p>
          </div>
        </div>

        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="btn btn-secondary btn-sm"
          style={{ textDecoration: 'none' }}
        >
          <span>Interactive Swagger UI</span>
          <ExternalLink size={14} />
        </a>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: '1.5rem' }}>
        {/* Section 1: UniFi Protect Webhook Ingestion */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Shield size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>UniFi Protect Webhook</h3>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Configure UniFi Protect or your smart doorbell to dispatch detection alerts directly to FaceEngine.
            When Protect tags a person, FaceEngine automatically extracts a 512-d ArcFace embedding and associates it with the household member.
          </p>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Webhook Endpoint (POST &amp; PUT)</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => copyToClipboard(webhookUrl, 'webhook_url')}
              >
                {copiedKey === 'webhook_url' ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                <span>{copiedKey === 'webhook_url' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <input
              type="text"
              className="form-input"
              readOnly
              value={webhookUrl}
              style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Sample JSON Payload</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => copyToClipboard(unifiPayloadSample, 'sample_json')}
              >
                {copiedKey === 'sample_json' ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                <span>{copiedKey === 'sample_json' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre style={{
              background: '#070a10',
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              fontFamily: 'JetBrains Mono, monospace',
              color: '#cbd5e1',
              overflowX: 'auto'
            }}>
              {unifiPayloadSample}
            </pre>
          </div>
        </div>

        {/* Section 2: Home Assistant & MQTT Automation */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Radio size={18} color="var(--accent-sky)" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Home Assistant &amp; MQTT</h3>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Subscribe your smart home automations to FaceEngine's real-time detection events.
            Trigger welcome greetings, unlock smart doors for verified family members, or send snapshot push notifications.
          </p>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ margin: 0 }}>MQTT Sensor Configuration (YAML)</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => copyToClipboard(haMqttYaml, 'mqtt_yaml')}
              >
                {copiedKey === 'mqtt_yaml' ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                <span>{copiedKey === 'mqtt_yaml' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre style={{
              background: '#070a10',
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              fontFamily: 'JetBrains Mono, monospace',
              color: '#cbd5e1',
              overflowX: 'auto'
            }}>
              {haMqttYaml}
            </pre>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Automation Action Example (YAML)</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => copyToClipboard(haWebhookYaml, 'webhook_yaml')}
              >
                {copiedKey === 'webhook_yaml' ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                <span>{copiedKey === 'webhook_yaml' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <pre style={{
              background: '#070a10',
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              fontFamily: 'JetBrains Mono, monospace',
              color: '#cbd5e1',
              overflowX: 'auto'
            }}>
              {haWebhookYaml}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
