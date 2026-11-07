import React, { useState } from 'react';
import { api } from '../api';
import { 
  Sparkles, 
  Search, 
  MapPin, 
  Sliders, 
  CheckCircle2, 
  X, 
  ShieldCheck, 
  Compass,
  ArrowRight,
  TrendingUp,
  Inbox,
  Clock
} from 'lucide-react';

const AVAILABLE_PORTALS = [
  { id: 'naukri', label: 'Naukri.com', icon: '🇮🇳', desc: "India's #1 Tech Job Portal (Direct 1-Click Apply)" },
];

export default function DiscoveryModal({ isOpen, onClose, profile, onDiscoveryComplete, addToast }) {

  const targetRoles = profile?.preferences?.target_roles || ['Junior AI Engineer', 'Python Developer'];
  const preferredLocs = profile?.preferences?.preferred_locations || ['India', 'Remote'];

  const [searchTerm, setSearchTerm] = useState(targetRoles[0] || 'Junior AI Engineer');
  const [location, setLocation] = useState(preferredLocs[0] || 'India');
  const [selectedPortals, setSelectedPortals] = useState(['naukri']);
  const [resultsWanted, setResultsWanted] = useState(4);
  const [freshnessDays, setFreshnessDays] = useState(profile?.preferences?.freshness_days ?? 1);
  const [minMatchScore, setMinMatchScore] = useState(70);
  const [maxProcess, setMaxProcess] = useState(2);

  // Sync with saved profile preferences
  React.useEffect(() => {
    if (profile?.preferences?.freshness_days !== undefined) {
      setFreshnessDays(profile.preferences.freshness_days);
    }
  }, [profile]);

  const [isScanning, setIsScanning] = useState(false);
  const [report, setReport] = useState(null);
  const [scanStep, setScanStep] = useState('');
  const [liveDiscoveryEvents, setLiveDiscoveryEvents] = useState([]);
  const [liveCounters, setLiveCounters] = useState({ found: 0, ready: 0, archived: 0 });

  const togglePortal = (portalId) => {
    setSelectedPortals(prev =>
      prev.includes(portalId)
        ? prev.filter(p => p !== portalId)
        : [...prev, portalId]
    );
  };

  const handleStartDiscovery = async () => {
    if (selectedPortals.length === 0) {
      if (addToast) addToast('Please select at least one job portal.', 'warning');
      return;
    }

    setIsScanning(true);
    setReport(null);
    setLiveDiscoveryEvents([]);
    setLiveCounters({ found: 0, ready: 0, archived: 0 });
    setScanStep(`Initiating stealth browser discovery across ${selectedPortals.map(p => p.toUpperCase()).join(', ')}...`);

    let unsubscribe = null;
    try {
      unsubscribe = api.subscribeToEvents('discovery', (eventData) => {
        if (eventData?.message) {
          setScanStep(eventData.message);
          setLiveDiscoveryEvents((prev) => [
            ...prev,
            {
              timestamp: new Date().toLocaleTimeString(),
              stage: eventData.stage,
              message: eventData.message,
              status: eventData.status,
            }
          ]);
        }
        if (eventData?.count) {
          setLiveCounters((prev) => ({ ...prev, found: eventData.count }));
        }
        if (eventData?.status === 'Ready') {
          setLiveCounters((prev) => ({ ...prev, ready: prev.ready + 1 }));
        } else if (eventData?.status === 'Archived') {
          setLiveCounters((prev) => ({ ...prev, archived: prev.archived + 1 }));
        }
      });

      let searchTermsToUse = null;
      if (searchTerm && searchTerm.includes(',')) {
        searchTermsToUse = searchTerm.split(',').map(s => s.trim()).filter(Boolean);
      } else if (searchTerm && searchTerm.trim()) {
        searchTermsToUse = [searchTerm.trim()];
      } else {
        searchTermsToUse = targetRoles.slice(0, 3);
      }

      let locationsToUse = null;
      if (location && location.includes(',')) {
        locationsToUse = location.split(',').map(l => l.trim()).filter(Boolean);
      } else if (location && location.trim()) {
        locationsToUse = [location.trim()];
      } else {
        locationsToUse = preferredLocs.slice(0, 2);
      }

      const result = await api.discoverJobs({
        search_terms: searchTermsToUse,
        search_term: searchTermsToUse[0] || 'Junior AI Engineer',
        locations: locationsToUse,
        location: locationsToUse.join(', '),
        portals: selectedPortals,
        results_wanted: Number(resultsWanted),
        freshness_days: Number(freshnessDays),
        min_match_score: Number(minMatchScore),
        max_process: Number(maxProcess),
      });

      setReport(result);
      setIsScanning(false);
      if (addToast) {
        addToast(
          `Discovery finished: ${result.high_matches_ready} Ready, ${result.low_matches_archived} Archived!`,
          'success'
        );
      }
      if (onDiscoveryComplete) {
        onDiscoveryComplete();
      }
    } catch (err) {
      setIsScanning(false);
      if (addToast) {
        addToast(`Discovery notice: ${err.message}`, 'error');
      }
    } finally {
      if (unsubscribe) unsubscribe();
    }
  };

  const handleResetAndClose = () => {
    setReport(null);
    setIsScanning(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div 
      id="discovery-modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(20, 45, 25, 0.35)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        overflowY: 'auto',
      }}
      onClick={handleResetAndClose}
    >
      <div 
        className="glass-panel-elevated"
        style={{ 
          maxWidth: '680px', 
          width: '100%', 
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          borderRadius: '24px',
          border: '1.8px solid #ffffff',
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(245, 252, 246, 0.88) 100%)',
          boxShadow: 'var(--shadow-lg), 0 20px 50px rgba(15, 40, 20, 0.16)',
          padding: '24px',
          animation: 'fadeIn 0.2s ease',
        }} 
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #5b8433 0%, #466725 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 16px rgba(74, 108, 37, 0.35)',
            }}>
              <Sparkles size={22} color="#ffffff" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                Autonomous Job Discovery
              </h2>
              <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Multi-Portal Browser Scraping + ATS AI Evaluation + Auto-Ingestion
              </p>
            </div>
          </div>
          <button 
            id="close-discovery-modal-btn"
            onClick={handleResetAndClose}
            style={{
              background: 'rgba(0, 0, 0, 0.04)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
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
        </div>

        {/* Modal Body */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {!report && !isScanning && (
            <>
              {/* Target Role & Quick Tags */}
              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
                  Target Role Search
                </label>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setSearchTerm(targetRoles.slice(0, 3).join(', '))}
                    style={{
                      padding: '5px 12px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      borderRadius: '9999px',
                      border: searchTerm === targetRoles.slice(0, 3).join(', ') ? '1.5px solid #2d6a4f' : '1px solid rgba(255, 255, 255, 0.9)',
                      background: searchTerm === targetRoles.slice(0, 3).join(', ') ? 'rgba(45, 106, 79, 0.20)' : 'rgba(255, 255, 255, 0.70)',
                      color: searchTerm === targetRoles.slice(0, 3).join(', ') ? '#1b4332' : 'var(--text-secondary)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      boxShadow: '0 1px 3px rgba(15, 40, 20, 0.05)',
                    }}
                  >
                    ✨ All Saved Roles ({targetRoles.slice(0, 3).length})
                  </button>
                  {targetRoles.map(role => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setSearchTerm(role)}
                      style={{
                        padding: '5px 12px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        borderRadius: '9999px',
                        border: searchTerm === role ? '1.5px solid #4a6b28' : '1px solid rgba(255, 255, 255, 0.9)',
                        background: searchTerm === role ? 'rgba(91, 132, 51, 0.16)' : 'rgba(255, 255, 255, 0.70)',
                        color: searchTerm === role ? '#37501e' : 'var(--text-secondary)',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        boxShadow: '0 1px 3px rgba(15, 40, 20, 0.05)',
                      }}
                    >
                      {role}
                    </button>
                  ))}
                </div>
                <div style={{ position: 'relative' }}>
                  <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    id="discovery-role-input"
                    type="text"
                    className="form-input"
                    style={{ paddingLeft: '36px' }}
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    placeholder="e.g. Junior AI Engineer, Python Developer"
                  />
                </div>
              </div>

              {/* Location & Minimum Threshold */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
                    Target Location
                  </label>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <button
                      type="button"
                      onClick={() => setLocation(preferredLocs.slice(0, 2).join(', '))}
                      style={{
                        padding: '4px 10px',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        borderRadius: '9999px',
                        border: location === preferredLocs.slice(0, 2).join(', ') ? '1.5px solid #2d6a4f' : '1px solid rgba(255, 255, 255, 0.9)',
                        background: location === preferredLocs.slice(0, 2).join(', ') ? 'rgba(45, 106, 79, 0.20)' : 'rgba(255, 255, 255, 0.70)',
                        color: location === preferredLocs.slice(0, 2).join(', ') ? '#1b4332' : 'var(--text-secondary)',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                      }}
                    >
                      ✨ Top Saved ({preferredLocs.slice(0, 2).length})
                    </button>
                    {preferredLocs.slice(0, 4).map(loc => (
                      <button
                        key={loc}
                        type="button"
                        onClick={() => setLocation(loc)}
                        style={{
                          padding: '4px 10px',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          borderRadius: '9999px',
                          border: location === loc ? '1.5px solid #4a6b28' : '1px solid rgba(255, 255, 255, 0.9)',
                          background: location === loc ? 'rgba(91, 132, 51, 0.16)' : 'rgba(255, 255, 255, 0.70)',
                          color: location === loc ? '#37501e' : 'var(--text-secondary)',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                        }}
                      >
                        {loc}
                      </button>
                    ))}
                  </div>
                  <div style={{ position: 'relative' }}>
                    <MapPin size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                    <input
                      id="discovery-location-input"
                      type="text"
                      className="form-input"
                      style={{ paddingLeft: '36px' }}
                      value={location}
                      onChange={e => setLocation(e.target.value)}
                      placeholder="e.g. India, Remote, Hyderabad, Bengaluru"
                    />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Min ATS Match Score
                    </label>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#047857' }}>
                      {minMatchScore}%
                    </span>
                  </div>
                  <input
                    id="discovery-min-score-slider"
                    type="range"
                    min="50"
                    max="90"
                    step="5"
                    value={minMatchScore}
                    onChange={e => setMinMatchScore(e.target.value)}
                    style={{ width: '100%', marginTop: '8px', accentColor: '#4a6b28' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    <span>50% (Permissive)</span>
                    <span>70% (Recommended)</span>
                    <span>90% (Strict)</span>
                  </div>
                </div>
              </div>

              {/* Posting Freshness (24 Hours Filter) */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Clock size={15} color="#4a6b28" /> Posting Freshness Filter
                  </label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#047857' }}>
                    {freshnessDays === 1 ? '⚡ 24h Filter Active' : freshnessDays === 3 ? '3 Days Active' : freshnessDays === 7 ? '7 Days Active' : 'All Postings'}
                  </span>
                </div>
                <select
                  id="discovery-freshness-select"
                  className="form-select"
                  value={freshnessDays}
                  onChange={(e) => setFreshnessDays(Number(e.target.value))}
                  style={{ width: '100%', fontSize: '0.86rem', padding: '8px 12px' }}
                >
                  <option value={1}>⚡ Past 24 Hours (Fastest Callbacks — Recommended)</option>
                  <option value={3}>📅 Past 3 Days (Recent Openings)</option>
                  <option value={7}>🗓️ Past 7 Days (Last 1 Week)</option>
                  <option value={0}>🌐 Anytime (All Active Postings)</option>
                </select>
              </div>

              {/* Portal Selection */}
              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
                  Target Job Portals ({selectedPortals.length} enabled)
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                  {AVAILABLE_PORTALS.map(portal => {
                    const isSelected = selectedPortals.includes(portal.id);
                    return (
                      <div
                        key={portal.id}
                        onClick={() => togglePortal(portal.id)}
                        style={{
                          padding: '10px',
                          borderRadius: '12px',
                          border: isSelected ? '1.5px solid #4a6b28' : '1px solid rgba(255, 255, 255, 0.9)',
                          background: isSelected ? 'rgba(91, 132, 51, 0.12)' : 'rgba(255, 255, 255, 0.65)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          transition: 'all 0.2s ease',
                          boxShadow: '0 2px 6px rgba(15, 40, 20, 0.05)',
                        }}
                      >
                        <span style={{ fontSize: '1.3rem' }}>{portal.icon}</span>
                        <div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: isSelected ? '#37501e' : 'var(--text-main)' }}>
                            {portal.label}
                          </div>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                            {portal.desc}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Limit & Anti-bot Pacing */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: '1fr 1fr', 
                gap: '16px', 
                background: 'rgba(255, 255, 255, 0.65)', 
                padding: '12px 16px', 
                borderRadius: '14px', 
                border: '1.5px solid rgba(255, 255, 255, 0.95)',
                boxShadow: '0 2px 8px rgba(15, 40, 20, 0.04)',
              }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                    Max New Postings to Ingest
                  </label>
                  <select
                    className="form-select"
                    value={maxProcess}
                    onChange={e => setMaxProcess(e.target.value)}
                    style={{ fontSize: '0.85rem' }}
                  >
                    <option value="1">1 job (Instant verification)</option>
                    <option value="2">2 jobs (Fast batch)</option>
                    <option value="3">3 jobs (Standard)</option>
                    <option value="5">5 jobs (Deep discovery)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                    Stealth & Deduplication
                  </label>
                  <div style={{ marginTop: '6px', fontSize: '0.8rem', color: 'var(--emerald-light)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ShieldCheck size={16} />
                    <span>Anti-Bot Stealth Active</span>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Active Scanning Animation & Real-Time Live Activity Stream */}
          {isScanning && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px 0' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  border: '3px solid rgba(6, 182, 212, 0.2)',
                  borderTopColor: '#06b6d4',
                  borderRadius: '50%',
                  margin: '0 auto 16px',
                  animation: 'spin 1s linear infinite'
                }}></div>
                <h3 style={{ margin: '0 0 6px 0', fontSize: '1.15rem', fontWeight: 800, color: '#06b6d4' }}>
                  Autonomous Job Discovery in Progress
                </h3>
                <p style={{ margin: '0 0 14px 0', fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600 }}>
                  {scanStep}
                </p>

                {/* Real-Time Live Counters */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', marginBottom: '16px' }}>
                  <div style={{ background: 'rgba(6, 182, 212, 0.1)', border: '1px solid rgba(6, 182, 212, 0.3)', borderRadius: '8px', padding: '6px 14px', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-dim)', marginRight: '6px' }}>Found:</span>
                    <strong style={{ color: '#06b6d4' }}>{liveCounters.found}</strong>
                  </div>
                  <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '8px', padding: '6px 14px', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-dim)', marginRight: '6px' }}>Ready:</span>
                    <strong style={{ color: 'var(--emerald)' }}>{liveCounters.ready}</strong>
                  </div>
                  <div style={{ background: 'rgba(148, 163, 184, 0.1)', border: '1px solid rgba(148, 163, 184, 0.3)', borderRadius: '8px', padding: '6px 14px', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-dim)', marginRight: '6px' }}>Archived:</span>
                    <strong style={{ color: 'var(--text-muted)' }}>{liveCounters.archived}</strong>
                  </div>
                </div>
              </div>

              {/* LIVE REAL-TIME SSE LOGS */}
              <div style={{
                background: 'rgba(5, 8, 22, 0.85)',
                border: '1px solid rgba(6, 182, 212, 0.3)',
                borderRadius: '12px',
                padding: '14px 16px',
                fontFamily: 'monospace',
                fontSize: '0.76rem',
                maxHeight: '180px',
                overflowY: 'auto',
                boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.5)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '4px' }}>
                  <span style={{ color: '#06b6d4', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06b6d4', display: 'inline-block', boxShadow: '0 0 8px #06b6d4' }} />
                    REAL-TIME DISCOVERY EVENTS
                  </span>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>
                    SSE Channel: discovery
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {liveDiscoveryEvents.length === 0 ? (
                    <div style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                      Listening for scraper and scoring telemetry...
                    </div>
                  ) : (
                    liveDiscoveryEvents.map((ev, idx) => (
                      <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', lineHeight: '1.4' }}>
                        <span style={{ color: '#06b6d4', opacity: 0.8 }}>[{ev.timestamp}]</span>
                        <span style={{ 
                          color: ev.status === 'Ready' ? 'var(--emerald)' : ev.status === 'Archived' ? 'var(--amber)' : '#e2e8f0',
                          flex: 1
                        }}>
                          {ev.message}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Discovery Report */}
          {report && !isScanning && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{
                background: 'rgba(6, 182, 212, 0.08)',
                border: '1px solid rgba(6, 182, 212, 0.25)',
                borderRadius: '12px',
                padding: '16px',
                textAlign: 'center',
              }}>
                <CheckCircle2 size={28} color="#06b6d4" style={{ margin: '0 auto 6px auto' }} />
                <h3 style={{ margin: '0 0 4px 0', color: 'var(--text-primary)', fontSize: '1.1rem' }}>
                  Discovery & Ingestion Completed!
                </h3>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Scanned live postings and auto-triaged based on ATS match score.
                </p>
              </div>

              {/* Stats Breakdown */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', textAlign: 'center' }}>
                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>{report.total_discovered}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>Discovered</div>
                </div>
                <div style={{ background: 'rgba(52, 211, 153, 0.1)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(52, 211, 153, 0.3)' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--emerald-light)' }}>{report.high_matches_ready}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--emerald-light)', marginTop: '2px' }}>Ready (≥{minMatchScore}%)</div>
                </div>
                <div style={{ background: 'rgba(244, 63, 94, 0.1)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(244, 63, 94, 0.25)' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--rose-light)' }}>{report.low_matches_archived}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--rose-light)', marginTop: '2px' }}>Archived (&lt;{minMatchScore}%)</div>
                </div>
                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f59e0b' }}>{report.duplicates_skipped}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>Deduplicated</div>
                </div>
              </div>

              {/* Triaged Jobs List */}
              {report.jobs && report.jobs.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    Triaged Pipeline Additions ({report.jobs.length})
                  </div>
                  <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {report.jobs.map(job => (
                      <div
                        key={job.job_id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          background: 'rgba(255, 255, 255, 0.03)',
                          borderRadius: '8px',
                          border: '1px solid var(--border-subtle)',
                          fontSize: '0.8rem',
                        }}
                      >
                        <div>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{job.title}</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: '6px' }}>at {job.company}</span>
                          <span style={{ marginLeft: '8px', fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', textTransform: 'uppercase' }}>
                            {job.portal}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{
                            fontWeight: 700,
                            color: job.match_score >= minMatchScore ? 'var(--emerald-light)' : 'var(--text-muted)'
                          }}>
                            {job.match_score}%
                          </span>
                          <span style={{
                            padding: '3px 8px',
                            borderRadius: '9999px',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            background: job.status === 'Ready' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(255, 255, 255, 0.08)',
                            color: job.status === 'Ready' ? 'var(--emerald-light)' : 'var(--text-muted)',
                          }}>
                            {job.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          {!report ? (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleResetAndClose}
                disabled={isScanning}
              >
                Cancel
              </button>
              <button
                id="launch-discovery-btn"
                type="button"
                className="btn btn-primary"
                onClick={handleStartDiscovery}
                disabled={isScanning}
                style={{
                  background: 'linear-gradient(135deg, #688e3c 0%, #4a6c27 100%)',
                  border: '1.5px solid rgba(255, 255, 255, 0.40)',
                  color: '#ffffff',
                  fontWeight: 700,
                  borderRadius: '9999px',
                  boxShadow: '0 4px 16px rgba(45, 75, 20, 0.30)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Sparkles size={16} />
                <span>{isScanning ? 'Scanning...' : 'Launch Autonomous Discovery'}</span>
              </button>
            </>
          ) : (
            <button
              id="view-discovered-dashboard-btn"
              type="button"
              className="btn btn-primary"
              onClick={handleResetAndClose}
              style={{
                background: 'linear-gradient(135deg, #688e3c 0%, #4a6c27 100%)',
                border: '1.5px solid rgba(255, 255, 255, 0.40)',
                color: '#ffffff',
                fontWeight: 700,
                borderRadius: '9999px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>View On Pipeline Board</span>
              <ArrowRight size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
