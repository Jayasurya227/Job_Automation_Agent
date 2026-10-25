import React, { useState, useEffect, useRef } from 'react';
import { 
  User, 
  Mail, 
  Phone, 
  MapPin, 
  Globe, 
  Briefcase, 
  Code, 
  Save, 
  Plus, 
  X, 
  CheckCircle2, 
  DollarSign, 
  Clock,
  UploadCloud,
  FileText,
  Sparkles,
  FolderGit2,
  GraduationCap,
  Loader2,
  Check,
  Download
} from 'lucide-react';
import { api } from '../api';

export default function ProfileEditor({ isOpen, onClose, notify, onProfileUpdated, inline = false }) {
  if (!inline && !isOpen) return null;

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('preferences'); // 'preferences' | 'skills' | 'portfolio'

  const fileInputRef = useRef(null);

  // New tag inputs
  const [newRole, setNewRole] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newSkillCategory, setNewSkillCategory] = useState('programming_languages');
  const [newSkill, setNewSkill] = useState('');

  const handleDownloadResume = async () => {
    setDownloadingPdf(true);
    try {
      const url = api.downloadMasterResumePdfUrl();
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(profile?.personal_info?.name || 'Candidate').replace(/\s+/g, '_')}_Resume.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      notify('Master resume compiled and downloaded successfully in ATS PDF format!', 'success');
    } catch (err) {
      notify('Failed to download resume PDF: ' + err.message, 'error');
    } finally {
      setDownloadingPdf(false);
    }
  };

  useEffect(() => {
    if (inline || isOpen) {
      loadProfile();
    }
  }, [isOpen, inline]);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const data = await api.getProfile();
      setProfile(data);
    } catch (err) {
      notify('Failed to load candidate profile: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      notify('Please select a valid PDF file (.pdf)', 'warning');
      return;
    }

    setIsUploading(true);
    try {
      const res = await api.uploadResume(file);
      if (res.profile) {
        setProfile(res.profile);
        if (onProfileUpdated) onProfileUpdated(res.profile);
      }
      notify(res.message || 'Resume uploaded and parsed successfully by AI!', 'success');
    } catch (err) {
      notify('Resume upload failed: ' + err.message, 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
      if (onProfileUpdated) onProfileUpdated(updated);
      notify('Profile & career preferences saved successfully!', 'success');
      if (typeof onClose === 'function') {
        onClose();
      }
    } catch (err) {
      notify('Failed to save profile: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleAddRole = () => {
    if (!newRole.trim()) return;
    const currentRoles = profile.preferences?.target_roles || [];
    if (currentRoles.includes(newRole.trim())) return;
    setProfile({
      ...profile,
      preferences: {
        ...profile.preferences,
        target_roles: [...currentRoles, newRole.trim()],
      },
    });
    setNewRole('');
  };

  const handleRemoveRole = (roleToRemove) => {
    const currentRoles = profile.preferences?.target_roles || [];
    setProfile({
      ...profile,
      preferences: {
        ...profile.preferences,
        target_roles: currentRoles.filter((r) => r !== roleToRemove),
      },
    });
  };

  const handleAddLocation = () => {
    if (!newLocation.trim()) return;
    const currentLocs = profile.preferences?.preferred_locations || [];
    if (currentLocs.includes(newLocation.trim())) return;
    setProfile({
      ...profile,
      preferences: {
        ...profile.preferences,
        preferred_locations: [...currentLocs, newLocation.trim()],
      },
    });
    setNewLocation('');
  };

  const handleRemoveLocation = (locToRemove) => {
    const currentLocs = profile.preferences?.preferred_locations || [];
    setProfile({
      ...profile,
      preferences: {
        ...profile.preferences,
        preferred_locations: currentLocs.filter((l) => l !== locToRemove),
      },
    });
  };

  const handleAddSkill = () => {
    if (!newSkill.trim()) return;
    const skills = profile.technical_skills || {};
    const catSkills = skills[newSkillCategory] || [];
    if (catSkills.includes(newSkill.trim())) return;
    setProfile({
      ...profile,
      technical_skills: {
        ...skills,
        [newSkillCategory]: [...catSkills, newSkill.trim()],
      },
    });
    setNewSkill('');
  };

  const handleRemoveSkill = (category, skillToRemove) => {
    const skills = profile.technical_skills || {};
    const catSkills = skills[category] || [];
    setProfile({
      ...profile,
      technical_skills: {
        ...skills,
        [category]: catSkills.filter((s) => s !== skillToRemove),
      },
    });
  };

  const targetRoles = profile?.preferences?.target_roles || [];
  const preferredLocs = profile?.preferences?.preferred_locations || [];
  const technicalSkills = profile?.technical_skills || {};
  const totalSkillsCount = Object.values(technicalSkills).reduce((acc, curr) => acc + (Array.isArray(curr) ? curr.length : 0), 0);
  const projectsList = profile?.projects || [];
  const experienceList = profile?.experience || [];

  const panelContent = (
    <div
      className={inline ? "glass-panel" : "glass-panel-elevated"}
      style={{
        maxWidth: inline ? '100%' : '880px',
        width: '100%',
        maxHeight: inline ? 'none' : '92vh',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '16px',
        border: '1px solid var(--border-card)',
        background: 'var(--bg-card)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        boxShadow: inline ? 'var(--shadow-md)' : 'var(--shadow-lg)',
        animation: 'fadeIn 0.2s ease',
        overflow: 'hidden',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Modal / Card Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 24px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.75) 0%, rgba(255, 255, 255, 0.3) 100%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.35)',
          }}>
            <User size={22} color="#ffffff" />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              Profile & Resume Hub
            </h2>
            <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Upload your resume for AI skill extraction & configure autonomous agent preferences
            </p>
          </div>
        </div>

        {!inline && onClose && (
          <button
            id="close-profile-modal-btn"
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-muted)',
              borderRadius: '8px',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>

        {/* Modal Scrollable Body */}
        <div style={{ padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 12px' }} />
              <div>Loading Candidate Profile...</div>
            </div>
          ) : !profile ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--rose-light)' }}>
              Could not load candidate profile. Ensure backend is running.
            </div>
          ) : (
            <>
              {/* HERO: Resume Upload Box */}
              <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                style={{
                  background: dragActive ? 'rgba(79, 70, 229, 0.12)' : 'linear-gradient(135deg, rgba(255, 255, 255, 0.8) 0%, rgba(246, 249, 254, 0.6) 100%)',
                  border: dragActive ? '2px dashed var(--primary)' : '2px dashed rgba(79, 70, 229, 0.35)',
                  borderRadius: '14px',
                  padding: '24px',
                  boxShadow: '0 2px 10px rgba(15, 23, 42, 0.03)',
                  textAlign: 'center',
                  transition: 'all 0.25s ease',
                  cursor: isUploading ? 'wait' : 'pointer',
                }}
                onClick={() => !isUploading && fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                  }}
                />

                {isUploading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                    <Loader2 size={36} color="var(--primary-light)" className="animate-spin" />
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--primary-light)' }}>
                      Analyzing Resume with Gemini AI...
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Extracting technical skills, projects, work experience, and contact details
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{
                      width: '50px',
                      height: '50px',
                      borderRadius: '12px',
                      background: 'rgba(99, 102, 241, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 12px',
                      color: 'var(--primary-light)',
                    }}>
                      <UploadCloud size={26} />
                    </div>

                    <div style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
                      Upload Candidate Resume (PDF)
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '520px', margin: '0 auto 14px' }}>
                      Drag and drop your PDF resume here, or click to browse. The AI extracts skills and projects so you never have to re-type them manually.
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '7px 18px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                      >
                        <FileText size={15} /> Select PDF Resume
                      </button>

                      <button
                        id="download-resume-pdf-btn"
                        type="button"
                        className="btn btn-secondary btn-sm"
                        style={{ padding: '7px 18px', fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadResume();
                        }}
                        disabled={downloadingPdf}
                      >
                        {downloadingPdf ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                        <span>{downloadingPdf ? 'Compiling PDF...' : 'Download Updated Resume (PDF)'}</span>
                      </button>
                    </div>

                    {/* Extracted Stats Summary Badge */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexWrap: 'wrap',
                      gap: '12px',
                      marginTop: '16px',
                      paddingTop: '14px',
                      borderTop: '1px solid var(--border-subtle)',
                      fontSize: '0.78rem',
                      color: 'var(--text-secondary)',
                    }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--emerald-light)', fontWeight: 600 }}>
                        <CheckCircle2 size={14} /> Resume Connected
                      </span>
                      <span>•</span>
                      <span>Candidate: <strong style={{ color: 'var(--text-main)' }}>{profile.personal_info?.name || 'Jai'}</strong></span>
                      <span>•</span>
                      <span><strong style={{ color: 'var(--cyan-light)' }}>{totalSkillsCount}</strong> Skills</span>
                      <span>•</span>
                      <span><strong style={{ color: 'var(--emerald-light)' }}>{projectsList.length}</strong> Projects</span>
                      <span>•</span>
                      <span><strong style={{ color: 'var(--primary-light)' }}>{experienceList.length}</strong> Experience</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Navigation Sub-Tabs */}
              <div 
                className="profile-subtabs-nav"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  borderBottom: '1px solid var(--border-subtle)',
                  paddingBottom: '8px',
                }}
              >
                <button
                  type="button"
                  onClick={() => setActiveSubTab('preferences')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '7px 14px',
                    borderRadius: '8px',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                    background: activeSubTab === 'preferences' ? 'rgba(79, 70, 229, 0.12)' : 'transparent',
                    color: activeSubTab === 'preferences' ? 'var(--primary)' : 'var(--text-secondary)',
                    transition: 'all 0.2s',
                  }}
                >
                  <Briefcase size={15} />
                  Target Roles & Preferences
                </button>

                <button
                  type="button"
                  onClick={() => setActiveSubTab('skills')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '7px 14px',
                    borderRadius: '8px',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                    background: activeSubTab === 'skills' ? 'rgba(8, 145, 178, 0.12)' : 'transparent',
                    color: activeSubTab === 'skills' ? 'var(--cyan)' : 'var(--text-secondary)',
                    transition: 'all 0.2s',
                  }}
                >
                  <Code size={15} />
                  Technical Skills & Contact
                </button>

                <button
                  type="button"
                  onClick={() => setActiveSubTab('portfolio')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '7px 14px',
                    borderRadius: '8px',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                    background: activeSubTab === 'portfolio' ? 'rgba(5, 150, 105, 0.12)' : 'transparent',
                    color: activeSubTab === 'portfolio' ? 'var(--emerald)' : 'var(--text-secondary)',
                    transition: 'all 0.2s',
                  }}
                >
                  <FolderGit2 size={15} />
                  Projects & Experience ({projectsList.length + experienceList.length})
                </button>
              </div>

              {/* SUB-TAB 1: TARGET ROLES & PREFERENCES */}
              {activeSubTab === 'preferences' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                  {/* Target Roles */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                      Target Job Titles (Agent automatically searches & scores jobs matching these titles)
                    </label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                      {targetRoles.map((role, idx) => (
                        <span
                          key={idx}
                          className="badge badge-indigo"
                          style={{ fontSize: '0.8rem', padding: '5px 12px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                        >
                          {role}
                          <button
                            type="button"
                            onClick={() => handleRemoveRole(role)}
                            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
                          >
                            <X size={13} />
                          </button>
                        </span>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: '8px', maxWidth: '420px' }}>
                      <input
                        id="add-target-role-input"
                        className="form-input"
                        placeholder="Add role (e.g. AI Engineer)..."
                        value={newRole}
                        onChange={(e) => setNewRole(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddRole();
                          }
                        }}
                      />
                      <button id="add-role-btn" type="button" className="btn btn-secondary" onClick={handleAddRole}>
                        <Plus size={16} /> Add
                      </button>
                    </div>
                  </div>

                  {/* Career Preferences Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '5px' }}>
                        Min Expected Salary / CTC
                      </label>
                      <input
                        id="salary-preference-input"
                        className="form-input"
                        value={profile.preferences?.min_expected_salary || ''}
                        onChange={(e) => setProfile({
                          ...profile,
                          preferences: { ...profile.preferences, min_expected_salary: e.target.value }
                        })}
                      />
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '5px' }}>
                        Notice Period (Days)
                      </label>
                      <input
                        id="notice-period-input"
                        type="number"
                        className="form-input"
                        value={profile.preferences?.notice_period_days ?? 0}
                        onChange={(e) => setProfile({
                          ...profile,
                          preferences: { ...profile.preferences, notice_period_days: parseInt(e.target.value) || 0 }
                        })}
                      />
                    </div>
                  </div>

                  {/* Preferred Locations */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                      Preferred Job Locations
                    </label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                      {preferredLocs.map((loc, idx) => (
                        <span
                          key={idx}
                          className="badge badge-cyan"
                          style={{ fontSize: '0.8rem', padding: '5px 12px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                        >
                          <MapPin size={12} /> {loc}
                          <button
                            type="button"
                            onClick={() => handleRemoveLocation(loc)}
                            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
                          >
                            <X size={13} />
                          </button>
                        </span>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: '8px', maxWidth: '420px' }}>
                      <input
                        id="add-location-input"
                        className="form-input"
                        placeholder="Add location (e.g. Hyderabad, Remote)..."
                        value={newLocation}
                        onChange={(e) => setNewLocation(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddLocation();
                          }
                        }}
                      />
                      <button id="add-loc-btn" type="button" className="btn btn-secondary" onClick={handleAddLocation}>
                        <Plus size={16} /> Add
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* SUB-TAB 2: TECHNICAL SKILLS & CONTACT */}
              {activeSubTab === 'skills' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Contact Information */}
                  <div style={{
                    background: 'rgba(255, 255, 255, 0.7)',
                    padding: '16px',
                    borderRadius: '12px',
                    border: '1px solid var(--border-card)',
                    boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
                  }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <User size={15} color="var(--primary-light)" /> Contact Details
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Candidate Name</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.name || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, name: e.target.value }
                          })}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Email Address</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.email || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, email: e.target.value }
                          })}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Phone Number</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.phone || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, phone: e.target.value }
                          })}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Location</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.location || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, location: e.target.value }
                          })}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>LinkedIn URL</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.linkedin_url || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, linkedin_url: e.target.value }
                          })}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>GitHub URL</label>
                        <input
                          className="form-input"
                          value={profile.personal_info?.github_url || ''}
                          onChange={(e) => setProfile({
                            ...profile,
                            personal_info: { ...profile.personal_info, github_url: e.target.value }
                          })}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Skills Inventory */}
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Code size={15} color="var(--emerald-light)" /> Extracted Technical Skills ({totalSkillsCount})
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      {Object.entries(technicalSkills).map(([category, skillsList]) => {
                        const formattedCat = category.replace(/_/g, ' ').toUpperCase();
                        const list = Array.isArray(skillsList) ? skillsList : [];
                        return (
                          <div key={category} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
                            <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--cyan-light)', marginBottom: '6px' }}>
                              {formattedCat} ({list.length})
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {list.map((skill, sIdx) => (
                                <span
                                  key={sIdx}
                                  className="badge badge-emerald"
                                  style={{ fontSize: '0.74rem', padding: '3px 8px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                >
                                  {skill}
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveSkill(category, skill)}
                                    style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
                                  >
                                    <X size={11} />
                                  </button>
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}

                      {/* Add Skill Form */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', marginTop: '6px' }}>
                        <select
                          id="skill-cat-select"
                          className="form-select"
                          style={{ width: 'auto' }}
                          value={newSkillCategory}
                          onChange={(e) => setNewSkillCategory(e.target.value)}
                        >
                          <option value="programming_languages">Languages</option>
                          <option value="frameworks_and_libraries">Frameworks</option>
                          <option value="ai_and_ml">AI & ML Tools</option>
                          <option value="databases">Databases</option>
                          <option value="tools_and_platforms">DevOps & Cloud</option>
                        </select>

                        <input
                          id="add-skill-input"
                          className="form-input"
                          style={{ width: '200px' }}
                          placeholder="New skill (e.g. PyTorch)..."
                          value={newSkill}
                          onChange={(e) => setNewSkill(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              handleAddSkill();
                            }
                          }}
                        />

                        <button id="add-skill-btn" type="button" className="btn btn-secondary btn-sm" onClick={handleAddSkill}>
                          <Plus size={15} /> Add Skill
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SUB-TAB 3: EXTRACTED PROJECTS & EXPERIENCE */}
              {activeSubTab === 'portfolio' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                  {/* Extracted Projects */}
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FolderGit2 size={15} color="var(--cyan-light)" /> Candidate Projects ({projectsList.length})
                    </div>
                    {projectsList.length === 0 ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '12px' }}>
                        No projects parsed yet. Upload a PDF resume above to auto-populate projects.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {projectsList.map((proj, pIdx) => (
                          <div
                            key={pIdx}
                            style={{
                              background: 'rgba(255, 255, 255, 0.7)',
                              border: '1px solid var(--border-card)',
                              boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
                              borderRadius: '10px',
                              padding: '14px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
                                {proj.title}
                              </span>
                              {proj.live_url && (
                                <a href={proj.live_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: 'var(--cyan-light)' }}>
                                  Live Demo
                                </a>
                              )}
                            </div>
                            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                              {proj.description}
                            </p>
                            {proj.tech_stack && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
                                {proj.tech_stack.map((t, tIdx) => (
                                  <span key={tIdx} className="badge badge-indigo" style={{ fontSize: '0.7rem', padding: '2px 6px' }}>
                                    {t}
                                  </span>
                                ))}
                              </div>
                            )}
                            {proj.key_achievements && (
                              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {proj.key_achievements.map((ach, aIdx) => (
                                  <li key={aIdx}>{ach}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Extracted Experience */}
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Briefcase size={15} color="var(--emerald-light)" /> Work Experience ({experienceList.length})
                    </div>
                    {experienceList.length === 0 ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '12px' }}>
                        No work experience parsed yet. Upload a PDF resume above to auto-populate experience.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {experienceList.map((exp, eIdx) => (
                          <div
                            key={eIdx}
                            style={{
                              background: 'rgba(255, 255, 255, 0.7)',
                              border: '1px solid var(--border-card)',
                              boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
                              borderRadius: '10px',
                              padding: '14px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
                                {exp.role} • <span style={{ color: 'var(--cyan-light)' }}>{exp.company}</span>
                              </span>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {exp.start_date} – {exp.end_date || 'Present'}
                              </span>
                            </div>
                            {exp.location && (
                              <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '6px' }}>
                                📍 {exp.location}
                              </div>
                            )}
                            {exp.highlights && (
                              <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                {exp.highlights.map((h, hIdx) => (
                                  <li key={hIdx}>{h}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '12px',
          padding: '16px 24px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0.75) 100%)',
        }}>
          {typeof onClose === 'function' ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={loadProfile}
              disabled={saving || loading}
            >
              Discard Changes
            </button>
          )}

          <button
            id="save-profile-btn"
            type="button"
            className="btn btn-emerald"
            onClick={handleSave}
            disabled={saving || loading || !profile}
            style={{ padding: '8px 22px' }}
          >
            <Save size={16} />
            <span>{saving ? 'Saving...' : 'Save Profile Changes'}</span>
          </button>
        </div>
      </div>
  );

  if (inline) {
    return panelContent;
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.78)',
        backdropFilter: 'blur(8px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        overflowY: 'auto',
      }}
      onClick={() => {
        if (typeof onClose === 'function') onClose();
      }}
    >
      {panelContent}
    </div>
  );
}
