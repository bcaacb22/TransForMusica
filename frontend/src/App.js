import { useState, useEffect, useRef, useCallback } from 'react'

// ─── Backend API ──────────────────────────────────────────────────────────────

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'

async function apiPost(path, body) {
  const isForm = body instanceof FormData
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? body : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

async function apiGetBlob(path) {
  const res = await fetch(`${BACKEND_URL}${path}`)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.blob()
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// ─── Mock data (used for gateways without backend impl.) ─────────────────────

const MOCK_FILE = {
  name: 'LOSE_YOURSELF.MP3',
  duration: '5:26',
  format: 'MP3',
  bitrate: '320 KBPS',
  sampleRate: '44.1 KHZ',
  size: '12.4 MB',
}

const MOCK = {
  gateway_01: {
    similarityScore: 0,
    matchedSource: 'NO MATCH FOUND',
    audioFingerprint: '—',
    lyricalMatch: 0,
    violationRisk: 'NONE',
    isrc: null,
    label: null,
    releaseDate: null,
    genre: null,
  },
  gateway_02: {
    stems: ['KICK', 'BASS', 'MELODY', 'HARMONY', 'PERCUSSION', 'VOCAL'],
    midiFiles: 6,
    musicXmlFiles: 4,
    bpm: 87,
    key: 'Am',
  },
  gateway_03: {
    bpm: 91,
    key: 'F#m',
    tempoShift: '+4.6%',
    similarityAchieved: 35,
    deviationAchieved: 65,
  },
  gateway_04: {
    bars: 32,
    rhymeDensity: 'HIGH',
    style: 'DEFINED // PRESET_01',
    structureMode: 'PLACEHOLDER CADENCE',
    lyrics: `[VERSE 1]
When the moment arrives every atom aligns
Every signal collides at the fracture of time
No permission required just the fire inside
When the current runs clear there is nowhere to hide

[CHORUS]
Locked into the feed the signal is mine
Every frequency freed from the origin line
The doctrine is earned by the work that you build
When the system is clean every measure is filled

[VERSE 2]
Every stem that I touch has a traceable root
Every note on the grid has a calculable proof
No deviation unmapped no deviation unknown
Everything here has a mathematical home

[CHORUS]
Locked into the feed the signal is mine
Every frequency freed from the origin line
The doctrine is earned by the work that you build
When the system is clean every measure is filled`,
  },
  gateway_05: {
    clearanceStatus: 'ORIGINAL',
    similarityFinal: 35,
    processingTime: '14:22',
    stems: ['KICK', 'BASS', 'MELODY', 'HARMONY', 'PERCUSSION', 'VOCAL'],
    bpm: 91,
    key: 'F#m',
  },
}

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

// ─── Similarity scale ─────────────────────────────────────────────────────────

function SimilarityScale({ current, target, onTargetChange, violationLine = 80, locked = false }) {
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
        <span>// {locked ? 'SIMILARITY — LOCKED' : 'SET MORPH TARGET'}</span>
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
              DEVIATION TARGET
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
              SOURCE POSITION
            </div>
            <div style={{
              fontFamily: 'Unbounded', fontWeight: 700, fontSize: '28px',
              color: 'rgba(255,255,255,0.6)', lineHeight: 1,
            }}>
              {current}%
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
        <div style={{
          position: 'absolute',
          left: `${current}%`,
          top: '12px',
          transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px',
        }}>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '8px',
            color: 'rgba(255,255,255,0.55)', letterSpacing: '0.05em', whiteSpace: 'nowrap',
          }}>
            SRC
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
            DRAG TO SET DEVIATION TARGET · BELOW {violationLine}% VIOLATION LINE
          </div>
        </>
      )}

      {locked && (
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

// ─── Button components ────────────────────────────────────────────────────────

function BtnPrimary({ children, onClick, disabled, small }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'var(--neon)',
        color: '#000000',
        fontFamily: 'JetBrains Mono',
        fontWeight: 500,
        fontSize: small ? '11px' : '12px',
        letterSpacing: '0.1em',
        padding: small ? '8px 14px' : '12px 20px',
        border: 'none',
        boxShadow: disabled ? 'none' : 'var(--neon-glow)',
        transition: 'opacity 0.15s',
      }}
    >
      {children}
    </button>
  )
}

function BtnHollow({ children, onClick, disabled, small }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'transparent',
        color: 'var(--neon)',
        fontFamily: 'JetBrains Mono',
        fontWeight: 400,
        fontSize: small ? '11px' : '12px',
        letterSpacing: '0.1em',
        padding: small ? '7px 13px' : '11px 19px',
        border: '1px solid var(--neon)',
        transition: 'opacity 0.15s',
      }}
    >
      {children}
    </button>
  )
}

// ─── Pane header ──────────────────────────────────────────────────────────────

function PaneHeader({ label, node }) {
  return (
    <div style={{
      padding: '14px 18px 12px',
      borderBottom: '1px solid var(--border-dim)',
    }}>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '10px',
        color: 'var(--text-secondary)', letterSpacing: '0.15em',
        marginBottom: '2px',
      }}>
        // {label}
      </div>
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'rgba(255,255,255,0.2)', letterSpacing: '0.12em',
      }}>
        {node}
      </div>
    </div>
  )
}

// ─── Stem manifest ────────────────────────────────────────────────────────────

const ALL_STEMS = [
  { id: 'kick',       label: 'KICK',       audio: true, midi: true,  xml: false },
  { id: 'bass',       label: 'BASS',       audio: true, midi: true,  xml: false },
  { id: 'melody',     label: 'MELODY',     audio: true, midi: true,  xml: true  },
  { id: 'harmony',    label: 'HARMONY',    audio: true, midi: true,  xml: true  },
  { id: 'percussion', label: 'PERCUSSION', audio: true, midi: true,  xml: false },
  { id: 'vocal',      label: 'VOCAL',      audio: true, midi: true,  xml: true  },
  { id: 'full_score', label: 'FULL SCORE', audio: false,midi: false, xml: true  },
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

// ─── Voice profile block ──────────────────────────────────────────────────────

function VoiceProfileBlock({ profile, onLoad }) {
  const replaceRef = useRef(null)

  return (
    <ControlBlock label="VOICE PROFILE — VOCAL CLONING">
      {profile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 12px',
            border: '1px solid rgba(0,255,136,0.35)',
            background: 'rgba(0,255,136,0.04)',
          }}>
            <div style={{ width: '8px', height: '8px', background: 'var(--neon)', boxShadow: 'var(--neon-glow)', flexShrink: 0 }} />
            <div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: 'var(--neon)' }}>
                VOCAL PROFILE LOADED
              </div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', marginTop: '3px' }}>
                {profile.name} · {profile.duration}
              </div>
            </div>
          </div>
          <input
            ref={replaceRef}
            type="file"
            accept="audio/*"
            style={{ display: 'none' }}
            onChange={e => {
              const f = e.target.files?.[0]
              if (f) onLoad({ name: f.name.toUpperCase(), duration: '0:18' })
              e.target.value = ''
            }}
          />
          <button
            onClick={() => replaceRef.current?.click()}
            style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.08em',
              color: 'var(--text-secondary)', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.15)', padding: '6px 10px',
              cursor: 'pointer', width: '100%',
            }}
          >
            REPLACE SAMPLE
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <label style={{ cursor: 'pointer' }}>
            <div style={{
              border: '1px dashed rgba(0,255,136,0.5)',
              padding: '18px',
              textAlign: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
            }}>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: 'var(--neon)', letterSpacing: '0.1em' }}>
                LOAD VOCAL SAMPLE
              </div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'rgba(255,255,255,0.3)' }}>
                WAV · MP3 · 5–30 SEC CLEAN VOCAL
              </div>
            </div>
            <input
              type="file"
              accept="audio/*"
              style={{ display: 'none' }}
              onChange={e => {
                const f = e.target.files?.[0]
                if (f) onLoad({ name: f.name.toUpperCase(), duration: '0:22' })
                e.target.value = ''
              }}
            />
          </label>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '9px',
            color: 'rgba(255,255,255,0.25)', lineHeight: 1.7, textAlign: 'center',
          }}>
            USED AT GATEWAY 05 — RE-PLANT.<br />
            YOUR VOICE REPLACES THE GENERATED VOCAL STEM.<br />
            NO ORIGINAL ARTIST VOICE RETAINED.
          </div>
        </div>
      )}
    </ControlBlock>
  )
}

// ─── Control block wrapper ────────────────────────────────────────────────────

function ControlBlock({ label, children }) {
  return (
    <div style={{
      border: '1px solid rgba(0,255,136,0.45)',
      background: 'rgba(0,255,136,0.03)',
      boxShadow: '0 0 20px rgba(0,255,136,0.08)',
    }}>
      <div style={{
        borderBottom: '1px solid rgba(0,255,136,0.2)',
        padding: '8px 14px',
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'var(--neon)', letterSpacing: '0.15em',
      }}>
        // {label}
      </div>
      <div style={{ padding: '14px' }}>
        {children}
      </div>
    </div>
  )
}

// ─── Choice button row ────────────────────────────────────────────────────────

function ChoiceRow({ options, selected, onSelect }) {
  return (
    <div style={{ display: 'flex', gap: '1px' }}>
      {options.map(opt => {
        const isSelected = selected === opt.value
        return (
          <button
            key={opt.value}
            onClick={() => onSelect(opt.value)}
            style={{
              flex: 1,
              padding: '10px 6px',
              fontFamily: 'JetBrains Mono',
              fontSize: '10px',
              letterSpacing: '0.06em',
              background: isSelected ? 'var(--neon)' : 'rgba(255,255,255,0.04)',
              color: isSelected ? '#000000' : 'rgba(255,255,255,0.45)',
              border: `1px solid ${isSelected ? 'var(--neon)' : 'rgba(255,255,255,0.12)'}`,
              boxShadow: isSelected ? 'var(--neon-glow)' : 'none',
              cursor: 'pointer',
              transition: 'all 0.12s',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

// ─── LM Studio settings ───────────────────────────────────────────────────────

function LmSettings({ settings, onChange }) {
  const update = (key, val) => {
    const next = { ...settings, [key]: val }
    onChange(next)
    localStorage.setItem('tmLmSettings', JSON.stringify(next))
  }
  return (
    <ControlBlock label="AI SETTINGS — LM STUDIO">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', letterSpacing: '0.1em', marginBottom: '5px' }}>
            BASE URL
          </div>
          <input
            type="text"
            value={settings.url || ''}
            placeholder="http://localhost:1234"
            onChange={e => update('url', e.target.value)}
            style={{
              fontFamily: 'JetBrains Mono', fontSize: '11px',
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
              color: 'var(--text-primary)', padding: '7px 10px', width: '100%',
              outline: 'none',
            }}
          />
        </div>
        <div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', color: 'var(--text-secondary)', letterSpacing: '0.1em', marginBottom: '5px' }}>
            MODEL ID
          </div>
          <input
            type="text"
            value={settings.model || ''}
            placeholder="qwen3-14b"
            onChange={e => update('model', e.target.value)}
            style={{
              fontFamily: 'JetBrains Mono', fontSize: '11px',
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
              color: 'var(--text-primary)', padding: '7px 10px', width: '100%',
              outline: 'none',
            }}
          />
        </div>
      </div>
    </ControlBlock>
  )
}

// ─── Pane 1 — INPUT ───────────────────────────────────────────────────────────

function PaneInput({
  state, file, similarityTarget, onTargetChange,
  lyricMode, onLyricMode, structureMode, onStructureMode,
  voiceProfile, onVoiceProfile, onIngest,
  lmSettings, onLmSettings,
}) {
  const phase = getPhase(state)
  const gwNum = getGatewayNum(state)
  const d01 = MOCK.gateway_01
  const fileInputRef = useRef(null)

  const showSimilarityInteractive = state === 'gateway_02'
  const showSimilarityLocked = gwNum >= 3 && phase === 3
  const showLyricEngine = state === 'gateway_03'
  const showVoiceProfile = phase >= 2

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PaneHeader label="INPUT" node="NODE_07_A" />

      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>

        {phase === 1 && (
          <label style={{ cursor: 'pointer', display: 'block' }}>
            <div style={{
              border: '1px dashed var(--neon)',
              padding: '32px 20px',
              textAlign: 'center',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px',
            }}>
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '10px',
                color: 'var(--text-secondary)', letterSpacing: '0.12em',
              }}>
                DROP AUDIO FILE OR CLICK TO SELECT
              </div>
              <div style={{
                fontFamily: 'JetBrains Mono', fontSize: '9px',
                color: 'rgba(255,255,255,0.2)',
              }}>
                MP3 · WAV · FLAC · AAC
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              style={{ display: 'none' }}
              onChange={e => {
                const f = e.target.files?.[0]
                if (f) onIngest(f)
                e.target.value = ''
              }}
            />
          </label>
        )}

        {phase === 1 && (
          <div style={{ textAlign: 'center' }}>
            <BtnPrimary onClick={() => fileInputRef.current?.click()}>
              {'>'} INGEST AUDIO
            </BtnPrimary>
          </div>
        )}

        {phase >= 2 && file && (
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '11px',
            color: 'var(--text-terminal)', lineHeight: 2,
            borderLeft: '2px solid var(--neon)',
            paddingLeft: '12px',
          }}>
            <div><span style={{ color: 'var(--text-secondary)' }}>FILE //</span> {file.name}</div>
            <div><span style={{ color: 'var(--text-secondary)' }}>DURATION //</span> {file.duration}</div>
            <div><span style={{ color: 'var(--text-secondary)' }}>FORMAT //</span> {file.format}{file.bitrate !== '—' ? ` · ${file.bitrate}` : ''}</div>
            <div><span style={{ color: 'var(--text-secondary)' }}>SIZE //</span> {file.size}</div>
          </div>
        )}

        {gwNum >= 1 && phase === 3 && (
          <div>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px',
              color: 'var(--text-secondary)', letterSpacing: '0.15em',
              marginBottom: '8px',
            }}>
              // LEGAL DIAGNOSTIC
            </div>
            <div style={{ display: 'grid', gap: '1px' }}>
              <MetricCell label="SIMILARITY" value={`${d01.similarityScore}%`} highlight={d01.similarityScore > 50} />
              <MetricCell label="MATCHED SOURCE" value={d01.matchedSource} />
              <MetricCell label="LYRICAL MATCH" value={`${d01.lyricalMatch}%`} />
              <MetricCell
                label="VIOLATION RISK"
                value={d01.violationRisk}
                highlight={d01.violationRisk === 'MODERATE' || d01.violationRisk === 'HIGH'}
              />
            </div>
          </div>
        )}

        {showSimilarityInteractive && (
          <SimilarityScale
            current={d01.similarityScore}
            target={similarityTarget}
            onTargetChange={onTargetChange}
          />
        )}

        {showSimilarityLocked && (
          <SimilarityScale
            current={d01.similarityScore}
            target={similarityTarget}
            onTargetChange={onTargetChange}
            locked
          />
        )}

        {showLyricEngine && (
          <>
            <ControlBlock label="LYRIC ENGINE — SELECT MODE">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <ChoiceRow
                  options={[
                    { label: 'PRESET', value: 'PRESET' },
                    { label: 'DEFINED', value: 'DEFINED' },
                    { label: 'LEARNED', value: 'LEARNED' },
                  ]}
                  selected={lyricMode}
                  onSelect={onLyricMode}
                />
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '9px',
                  color: 'rgba(255,255,255,0.3)', lineHeight: 1.7,
                  borderLeft: '2px solid rgba(0,255,136,0.2)',
                  paddingLeft: '8px',
                }}>
                  {lyricMode === 'PRESET' && 'GENRE-BASED STYLE SELECTION'}
                  {lyricMode === 'DEFINED' && 'HAND-CRAFTED STYLE PROFILE — SAVEABLE & REUSABLE'}
                  {lyricMode === 'LEARNED' && 'AI-TRAINED ON YOUR OWN VOICE CORPUS'}
                </div>
              </div>
            </ControlBlock>

            <ControlBlock label="STRUCTURE MODE">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <ChoiceRow
                  options={[
                    { label: 'CADENCE', value: 'PLACEHOLDER' },
                    { label: 'FRESH', value: 'FRESH' },
                  ]}
                  selected={structureMode}
                  onSelect={onStructureMode}
                />
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '9px',
                  color: 'rgba(255,255,255,0.3)', lineHeight: 1.7,
                  borderLeft: '2px solid rgba(0,255,136,0.2)',
                  paddingLeft: '8px',
                }}>
                  {structureMode === 'PLACEHOLDER' && 'PRESERVE ORIGINAL BAR & RHYME STRUCTURE — REWRITE CONTENT ONLY'}
                  {structureMode === 'FRESH' && 'BUILD NEW PHONETIC ARCHITECTURE FROM FINAL BEAT OUTPUT'}
                </div>
              </div>
            </ControlBlock>

            <LmSettings settings={lmSettings} onChange={onLmSettings} />
          </>
        )}

        {showVoiceProfile && (
          <VoiceProfileBlock profile={voiceProfile} onLoad={onVoiceProfile} />
        )}
      </div>
    </div>
  )
}

// ─── Pane 2 — FUSION MATRIX ───────────────────────────────────────────────────

function PaneFusion({ state, transformResult }) {
  const phase = getPhase(state)
  const isProcessing = !!PROCESSING_NEXT[state]
  const telemetryLines = TELEMETRY[state] || []
  const gwNum = getGatewayNum(state)

  // Use real transform data when available, fall back to mock
  const g02 = transformResult
    ? {
        stems: transformResult.midi_files?.length
          ? transformResult.midi_files.map(f => f.split('/').pop().replace('.mid', '').toUpperCase())
          : MOCK.gateway_02.stems,
        midiFiles: transformResult.midi_files?.length ?? MOCK.gateway_02.midiFiles,
        musicXmlFiles: transformResult.musicxml_files?.length ?? MOCK.gateway_02.musicXmlFiles,
        bpm: MOCK.gateway_02.bpm,
        key: MOCK.gateway_02.key,
      }
    : MOCK.gateway_02

  const lockedMetrics = {
    gateway_01: [
      { label: 'FINGERPRINT', value: MOCK.gateway_01.audioFingerprint },
      { label: 'SIMILARITY', value: `${MOCK.gateway_01.similarityScore}%` },
      { label: 'LYRICAL MATCH', value: `${MOCK.gateway_01.lyricalMatch}%` },
      { label: 'STATUS', value: 'SCAN COMPLETE' },
    ],
    gateway_02: [
      { label: 'STEMS', value: `0${g02.midiFiles}` },
      { label: 'MIDI FILES', value: `0${g02.midiFiles}` },
      { label: 'MUSICXML', value: `0${g02.musicXmlFiles}` },
      { label: 'BPM', value: String(g02.bpm) },
      { label: 'KEY', value: g02.key },
    ],
    gateway_03: [
      { label: 'BPM', value: String(MOCK.gateway_03.bpm) },
      { label: 'KEY', value: MOCK.gateway_03.key },
      { label: 'TEMPO SHIFT', value: MOCK.gateway_03.tempoShift },
      { label: 'SIMILARITY ACHIEVED', value: `${MOCK.gateway_03.similarityAchieved}%` },
      { label: 'DEVIATION', value: `${MOCK.gateway_03.deviationAchieved}%` },
    ],
    gateway_04: [
      { label: 'BARS', value: String(MOCK.gateway_04.bars) },
      { label: 'RHYME DENSITY', value: MOCK.gateway_04.rhymeDensity },
      { label: 'STYLE', value: MOCK.gateway_04.style },
      { label: 'STRUCTURE', value: MOCK.gateway_04.structureMode },
    ],
    gateway_05: [
      { label: 'BPM', value: String(MOCK.gateway_05.bpm) },
      { label: 'KEY', value: MOCK.gateway_05.key },
      { label: 'SIMILARITY', value: `${MOCK.gateway_05.similarityFinal}%` },
      { label: 'STEMS', value: `0${MOCK.gateway_05.stems.length}` },
      { label: 'PROCESSING TIME', value: MOCK.gateway_05.processingTime },
      { label: 'CLEARANCE', value: MOCK.gateway_05.clearanceStatus, highlight: true },
    ],
  }

  const currentMetrics = lockedMetrics[state] || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PaneHeader label="FUSION MATRIX" node="NODE_07_B" />

      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>

        <Spectrogram active={isProcessing} />

        {isProcessing && (
          <TelemetryFeed lines={telemetryLines} active={isProcessing} />
        )}

        {phase === 1 && (
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '11px',
            color: 'rgba(255,255,255,0.15)', textAlign: 'center',
            paddingTop: '12px',
          }}>
            AWAITING INPUT
          </div>
        )}

        {phase === 3 && currentMetrics.length > 0 && (
          <div>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '10px',
              color: 'var(--text-secondary)', letterSpacing: '0.12em',
              marginBottom: '8px',
            }}>
              LOCKED METRICS
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
              {currentMetrics.map(m => (
                <MetricCell key={m.label} label={m.label} value={m.value} highlight={m.highlight} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Pane 3 — SOVEREIGN OUTPUT ────────────────────────────────────────────────

function PaneOutput({ state, onExit, onProceed, stemSelection, onStemSelection, lyricsResult }) {
  const phase = getPhase(state)
  const isProcessing = !!PROCESSING_NEXT[state]
  const gwNum = getGatewayNum(state)

  const proceedLabels = {
    gateway_01: '> PROCEED TO DECONSTRUCTION',
    gateway_02: '> PROCEED TO MORPH ENGINE',
    gateway_03: '> PROCEED TO LYRIC REBUILD',
    gateway_04: '> PROCEED TO RE-PLANT',
    gateway_05: null,
  }

  const exitLabels = {
    gateway_01: 'EXIT: DOWNLOAD LEGAL REPORT',
    gateway_02: 'EXIT: DOWNLOAD DAW PACKAGE',
    gateway_03: 'EXIT: EXPORT CLEARED BEAT',
    gateway_04: 'EXIT: EXPORT LYRIC CANVAS',
    gateway_05: '> EXPORT FINAL MASTER',
  }

  const earnedTitle = {
    gateway_01: 'EARNED PRODUCT — LEGAL DIAGNOSTIC REPORT',
    gateway_02: 'EARNED PRODUCT — THE DAW PACKAGE',
    gateway_03: 'EARNED PRODUCT — THE CLEARED BEAT',
    gateway_04: 'EARNED PRODUCT — THE CLEARED LYRIC CANVAS',
    gateway_05: 'EARNED PRODUCT — THE FINAL MASTER',
  }

  const lyrics = lyricsResult || MOCK.gateway_04.lyrics

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PaneHeader label="SOVEREIGN OUTPUT" node="NODE_07_C" />

      <div style={{ flex: 1, padding: '18px', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>

        {phase === 1 && (
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '11px',
            color: 'rgba(255,255,255,0.12)', textAlign: 'center',
            paddingTop: '20px',
          }}>
            DOCTRINE-GRADE CANVAS
            <br /><br />
            <span style={{ fontSize: '9px', display: 'block', lineHeight: 2 }}>
              AWAITING INPUT
            </span>
          </div>
        )}

        {isProcessing && (
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '11px',
            color: 'rgba(255,255,255,0.2)', textAlign: 'center',
            paddingTop: '20px',
            animation: 'blink 1.4s step-end infinite',
          }}>
            PROCESSING...
          </div>
        )}

        {phase === 3 && (
          <>
            <div style={{
              fontFamily: 'JetBrains Mono', fontSize: '9px',
              color: 'var(--neon)', letterSpacing: '0.15em',
              borderBottom: '1px solid rgba(0,255,136,0.2)',
              paddingBottom: '10px',
            }}>
              {earnedTitle[state]}
            </div>

            {state === 'gateway_01' && (
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
                <div style={{ marginBottom: '12px', color: 'var(--text-secondary)', fontSize: '10px' }}>
                  SCAN COMPLETE. REVIEW YOUR LEGAL POSITION BEFORE PROCEEDING.
                </div>
                <div>
                  Your uploaded audio matches a registered composition at{' '}
                  <span style={{ color: '#ffffff' }}>{MOCK.gateway_01.similarityScore}%</span> similarity.
                </div>
                <div>
                  Lyrical content matches at{' '}
                  <span style={{ color: '#ffffff' }}>{MOCK.gateway_01.lyricalMatch}%</span>.
                </div>
                <div style={{ marginTop: '10px', color: 'var(--warning)' }}>
                  RISK: {MOCK.gateway_01.violationRisk}
                </div>
                <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-secondary)' }}>
                  Transformation recommended. Proceed to bring similarity below the violation line.
                </div>
              </div>
            )}

            {state === 'gateway_02' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '9px',
                  color: 'var(--text-secondary)', letterSpacing: '0.1em',
                }}>
                  STEMS EXTRACTED · SELECT FILES TO DOWNLOAD
                </div>
                <StemSelectionTable selection={stemSelection} onChange={onStemSelection} />
              </div>
            )}

            {state === 'gateway_03' && (
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
                <div style={{ marginBottom: '10px', color: 'var(--text-secondary)', fontSize: '10px' }}>
                  ORIGINAL INSTRUMENTAL — CLEARED FOR STANDALONE EXPORT
                </div>
                <div>Original DNA preserved at <span style={{ color: '#fff' }}>{MOCK.gateway_03.similarityAchieved}%</span></div>
                <div>Deviation from source: <span style={{ color: 'var(--neon)' }}>{MOCK.gateway_03.deviationAchieved}%</span></div>
                <div>New key: <span style={{ color: '#fff' }}>{MOCK.gateway_03.key}</span></div>
                <div>New BPM: <span style={{ color: '#fff' }}>{MOCK.gateway_03.bpm}</span></div>
                <div style={{ marginTop: '10px', fontSize: '9px', color: 'var(--text-secondary)' }}>
                  All modifications traceable to source material. No unknowns.
                </div>
              </div>
            )}

            {state === 'gateway_04' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1, minHeight: 0 }}>
                <div style={{
                  fontFamily: 'JetBrains Mono', fontSize: '10px',
                  color: 'var(--text-secondary)',
                }}>
                  STYLE: {MOCK.gateway_04.style} · MODE: {MOCK.gateway_04.structureMode}
                </div>
                <div style={{
                  flex: 1,
                  overflow: 'auto',
                  border: '1px solid rgba(255,255,255,0.08)',
                  padding: '14px',
                  fontFamily: 'Outfit',
                  fontWeight: 300,
                  fontSize: '12px',
                  lineHeight: 1.8,
                  color: 'rgba(255,255,255,0.85)',
                  whiteSpace: 'pre-line',
                }}>
                  {lyrics}
                </div>
              </div>
            )}

            {state === 'gateway_05' && (
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
                <div style={{
                  padding: '14px',
                  border: '1px solid rgba(0,255,136,0.3)',
                  background: 'rgba(0,255,136,0.04)',
                  marginBottom: '12px',
                  textAlign: 'center',
                }}>
                  <div style={{ color: 'var(--neon)', fontFamily: 'Unbounded', fontWeight: 700, fontSize: '14px', letterSpacing: '0.1em' }}>
                    CLEARANCE STATUS: ORIGINAL
                  </div>
                  <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                    READY FOR PUBLIC RELEASE
                  </div>
                </div>
                <div>BPM: <span style={{ color: '#fff' }}>{MOCK.gateway_05.bpm}</span></div>
                <div>KEY: <span style={{ color: '#fff' }}>{MOCK.gateway_05.key}</span></div>
                <div>SIMILARITY: <span style={{ color: 'var(--neon)' }}>{MOCK.gateway_05.similarityFinal}%</span></div>
                <div>STEMS: <span style={{ color: '#fff' }}>{MOCK.gateway_05.stems.join(' · ')}</span></div>
                <div>TOTAL PROCESSING: <span style={{ color: '#fff' }}>{MOCK.gateway_05.processingTime}</span></div>
              </div>
            )}
          </>
        )}
      </div>

      {phase === 3 && (
        <div style={{
          padding: '14px 18px',
          borderTop: '1px solid var(--border-dim)',
          display: 'flex', flexDirection: 'column', gap: '8px',
        }}>
          {state === 'gateway_05' ? (
            <BtnPrimary onClick={onExit}>
              {'>'} EXPORT FINAL MASTER
            </BtnPrimary>
          ) : (
            <>
              <BtnPrimary onClick={onProceed}>
                {proceedLabels[state]}
              </BtnPrimary>
              <BtnHollow onClick={onExit} small>
                {exitLabels[state]}
              </BtnHollow>
            </>
          )}
        </div>
      )}
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
      <button
        onClick={onDismiss}
        style={{
          fontFamily: 'JetBrains Mono', fontSize: '9px',
          color: 'rgba(255,255,255,0.4)', background: 'transparent',
          border: '1px solid rgba(255,255,255,0.15)', padding: '3px 8px', cursor: 'pointer',
        }}
      >
        DISMISS
      </button>
    </div>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [state, setState] = useState('idle')
  const [file, setFile] = useState(null)
  const [similarityTarget, setSimilarityTarget] = useState(35)
  const [lyricMode, setLyricMode] = useState('PRESET')
  const [structureMode, setStructureMode] = useState('PLACEHOLDER')
  const [stemSelection, setStemSelection] = useState(initStemSelection)
  const [voiceProfile, setVoiceProfile] = useState(null)

  // API state
  const [projectId, setProjectId] = useState(null)
  const [transformResult, setTransformResult] = useState(null)
  const [lyricsResult, setLyricsResult] = useState(null)
  const [lmSettings, setLmSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tmLmSettings') || '{}') } catch { return {} }
  })
  const [apiError, setApiError] = useState(null)

  const timerRef = useRef(null)

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
      const form = new FormData()
      form.append('file', rawFile)
      await apiPost(`/api/projects/${proj.id}/upload`, form)
    } catch (e) {
      setApiError(`Upload: ${e.message}`)
    }
  }, [startProcessing])

  const handleProceed = useCallback(() => {
    if (state === 'gateway_01') {
      startProcessing('deconstructing')
      if (projectId) {
        apiPost(`/api/projects/${projectId}/transform`, {})
          .then(result => setTransformResult(result))
          .catch(e => setApiError(`Transform: ${e.message}`))
      }
    } else if (state === 'gateway_02') {
      startProcessing('morphing')
    } else if (state === 'gateway_03') {
      startProcessing('rebuilding_lyrics')
      if (projectId) {
        apiPost(`/api/projects/${projectId}/generate-lyrics`, {
          style: lyricMode.toLowerCase(),
          ollama_base_url: lmSettings.url || 'http://localhost:1234',
          ollama_model: lmSettings.model || '',
        })
          .then(result => setLyricsResult(result.lyrics))
          .catch(e => setApiError(`Lyrics: ${e.message}`))
      }
    } else if (state === 'gateway_04') {
      startProcessing('planting')
    }
  }, [state, startProcessing, projectId, lmSettings, lyricMode])

  const handleExit = useCallback(async () => {
    setApiError(null)
    if (state === 'gateway_02' && projectId) {
      try {
        const blob = await apiGetBlob(`/api/projects/${projectId}/download-stems`)
        triggerDownload(blob, 'DAW_PACKAGE.zip')
      } catch (e) {
        setApiError(`Download: ${e.message}`)
      }
      return
    }
    if (state === 'gateway_04' && projectId) {
      try {
        const blob = await apiGetBlob(`/api/projects/${projectId}/download-lyrics`)
        triggerDownload(blob, 'LYRIC_CANVAS.txt')
      } catch (e) {
        setApiError(`Download: ${e.message}`)
      }
      return
    }
    // Gateways 01, 03, 05: no real download yet
    console.log(`[MOCK EXIT] gateway: ${state}`)
  }, [state, projectId])

  const handleReset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setState('idle')
    setFile(null)
    setSimilarityTarget(35)
    setProjectId(null)
    setTransformResult(null)
    setLyricsResult(null)
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

  return (
    <div style={{
      height: '100vh',
      background: 'var(--bg-primary)',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px',
      gap: '14px',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexShrink: 0,
      }}>
        <Logo phase={phase} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <GatewayBar state={state} />

          {state !== 'idle' && (
            <button
              onClick={handleReset}
              style={{
                fontFamily: 'JetBrains Mono',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.25)',
                background: 'none',
                border: '1px solid rgba(255,255,255,0.1)',
                padding: '6px 10px',
                letterSpacing: '0.1em',
                cursor: 'pointer',
              }}
            >
              RESET
            </button>
          )}
        </div>
      </div>

      {/* Status bar */}
      {state !== 'idle' && (
        <div style={{
          fontFamily: 'JetBrains Mono',
          fontSize: '10px',
          color: phase === 2 ? 'var(--neon)' : 'var(--text-secondary)',
          letterSpacing: '0.1em',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          animation: phase === 2 ? 'blink 1.4s step-end infinite' : 'none',
        }}>
          <span style={{
            display: 'inline-block',
            width: '6px', height: '6px',
            background: phase === 2 ? 'var(--neon)' : 'rgba(0,255,136,0.4)',
          }} />
          {phase === 2 && TELEMETRY[state]?.[0]}
          {phase === 3 && `GATEWAY ${String(getGatewayNum(state)).padStart(2, '0')} — COMPLETE`}
        </div>
      )}

      {/* Error banner */}
      <ErrorBanner error={apiError} onDismiss={() => setApiError(null)} />

      {/* Three-pane layout */}
      <div style={{
        flex: 1,
        display: 'flex',
        gap: '12px',
        minHeight: 0,
      }}>
        <div style={paneStyles(0)}>
          <PaneInput
            state={state}
            file={file}
            similarityTarget={similarityTarget}
            onTargetChange={setSimilarityTarget}
            lyricMode={lyricMode}
            onLyricMode={setLyricMode}
            structureMode={structureMode}
            onStructureMode={setStructureMode}
            voiceProfile={voiceProfile}
            onVoiceProfile={setVoiceProfile}
            onIngest={handleIngest}
            lmSettings={lmSettings}
            onLmSettings={setLmSettings}
          />
        </div>

        <div style={paneStyles(1)}>
          <PaneFusion state={state} transformResult={transformResult} />
        </div>

        <div style={paneStyles(2)}>
          <PaneOutput
            state={state}
            onExit={handleExit}
            onProceed={handleProceed}
            stemSelection={stemSelection}
            onStemSelection={setStemSelection}
            lyricsResult={lyricsResult}
          />
        </div>
      </div>

      {/* Footer */}
      <div style={{
        flexShrink: 0,
        fontFamily: 'JetBrains Mono',
        fontSize: '9px',
        color: 'rgba(255,255,255,0.12)',
        letterSpacing: '0.12em',
        display: 'flex',
        justifyContent: 'space-between',
      }}>
        <span>TRANSFORMUSIC // GATEWAY PIPELINE</span>
        <span>EASE IS EARNED</span>
      </div>
    </div>
  )
}
