import React, { useState, useEffect } from 'react';
import {
  Inbox,
  UserCheck,
  UserPlus,
  Trash2,
  RefreshCw,
  Clock,
  Camera,
  CheckCircle,
  Sparkles,
  Layers,
  X
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { Detection, Person } from '../../types';
import { useToast } from '../Toast';

interface ReviewTabProps {
  onAssignmentComplete: () => void;
}

export const ReviewTab: React.FC<ReviewTabProps> = ({ onAssignmentComplete }) => {
  const { showToast } = useToast();
  const [detections, setDetections] = useState<Detection[]>([]);
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(false);
  const [purging, setPurging] = useState(false);
  const [deduplicating, setDeduplicating] = useState(false);
  const [activeDetection, setActiveDetection] = useState<Detection | null>(null);

  // Assign modal state
  const [selectedPersonId, setSelectedPersonId] = useState<string>('');
  const [newPersonName, setNewPersonName] = useState<string>('');
  const [assignMode, setAssignMode] = useState<'existing' | 'new'>('existing');
  const [assigning, setAssigning] = useState(false);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const [detRes, perRes] = await Promise.all([
        apiFetch<{ count: number; detections: Detection[] }>('/api/v1/detections/unrecognized'),
        apiFetch<{ count: number; persons: Person[] }>('/api/v1/persons')
      ]);
      setDetections(detRes.detections || []);
      setPersons(perRes.persons || []);
      if (perRes.persons && perRes.persons.length > 0) {
        setSelectedPersonId(perRes.persons[0].id);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load review queue', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleDismiss = async (id: string) => {
    try {
      await apiFetch(`/api/v1/detections/${id}/dismiss`, { method: 'DELETE' });
      setDetections(prev => prev.filter(d => d.id !== id));
      showToast('Face dismissed from queue', 'info');
      onAssignmentComplete();
    } catch (err: any) {
      showToast(err.message || 'Failed to dismiss detection', 'error');
    }
  };

  const handlePurgeLowConfidence = async () => {
    if (!window.confirm('Purge all unrecognized detections below 65% confidence that are likely non-face artifacts?')) {
      return;
    }
    setPurging(true);
    try {
      const res = await apiFetch<{ status: string; message: string; deleted_count: number }>(
        '/api/v1/detections/clean-low-confidence',
        { method: 'POST' }
      );
      showToast(res.message || `Removed ${res.deleted_count} low-confidence detections`, 'success');
      fetchQueue();
      onAssignmentComplete();
    } catch (err: any) {
      showToast(err.message || 'Failed to purge low-confidence detections', 'error');
    } finally {
      setPurging(false);
    }
  };

  const handleDeduplicate = async () => {
    if (!window.confirm('Combine consecutive detections within timeframe and keep only the highest confidence best-shots?')) {
      return;
    }
    setDeduplicating(true);
    try {
      const res = await apiFetch<{ status: string; message: string; deleted_count: number; kept_count: number }>(
        '/api/v1/detections/deduplicate',
        { method: 'POST' }
      );
      showToast(res.message || `Deduplicated: merged ${res.deleted_count} duplicate frames`, 'success');
      fetchQueue();
      onAssignmentComplete();
    } catch (err: any) {
      showToast(err.message || 'Failed to deduplicate detections', 'error');
    } finally {
      setDeduplicating(false);
    }
  };

  const openAssignModal = (detection: Detection) => {
    setActiveDetection(detection);
    setNewPersonName('');
    if (persons.length > 0) {
      setSelectedPersonId(persons[0].id);
      setAssignMode('existing');
    } else {
      setAssignMode('new');
    }
  };

  const handleAssignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDetection) return;

    if (assignMode === 'new' && !newPersonName.trim()) {
      showToast('Please enter a name for the new member', 'error');
      return;
    }

    if (assignMode === 'existing' && !selectedPersonId) {
      showToast('Please select an existing member', 'error');
      return;
    }

    setAssigning(true);
    try {
      const payload = assignMode === 'existing'
        ? { person_id: selectedPersonId }
        : { new_person_name: newPersonName.trim() };

      const res = await apiFetch<{ status: string; message: string; person_name: string }>(
        `/api/v1/detections/${activeDetection.id}/assign`,
        {
          method: 'POST',
          body: JSON.stringify(payload)
        }
      );

      showToast(res.message || `Assigned to ${res.person_name}`, 'success');
      setDetections(prev => prev.filter(d => d.id !== activeDetection.id));
      setActiveDetection(null);
      onAssignmentComplete();
      fetchQueue();
    } catch (err: any) {
      showToast(err.message || 'Failed to assign detection', 'error');
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header bar */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: 'rgba(245, 158, 11, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--accent-amber)'
            }}>
              <Inbox size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Review Queue</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Label unrecognized faces to continuously improve household recognition accuracy
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="chip chip-warning">
            {detections.length} pending face{detections.length === 1 ? '' : 's'}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handlePurgeLowConfidence}
            disabled={purging || loading || detections.length === 0}
            title="Clean detections below 65% confidence"
          >
            <Sparkles size={14} className={purging ? 'animate-spin' : ''} />
            <span>Clean False Positives</span>
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleDeduplicate}
            disabled={deduplicating || loading || detections.length === 0}
            title="Combine consecutive duplicate frames and keep highest confidence best-shots"
          >
            <Layers size={14} className={deduplicating ? 'animate-spin' : ''} />
            <span>Combine Duplicates</span>
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchQueue}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Grid of Unrecognized Detections */}
      {loading && detections.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div className="animate-spin" style={{ display: 'inline-block', marginBottom: '1rem' }}>
            <RefreshCw size={28} />
          </div>
          <div>Loading review queue...</div>
        </div>
      ) : detections.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem'
          }}>
            <CheckCircle size={32} />
          </div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.35rem' }}>Queue is Clear</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', maxWidth: '420px', margin: '0 auto' }}>
            All detected faces have been verified or dismissed. When your cameras spot someone new, they'll appear here for one-click labeling.
          </p>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '1.25rem'
        }}>
          {detections.map(det => {
            const timeStr = typeof det.timestamp === 'number'
              ? new Date(det.timestamp * 1000).toLocaleString()
              : new Date(det.timestamp).toLocaleString();

            return (
              <div
                key={det.id}
                className="glass-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  borderColor: 'rgba(245, 158, 11, 0.3)'
                }}
              >
                {/* Thumbnail Header */}
                <div style={{
                  position: 'relative',
                  width: '100%',
                  height: '220px',
                  backgroundColor: '#0a0d14',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden'
                }}>
                  <img
                    src={det.thumbnail_url || `/api/v1/thumbnails/${det.thumbnail_path}`}
                    alt="Unknown face crop"
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                      transition: 'transform 0.3s ease'
                    }}
                    onError={e => {
                      (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="%2364748b" stroke-width="2"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>';
                    }}
                  />
                  <div style={{
                    position: 'absolute',
                    top: '0.75rem',
                    right: '0.75rem',
                    background: 'rgba(0, 0, 0, 0.75)',
                    backdropFilter: 'blur(8px)',
                    padding: '0.2rem 0.5rem',
                    borderRadius: '6px',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color: 'var(--accent-amber)'
                  }}>
                    {det.confidence !== undefined && det.confidence !== null && !isNaN(det.confidence) && det.confidence > 0
                      ? `${Math.round(det.confidence * 100)}% Det.`
                      : 'Review'}
                  </div>
                </div>

                {/* Info & Meta */}
                <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem', color: '#cbd5e1' }}>
                    <Camera size={14} color="var(--accent-primary)" />
                    <span style={{ fontWeight: 600 }}>{det.camera_id || 'Front Door Camera'}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <Clock size={14} />
                    <span>{timeStr}</span>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
                    <button
                      className="btn btn-primary btn-sm"
                      style={{ flex: 1 }}
                      onClick={() => openAssignModal(det)}
                    >
                      <UserCheck size={14} />
                      <span>Assign</span>
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      title="Dismiss face"
                      onClick={() => handleDismiss(det.id)}
                    >
                      <Trash2 size={14} color="var(--accent-rose)" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Assignment Modal */}
      {activeDetection && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '440px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Label Unrecognized Face</h3>
              <button
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.3rem', borderRadius: '50%' }}
                onClick={() => setActiveDetection(null)}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem', padding: '0.75rem', background: 'rgba(0,0,0,0.3)', borderRadius: 'var(--radius-sm)' }}>
              <img
                src={activeDetection.thumbnail_url || `/api/v1/thumbnails/${activeDetection.thumbnail_path}`}
                alt="Selected Face"
                style={{ width: '64px', height: '64px', borderRadius: '8px', objectFit: 'cover' }}
              />
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <div><strong>Camera:</strong> {activeDetection.camera_id || 'Camera'}</div>
                <div><strong>Confidence:</strong> {Math.round(activeDetection.confidence * 100)}%</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '2px' }}>
                  Assigning automatically adds this crop to the person's vector embeddings.
                </div>
              </div>
            </div>

            {/* Mode Tabs */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <button
                type="button"
                className={`btn btn-sm ${assignMode === 'existing' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
                onClick={() => setAssignMode('existing')}
              >
                <UserCheck size={14} />
                <span>Existing Member</span>
              </button>
              <button
                type="button"
                className={`btn btn-sm ${assignMode === 'new' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1 }}
                onClick={() => setAssignMode('new')}
              >
                <UserPlus size={14} />
                <span>New Person</span>
              </button>
            </div>

            <form onSubmit={handleAssignSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {assignMode === 'existing' ? (
                <div>
                  <label className="form-label">Select Household Member</label>
                  {persons.length === 0 ? (
                    <div style={{ fontSize: '0.8rem', color: 'var(--accent-amber)', padding: '0.5rem 0' }}>
                      No members registered yet. Switch to "New Person" to create one.
                    </div>
                  ) : (
                    <select
                      className="form-input"
                      value={selectedPersonId}
                      onChange={e => setSelectedPersonId(e.target.value)}
                    >
                      {persons.map(p => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.sample_count} sample{p.sample_count === 1 ? '' : 's'})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              ) : (
                <div>
                  <label className="form-label">New Person Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. John Doe"
                    value={newPersonName}
                    onChange={e => setNewPersonName(e.target.value)}
                    autoFocus
                    required
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setActiveDetection(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={assigning || (assignMode === 'existing' && persons.length === 0)}
                >
                  {assigning ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
