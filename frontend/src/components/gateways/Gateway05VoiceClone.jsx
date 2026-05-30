// src/components/gateways/Gateway05VoiceClone.jsx — Voice Clone Gateway
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiPost, apiGet, apiGetBlob, triggerDownload } from '../../lib/apiClient';

// ─── Telemetry lines for voice clone processing ───────────────────────────────

const PLANTING_TELEMETRY = [
  'LOADING VOCAL SAMPLE...',
  'CLONING VOCAL SIGNATURE...',
  'SYNTHESIZING PERFORMANCE FROM LYRICS...',
  'ALIGNING TO BEAT GRID...',
  'EMBEDDING VOCAL STEM...',
  'REPLACING SOURCE ARTIST VOICE...',
  'RENDERING FINAL MIX...',
  'PRINTING MASTER...',
];

// ─── TelemetryFeed sub-component ──────────────────────────────────────────────

function TelemetryFeed({ lines, active }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!active) { setCount(0); return; }
    setCount(0);
    const timers = lines.map((_, i) =>
      setTimeout(() => setCount(c => Math.max(c, i + 1)), i * 420)
    );
    return () => timers.forEach(clearTimeout);
  }, [active, lines]);

  return (
    <div style={{
      fontFamily: 'JetBrains Mono', fontSize: '11px',
      lineHeight: 1.9, color: 'rgba(255,255,255,0.7)',
    }}>
      {lines.slice(0, count).map((line, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          animation: 'telemetryIn 0.15s ease-out',
        }}>
          <span style={{ color: '#00ff88', flexShrink: 0 }}>›</span>
          <span style={{ opacity: i < count - 1 ? 0.65 : 1 }}>{line}</span>
          {i === count - 1 && (
            <span style={{ color: '#00ff88', animation: 'blink 0.7s step-end infinite' }}>█</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── MetricCell sub-component ─────────────────────────────────────────────────

function MetricCell({ label, value, highlight }) {
  return (
    <div style={{
      padding: '10px 12px',
      border: `1px solid ${highlight ? 'rgba(0,255,136,0.3)' : 'rgba(255,255,255,0.08)'}`,
      background: highlight ? 'rgba(0,255,136,0.05)' : 'transparent',
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'rgba(255,255,255,0.45)', marginBottom: '4px', letterSpacing: '0.1em',
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '14px',
        color: highlight ? '#00ff88' : 'rgba(255,255,255,0.9)', fontWeight: 500,
      }}>
        {value}
      </div>
    </div>
  );
}

// ─── Main Gateway05VoiceClone component ───────────────────────────────────────

export default function Gateway05VoiceClone({ projectId, project, onComplete }) {
  const [voiceProfile, setVoiceProfile] = useState(null);
  const [cloneStatus, setCloneStatus] = useState('idle'); // idle | processing | complete | failed
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const pollRef = useRef(null);
  const fileInputRef = useRef(null);
  const dropRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  // ─── Upload voice sample ─────────────────────────────────────────────────────

  const handleUploadSample = useCallback(async (file) => {
    try {
      const form = new FormData();
      form.append('file', file);
      await apiPost(`/api/projects/${projectId}/voice-sample`, form);
      setVoiceProfile({ name: file.name.toUpperCase(), file });
      setError(null);
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    }
  }, [projectId]);

  // ─── Trigger voice clone ──────────────────────────────────────────────────────

  const handleTriggerClone = useCallback(async () => {
    setCloneStatus('processing');
    setError(null);
    try {
      await apiPost(`/api/projects/${projectId}/voice-clone`, {});
      startPolling();
    } catch (err) {
      setCloneStatus('failed');
      setError(err.message);
    }
  }, [projectId]);

  // ─── Polling ──────────────────────────────────────────────────────────────────

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const result = await apiGet(`/api/projects/${projectId}/voice-clone-status`);
        if (result.status === 'complete') {
          setCloneStatus('complete');
          clearInterval(pollRef.current);
          pollRef.current = null;
        } else if (result.status === 'failed') {
          setCloneStatus('failed');
          setError(result.error || 'Voice clone failed');
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 3000);
  }, [projectId]);

  // ─── Cleanup polling on unmount ───────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  // ─── Download cloned vocal ────────────────────────────────────────────────────

  const handleDownload = useCallback(async () => {
    setDownloading(true);
    try {
      const blob = await apiGetBlob(`/api/projects/${projectId}/download-vocal`);
      triggerDownload(blob, 'CLONED_VOCAL.wav');
    } catch (err) {
      setError(`Download failed: ${err.message}`);
    } finally {
      setDownloading(false);
    }
  }, [projectId]);

  // ─── Retry after failure ──────────────────────────────────────────────────────

  const handleRetry = useCallback(() => {
    setCloneStatus('idle');
    setError(null);
  }, []);

  // ─── Drag and drop handlers ───────────────────────────────────────────────────

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('audio/')) {
      handleUploadSample(file);
    }
  }, [handleUploadSample]);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUploadSample(file);
    }
    e.target.value = '';
  }, [handleUploadSample]);

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div style={{
      fontFamily: 'JetBrains Mono',
      display: 'flex', flexDirection: 'column', gap: '16px',
    }}>
      {/* Header */}
      <div style={{
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        paddingBottom: '12px',
      }}>
        <div style={{
          fontSize: '10px', letterSpacing: '0.15em',
          color: '#00ff88', marginBottom: '4px',
        }}>
          // GATEWAY 05 — RE-PLANT
        </div>
        <div style={{
          fontSize: '9px', letterSpacing: '0.12em',
          color: 'rgba(255,255,255,0.3)',
        }}>
          VOICE CLONE · VOCAL SYNTHESIS · FINAL MASTER
        </div>
      </div>

      {/* ─── IDLE: Upload area ─────────────────────────────────────────────────── */}
      {cloneStatus === 'idle' && !voiceProfile && (
        <div
          ref={dropRef}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: `1px dashed ${dragOver ? '#00ff88' : 'rgba(0,255,136,0.5)'}`,
            background: dragOver ? 'rgba(0,255,136,0.08)' : 'rgba(0,255,136,0.03)',
            padding: '28px',
            textAlign: 'center',
            cursor: 'pointer',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px',
            transition: 'all 0.15s',
          }}
        >
          <div style={{
            fontSize: '10px', color: '#00ff88', letterSpacing: '0.1em',
          }}>
            LOAD VOCAL SAMPLE
          </div>
          <div style={{
            fontSize: '9px', color: 'rgba(255,255,255,0.3)',
          }}>
            DRAG & DROP OR CLICK TO SELECT
          </div>
          <div style={{
            fontSize: '9px', color: 'rgba(255,255,255,0.2)', marginTop: '4px',
          }}>
            WAV · MP3 · 5–30 SEC CLEAN VOCAL
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
        </div>
      )}

      {/* ─── IDLE: Voice profile loaded ────────────────────────────────────────── */}
      {cloneStatus === 'idle' && voiceProfile && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Profile info */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '12px 14px',
            border: '1px solid rgba(0,255,136,0.35)',
            background: 'rgba(0,255,136,0.04)',
          }}>
            <div style={{
              width: '8px', height: '8px',
              background: '#00ff88',
              boxShadow: '0 0 8px rgba(0,255,136,0.6)',
              flexShrink: 0,
            }} />
            <div>
              <div style={{ fontSize: '11px', color: '#00ff88' }}>
                VOCAL PROFILE LOADED
              </div>
              <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.45)', marginTop: '3px' }}>
                {voiceProfile.name}
              </div>
            </div>
          </div>

          {/* Replace sample button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              fontSize: '9px', letterSpacing: '0.08em',
              color: 'rgba(255,255,255,0.45)', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.15)', padding: '7px 10px',
              cursor: 'pointer', fontFamily: 'JetBrains Mono',
            }}
          >
            REPLACE SAMPLE
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />

          {/* Clone button */}
          <button
            onClick={handleTriggerClone}
            style={{
              background: '#00ff88',
              color: '#000000',
              fontFamily: 'JetBrains Mono',
              fontWeight: 500,
              fontSize: '12px',
              letterSpacing: '0.1em',
              padding: '12px 20px',
              border: 'none',
              boxShadow: '0 0 20px rgba(0,255,136,0.4)',
              cursor: 'pointer',
              transition: 'opacity 0.15s',
            }}
          >
            CLONE VOICE
          </button>
        </div>
      )}

      {/* ─── PROCESSING: Telemetry + status ────────────────────────────────────── */}
      {cloneStatus === 'processing' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Status indicator */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '12px 14px',
            border: '1px solid rgba(0,255,136,0.25)',
            background: 'rgba(0,255,136,0.03)',
          }}>
            <div style={{
              width: '8px', height: '8px',
              background: '#00ff88',
              boxShadow: '0 0 8px rgba(0,255,136,0.6)',
              animation: 'blink 1s step-end infinite',
              flexShrink: 0,
            }} />
            <div style={{ fontSize: '10px', color: '#00ff88', letterSpacing: '0.1em' }}>
              VOICE CLONE IN PROGRESS
            </div>
          </div>

          {/* Metrics during processing */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <MetricCell label="STATUS" value="PROCESSING" highlight />
            <MetricCell label="ENGINE" value="XTTS-V2" />
            <MetricCell label="SAMPLE" value={voiceProfile?.name || '—'} />
            <MetricCell label="POLL INTERVAL" value="3S" />
          </div>

          {/* Telemetry feed */}
          <TelemetryFeed lines={PLANTING_TELEMETRY} active={true} />
        </div>
      )}

      {/* ─── COMPLETE: Download + proceed ──────────────────────────────────────── */}
      {cloneStatus === 'complete' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Success indicator */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '12px 14px',
            border: '1px solid rgba(0,255,136,0.5)',
            background: 'rgba(0,255,136,0.06)',
          }}>
            <div style={{
              width: '8px', height: '8px',
              background: '#00ff88',
              boxShadow: '0 0 12px rgba(0,255,136,0.8)',
              flexShrink: 0,
            }} />
            <div style={{ fontSize: '11px', color: '#00ff88' }}>
              VOICE CLONE: COMPLETE
            </div>
          </div>

          {/* Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
            <MetricCell label="STATUS" value="COMPLETE" highlight />
            <MetricCell label="ENGINE" value="XTTS-V2" />
            <MetricCell label="OUTPUT" value="CLONED_VOCAL.WAV" />
          </div>

          {/* Download button */}
          <button
            onClick={handleDownload}
            disabled={downloading}
            style={{
              background: 'transparent',
              color: '#00ff88',
              fontFamily: 'JetBrains Mono',
              fontWeight: 400,
              fontSize: '12px',
              letterSpacing: '0.1em',
              padding: '11px 19px',
              border: '1px solid #00ff88',
              cursor: downloading ? 'default' : 'pointer',
              opacity: downloading ? 0.5 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            {downloading ? '// DOWNLOADING...' : '> DOWNLOAD CLONED VOCAL'}
          </button>

          {/* Proceed / Complete button */}
          <button
            onClick={onComplete}
            style={{
              background: '#00ff88',
              color: '#000000',
              fontFamily: 'JetBrains Mono',
              fontWeight: 500,
              fontSize: '12px',
              letterSpacing: '0.1em',
              padding: '12px 20px',
              border: 'none',
              boxShadow: '0 0 20px rgba(0,255,136,0.4)',
              cursor: 'pointer',
              transition: 'opacity 0.15s',
            }}
          >
            COMPLETE
          </button>
        </div>
      )}

      {/* ─── FAILED: Error + retry ─────────────────────────────────────────────── */}
      {cloneStatus === 'failed' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Error indicator */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '12px 14px',
            border: '1px solid rgba(255,60,60,0.4)',
            background: 'rgba(255,60,60,0.05)',
          }}>
            <div style={{
              width: '8px', height: '8px',
              background: '#ff3c3c',
              boxShadow: '0 0 8px rgba(255,60,60,0.6)',
              flexShrink: 0,
            }} />
            <div>
              <div style={{ fontSize: '11px', color: '#ff3c3c' }}>
                VOICE CLONE: FAILED
              </div>
              {error && (
                <div style={{
                  fontSize: '9px', color: 'rgba(255,255,255,0.45)',
                  marginTop: '4px', lineHeight: 1.5,
                }}>
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* Retry button */}
          <button
            onClick={handleRetry}
            style={{
              background: 'transparent',
              color: '#00ff88',
              fontFamily: 'JetBrains Mono',
              fontWeight: 400,
              fontSize: '12px',
              letterSpacing: '0.1em',
              padding: '11px 19px',
              border: '1px solid #00ff88',
              cursor: 'pointer',
              transition: 'opacity 0.15s',
            }}
          >
            RETRY
          </button>
        </div>
      )}

      {/* ─── Error display (for upload errors in idle state) ───────────────────── */}
      {cloneStatus === 'idle' && error && (
        <div style={{
          padding: '10px 12px',
          border: '1px solid rgba(255,60,60,0.3)',
          background: 'rgba(255,60,60,0.04)',
          fontSize: '10px', color: '#ff3c3c',
        }}>
          {error}
        </div>
      )}
    </div>
  );
}
