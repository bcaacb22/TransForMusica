import { useState, useCallback } from 'react'
import { apiPost, apiGetBlob, triggerDownload } from '../../lib/apiClient'

// ─── Mock data (fallback when no real data available) ─────────────────────────

const MOCK_GATEWAY_04 = {
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
}

// ─── Local helper components ──────────────────────────────────────────────────

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

function BtnPrimary({ children, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'var(--neon)',
        color: '#000000',
        fontFamily: 'JetBrains Mono',
        fontWeight: 500,
        fontSize: '12px',
        letterSpacing: '0.1em',
        padding: '12px 20px',
        border: 'none',
        boxShadow: disabled ? 'none' : 'var(--neon-glow)',
        transition: 'opacity 0.15s',
      }}
    >
      {children}
    </button>
  )
}

function BtnHollow({ children, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
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
      {children}
    </button>
  )
}

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

// ─── Gateway 04 — Lyric Rebuild ───────────────────────────────────────────────

export default function Gateway04LyricRebuild({ projectId, project, onComplete }) {
  // Lyric engine state
  const [lyricMode, setLyricMode] = useState('PRESET')
  const [structureMode, setStructureMode] = useState('PLACEHOLDER')
  const [lmSettings, setLmSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tmLmSettings') || '{}') } catch { return {} }
  })

  // Generation state
  const [lyricsResult, setLyricsResult] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(null)

  const lyrics = lyricsResult || MOCK_GATEWAY_04.lyrics

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const handleGenerateLyrics = useCallback(async () => {
    if (!projectId) return
    setError(null)
    setGenerating(true)
    try {
      const result = await apiPost(`/api/projects/${projectId}/generate-lyrics`, {
        style: lyricMode.toLowerCase(),
        structure_mode: structureMode.toLowerCase(),
        ollama_base_url: lmSettings.url || 'http://localhost:1234',
        ollama_model: lmSettings.model || '',
      })
      setLyricsResult(result.lyrics)
    } catch (e) {
      setError(`Lyrics generation: ${e.message}`)
    } finally {
      setGenerating(false)
    }
  }, [projectId, lyricMode, structureMode, lmSettings])

  const handleDownloadLyrics = useCallback(() => {
    const title = project?.name
      ? project.name.replace(/\.[^.]+$/, '').toUpperCase()
      : 'UNTITLED'
    const content = [
      '╔══════════════════════════════════════════════════════╗',
      '║           TRANSFORMUSIC — LYRIC CANVAS               ║',
      '╚══════════════════════════════════════════════════════╝',
      `TITLE:    ${title}`,
      `STYLE:    ${lyricMode}`,
      `CREATED:  ${new Date().toISOString()}`,
      `STATUS:   ORIGINAL WORK — READY FOR PUBLISHING`,
      '',
      '─────────────────────────────────────────────────────────',
      '',
      lyrics,
      '',
      '─────────────────────────────────────────────────────────',
      'Generated by Transformusic',
      'This work is original and ready for copyright registration.',
    ].join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    triggerDownload(blob, 'LYRIC_CANVAS.txt')
  }, [lyrics, lyricMode, project])

  const handleProceed = useCallback(() => {
    onComplete()
  }, [onComplete])

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Error banner */}
      {error && (
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
            onClick={() => setError(null)}
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

      {/* Main content area */}
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', padding: '18px' }}>

        {/* Lyric Engine Controls */}
        <ControlBlock label="LYRIC ENGINE — SELECT MODE">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <ChoiceRow
              options={[
                { label: 'PRESET', value: 'PRESET' },
                { label: 'DEFINED', value: 'DEFINED' },
                { label: 'LEARNED', value: 'LEARNED' },
              ]}
              selected={lyricMode}
              onSelect={setLyricMode}
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
              onSelect={setStructureMode}
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

        <LmSettings settings={lmSettings} onChange={setLmSettings} />

        {/* Generate button */}
        <div style={{ textAlign: 'center' }}>
          <BtnPrimary onClick={handleGenerateLyrics} disabled={generating}>
            {generating ? '// GENERATING...' : '> GENERATE LYRICS'}
          </BtnPrimary>
        </div>

        {/* Metrics */}
        <div>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '10px',
            color: 'var(--text-secondary)', letterSpacing: '0.12em',
            marginBottom: '8px',
          }}>
            LOCKED METRICS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
            <MetricCell label="BARS" value={String(MOCK_GATEWAY_04.bars)} />
            <MetricCell label="RHYME DENSITY" value={MOCK_GATEWAY_04.rhymeDensity} />
            <MetricCell label="STYLE" value={MOCK_GATEWAY_04.style} />
            <MetricCell label="STRUCTURE" value={MOCK_GATEWAY_04.structureMode} />
          </div>
        </div>

        {/* Lyrics display */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1, minHeight: 0 }}>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '9px',
            color: 'var(--neon)', letterSpacing: '0.15em',
            borderBottom: '1px solid rgba(0,255,136,0.2)',
            paddingBottom: '10px',
          }}>
            EARNED PRODUCT — THE CLEARED LYRIC CANVAS
          </div>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '10px',
            color: 'var(--text-secondary)',
          }}>
            STYLE: {MOCK_GATEWAY_04.style} · MODE: {MOCK_GATEWAY_04.structureMode}
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
      </div>

      {/* Action buttons */}
      <div style={{
        padding: '14px 18px',
        borderTop: '1px solid var(--border-dim)',
        display: 'flex', flexDirection: 'column', gap: '8px',
      }}>
        <BtnPrimary onClick={handleProceed} disabled={generating}>
          {'> PROCEED TO RE-PLANT'}
        </BtnPrimary>
        <BtnHollow onClick={!downloading ? handleDownloadLyrics : undefined} disabled={downloading || generating}>
          {downloading ? '// PACKAGING...' : 'EXIT: EXPORT LYRIC CANVAS'}
        </BtnHollow>
      </div>
    </div>
  )
}
