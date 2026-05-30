import { useState, useEffect, useRef, useCallback } from 'react'
import { Toaster } from 'sonner'
import { GatewayErrorBoundary } from './components/ErrorBoundary'
import Gateway01Legal from './components/gateways/Gateway01Legal'
import Gateway02Deconstruction from './components/gateways/Gateway02Deconstruction'
import Gateway04LyricRebuild from './components/gateways/Gateway04LyricRebuild'
import Gateway05VoiceClone from './components/gateways/Gateway05VoiceClone'
import { apiPost } from './lib/apiClient'

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_FILE = {
  name: 'LOSE_YOURSELF.MP3',
  duration: '5:26',
  format: 'MP3',
  bitrate: '320 KBPS',
  sampleRate: '44.1 KHZ',
  size: '12.4 MB',
}

const MOCK_GATEWAY_03 = {
  bpm: 91,
  key: 'F#m',
  tempoShift: '+4.6%',
  similarityAchieved: 35,
  deviationAchieved: 65,
}

// ─── Telemetry lines ──────────────────────────────────────────────────────────

const TELEMETRY = {
  ingesting: [
    'INGESTING AUDIO FILE...',
    'PARSING AUDIO METADATA...',
    'RUNNING AUDIO FINGERPRINT SCAN...',
    'QUERYING PUBLIC RECORDS DATABASE...',
    'RUNNING LYRIC MATCH ALGORITHM...',
    'COMPUTING SIMILARITY INDEX...',
    'APPLYING VIOLATION THRESHOLD...',
    'COMPILING LEGAL DIAGNOSTIC...',
  ],
  deconstructing: [
    'DECONSTRUCTING AUDIO FILE...',
    'ISOLATING FREQUENCY BANDS...',
    'KICK: ISOLATED',
    'BASS: ISOLATED',
    'MELODY: CALCULATED',
    'HARMONY: EXTRACTED',
    'PERCUSSION: SEPARATED',
    'VOCAL: SEPARATED',
    'RUNNING BASIC PITCH CONVERSION...',
    'GENERATING MIDI STEMS — 06 TRACKS...',
    'GENERATING MUSICXML NOTATION — 04 SCORES...',
    'BUNDLING DAW PACKAGE...',
  ],
  morphing: [
    'LOADING MIDI STEM DATA...',
    'ANALYZING BEAT SKELETON...',
    'APPLYING SIMILARITY TARGET: 35%...',
    'RESHAPING RHYTHM GRID...',
    'TRANSPOSING KEY SIGNATURE: Am → F#m...',
    'SHIFTING TEMPO ANCHOR: +4.6%...',
    'REBUILDING HARMONIC STRUCTURE...',
    'TRACING ALL MODIFICATIONS TO SOURCE...',
    'BEAT RECONSTRUCTION FINALIZING...',
  ],
  rebuilding_lyrics: [
    'LOADING PHONETIC STRUCTURE...',
    'ANALYZING CADENCE PATTERN...',
    'APPLYING STYLE: DEFINED // PRESET_01...',
    'MAPPING RHYME ARCHITECTURE...',
    'MODE: PLACEHOLDER CADENCE...',
    'FILLING LYRIC CONTENT...',
    'RUNNING PHONETIC DENSITY CHECK...',
    'FINALIZING LYRIC CANVAS...',
  ],
  planting: [
    'LOADING VOCAL SAMPLE...',
    'CLONING VOCAL SIGNATURE...',
    'SYNTHESIZING PERFORMANCE FROM LYRICS...',
    'ALIGNING TO BEAT GRID...',
    'EMBEDDING VOCAL STEM...',
    'REPLACING SOURCE ARTIST VOICE...',
    'RENDERING FINAL MIX...',
    'PRINTING MASTER...',
  ],
}

// ─── State machine ────────────────────────────────────────────────────────────

const PROCESSING_NEXT = {
  ingesting: 'gateway_01',
  deconstructing: 'gateway_02',
  morphing: 'gateway_03',
  rebuilding_lyrics: 'gateway_04',
  planting: 'gateway_05',
}

const PROCESSING_DELAYS = {
  ingesting: 4000,
  deconstructing: 5000,
  morphing: 4500,
  rebuilding_lyrics: 5000,
  planting: 4500,
}

const GATEWAY_SEQUENCE = [
  'gateway_01', 'gateway_02', 'gateway_03', 'gateway_04', 'gateway_05',
]

function getPhase(state) {
  if (state === 'idle') return 1
  if (PROCESSING_NEXT[state]) return 2
  return 3
}

function getActivePaneIdx(state) {
  const phase = getPhase(state)
  if (phase === 1) return 0
  if (phase === 2) return 1
  return 2
}

function getGatewayNum(state) {
  if (!state || state === 'idle') return 0
  const map = {
    ingesting: 1, gateway_01: 1,
    deconstructing: 2, gateway_02: 2,
    morphing: 3, gateway_03: 3,
    rebuilding_lyrics: 4, gateway_04: 4,
    planting: 5, gateway_05: 5,
  }
  return map[state] || 0
}

// ─── Spectrogram ──────────────────────────────────────────────────────────────

function Spectrogram({ active }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const barsRef = useRef([])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    if (!active) {
      if (animRef.current) cancelAnimationFrame(animRef.current)
      animRef.current = null
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.strokeStyle = 'rgba(255,255,255,0.04)'
      ctx.lineWidth = 1
      for (let x = 0; x <= canvas.width; x += 22) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke()
      }
      for (let y = 0; y <= canvas.height; y += 18) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke()
      }
      return
    }

    const BAR_COUNT = 52
    const w = canvas.width
    const h = canvas.height
    const BAR_W = Math.floor(w / BAR_COUNT) - 1

    if (barsRef.current.length !== BAR_COUNT) {
      barsRef.current = Array.from({ length: BAR_COUNT }, () => ({
        h: Math.random() * 0.5 + 0.05,
        target: Math.random() * 0.8 + 0.1,
        v: 0,
      }))
    }

    const draw = () => {
      ctx.fillStyle = '#000000'
      ctx.fillRect(0, 0, w, h)

      barsRef.current.forEach((bar, i) => {
        bar.v += (bar.target - bar.h) * 0.12
        bar.v *= 0.86
        bar.h = Math.max(0.02, Math.min(1.0, bar.h + bar.v))
        if (Math.random() < 0.04) bar.target = Math.random() * 0.9 + 0.05

        const x = i * (BAR_W + 1)
        const bh = bar.h * h
        const y = h - bh
        const alpha = 0.2 + bar.h * 0.8

        ctx.fillStyle = `rgba(0, 255, 136, ${alpha})`
        ctx.fillRect(x, y + 1, BAR_W, bh - 1)
        ctx.fillStyle = '#00ff88'
        ctx.fillRect(x, y, BAR_W, 1)
      })

      animRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [active])

  return (
    <canvas
      ref={canvasRef}
      width={600}
      height={110}
      style={{ width: '100%', height: '110px', display: 'block' }}
    />
  )
}

// ─── Telemetry feed ───────────────────────────────────────────────────────────

function TelemetryFeed({ lines, active }) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!active) { setCount(0); return }
    setCount(0)
    const timers = lines.map((_, i) =>
      setTimeout(() => setCount(c => Math.max(c, i + 1)), i * 420)
    )
    return () => timers.forEach(clearTimeout)
  }, [active, lines.join('')]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      fontFamily: 'JetBrains Mono', fontSize: '11px',
      lineHeight: 1.9, color: 'var(--text-terminal)',
    }}>
      {lines.slice(0, count).map((line, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          animation: 'telemetryIn 0.15s ease-out',
        }}>
          <span style={{ color: 'var(--neon)', flexShrink: 0 }}>›</span>
          <span style={{ opacity: i < count - 1 ? 0.65 : 1 }}>{line}</span>
          {i === count - 1 && (
            <span style={{ color: 'var(--neon)', animation: 'blink 0.7s step-end infinite' }}>█</span>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Logo ─────────────────────────────────────────────────────────────────────

const LOGO_BARS = [6, 14, 9, 18, 11, 16, 8, 12, 17, 10]

function Logo({ phase }) {
  if (phase === 3) return (
    <div>
      <div style={{
        fontFamily: 'Unbounded', fontWeight: 900, fontSize: '15px',
        color: '#ffffff', letterSpacing: '0.04em',
      }}>
        TRANSFORMUSIC
      </div>
      <div style={{ height: '3px', background: 'var(--neon)', marginTop: '5px', boxShadow: 'var(--neon-glow)' }} />
    </div>
  )

  if (phase === 2) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontWeight: 500, fontSize: '13px',
        color: 'rgba(255,255,255,0.65)', letterSpacing: '0.12em',
      }}>
        TRANSFORMUSIC
      </div>
      <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '20px' }}>
        {LOGO_BARS.map((h, i) => (
          <div key={i} style={{
            width: '3px',
            height: `${h}px`,
            background: 'var(--neon)',
            boxShadow: 'var(--neon-glow)',
            transformOrigin: 'bottom',
            animation: `barPulse ${0.25 + i * 0.06}s ease-in-out ${i * 0.04}s infinite alternate`,
          }} />
        ))}
      </div>
    </div>
  )

  return (
    <div style={{
      fontFamily: 'JetBrains Mono', fontWeight: 500, fontSize: '13px',
      color: 'rgba(255,255,255,0.45)', letterSpacing: '0.12em',
    }}>
      TRANSFORMUSIC{' '}
      <span style={{ color: 'rgba(255,255,255,0.2)' }}>//</span>
      {' '}NODE_07
    </div>
  )
}

// ─── Gateway bar ──────────────────────────────────────────────────────────────

function GatewayBar({ state }) {
  const current = getGatewayNum(state)
  if (current === 0) return null

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '6px',
      fontFamily: 'JetBrains Mono', fontSize: '10px', color: 'var(--text-secondary)',
    }}>
      {GATEWAY_SEQUENCE.map((gw, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={gw} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '8px', height: '8px',
              background: active ? 'var(--neon)' : done ? 'rgba(0,255,136,0.4)' : 'transparent',
              border: `1px solid ${active ? 'var(--neon)' : done ? 'rgba(0,255,136,0.4)' : 'rgba(255,255,255,0.2)'}`,
              boxShadow: active ? 'var(--neon-glow)' : 'none',
            }} />
            <span style={{ color: active ? 'var(--neon)' : done ? 'rgba(0,255,136,0.5)' : 'rgba(255,255,255,0.2)' }}>
              0{n}
            </span>
            {i < 4 && <span style={{ color: 'rgba(255,255,255,0.1)' }}>──</span>}
          </div>
        )
      })}
    </div>
  )
}

// ─── Similarity scale (used in Gateway 03 mock) ──────────────────────────────

function SimilarityScale({ current, target, violationLine = 80, locked = false }) {
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
      }}>
        // SIMILARITY — LOCKED
      </div>
      <div style={{ position: 'relative', height: '48px', marginBottom: '8px' }}>
        <div style={{
          position: 'absolute', top: '22px', left: 0, right: 0,
          height: '4px', background: 'rgba(255,255,255,0.1)',
        }} />
        <div style={{
          position: 'absolute', top: '22px', left: 0,
          width: `${violationLine}%`, height: '4px',
          background: 'rgba(255,255,255,0.22)',
        }} />
        <div style={{
          position: 'absolute', left: `${current}%`, top: '12px',
          transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px',
        }}>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '8px',
            color: 'rgba(255,255,255,0.55)', letterSpacing: '0.05em',
          }}>SRC</div>
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
          }}>{violationLine}%</div>
          <div style={{ width: '1px', height: '48px', background: 'var(--danger)', opacity: 0.8 }} />
        </div>
      </div>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontFamily: 'JetBrains Mono', fontSize: '10px',
      }}>
        <span style={{ color: 'var(--text-secondary)' }}>
          SOURCE <span style={{ color: '#fff' }}>{current}%</span>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          TARGET <span style={{ color: 'var(--neon)' }}>{target}%</span>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          LINE <span style={{ color: 'var(--danger)' }}>{violationLine}%</span>
        </span>
      </div>
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

// ─── Button components ────────────────────────────────────────────────────────

function BtnPrimary({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: 'var(--neon)', color: '#000000',
      fontFamily: 'JetBrains Mono', fontWeight: 500, fontSize: '12px',
      letterSpacing: '0.1em', padding: '12px 20px', border: 'none',
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
      border: '1px solid var(--neon)', transition: 'opacity 0.15s',
    }}>{children}</button>
  )
}

// ─── Pane header ──────────────────────────────────────────────────────────────

function PaneHeader({ label, node }) {
  return (
    <div style={{ padding: '14px 18px 12px', borderBottom: '1px solid var(--border-dim)' }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '10px',
        color: 'var(--text-secondary)', letterSpacing: '0.15em', marginBottom: '2px',
      }}>// {label}</div>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'rgba(255,255,255,0.2)', letterSpacing: '0.12em',
      }}>{node}</div>
    </div>
  )
}

// ─── Error banner ─────────────────────────────────────────────────────────────

function ErrorBanner({ error, onDismiss }) {
  if (!error) return null
  return (
    <div style={{
      fontFamily: 'JetBrains Mono', fontSize: '10px',
      color: 'var(--danger)', letterSpacing: '0.08em',
      padding: '8px 14px',
      border: '1px solid rgba(255,59,59,0.3)',
      background: 'rgba(255,59,59,0.06)',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      flexShrink: 0,
    }}>
      <span>// ERROR: {error}</span>
      <button onClick={onDismiss} style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'rgba(255,255,255,0.4)', background: 'transparent',
        border: '1px solid rgba(255,255,255,0.15)', padding: '3px 8px', cursor: 'pointer',
      }}>DISMISS</button>
    </div>
  )
}

// ─── Gateway 03 mock (not yet implemented as separate component) ──────────────

function Gateway03Mock({ onComplete }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '9px',
          color: 'var(--neon)', letterSpacing: '0.15em',
          borderBottom: '1px solid rgba(0,255,136,0.2)', paddingBottom: '10px',
        }}>
          EARNED PRODUCT — THE CLEARED BEAT
        </div>
        <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
          <div style={{ marginBottom: '10px', color: 'var(--text-secondary)', fontSize: '10px' }}>
            ORIGINAL INSTRUMENTAL — CLEARED FOR STANDALONE EXPORT
          </div>
          <div>Original DNA preserved at <span style={{ color: '#fff' }}>{MOCK_GATEWAY_03.similarityAchieved}%</span></div>
          <div>Deviation from source: <span style={{ color: 'var(--neon)' }}>{MOCK_GATEWAY_03.deviationAchieved}%</span></div>
          <div>New key: <span style={{ color: '#fff' }}>{MOCK_GATEWAY_03.key}</span></div>
          <div>New BPM: <span style={{ color: '#fff' }}>{MOCK_GATEWAY_03.bpm}</span></div>
          <div style={{ marginTop: '10px', fontSize: '9px', color: 'var(--text-secondary)' }}>
            All modifications traceable to source material. No unknowns.
          </div>
        </div>
        <SimilarityScale current={MOCK_GATEWAY_03.similarityAchieved} target={MOCK_GATEWAY_03.deviationAchieved} locked />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
          <MetricCell label="BPM" value={String(MOCK_GATEWAY_03.bpm)} />
          <MetricCell label="KEY" value={MOCK_GATEWAY_03.key} />
          <MetricCell label="TEMPO SHIFT" value={MOCK_GATEWAY_03.tempoShift} />
          <MetricCell label="SIMILARITY" value={`${MOCK_GATEWAY_03.similarityAchieved}%`} />
          <MetricCell label="DEVIATION" value={`${MOCK_GATEWAY_03.deviationAchieved}%`} highlight />
        </div>
      </div>
      <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border-dim)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <BtnPrimary onClick={onComplete}>{'>'}  PROCEED TO LYRIC REBUILD</BtnPrimary>
        <BtnHollow>EXIT: EXPORT CLEARED BEAT</BtnHollow>
      </div>
    </div>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [state, setState] = useState('idle')
  const [file, setFile] = useState(null)
  const [projectId, setProjectId] = useState(null)
  const [project, setProject] = useState(null)
  const [apiError, setApiError] = useState(null)

  const timerRef = useRef(null)
  const fileInputRef = useRef(null)

  const phase = getPhase(state)
  const activePaneIdx = getActivePaneIdx(state)

  const startProcessing = useCallback((processingState) => {
    setState(processingState)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      setState(PROCESSING_NEXT[processingState])
    }, PROCESSING_DELAYS[processingState])
  }, [])

  const handleIngest = useCallback(async (rawFile) => {
    setApiError(null)
    if (rawFile) {
      setFile({
        name: rawFile.name.toUpperCase(),
        duration: '—',
        format: rawFile.name.split('.').pop().toUpperCase(),
        bitrate: '—',
        sampleRate: '—',
        size: `${(rawFile.size / 1024 / 1024).toFixed(1)} MB`,
      })
    } else {
      setFile(MOCK_FILE)
    }
    startProcessing('ingesting')
    if (!rawFile) return
    try {
      const proj = await apiPost('/api/projects', { name: rawFile.name })
      setProjectId(proj.id)
      setProject(proj)
      const form = new FormData()
      form.append('file', rawFile)
      await apiPost(`/api/projects/${proj.id}/upload`, form)
    } catch (e) {
      setApiError(`Upload: ${e.message}`)
    }
  }, [startProcessing])

  const handleGatewayComplete = useCallback(() => {
    if (state === 'gateway_01') startProcessing('deconstructing')
    else if (state === 'gateway_02') startProcessing('morphing')
    else if (state === 'gateway_03') startProcessing('rebuilding_lyrics')
    else if (state === 'gateway_04') startProcessing('planting')
    else if (state === 'gateway_05') { /* final gateway — no next step */ }
  }, [state, startProcessing])

  const handleReset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setState('idle')
    setFile(null)
    setProjectId(null)
    setProject(null)
    setApiError(null)
  }, [])

  const paneStyles = (idx) => {
    const isActive = idx === activePaneIdx
    const isPhase1 = phase === 1
    return {
      flex: 1,
      border: `1px solid ${isActive && !isPhase1 ? 'var(--border-active)' : 'rgba(255,255,255,0.14)'}`,
      boxShadow: isActive && !isPhase1 ? 'var(--neon-glow)' : 'none',
      background: isActive && !isPhase1 ? 'var(--bg-surface)' : '#080808',
      opacity: !isPhase1 && !isActive ? 0.78 : 1,
      transition: 'opacity 0.4s ease, border-color 0.3s ease, box-shadow 0.3s ease, background 0.3s ease',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      minWidth: 0,
    }
  }

  const isProcessing = !!PROCESSING_NEXT[state]
  const telemetryLines = TELEMETRY[state] || []

  return (
    <div style={{
      height: '100vh', background: 'var(--bg-primary)',
      display: 'flex', flexDirection: 'column', padding: '16px', gap: '14px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <Logo phase={phase} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <GatewayBar state={state} />
          {state !== 'idle' && (
            <button onClick={handleReset} style={{
              fontFamily: 'JetBrains Mono', fontSize: '10px',
              color: 'rgba(255,255,255,0.25)', background: 'none',
              border: '1px solid rgba(255,255,255,0.1)', padding: '6px 10px',
              letterSpacing: '0.1em', cursor: 'pointer',
            }}>RESET</button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {state !== 'idle' && (
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '10px',
          color: phase === 2 ? 'var(--neon)' : 'var(--text-secondary)',
          letterSpacing: '0.1em', flexShrink: 0,
          display: 'flex', alignItems: 'center', gap: '8px',
          animation: phase === 2 ? 'blink 1.4s step-end infinite' : 'none',
        }}>
          <span style={{
            display: 'inline-block', width: '6px', height: '6px',
            background: phase === 2 ? 'var(--neon)' : 'rgba(0,255,136,0.4)',
          }} />
          {phase === 2 && TELEMETRY[state]?.[0]}
          {phase === 3 && `GATEWAY ${String(getGatewayNum(state)).padStart(2, '0')} — COMPLETE`}
        </div>
      )}

      {/* Error banner */}
      <ErrorBanner error={apiError} onDismiss={() => setApiError(null)} />

      {/* Three-pane layout */}
      <div style={{ flex: 1, display: 'flex', gap: '12px', minHeight: 0 }}>
        {/* Pane 1 — INPUT */}
        <div style={paneStyles(0)}>
          <PaneHeader label="INPUT" node="NODE_07_A" />
          <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {phase === 1 && (
              <>
                <label style={{ cursor: 'pointer', display: 'block' }}>
                  <div style={{
                    border: '1px dashed var(--neon)', padding: '32px 20px', textAlign: 'center',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
                  }}>
                    <div style={{
                      fontFamily: 'JetBrains Mono', fontSize: '10px',
                      color: 'var(--text-secondary)', letterSpacing: '0.12em',
                    }}>DROP AUDIO FILE OR CLICK TO SELECT</div>
                    <div style={{
                      fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'rgba(255,255,255,0.2)',
                    }}>MP3 · WAV · FLAC · AAC</div>
                  </div>
                  <input ref={fileInputRef} type="file" accept="audio/*" style={{ display: 'none' }}
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleIngest(f); e.target.value = '' }} />
                </label>
                <div style={{ textAlign: 'center' }}>
                  <BtnPrimary onClick={() => fileInputRef.current?.click()}>{'>'} INGEST AUDIO</BtnPrimary>
                </div>
              </>
            )}
            {phase >= 2 && file && (
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '11px',
                color: 'var(--text-terminal)', lineHeight: 2,
                borderLeft: '2px solid var(--neon)', paddingLeft: '12px',
              }}>
                <div><span style={{ color: 'var(--text-secondary)' }}>FILE //</span> {file.name}</div>
                <div><span style={{ color: 'var(--text-secondary)' }}>DURATION //</span> {file.duration}</div>
                <div><span style={{ color: 'var(--text-secondary)' }}>FORMAT //</span> {file.format}{file.bitrate !== '—' ? ` · ${file.bitrate}` : ''}</div>
                <div><span style={{ color: 'var(--text-secondary)' }}>SIZE //</span> {file.size}</div>
              </div>
            )}
          </div>
        </div>

        {/* Pane 2 — FUSION MATRIX */}
        <div style={paneStyles(1)}>
          <PaneHeader label="FUSION MATRIX" node="NODE_07_B" />
          <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Spectrogram active={isProcessing} />
            {isProcessing && <TelemetryFeed lines={telemetryLines} active={isProcessing} />}
            {phase === 1 && (
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '11px',
                color: 'rgba(255,255,255,0.15)', textAlign: 'center', paddingTop: '12px',
              }}>AWAITING INPUT</div>
            )}
          </div>
        </div>

        {/* Pane 3 — SOVEREIGN OUTPUT (Gateway Components) */}
        <div style={paneStyles(2)}>
          <PaneHeader label="SOVEREIGN OUTPUT" node="NODE_07_C" />
          <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
            {phase === 1 && (
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '11px',
                color: 'rgba(255,255,255,0.12)', textAlign: 'center', paddingTop: '20px',
              }}>
                DOCTRINE-GRADE CANVAS<br /><br />
                <span style={{ fontSize: '9px', display: 'block', lineHeight: 2 }}>AWAITING INPUT</span>
              </div>
            )}
            {isProcessing && (
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '11px',
                color: 'rgba(255,255,255,0.2)', textAlign: 'center', paddingTop: '20px',
                animation: 'blink 1.4s step-end infinite',
              }}>PROCESSING...</div>
            )}
            {phase === 3 && state === 'gateway_01' && (
              <GatewayErrorBoundary>
                <Gateway01Legal
                  projectId={projectId}
                  project={project}
                  onComplete={handleGatewayComplete}
                />
              </GatewayErrorBoundary>
            )}
            {phase === 3 && state === 'gateway_02' && (
              <GatewayErrorBoundary>
                <Gateway02Deconstruction
                  projectId={projectId}
                  project={project}
                  onComplete={handleGatewayComplete}
                />
              </GatewayErrorBoundary>
            )}
            {phase === 3 && state === 'gateway_03' && (
              <GatewayErrorBoundary>
                <Gateway03Mock onComplete={handleGatewayComplete} />
              </GatewayErrorBoundary>
            )}
            {phase === 3 && state === 'gateway_04' && (
              <GatewayErrorBoundary>
                <Gateway04LyricRebuild
                  projectId={projectId}
                  project={project}
                  onComplete={handleGatewayComplete}
                />
              </GatewayErrorBoundary>
            )}
            {phase === 3 && state === 'gateway_05' && (
              <GatewayErrorBoundary>
                <Gateway05VoiceClone
                  projectId={projectId}
                  project={project}
                  onComplete={handleGatewayComplete}
                />
              </GatewayErrorBoundary>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        flexShrink: 0, fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'rgba(255,255,255,0.12)', letterSpacing: '0.12em',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span>TRANSFORMUSIC // GATEWAY PIPELINE</span>
        <span>EASE IS EARNED</span>
      </div>

      {/* Toast notifications */}
      <Toaster theme="dark" position="bottom-right" />
    </div>
  )
}
