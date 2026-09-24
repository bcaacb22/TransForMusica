import { useState, useEffect, useRef, useCallback } from 'react'
import { apiPost, apiGet, apiGetBlob, triggerDownload } from '../../lib/apiClient'
import AudioPlayer from '../AudioPlayer'

// ─── Stem manifest (matches the demucs + basic-pitch pipeline output) ────────

const ALL_STEMS = [
  { id: 'vocals',       label: 'VOCALS',       audio: true, midi: true, xml: true },
  { id: 'instrumental', label: 'INSTRUMENTAL', audio: true, midi: true, xml: true },
  { id: 'drums',        label: 'DRUMS',        audio: true, midi: true, xml: true },
  { id: 'bass',         label: 'BASS',         audio: true, midi: true, xml: true },
  { id: 'other',        label: 'OTHER',        audio: true, midi: true, xml: true },
]

function initStemSelection() {
  const sel = {}
  ALL_STEMS.forEach(s => {
    if (s.audio) sel[`${s.id}_audio`] = true
    if (s.midi)  sel[`${s.id}_midi`]  = true
    if (s.xml)   sel[`${s.id}_xml`]   = true
  })
  return sel
}

// ─── Stem Selection Table ─────────────────────────────────────────────────────

function StemSelectionTable({ selection, onChange }) {
  const toggle = (key) => onChange({ ...selection, [key]: !selection[key] })

  const selectAll = () => {
    const sel = {}
    ALL_STEMS.forEach(s => {
      if (s.audio) sel[`${s.id}_audio`] = true
      if (s.midi)  sel[`${s.id}_midi`]  = true
      if (s.xml)   sel[`${s.id}_xml`]   = true
    })
    onChange(sel)
  }

  const deselectAll = () => {
    const sel = {}
    Object.keys(selection).forEach(k => { sel[k] = false })
    onChange(sel)
  }

  const totalSelected = Object.values(selection).filter(Boolean).length

  const Tick = ({ active, onClick }) => (
    <button
      onClick={onClick}
      style={{
        width: '28px', height: '22px',
        background: active ? 'var(--neon)' : 'rgba(255,255,255,0.05)',
        border: `1px solid ${active ? 'var(--neon)' : 'rgba(255,255,255,0.12)'}`,
        color: active ? '#000' : 'rgba(255,255,255,0.2)',
        fontFamily: 'JetBrains Mono', fontSize: '10px',
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: active ? '0 0 6px rgba(0,255,136,0.4)' : 'none',
        transition: 'all 0.1s',
        flexShrink: 0,
      }}
    >
      {active ? '✓' : '—'}
    </button>
  )

  const NA = () => (
    <div style={{
      width: '28px', height: '22px',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'JetBrains Mono', fontSize: '9px',
      color: 'rgba(255,255,255,0.1)', flexShrink: 0,
    }}>·</div>
  )

  return (
    <div>
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 28px 28px 28px',
        gap: '4px', alignItems: 'center',
        padding: '4px 0 6px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        marginBottom: '4px',
      }}>
        <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', letterSpacing: '0.1em' }}>STEM</div>
        {['WAV', 'MIDI', 'XML'].map(h => (
          <div key={h} style={{ fontFamily: 'JetBrains Mono', fontSize: '8px', color: 'var(--neon)', textAlign: 'center', letterSpacing: '0.05em' }}>{h}</div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '10px' }}>
        {ALL_STEMS.map(s => (
          <div key={s.id} style={{
            display: 'grid', gridTemplateColumns: '1fr 28px 28px 28px',
            gap: '4px', alignItems: 'center',
            padding: '4px 6px',
            background: s.id === 'vocal' ? 'rgba(0,255,136,0.04)' : 'transparent',
            border: s.id === 'vocal' ? '1px solid rgba(0,255,136,0.12)' : '1px solid transparent',
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '10px',
              color: s.id === 'vocal' ? 'var(--neon)' : 'var(--text-terminal)',
              letterSpacing: '0.06em',
            }}>
              {s.label}
            </div>
            {s.audio ? <Tick active={!!selection[`${s.id}_audio`]} onClick={() => toggle(`${s.id}_audio`)} /> : <NA />}
            {s.midi  ? <Tick active={!!selection[`${s.id}_midi`]}  onClick={() => toggle(`${s.id}_midi`)}  /> : <NA />}
            {s.xml   ? <Tick active={!!selection[`${s.id}_xml`]}   onClick={() => toggle(`${s.id}_xml`)}   /> : <NA />}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button onClick={selectAll} style={{
            fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.08em',
            color: 'var(--text-secondary)', background: 'transparent',
            border: '1px solid rgba(255,255,255,0.15)', padding: '5px 8px', cursor: 'pointer',
          }}>ALL</button>
          <button onClick={deselectAll} style={{
            fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.08em',
            color: 'var(--text-secondary)', background: 'transparent',
            border: '1px solid rgba(255,255,255,0.15)', padding: '5px 8px', cursor: 'pointer',
          }}>NONE</button>
        </div>
        <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)' }}>
          <span style={{ color: 'var(--neon)' }}>{totalSelected}</span> FILE{totalSelected !== 1 ? 'S' : ''} SELECTED
        </div>
      </div>
    </div>
  )
}

// ─── Metric Cell ──────────────────────────────────────────────────────────────

function MetricCell({ label, value, highlight }) {
  return (
    <div style={{
      padding: '10px 12px',
      border: `1px solid ${highlight ? 'rgba(0,255,136,0.3)' : 'rgba(255,255,255,0.08)'}`,
      background: highlight ? 'rgba(0,255,136,0.05)' : 'transparent',
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'var(--text-secondary)', marginBottom: '4px', letterSpacing: '0.1em',
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '14px',
        color: highlight ? 'var(--neon)' : 'var(--text-primary)', fontWeight: 500,
      }}>
        {value}
      </div>
    </div>
  )
}

// ─── Mock fallback data ───────────────────────────────────────────────────────

const MOCK_GATEWAY_02 = {
  stems: ['KICK', 'BASS', 'MELODY', 'HARMONY', 'PERCUSSION', 'VOCAL'],
  midiFiles: 6,
  musicXmlFiles: 4,
  bpm: 87,
  key: 'Am',
}

// ─── Gateway02Deconstruction ──────────────────────────────────────────────────

export default function Gateway02Deconstruction({ projectId, project, onComplete }) {
  const [transformPending, setTransformPending] = useState(true)
  const [transformResult, setTransformResult] = useState(null)
  const [stemSelection, setStemSelection] = useState(initStemSelection)
  const [downloading, setDownloading] = useState(false)
  const [apiError, setApiError] = useState(null)
  const [transcription, setTranscription] = useState(null)
  const [progress, setProgress] = useState(null)
  const pollRef = useRef(null)

  // Trigger transform on mount and poll for status
  useEffect(() => {
    let cancelled = false

    async function triggerTransform() {
      try {
        await apiPost(`/api/projects/${projectId}/transform`, {})
        startPolling()
      } catch (e) {
        if (!cancelled) {
          setTransformPending(false)
          setApiError(`Transform: ${e.message}`)
        }
      }
    }

    function startPolling() {
      pollRef.current = setInterval(async () => {
        try {
          const data = await apiGet(`/api/projects/${projectId}/transform-status`)
          if (data.status === 'complete') {
            clearInterval(pollRef.current)
            pollRef.current = null
            if (!cancelled) {
              setTransformPending(false)
              setTransformResult(data)
              apiGet(`/api/projects/${projectId}/transcription`)
                .then(t => { if (!cancelled && t?.text) setTranscription(t.text) })
                .catch(() => {})
            }
          } else if (data.status === 'failed') {
            clearInterval(pollRef.current)
            pollRef.current = null
            if (!cancelled) {
              setTransformPending(false)
              setApiError(`Transform: ${data.error}`)
            }
          } else if (data.status === 'processing' && data.progress) {
            if (!cancelled) setProgress(data.progress)
          }
        } catch (e) {
          // keep polling on transient errors
        }
      }, 3000)
    }

    triggerTransform()

    return () => {
      cancelled = true
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [projectId])

  // Compute display data from transform result or mock
  const g02 = transformResult
    ? {
        stems: transformResult.midi_files?.length
          ? transformResult.midi_files.map(f => f.split('/').pop().replace('.mid', '').toUpperCase())
          : MOCK_GATEWAY_02.stems,
        midiFiles: transformResult.midi_files?.length ?? MOCK_GATEWAY_02.midiFiles,
        musicXmlFiles: transformResult.musicxml_files?.length ?? MOCK_GATEWAY_02.musicXmlFiles,
        bpm: MOCK_GATEWAY_02.bpm,
        key: MOCK_GATEWAY_02.key,
      }
    : MOCK_GATEWAY_02

  const metrics = [
    { label: 'STEMS', value: `0${g02.midiFiles}` },
    { label: 'MIDI FILES', value: `0${g02.midiFiles}` },
    { label: 'MUSICXML', value: `0${g02.musicXmlFiles}` },
    { label: 'BPM', value: String(g02.bpm) },
    { label: 'KEY', value: g02.key },
  ]

  const handleProceed = useCallback(() => {
    onComplete()
  }, [onComplete])

  const handleExit = useCallback(() => {
    if (!projectId) return
    setApiError(null)
    // Direct browser download — streams the (large) ZIP natively instead of
    // buffering it in memory via fetch, which fails on ~180MB packages.
    const a = document.createElement('a')
    a.href = `/api/projects/${projectId}/download-stems`
    a.download = 'DAW_PACKAGE.zip'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }, [projectId])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Error banner */}
      {apiError && (
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '10px',
          color: 'var(--danger)', letterSpacing: '0.08em',
          padding: '8px 14px',
          border: '1px solid rgba(255,59,59,0.3)',
          background: 'rgba(255,59,59,0.06)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexShrink: 0,
        }}>
          <span>// ERROR: {apiError}</span>
          <button
            onClick={() => setApiError(null)}
            style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px',
              color: 'rgba(255,255,255,0.4)', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.15)', padding: '3px 8px', cursor: 'pointer',
            }}
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Main content */}
      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Earned product title */}
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '9px',
          color: 'var(--neon)', letterSpacing: '0.15em',
          borderBottom: '1px solid rgba(0,255,136,0.2)',
          paddingBottom: '10px',
        }}>
          EARNED PRODUCT — THE DAW PACKAGE
        </div>

        {/* Gateway content: pending or complete */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {transformPending ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '9px',
                color: 'var(--neon)', letterSpacing: '0.15em',
              }}>
                ▶ {progress?.detail?.toUpperCase() || 'DECONSTRUCTING AUDIO...'}
              </div>

              {/* Live progress bar */}
              <div>
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'JetBrains Mono', fontSize: '9px',
                  color: 'var(--text-secondary)', marginBottom: '6px',
                }}>
                  <span>{(progress?.stage || 'start').toUpperCase()}</span>
                  <span style={{ color: 'var(--neon)' }}>{progress?.percent ?? 0}%</span>
                </div>
                <div style={{
                  height: '6px', background: 'rgba(0,255,136,0.1)',
                  border: '1px solid rgba(0,255,136,0.2)', position: 'relative', overflow: 'hidden',
                }}>
                  <div style={{
                    position: 'absolute', top: 0, left: 0, bottom: 0,
                    width: `${progress?.percent ?? 0}%`,
                    background: 'var(--neon)', boxShadow: 'var(--neon-glow)',
                    transition: 'width 0.6s ease',
                  }} />
                </div>
              </div>

              {/* Stage checklist */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {[
                  { key: 'basic_pitch', label: 'MIDI TRANSCRIPTION (BASIC PITCH)' },
                  { key: 'demucs', label: 'NEURAL STEM SEPARATION (DEMUCS)' },
                  { key: 'midi', label: 'STEM → MIDI + MUSICXML' },
                  { key: 'instrumental', label: 'INSTRUMENTAL MIX (NO VOCALS)' },
                  { key: 'transcription', label: 'VOCAL TRANSCRIPTION' },
                ].map((s, i, arr) => {
                  const order = ['basic_pitch', 'demucs', 'midi', 'instrumental', 'transcription']
                  const cur = progress?.stage || 'start'
                  const curIdx = order.indexOf(cur)
                  const done = curIdx > i || cur === 'done'
                  const active = cur === s.key
                  return (
                    <div key={s.key} style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.08em',
                      color: done ? 'rgba(0,255,136,0.6)' : active ? 'var(--neon)' : 'rgba(255,255,255,0.25)',
                    }}>
                      <span style={{ width: '12px' }}>{done ? '✓' : active ? '▶' : '·'}</span>
                      <span>{s.label}</span>
                      {active && <span style={{ animation: 'blink 0.8s step-end infinite' }}>█</span>}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <>
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '9px',
                color: 'var(--text-secondary)', letterSpacing: '0.1em',
              }}>
                STEMS EXTRACTED · SELECT FILES TO DOWNLOAD
              </div>
              <StemSelectionTable selection={stemSelection} onChange={setStemSelection} />

              {/* Audio players — hear the stems to confirm the right files */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '9px',
                  color: 'var(--text-secondary)', letterSpacing: '0.12em',
                }}>
                  LISTEN
                </div>
                <AudioPlayer src={`/api/projects/${projectId}/stem-audio/instrumental.mp3`} label="INSTRUMENTAL" />
                <AudioPlayer src={`/api/projects/${projectId}/stem-audio/vocals.mp3`} label="VOCALS" />
              </div>

              {/* Original-vocal transcription */}
              {transcription && (
                <div style={{
                  border: '1px solid rgba(255,255,255,0.1)',
                  padding: '12px',
                }}>
                  <div style={{
                    fontFamily: 'JetBrains Mono', fontSize: '9px',
                    color: 'var(--neon)', letterSpacing: '0.12em', marginBottom: '8px',
                  }}>
                    ORIGINAL LYRICS — TRANSCRIBED
                  </div>
                  <div style={{
                    fontFamily: 'Outfit', fontWeight: 300, fontSize: '11px',
                    lineHeight: 1.7, color: 'rgba(255,255,255,0.75)',
                    whiteSpace: 'pre-line', maxHeight: '140px', overflow: 'auto',
                  }}>
                    {transcription}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Metrics grid (shown when transform is complete) */}
        {!transformPending && (
          <div>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '10px',
              color: 'var(--text-secondary)', letterSpacing: '0.12em',
              marginBottom: '8px',
            }}>
              LOCKED METRICS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
              {metrics.map(m => (
                <MetricCell key={m.label} label={m.label} value={m.value} highlight={m.highlight} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{
        padding: '14px 18px',
        borderTop: '1px solid var(--border-dim)',
        display: 'flex', flexDirection: 'column', gap: '8px',
      }}>
        <button
          onClick={!downloading ? handleExit : undefined}
          disabled={downloading || transformPending}
          style={{
            background: 'transparent',
            color: 'var(--neon)',
            fontFamily: 'JetBrains Mono',
            fontWeight: 400,
            fontSize: '11px',
            letterSpacing: '0.1em',
            padding: '7px 13px',
            border: '1px solid var(--neon)',
            transition: 'opacity 0.15s',
          }}
        >
          {downloading
            ? '// PACKAGING...'
            : transformPending
              ? '// PROCESSING...'
              : 'DOWNLOAD DAW PACKAGE'}
        </button>
        <button
          onClick={handleProceed}
          disabled={transformPending}
          style={{
            background: 'var(--neon)',
            color: '#000000',
            fontFamily: 'JetBrains Mono',
            fontWeight: 500,
            fontSize: '12px',
            letterSpacing: '0.1em',
            padding: '12px 20px',
            border: 'none',
            boxShadow: transformPending ? 'none' : 'var(--neon-glow)',
            transition: 'opacity 0.15s',
          }}
        >
          {transformPending ? '// PROCESSING...' : '> PROCEED TO MORPH ENGINE'}
        </button>
      </div>
    </div>
  )
}
