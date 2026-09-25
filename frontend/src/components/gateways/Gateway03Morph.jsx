import { useState, useEffect, useRef, useCallback } from 'react'
import { apiPost, apiGet } from '../../lib/apiClient'
import AudioPlayer from '../AudioPlayer'

// ─── Constants ────────────────────────────────────────────────────────────────

const VIOLATION_LINE = 80
const DEFAULT_TARGET = 35
const KEY_OPTIONS = ['AUTO', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

// ─── Similarity scale ─────────────────────────────────────────────────────────
// Interactive when unlocked (user drags the morph target), locked readout after
// the morph completes (target vs. achieved). Scale measures similarity to
// source; the violation line is 80%.

function SimilarityScale({ current, target, onTargetChange, violationLine = VIOLATION_LINE, locked = false }) {
  return (
    <div style={{
      border: `1px solid ${locked ? 'rgba(255,255,255,0.12)' : 'rgba(0,255,136,0.45)'}`,
      background: locked ? 'transparent' : 'rgba(0,255,136,0.03)',
      padding: '14px',
      boxShadow: locked ? 'none' : '0 0 20px rgba(0,255,136,0.08)',
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.15em',
        color: locked ? 'var(--text-secondary)' : 'var(--neon)',
        marginBottom: '12px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>// {locked ? 'SIMILARITY — MEASURED' : 'SET MORPH TARGET'}</span>
        {!locked && (
          <span style={{ color: 'var(--danger)', fontSize: '9px' }}>
            VIOLATION LINE: {violationLine}%
          </span>
        )}
      </div>

      {!locked && (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '16px', marginBottom: '14px' }}>
          <div>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px',
              color: 'var(--text-secondary)', marginBottom: '4px', letterSpacing: '0.1em',
            }}>
              SIMILARITY TARGET
            </div>
            <div style={{
              fontFamily: 'Unbounded', fontWeight: 700, fontSize: '28px',
              color: 'var(--neon)', lineHeight: 1,
              textShadow: '0 0 18px rgba(0,255,136,0.5)',
            }}>
              {target}%
            </div>
          </div>
          <div style={{ flex: 1, paddingBottom: '6px' }}>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px',
              color: 'var(--text-secondary)', marginBottom: '4px', letterSpacing: '0.1em',
            }}>
              DEVIATION
            </div>
            <div style={{
              fontFamily: 'Unbounded', fontWeight: 700, fontSize: '28px',
              color: 'rgba(255,255,255,0.6)', lineHeight: 1,
            }}>
              {100 - target}%
            </div>
          </div>
        </div>
      )}

      {/* Track */}
      <div style={{ position: 'relative', height: '48px', marginBottom: locked ? '8px' : '10px' }}>
        <div style={{
          position: 'absolute', top: '22px', left: 0, right: 0,
          height: '4px', background: 'rgba(255,255,255,0.1)',
        }} />
        <div style={{
          position: 'absolute', top: '22px', left: 0,
          width: `${violationLine}%`, height: '4px',
          background: 'rgba(255,255,255,0.22)',
        }} />
        {!locked && (
          <div style={{
            position: 'absolute', top: '22px', left: 0,
            width: `${target}%`, height: '4px',
            background: 'var(--neon)',
            boxShadow: '0 0 8px rgba(0,255,136,0.6)',
          }} />
        )}
        {locked && (
          <div style={{
            position: 'absolute', top: '22px', left: 0,
            width: `${current}%`, height: '4px',
            background: 'var(--neon)',
            boxShadow: '0 0 8px rgba(0,255,136,0.6)',
          }} />
        )}
        <div style={{
          position: 'absolute',
          left: `${locked ? current : 100}%`,
          top: '12px',
          transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px',
        }}>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '8px',
            color: 'rgba(255,255,255,0.55)', letterSpacing: '0.05em', whiteSpace: 'nowrap',
          }}>
            {locked ? 'ACHIEVED' : 'SRC'}
          </div>
          <div style={{ width: '2px', height: '24px', background: 'rgba(255,255,255,0.5)' }} />
        </div>
        <div style={{
          position: 'absolute', left: `${violationLine}%`, top: 0,
          transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
        }}>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '8px',
            color: 'var(--danger)', letterSpacing: '0.05em',
          }}>
            {violationLine}%
          </div>
          <div style={{ width: '1px', height: '48px', background: 'var(--danger)', opacity: 0.8 }} />
        </div>
      </div>

      {!locked && (
        <>
          <input
            type="range"
            min={0}
            max={violationLine - 1}
            value={target}
            onChange={e => onTargetChange(Number(e.target.value))}
            style={{ width: '100%', marginBottom: '8px' }}
          />
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '9px',
            color: 'rgba(255,255,255,0.25)', letterSpacing: '0.08em', textAlign: 'center',
          }}>
            DRAG TO SET SIMILARITY TARGET · BELOW {violationLine}% VIOLATION LINE
          </div>
        </>
      )}

      {locked && (
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          fontFamily: 'JetBrains Mono', fontSize: '10px',
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            ACHIEVED <span style={{ color: '#fff' }}>{current}%</span>
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            TARGET <span style={{ color: 'var(--neon)' }}>{target}%</span>
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            LINE <span style={{ color: 'var(--danger)' }}>{violationLine}%</span>
          </span>
        </div>
      )}
    </div>
  )
}

// ─── Metric cell ──────────────────────────────────────────────────────────────

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
      }}>{label}</div>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '14px',
        color: highlight ? 'var(--neon)' : 'var(--text-primary)', fontWeight: 500,
      }}>{value}</div>
    </div>
  )
}

// ─── Buttons ──────────────────────────────────────────────────────────────────

function BtnPrimary({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: disabled ? 'rgba(255,255,255,0.15)' : 'var(--neon)',
      color: disabled ? 'rgba(255,255,255,0.4)' : '#000000',
      fontFamily: 'JetBrains Mono', fontWeight: 500, fontSize: '12px',
      letterSpacing: '0.1em', padding: '12px 20px', border: 'none',
      cursor: disabled ? 'default' : 'pointer',
      boxShadow: disabled ? 'none' : 'var(--neon-glow)', transition: 'opacity 0.15s',
    }}>{children}</button>
  )
}

function BtnHollow({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: 'transparent', color: 'var(--neon)',
      fontFamily: 'JetBrains Mono', fontWeight: 400, fontSize: '11px',
      letterSpacing: '0.1em', padding: '7px 13px',
      border: '1px solid var(--neon)', cursor: disabled ? 'default' : 'pointer',
      opacity: disabled ? 0.5 : 1, transition: 'opacity 0.15s',
    }}>{children}</button>
  )
}

// ─── Gateway03Morph ───────────────────────────────────────────────────────────
// User-initiated (unlike GW02's mount-time auto-trigger): the target slider
// comes first. On mount, GET morph-status — resume polling if a morph is
// already in flight, render the persisted result if complete (True Isolation:
// survives refresh).

export default function Gateway03Morph({ projectId, project, onComplete }) {
  const [status, setStatus] = useState('pending') // pending | processing | complete | failed
  const [result, setResult] = useState(null)      // morph_result from status payload
  const [params, setParams] = useState(null)      // morph_params from status payload
  const [progress, setProgress] = useState(null)
  const [apiError, setApiError] = useState(null)
  const [previewV, setPreviewV] = useState(0)

  // Controls
  const [target, setTarget] = useState(DEFAULT_TARGET)
  const [keyTarget, setKeyTarget] = useState('AUTO')
  const [bpmTarget, setBpmTarget] = useState('')
  const pollRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const data = await apiGet(`/api/projects/${projectId}/morph-status`)
        if (data.status === 'complete') {
          stopPolling()
          setStatus('complete')
          setResult(data.morph_result || null)
          setParams(data.morph_params || null)
          setPreviewV(Date.now())
        } else if (data.status === 'failed') {
          stopPolling()
          setStatus('failed')
          setApiError(`Morph: ${data.error || 'unknown error'}`)
        } else if (data.status === 'processing' && data.progress) {
          setProgress(data.progress)
        }
      } catch (e) {
        // keep polling on transient errors
      }
    }, 3000)
  }, [projectId, stopPolling])

  // Mount: discover existing morph state (refresh / re-entry safe)
  useEffect(() => {
    let cancelled = false

    apiGet(`/api/projects/${projectId}/morph-status`)
      .then(data => {
        if (cancelled) return
        if (data.status === 'complete') {
          setStatus('complete')
          setResult(data.morph_result || null)
          setParams(data.morph_params || null)
          if (data.morph_params) {
            if (typeof data.morph_params.similarity_target === 'number') setTarget(data.morph_params.similarity_target)
            if (data.morph_params.key_target) setKeyTarget(data.morph_params.key_target)
            if (data.morph_params.bpm_target) setBpmTarget(String(data.morph_params.bpm_target))
          }
          setPreviewV(Date.now())
        } else if (data.status === 'processing') {
          setStatus('processing')
          if (data.progress) setProgress(data.progress)
          startPolling()
        } else if (data.status === 'failed') {
          setStatus('failed')
          setApiError(`Morph: ${data.error || 'unknown error'}`)
        }
        // 'pending' → stay idle, user picks a target first
      })
      .catch(() => { /* stay idle on transient error */ })

    return () => {
      cancelled = true
      stopPolling()
    }
  }, [projectId, startPolling, stopPolling])

  const handleMorph = useCallback(async () => {
    if (!projectId) return
    setApiError(null)
    setProgress(null)
    setStatus('processing')
    try {
      const body = { similarity_target: target }
      if (keyTarget !== 'AUTO') body.key_target = keyTarget
      const bpmNum = parseFloat(bpmTarget)
      if (bpmTarget !== '' && !Number.isNaN(bpmNum) && bpmNum > 0) body.bpm_target = bpmNum
      await apiPost(`/api/projects/${projectId}/morph`, body)
      startPolling()
    } catch (e) {
      setStatus('failed')
      setApiError(`Morph: ${e.message}`)
    }
  }, [projectId, target, keyTarget, bpmTarget, startPolling])

  const handleRemorph = useCallback(() => {
    stopPolling()
    setStatus('pending')
    setResult(null)
    setProgress(null)
    setApiError(null)
    // Controls stay pre-filled from the last run's morph_params
  }, [stopPolling])

  const handleRetry = useCallback(() => {
    setStatus('pending')
    setApiError(null)
    setProgress(null)
  }, [])

  const handleDownload = useCallback(() => {
    if (!projectId) return
    // Direct browser download (GW02 lesson: no blob buffering for large audio)
    const a = document.createElement('a')
    a.href = `/api/projects/${projectId}/download-beat`
    a.download = 'CLEARED_BEAT.mp3'
    document.body.appendChild(a)
    a.click()
    a.remove()
  }, [projectId])

  const isComplete = status === 'complete' && result
  const isProcessing = status === 'processing'
  const isFailed = status === 'failed'
  const isIdle = status === 'pending'

  const tempoShiftStr = result
    ? `${result.tempo_shift_pct >= 0 ? '+' : ''}${result.tempo_shift_pct}%`
    : '—'
  const pitchStr = result
    ? `${result.pitch_semitones >= 0 ? '+' : ''}${result.pitch_semitones} ST`
    : '—'

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

      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '9px',
          color: 'var(--neon)', letterSpacing: '0.15em',
          borderBottom: '1px solid rgba(0,255,136,0.2)', paddingBottom: '10px',
        }}>
          GATEWAY 03 — MORPH ENGINE
        </div>

        {/* IDLE: target selection */}
        {isIdle && (
          <>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              RESHAPE THE BEAT SKELETON — TIME-STRETCH + PITCH-SHIFT ON THE DECONSTRUCTED
              INSTRUMENTAL STEMS. EVERY MODIFICATION IS A CALCULABLE OPERATION ON SOURCE
              MATERIAL. PREVIEW AND RE-ADJUST BEFORE COMMITTING.
            </div>
            <SimilarityScale current={100} target={target} onTargetChange={setTarget} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', letterSpacing: '0.1em' }}>
                  KEY TARGET
                </span>
                <select
                  value={keyTarget}
                  onChange={e => setKeyTarget(e.target.value)}
                  style={{
                    fontFamily: 'JetBrains Mono', fontSize: '11px',
                    background: 'rgba(255,255,255,0.04)', color: 'var(--text-primary)',
                    border: '1px solid rgba(255,255,255,0.15)', padding: '8px',
                  }}
                >
                  {KEY_OPTIONS.map(k => <option key={k} value={k} style={{ background: '#111', color: '#eee' }}>{k}</option>)}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', letterSpacing: '0.1em' }}>
                  BPM TARGET (BLANK = AUTO)
                </span>
                <input
                  type="number"
                  min={20}
                  max={300}
                  step={0.1}
                  value={bpmTarget}
                  onChange={e => setBpmTarget(e.target.value)}
                  placeholder="auto"
                  style={{
                    fontFamily: 'JetBrains Mono', fontSize: '11px',
                    background: 'rgba(255,255,255,0.04)', color: 'var(--text-primary)',
                    border: '1px solid rgba(255,255,255,0.15)', padding: '8px',
                  }}
                />
              </label>
            </div>
          </>
        )}

        {/* PROCESSING: live stage/percent from the poller */}
        {isProcessing && (
          <>
            <SimilarityScale current={100} target={target} locked />
            <div style={{
              border: '1px solid rgba(0,255,136,0.3)', padding: '14px',
              background: 'rgba(0,255,136,0.03)',
            }}>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--neon)', letterSpacing: '0.15em', marginBottom: '10px' }}>
                // MORPH IN PROGRESS
              </div>
              <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', marginBottom: '10px' }}>
                <div style={{
                  height: '4px', background: 'var(--neon)',
                  width: `${progress?.percent ?? 0}%`,
                  boxShadow: '0 0 8px rgba(0,255,136,0.6)',
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: 'var(--text-terminal)' }}>
                <span style={{ color: 'var(--neon)' }}>&gt;</span> {progress?.stage?.toUpperCase() || 'STARTING'}
                {progress?.detail ? ` — ${progress.detail}` : ''}
                <span style={{ color: 'var(--text-secondary)' }}> ({progress?.percent ?? 0}%)</span>
              </div>
            </div>
          </>
        )}

        {/* COMPLETE: measured result */}
        {isComplete && (
          <>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
              <div style={{ marginBottom: '10px', color: 'var(--text-secondary)', fontSize: '10px' }}>
                THE CLEARED BEAT — MORPHED INSTRUMENTAL, MEASURED AGAINST SOURCE
              </div>
              <div>Original DNA preserved at <span style={{ color: '#fff' }}>{result.similarity_achieved}%</span></div>
              <div>Deviation from source: <span style={{ color: 'var(--neon)' }}>{result.deviation_achieved}%</span></div>
              <div style={{ marginTop: '10px', fontSize: '9px', color: 'var(--text-secondary)' }}>
                All modifications traceable to source material. No unknowns.
              </div>
            </div>
            <SimilarityScale
              current={result.similarity_achieved}
              target={params?.similarity_target ?? target}
              locked
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
              <MetricCell label="BPM" value={`${result.bpm_original} → ${result.bpm_morphed}`} />
              <MetricCell label="KEY" value={`${result.key_original} → ${result.key_morphed}`} />
              <MetricCell label="TEMPO SHIFT" value={tempoShiftStr} />
              <MetricCell label="PITCH SHIFT" value={pitchStr} />
              <MetricCell label="SIMILARITY" value={`${result.similarity_achieved}%`} />
              <MetricCell label="DEVIATION" value={`${result.deviation_achieved}%`} highlight />
            </div>
            <AudioPlayer
              src={`/api/projects/${projectId}/morph-preview?v=${previewV}`}
              label="CLEARED BEAT (MORPHED)"
            />
          </>
        )}

        {/* FAILED */}
        {isFailed && !apiError && (
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: 'var(--danger)' }}>
            // MORPH FAILED — RETRY OR ADJUST PARAMETERS
          </div>
        )}
      </div>

      {/* Footer controls */}
      <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border-dim)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {isIdle && (
          <BtnPrimary onClick={handleMorph}>{'>'}  EXECUTE MORPH</BtnPrimary>
        )}
        {isProcessing && (
          <BtnPrimary disabled>MORPHING...</BtnPrimary>
        )}
        {isFailed && (
          <BtnPrimary onClick={handleRetry}>{'>'}  ADJUST & RETRY</BtnPrimary>
        )}
        {isComplete && (
          <>
            <BtnHollow onClick={handleRemorph}>RE-MORPH (ADJUST TARGET)</BtnHollow>
            <BtnHollow onClick={handleDownload}>DOWNLOAD CLEARED BEAT</BtnHollow>
            <BtnPrimary onClick={onComplete}>{'>'}  PROCEED TO LYRIC REBUILD</BtnPrimary>
          </>
        )}
      </div>
    </div>
  )
}
