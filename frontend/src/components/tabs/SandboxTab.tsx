import React, { useState, useRef, useEffect } from 'react';
import {
  FlaskConical,
  Upload,
  Zap,
  CheckCircle,
  AlertTriangle,
  RotateCcw,
  Sliders
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { SandboxResult, SandboxFace } from '../../types';
import { useToast } from '../Toast';

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = err => reject(err);
  });
}

export const SandboxTab: React.FC = () => {
  const { showToast } = useToast();
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SandboxResult | null>(null);

  // Tuning parameters for test runs
  const [minConfidence, setMinConfidence] = useState<number>(0.6);
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.45);
  const [showConfig, setShowConfig] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageObjRef = useRef<HTMLImageElement | null>(null);

  const handleFileUpload = async (file: File) => {
    try {
      const b64 = await fileToBase64(file);
      setImageSrc(b64);
      runDetection(b64);
    } catch (err) {
      showToast('Error reading uploaded image', 'error');
    }
  };

  const runDetection = async (base64Img: string) => {
    setLoading(true);
    setResult(null);

    try {
      const res = await apiFetch<SandboxResult>('/api/v1/recognize', {
        method: 'POST',
        body: JSON.stringify({
          image: base64Img,
          min_confidence: minConfidence,
          similarity_threshold: similarityThreshold,
          save_unrecognized: false // sandbox test run does not clutter queue unless desired
        })
      });

      setResult(res);
      showToast(`Detected ${res.count} face${res.count === 1 ? '' : 's'} in ${res.latency_ms}ms`, 'success');
    } catch (err: any) {
      showToast(err.message || 'Face detection inference failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Re-draw canvas whenever imageSrc or result changes
  useEffect(() => {
    if (!imageSrc) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = imageSrc;
    img.onload = () => {
      imageObjRef.current = img;
      drawCanvas();
    };
  }, [imageSrc, result]);

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    const img = imageObjRef.current;
    if (!canvas || !img) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);

    if (!result || !result.faces) return;

    result.faces.forEach((face: SandboxFace) => {
      const [x1, y1, x2, y2] = Array.isArray(face.bbox)
        ? face.bbox
        : [face.bbox.x1, face.bbox.y1, face.bbox.x2, face.bbox.y2];

      const width = x2 - x1;
      const height = y2 - y1;
      const isMatched = face.match;

      // Draw bounding box
      ctx.lineWidth = Math.max(3, Math.round(canvas.width / 300));
      ctx.strokeStyle = isMatched ? '#10b981' : '#f59e0b';
      ctx.strokeRect(x1, y1, width, height);

      // Label background
      const labelText = isMatched
        ? `${face.name} (${Math.round(face.similarity * 100)}%)`
        : `Unknown (${Math.round(face.detection_confidence * 100)}%)`;

      ctx.font = `bold ${Math.max(16, Math.round(canvas.width / 50))}px Inter, sans-serif`;
      const textMetrics = ctx.measureText(labelText);
      const padding = 8;
      const textHeight = Math.max(16, Math.round(canvas.width / 50));
      const bgY = Math.max(0, y1 - textHeight - padding * 2);

      ctx.fillStyle = isMatched ? 'rgba(16, 185, 129, 0.9)' : 'rgba(245, 158, 11, 0.9)';
      ctx.fillRect(x1, bgY, textMetrics.width + padding * 2, textHeight + padding * 2);

      // Label text
      ctx.fillStyle = '#ffffff';
      ctx.fillText(labelText, x1 + padding, bgY + textHeight + padding / 2);
    });
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'rgba(56, 189, 248, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent-sky)'
          }}>
            <FlaskConical size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Inference Test Sandbox</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Evaluate RetinaFace detection and 512-d ArcFace recognition on any camera frame or photo
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            className={`btn btn-sm ${showConfig ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowConfig(!showConfig)}
          >
            <Sliders size={14} />
            <span>Thresholds</span>
          </button>

          {imageSrc && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => runDetection(imageSrc)}
              disabled={loading}
            >
              <RotateCcw size={14} className={loading ? 'animate-spin' : ''} />
              <span>Re-run</span>
            </button>
          )}
        </div>
      </div>

      {/* Threshold Config Collapsible */}
      {showConfig && (
        <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))', gap: '1.5rem' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <label className="form-label" style={{ margin: 0 }}>Face Confidence Cutoff</label>
              <span className="chip chip-info" style={{ fontSize: '0.7rem' }}>{Math.round(minConfidence * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.95"
              step="0.05"
              value={minConfidence}
              onChange={e => setMinConfidence(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
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
          </div>
        </div>
      )}

      {/* Main Sandbox Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: imageSrc ? '1fr 340px' : '1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left Side: Upload Dropzone & Canvas Viewer */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {!imageSrc ? (
            <div
              style={{
                width: '100%',
                padding: '4rem 2rem',
                border: '2px dashed var(--border-medium)',
                borderRadius: 'var(--radius-lg)',
                textAlign: 'center',
                background: 'rgba(0,0,0,0.15)',
                cursor: 'pointer',
                position: 'relative'
              }}
            >
              <Upload size={48} color="var(--accent-primary)" style={{ margin: '0 auto 1rem' }} />
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>Drop test photo or click to browse</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', maxWidth: '400px', margin: '0 auto 1rem' }}>
                Upload snapshots from your UniFi Protect or RTSP cameras to inspect real-time bounding boxes and confidence scores
              </p>
              <input
                type="file"
                accept="image/*"
                onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                style={{
                  position: 'absolute',
                  top: 0, left: 0, width: '100%', height: '100%',
                  opacity: 0, cursor: 'pointer'
                }}
              />
            </div>
          ) : (
            <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Annotated Detection Canvas</span>
                <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', margin: 0 }}>
                  <Upload size={14} />
                  <span>Choose Another Image</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                </label>
              </div>

              <div style={{
                position: 'relative',
                width: '100%',
                maxHeight: '600px',
                overflow: 'auto',
                backgroundColor: '#070a10',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'center'
              }}>
                <canvas
                  ref={canvasRef}
                  style={{
                    maxWidth: '100%',
                    height: 'auto',
                    display: 'block'
                  }}
                />
                {loading && (
                  <div style={{
                    position: 'absolute',
                    top: 0, left: 0, width: '100%', height: '100%',
                    background: 'rgba(0, 0, 0, 0.7)',
                    backdropFilter: 'blur(4px)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.75rem',
                    color: '#fff'
                  }}>
                    <Zap size={32} color="var(--accent-primary)" className="animate-spin" />
                    <div style={{ fontWeight: 600 }}>Analyzing embeddings (~20-50ms)...</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Results Diagnostics Panel */}
        {imageSrc && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Telemetry Summary */}
            <div className="glass-panel" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>Inference Metrics</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Latency</span>
                  <span style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {result ? `${result.latency_ms} ms` : '...'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Faces Detected</span>
                  <span style={{ fontWeight: 700 }}>
                    {result ? result.count : '...'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Recognized Match</span>
                  <span style={{ fontWeight: 700, color: result && result.faces.some(f => f.match) ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                    {result ? (result.faces.some(f => f.match) ? 'YES' : 'NO') : '...'}
                  </span>
                </div>
              </div>
            </div>

            {/* Individual Faces List */}
            <div className="glass-panel" style={{ padding: '1.25rem', maxHeight: '420px', overflowY: 'auto' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>Detected Entities</h3>
              {!result || !result.faces || result.faces.length === 0 ? (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1.5rem 0' }}>
                  {loading ? 'Running inference...' : 'No faces detected in this frame.'}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {result.faces.map((face, idx) => (
                    <div
                      key={idx}
                      className="glass-card"
                      style={{
                        padding: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        borderColor: face.match ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.4)'
                      }}
                    >
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '50%',
                        background: face.match ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                        color: face.match ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        {face.match ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {face.name}
                          </span>
                          <span className={`chip ${face.match ? 'chip-success' : 'chip-warning'}`} style={{ fontSize: '0.65rem' }}>
                            {face.match ? `${Math.round(face.similarity * 100)}% match` : 'Unknown'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Confidence: {Math.round(face.detection_confidence * 100)}%
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
