import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Trash2,
  Image as ImageIcon,
  Upload,
  RefreshCw,
  Search,
  X,
  Layers,
  Home,
  User
} from 'lucide-react';
import { apiFetch } from '../../api';
import type { Person, FaceSample } from '../../types';
import { useToast } from '../Toast';

interface PersonsTabProps {
  onRefreshStats: () => void;
  openAddModal?: boolean;
  onCloseAddModal?: () => void;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = err => reject(err);
  });
}

export const PersonsTab: React.FC<PersonsTabProps> = ({
  onRefreshStats,
  openAddModal = false,
  onCloseAddModal,
}) => {
  const { showToast } = useToast();
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'household' | 'visitor'>('all');

  // Add Member Modal State
  const [isAddOpen, setIsAddOpen] = useState(openAddModal);
  const [addName, setAddName] = useState('');
  const [addNotes, setAddNotes] = useState('');
  const [addIsHousehold, setAddIsHousehold] = useState(true);
  const [addImageBase64, setAddImageBase64] = useState<string | null>(null);
  const [addImagePreview, setAddImagePreview] = useState<string | null>(null);
  const [submittingAdd, setSubmittingAdd] = useState(false);

  // Manage Member Details & Samples Modal State
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [personSamples, setPersonSamples] = useState<FaceSample[]>([]);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [uploadingSample, setUploadingSample] = useState(false);
  const [updatingHousehold, setUpdatingHousehold] = useState(false);

  // Sync external openAddModal prop
  useEffect(() => {
    if (openAddModal) {
      setIsAddOpen(true);
    }
  }, [openAddModal]);

  const fetchPersons = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<{ count: number; persons: Person[] }>('/api/v1/persons');
      setPersons(res.persons || []);
    } catch (err: any) {
      showToast(err.message || 'Failed to load household members', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPersons();
  }, []);

  const handleOpenAdd = () => {
    setAddName('');
    setAddNotes('');
    setAddIsHousehold(true);
    setAddImageBase64(null);
    setAddImagePreview(null);
    setIsAddOpen(true);
  };

  const handleCloseAdd = () => {
    setIsAddOpen(false);
    if (onCloseAddModal) onCloseAddModal();
  };

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const b64 = await fileToBase64(file);
      setAddImageBase64(b64);
      setAddImagePreview(b64);
    } catch (err) {
      showToast('Could not read image file', 'error');
    }
  };

  const handleCreatePerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addName.trim()) {
      showToast('Please enter person name', 'error');
      return;
    }

    setSubmittingAdd(true);
    try {
      const payload: { name: string; notes?: string; is_household: boolean; initial_image?: string } = {
        name: addName.trim(),
        notes: addNotes.trim() || undefined,
        is_household: addIsHousehold,
        initial_image: addImageBase64 || undefined
      };

      const res = await apiFetch<{ status: string; person: Person; samples_added: number }>('/api/v1/persons', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      showToast(`Profile '${res.person.name}' (${res.person.is_household !== false ? 'Household' : 'Visitor'}) created!`, 'success');
      handleCloseAdd();
      fetchPersons();
      onRefreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to create person profile', 'error');
    } finally {
      setSubmittingAdd(false);
    }
  };

  const handleDeletePerson = async (person: Person) => {
    if (!confirm(`Are you sure you want to delete '${person.name}' and all associated face embeddings?`)) {
      return;
    }

    try {
      await apiFetch(`/api/v1/persons/${person.id}`, { method: 'DELETE' });
      showToast(`Removed ${person.name}`, 'info');
      setPersons(prev => prev.filter(p => p.id !== person.id));
      if (selectedPerson?.id === person.id) {
        setSelectedPerson(null);
      }
      onRefreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete member', 'error');
    }
  };

  // Manage Samples Modal
  const openManageModal = async (person: Person) => {
    setSelectedPerson(person);
    setLoadingSamples(true);
    try {
      const details = await apiFetch<Person>(`/api/v1/persons/${person.id}`);
      setSelectedPerson(details);
      setPersonSamples(details.samples || []);
    } catch (err: any) {
      showToast(err.message || 'Could not load person sample gallery', 'error');
    } finally {
      setLoadingSamples(false);
    }
  };

  const handleDeleteSample = async (sampleId: string) => {
    if (!selectedPerson) return;
    try {
      await apiFetch(`/api/v1/persons/${selectedPerson.id}/samples/${sampleId}`, { method: 'DELETE' });
      setPersonSamples(prev => prev.filter(s => s.id !== sampleId));
      showToast('Face sample removed', 'info');
      fetchPersons();
      onRefreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to remove sample', 'error');
    }
  };

  const handleUploadSample = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedPerson) return;

    setUploadingSample(true);
    try {
      const b64 = await fileToBase64(file);
      const res = await apiFetch<{ status: string; sample_id: string; thumbnail_url: string; confidence: number }>(
        `/api/v1/persons/${selectedPerson.id}/samples`,
        {
          method: 'POST',
          body: JSON.stringify({ image: b64 })
        }
      );

      showToast(`New training sample added (${Math.round(res.confidence * 100)}% face confidence)`, 'success');
      // Reload samples
      const details = await apiFetch<Person>(`/api/v1/persons/${selectedPerson.id}`);
      setSelectedPerson(details);
      setPersonSamples(details.samples || []);
      fetchPersons();
      onRefreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to upload face sample', 'error');
    } finally {
      setUploadingSample(false);
      e.target.value = '';
    }
  };

  const handleToggleHousehold = async (newVal: boolean) => {
    if (!selectedPerson) return;
    setUpdatingHousehold(true);
    try {
      const res = await apiFetch<{ status: string; person: Person }>(`/api/v1/persons/${selectedPerson.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_household: newVal })
      });
      setSelectedPerson(prev => prev ? { ...prev, is_household: res.person.is_household } : null);
      setPersons(prev => prev.map(p => p.id === res.person.id ? { ...p, is_household: res.person.is_household } : p));
      showToast(`Updated classification to ${newVal ? 'Household Member' : 'Visitor / Non-Household'}`, 'success');
      onRefreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to update classification', 'error');
    } finally {
      setUpdatingHousehold(false);
    }
  };

  const householdCount = persons.filter(p => p.is_household !== false).length;
  const visitorCount = persons.filter(p => p.is_household === false).length;

  const filteredPersons = persons.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.notes && p.notes.toLowerCase().includes(searchQuery.toLowerCase()));
    if (!matchesSearch) return false;
    if (filterType === 'household') return p.is_household !== false;
    if (filterType === 'visitor') return p.is_household === false;
    return true;
  });

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header / Actions */}
      <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'rgba(99, 102, 241, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent-primary)'
          }}>
            <Users size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Registered People</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Manage registered household members and visitors recognized by the ArcFace engine
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Search box */}
          <div style={{ position: 'relative', width: '220px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="form-input"
              placeholder="Search members..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '2rem', height: '36px', fontSize: '0.8rem' }}
            />
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={fetchPersons}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button
            className="btn btn-primary btn-sm"
            onClick={handleOpenAdd}
          >
            <UserPlus size={14} />
            <span>Add Person</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button
          className={`btn btn-sm ${filterType === 'all' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilterType('all')}
        >
          All ({persons.length})
        </button>
        <button
          className={`btn btn-sm ${filterType === 'household' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilterType('household')}
          style={filterType === 'household' ? { background: 'var(--accent-emerald)', borderColor: 'var(--accent-emerald)' } : {}}
        >
          <Home size={13} />
          <span>Household ({householdCount})</span>
        </button>
        <button
          className={`btn btn-sm ${filterType === 'visitor' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilterType('visitor')}
          style={filterType === 'visitor' ? { background: 'var(--accent-purple)', borderColor: 'var(--accent-purple)' } : {}}
        >
          <User size={13} />
          <span>Visitors / Non-Household ({visitorCount})</span>
        </button>
      </div>

      {/* Grid of Household & Visitor Members */}
      {loading && persons.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div className="animate-spin" style={{ display: 'inline-block', marginBottom: '1rem' }}>
            <RefreshCw size={28} />
          </div>
          <div>Loading profiles...</div>
        </div>
      ) : filteredPersons.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: 'rgba(99, 102, 241, 0.15)', color: 'var(--accent-primary)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem'
          }}>
            <Users size={32} />
          </div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.35rem' }}>
            {searchQuery ? 'No persons match search' : 'No persons registered in this category'}
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', maxWidth: '420px', margin: '0 auto 1.5rem' }}>
            {searchQuery
              ? 'Try adjusting your search query or filter.'
              : 'Add persons manually with photos, or assign them via the Review Queue.'}
          </p>
          {!searchQuery && (
            <button className="btn btn-primary" onClick={handleOpenAdd}>
              <UserPlus size={16} />
              <span>Add New Person</span>
            </button>
          )}
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '1.25rem'
        }}>
          {filteredPersons.map(person => (
            <div
              key={person.id}
              className="glass-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
              }}
            >
              {/* Member Card Top / Avatar */}
              <div style={{
                position: 'relative',
                height: '180px',
                backgroundColor: '#0a0d14',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden'
              }}>
                {person.primary_thumbnail ? (
                  <img
                    src={person.primary_thumbnail}
                    alt={person.name}
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    onError={e => {
                      (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="%2364748b" stroke-width="2"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>';
                    }}
                  />
                ) : (
                  <div style={{ color: 'var(--text-dim)', textAlign: 'center' }}>
                    <Users size={48} strokeWidth={1.5} />
                    <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>No face snapshot</div>
                  </div>
                )}

                {/* Household vs Visitor Badge */}
                <div style={{
                  position: 'absolute',
                  top: '0.75rem',
                  left: '0.75rem',
                  background: person.is_household !== false ? 'rgba(16, 185, 129, 0.85)' : 'rgba(168, 85, 247, 0.85)',
                  backdropFilter: 'blur(8px)',
                  padding: '0.2rem 0.55rem',
                  borderRadius: '6px',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem'
                }}>
                  {person.is_household !== false ? <Home size={11} /> : <User size={11} />}
                  <span>{person.is_household !== false ? 'Household' : 'Visitor'}</span>
                </div>

                <div style={{
                  position: 'absolute',
                  top: '0.75rem',
                  right: '0.75rem',
                  background: 'rgba(0, 0, 0, 0.75)',
                  backdropFilter: 'blur(8px)',
                  padding: '0.2rem 0.55rem',
                  borderRadius: '6px',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'var(--accent-sky)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem'
                }}>
                  <Layers size={12} />
                  <span>{person.sample_count} sample{person.sample_count === 1 ? '' : 's'}</span>
                </div>
              </div>

              {/* Member Card Body */}
              <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', flex: 1 }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff' }}>{person.name}</h3>
                {person.notes && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    {person.notes}
                  </p>
                )}

                <div style={{
                  display: 'flex',
                  gap: '0.5rem',
                  marginTop: 'auto',
                  paddingTop: '1rem',
                  borderTop: '1px solid var(--border-subtle)'
                }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                    onClick={() => openManageModal(person)}
                  >
                    <ImageIcon size={14} />
                    <span>Manage</span>
                  </button>

                  <button
                    className="btn btn-secondary btn-sm"
                    title={`Delete ${person.name}`}
                    onClick={() => handleDeletePerson(person)}
                  >
                    <Trash2 size={14} color="var(--accent-rose)" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Member Modal */}
      {isAddOpen && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '480px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Add New Person</h3>
              <button
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.3rem', borderRadius: '50%' }}
                onClick={handleCloseAdd}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreatePerson} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div>
                <label className="form-label">Classification *</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '0.25rem' }}>
                  <button
                    type="button"
                    className={`btn btn-sm ${addIsHousehold ? 'btn-primary' : 'btn-secondary'}`}
                    style={addIsHousehold ? { background: 'var(--accent-emerald)', borderColor: 'var(--accent-emerald)', justifyContent: 'center' } : { justifyContent: 'center' }}
                    onClick={() => setAddIsHousehold(true)}
                  >
                    <Home size={14} />
                    <span>Household Member</span>
                  </button>
                  <button
                    type="button"
                    className={`btn btn-sm ${!addIsHousehold ? 'btn-primary' : 'btn-secondary'}`}
                    style={!addIsHousehold ? { background: 'var(--accent-purple)', borderColor: 'var(--accent-purple)', justifyContent: 'center' } : { justifyContent: 'center' }}
                    onClick={() => setAddIsHousehold(false)}
                  >
                    <User size={14} />
                    <span>Visitor / Guest</span>
                  </button>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                  {addIsHousehold ? 'Classified as family or resident member.' : 'Classified as guest, worker, or non-household contact.'}
                </div>
              </div>

              <div>
                <label className="form-label">Full Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Sarah Jenkins"
                  value={addName}
                  onChange={e => setAddName(e.target.value)}
                  autoFocus
                  required
                />
              </div>

              <div>
                <label className="form-label">Notes (Optional)</label>
                <textarea
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Family member, front door alerts enabled"
                  value={addNotes}
                  onChange={e => setAddNotes(e.target.value)}
                />
              </div>

              <div>
                <label className="form-label">Initial Reference Photo (Optional)</label>
                <div style={{
                  border: '2px dashed var(--border-medium)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.25rem',
                  textAlign: 'center',
                  background: 'rgba(0,0,0,0.2)',
                  cursor: 'pointer',
                  position: 'relative'
                }}>
                  {addImagePreview ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                      <img
                        src={addImagePreview}
                        alt="Preview"
                        style={{ width: '80px', height: '80px', borderRadius: '10px', objectFit: 'cover' }}
                      />
                      <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)' }}>Photo attached (will extract face)</span>
                    </div>
                  ) : (
                    <div>
                      <Upload size={24} color="var(--accent-primary)" style={{ margin: '0 auto 0.5rem' }} />
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>Click to select face snapshot</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>JPG, PNG or WebP</div>
                    </div>
                  )}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageSelect}
                    style={{
                      position: 'absolute',
                      top: 0, left: 0, width: '100%', height: '100%',
                      opacity: 0, cursor: 'pointer'
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCloseAdd}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submittingAdd}
                >
                  {submittingAdd ? 'Saving...' : 'Create Profile'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manage Samples & Gallery Modal */}
      {selectedPerson && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '640px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{selectedPerson.name}</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Learned Embedding Vectors &amp; Face Gallery ({personSamples.length} samples)
                </span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                style={{ padding: '0.3rem', borderRadius: '50%' }}
                onClick={() => setSelectedPerson(null)}
              >
                <X size={16} />
              </button>
            </div>

            {/* Classification Quick Switcher */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1rem',
              background: 'rgba(0,0,0,0.25)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1rem',
              border: '1px solid var(--border-subtle)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Classification:</span>
                <span className={`chip ${selectedPerson.is_household !== false ? 'chip-success' : 'chip-purple'}`} style={{ fontSize: '0.7rem' }}>
                  {selectedPerson.is_household !== false ? 'Household Member' : 'Visitor / Non-Household'}
                </span>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={updatingHousehold}
                onClick={() => handleToggleHousehold(selectedPerson.is_household === false)}
              >
                {selectedPerson.is_household !== false ? 'Change to Visitor' : 'Change to Household'}
              </button>
            </div>

            {/* Upload Extra Sample Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              marginBottom: '1.25rem'
            }}>
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>Add New Face Angle</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Upload additional photos to improve recognition under different lighting or angles
                </div>
              </div>

              <label className="btn btn-primary btn-sm" style={{ cursor: 'pointer', margin: 0 }}>
                <Upload size={14} />
                <span>{uploadingSample ? 'Uploading...' : 'Upload Photo'}</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleUploadSample}
                  disabled={uploadingSample}
                  style={{ display: 'none' }}
                />
              </label>
            </div>

            {/* Samples Gallery Grid */}
            {loadingSamples ? (
              <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem' }} />
                <div>Loading samples...</div>
              </div>
            ) : personSamples.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
                <ImageIcon size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
                <div>No face samples stored for this person yet.</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>Upload a photo above to generate initial embeddings.</div>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                gap: '0.75rem',
                maxHeight: '380px',
                overflowY: 'auto',
                padding: '0.25rem'
              }}>
                {personSamples.map(sample => (
                  <div
                    key={sample.id}
                    className="glass-card"
                    style={{
                      padding: '0.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.5rem',
                      position: 'relative'
                    }}
                  >
                    <img
                      src={sample.thumbnail_path ? `/api/v1/thumbnails/${sample.thumbnail_path}` : ''}
                      alt="Face sample crop"
                      style={{
                        width: '100%',
                        height: '110px',
                        objectFit: 'cover',
                        borderRadius: '6px',
                        backgroundColor: '#0a0d14'
                      }}
                      onError={e => {
                        (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="%2364748b" stroke-width="2"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>';
                      }}
                    />
                    <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)', textTransform: 'capitalize' }}>
                        {sample.source.replace('_', ' ')}
                      </span>
                      <button
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '0.2rem 0.4rem', height: 'auto' }}
                        title="Remove sample"
                        onClick={() => handleDeleteSample(sample.id)}
                      >
                        <Trash2 size={12} color="var(--accent-rose)" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedPerson(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
