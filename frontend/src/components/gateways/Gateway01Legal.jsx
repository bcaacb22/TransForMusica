import { useState, useEffect, useCallback } from 'react'
import { apiPost } from '../../lib/apiClient'

// ─── Utility ──────────────────────────────────────────────────────────────────

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ─── MetricCell ───────────────────────────────────────────────────────────────

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

// ─── BtnPrimary ───────────────────────────────────────────────────────────────

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

// ─── BtnHollow ────────────────────────────────────────────────────────────────

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

// ─── Default mock data (fallback when no scan result) ─────────────────────────

const MOCK_LEGAL = {
  similarityScore: 0,
  matchedSource: 'NO MATCH FOUND',
  audioFingerprint: '—',
  lyricalMatch: 0,
  violationRisk: 'NONE',
  isrc: null,
  label: null,
  releaseDate: null,
  genre: null,
}

// ─── Gateway01Legal Component ─────────────────────────────────────────────────

/**
 * Gateway 01 — Legal Diagnostic
 *
 * Displays the results of the Shazam legal scan for the uploaded audio file.
 * Shows matched source, ISRC, label, release date, genre, BPM, key, and violation risk.
 * Provides a PROCEED button to advance to the next gateway and an EXIT button
 * to download the legal diagnostic report.
 *
 * Props:
 *   - projectId: string — the current project ID
 *   - project: object — the project data (includes original file info)
 *   - onComplete: () => void — callback to advance to the next gateway
 */
export default function Gateway01Legal({ projectId, project, onComplete }) {
  const [scanResult, setScanResult] = useState(null)
  const [scanError, setScanError] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const d = scanResult || MOCK_LEGAL
  const scanPending = !scanResult && !scanError

  // Trigger legal scan on mount if projectId is available
  useEffect(() => {
    if (!projectId) return
    let cancelled = false

    const runScan = async () => {
      setScanning(true)
      setScanError(null)
      try {
        const result = await apiPost(`/api/projects/${projectId}/legal-scan`, {})
        if (!cancelled) {
          setScanResult(result)
        }
      } catch (e) {
        if (!cancelled) {
          setScanError(e.message || 'Legal scan failed')
        }
      } finally {
        if (!cancelled) {
          setScanning(false)
        }
      }
    }

    runScan()
    return () => { cancelled = true }
  }, [projectId])

  // Build a single engine section for the text report
  const engineSection = (eng) => {
    if (!eng) return [
      'SOURCE               : (no result)',
      'MATCHED SOURCE       : N/A',
      'ISRC                 : -',
      'LABEL                : -',
      'RELEASE DATE         : -',
      'GENRE                : -',
      'ALBUM                : -',
      'MATCHED AT           : -',
      'SPOTIFY              : -',
      'APPLE MUSIC          : -',
    ]
    return [
      `SOURCE               : ${eng.source}`,
      `MATCHED SOURCE       : ${eng.matchedSource || 'N/A'}`,
      `ISRC                 : ${eng.isrc || '-'}`,
      `LABEL                : ${eng.label || '-'}`,
      `RELEASE DATE         : ${eng.releaseDate || '-'}`,
      `GENRE                : ${eng.genre || '-'}`,
      `ALBUM                : ${eng.album || '-'}`,
      eng.timecode ? `MATCHED AT           : ${eng.timecode}` : 'MATCHED AT           : -',
      eng.spotifyUrl ? `SPOTIFY              : ${eng.spotifyUrl}` : 'SPOTIFY              : -',
      eng.appleMusicUrl ? `APPLE MUSIC          : ${eng.appleMusicUrl}` : 'APPLE MUSIC          : -',
    ]
  }

  // Download legal diagnostic report (text)
  const handleDownloadReport = useCallback(() => {
    setDownloading(true)
    const now = new Date().toISOString()
    const fname = project?.original_file || project?.name || 'UNKNOWN'
    const shazam = d.shazamResult
    const acoustid = d.acoustidResult
    const report = [
      '╔══════════════════════════════════════════════════════╗',
      '║         TRANSFORMUSIC — LEGAL DIAGNOSTIC REPORT      ║',
      '╚══════════════════════════════════════════════════════╝',
      '',
      `GENERATED     : ${now}`,
      `SOURCE FILE   : ${fname}`,
      '',
      '── IDENTIFICATION ──────────────────────────────────────',
      ...engineSection(shazam),
      '',
      '────────────────────────────────────────────────────────',
      ...engineSection(acoustid),
      '',
      '── AUDIO ANALYSIS ──────────────────────────────────────',
      `BPM                : ${d.bpm || '—'}`,
      `KEY                : ${d.key || '—'}`,
      `DURATION           : ${d.duration ? `${d.duration}s` : '—'}`,
      `LYRICAL MATCH      : ${d.lyricalMatch != null ? `${d.lyricalMatch}%` : '—'}`,
      `VIOLATION RISK     : ${d.violationRisk}`,
      '',
      '── RECOMMENDATION ──────────────────────────────────────',
      d.violationRisk === 'HIGH'
        ? 'TRACK IDENTIFIED ON STREAMING PLATFORMS. Transformation required before redistribution.'
        : 'CLEAR TO PROCEED. No registered match found in database.',
      '',
      '────────────────────────────────────────────────────────',
      'Powered by Shazam API v2 and AcoustID (Chromaprint) audio recognition.',
      'This report is generated for informational purposes only.',
      'It does not constitute legal advice.',
    ].filter(Boolean).join('\n')
    const blob = new Blob([report], { type: 'text/plain' })
    triggerDownload(blob, 'LEGAL_DIAGNOSTIC_REPORT.txt')
    setDownloading(false)
  }, [d, project])

  // Styled PDF report — opens a print-ready window
  const handlePdfReport = useCallback(() => {
    const now = new Date().toISOString()
    const fname = project?.original_file || project?.name || 'UNKNOWN'
    const shazam = d.shazamResult
    const acoustid = d.acoustidResult
    const riskColor = d.violationRisk === 'HIGH' ? '#ff3b3b' : d.violationRisk === 'MODERATE' ? '#ffaa00' : '#00ff88'
    const row = (label, value) => `<tr><td class="lbl">${label}</td><td class="val">${value || '—'}</td></tr>`
    const engineTable = (eng) => {
      if (!eng) return `<div class="engine"><div class="engine-name" style="color:#666">NO RESULT</div><p class="nomatch">No match found by this engine.</p></div>`
      return `<div class="engine">
        <div class="engine-name">${eng.source}</div>
        <table>
          ${row('MATCHED SOURCE', eng.matchedSource)}
          ${row('ISRC', eng.isrc)}
          ${row('LABEL', eng.label)}
          ${row('RELEASE DATE', eng.releaseDate)}
          ${row('GENRE', eng.genre)}
          ${row('ALBUM', eng.album)}
          ${row('MATCHED AT', eng.timecode)}
          ${eng.spotifyUrl ? `<tr><td class="lbl">SPOTIFY</td><td class="val"><a href="${eng.spotifyUrl}">${eng.spotifyUrl}</a></td></tr>` : ''}
          ${eng.appleMusicUrl ? `<tr><td class="lbl">APPLE MUSIC</td><td class="val"><a href="${eng.appleMusicUrl}">${eng.appleMusicUrl}</a></td></tr>` : ''}
        </table>
      </div>`
    }
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Legal Diagnostic Report</title>
<style>
  @page { margin: 2cm; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #fff; color: #1a1a1a; padding: 40px; }
  .header { display: flex; align-items: center; gap: 16px; border-bottom: 3px solid #00ff88; padding-bottom: 16px; margin-bottom: 24px; }
  .logo { width: 48px; height: 48px; background: #00ff88; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 20px; color: #000; }
  .header h1 { font-size: 22px; letter-spacing: 2px; }
  .header .sub { font-size: 12px; color: #666; }
  .meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 24px; font-size: 13px; color: #444; }
  .section { margin-bottom: 24px; }
  .section h2 { font-size: 14px; letter-spacing: 2px; color: #00aa55; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-bottom: 12px; }
  .engine { margin-bottom: 16px; padding: 12px; border: 1px solid #e0e0e0; border-radius: 6px; }
  .engine-name { font-weight: 700; font-size: 13px; color: #00aa55; margin-bottom: 8px; }
  .nomatch { color: #999; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 4px 8px; font-size: 13px; }
  .lbl { color: #666; width: 140px; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }
  .val { color: #1a1a1a; }
  a { color: #0066cc; text-decoration: none; }
  .risk { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 14px; color: #fff; background: ${riskColor}; }
  .analysis table td { padding: 6px 8px; }
  .footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 11px; color: #999; }
  .rec { font-size: 14px; font-weight: 600; margin-top: 8px; }
</style></head><body>
<div class="header">
  <div class="logo">TM</div>
  <div><h1>TRANSFORMUSIC</h1><div class="sub">LEGAL DIAGNOSTIC REPORT</div></div>
</div>
<div class="meta">
  <div><strong>Generated:</strong> ${now}</div>
  <div><strong>Source File:</strong> ${fname}</div>
</div>
<div class="section"><h2>IDENTIFICATION</h2>
  ${engineTable(shazam)}
  ${engineTable(acoustid)}
</div>
<div class="section analysis"><h2>AUDIO ANALYSIS</h2>
  <table>
    ${row('BPM', d.bpm)}
    ${row('KEY', d.key)}
    ${row('DURATION', d.duration ? `${d.duration}s` : null)}
    ${row('LYRICAL MATCH', d.lyricalMatch != null ? `${d.lyricalMatch}%` : null)}
    <tr><td class="lbl">VIOLATION RISK</td><td class="val"><span class="risk">${d.violationRisk}</span></td></tr>
  </table>
</div>
<div class="section"><h2>RECOMMENDATION</h2>
  <p class="rec">${d.violationRisk === 'HIGH'
    ? 'TRACK IDENTIFIED ON STREAMING PLATFORMS. Transformation required before redistribution.'
    : 'CLEAR TO PROCEED. No registered match found in database.'}</p>
</div>
<div class="footer">
  Powered by Shazam API v2 and AcoustID (Chromaprint) audio recognition.<br>
  This report is generated for informational purposes only. It does not constitute legal advice.
</div>
<script>window.onload = () => { setTimeout(() => window.print(), 300) }</script>
</body></html>`
    const w = window.open('', '_blank', 'width=800,height=900')
    if (w) {
      w.document.write(html)
      w.document.close()
    }
  }, [d, project])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <div style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'var(--neon)', letterSpacing: '0.15em',
      }}>
        // GATEWAY 01 — LEGAL DIAGNOSTIC
      </div>

      {/* Scan status / results */}
      <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', lineHeight: 2, color: 'var(--text-terminal)' }}>
        {scanPending || scanning ? (
          <div style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
            IDENTIFYING AUDIO... QUERYING RECOGNITION DATABASE...
          </div>
        ) : scanError ? (
          <div style={{ color: 'var(--danger)', fontSize: '10px' }}>
            SCAN ERROR: {scanError}
          </div>
        ) : (
          <>
            <div style={{ marginBottom: '12px', color: 'var(--text-secondary)', fontSize: '10px' }}>
              SCAN COMPLETE. REVIEW YOUR LEGAL POSITION BEFORE PROCEEDING.
            </div>
            {d.matchedSource && d.matchedSource !== 'NO MATCH FOUND' ? (
              <>
                <div>Matched: <span style={{ color: '#ffffff' }}>{d.matchedSource}</span></div>
                {d.isrc && <div>ISRC: <span style={{ color: '#ffffff' }}>{d.isrc}</span></div>}
                {d.label && <div>Label: <span style={{ color: '#ffffff' }}>{d.label}</span></div>}
                {d.releaseDate && <div>Released: <span style={{ color: '#ffffff' }}>{d.releaseDate}</span></div>}
                {d.genre && <div>Genre: <span style={{ color: '#ffffff' }}>{d.genre}</span></div>}
                {d.timecode && <div>Matched at: <span style={{ color: '#ffffff' }}>{d.timecode}</span></div>}
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>NO REGISTERED MATCH FOUND IN DATABASE.</div>
            )}
            {d.bpm && (
              <div style={{ marginTop: '8px' }}>BPM: <span style={{ color: '#ffffff' }}>{d.bpm}</span>{d.key ? ` / KEY: ${d.key}` : ''}</div>
            )}
            <div style={{ marginTop: '10px', color: d.violationRisk === 'HIGH' ? 'var(--danger)' : d.violationRisk === 'MODERATE' ? 'var(--warning)' : 'var(--neon)' }}>
              RISK: {d.violationRisk}
            </div>
            <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-secondary)' }}>
              {d.violationRisk === 'NONE' || d.matchedSource === 'NO MATCH FOUND'
                ? 'No significant copyright risk detected. Clear to proceed.'
                : 'Track identified on streaming platforms. Transformation required before redistribution.'}
            </div>
          </>
        )}
      </div>

      {/* Metrics grid */}
      {!scanPending && !scanning && !scanError && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
          <MetricCell label="SIMILARITY" value={`${d.similarityScore ?? 0}%`} highlight />
          <MetricCell
            label="VIOLATION RISK"
            value={d.violationRisk}
            highlight={d.violationRisk === 'MODERATE' || d.violationRisk === 'HIGH'}
          />
          <MetricCell label="MATCHED SOURCE" value={d.matchedSource} />
          <MetricCell label="ISRC" value={d.isrc || 'NOT REGISTERED'} />
          <MetricCell label="LABEL" value={d.label || '—'} />
          <MetricCell label="RELEASE DATE" value={d.releaseDate || '—'} />
          <MetricCell label="GENRE" value={d.genre || '—'} />
          <MetricCell label="LYRICAL MATCH" value={d.lyricalMatch != null ? `${d.lyricalMatch}%` : '—'} />
          {d.bpm && <MetricCell label="BPM" value={d.bpm} />}
          {d.key && <MetricCell label="KEY" value={d.key} />}
        </div>
      )}

      {/* Action buttons — the deliverable first, then proceed */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '8px' }}>
        <BtnHollow
          onClick={handleDownloadReport}
          small
          disabled={downloading || scanPending || scanning}
        >
          {downloading ? '// PACKAGING...' : 'DOWNLOAD REPORT'}
        </BtnHollow>
        <BtnHollow
          onClick={handlePdfReport}
          small
          disabled={scanPending || scanning}
        >
          PDF REPORT
        </BtnHollow>
        <BtnPrimary
          onClick={onComplete}
          disabled={scanPending || scanning}
        >
          {scanPending || scanning ? '// SCANNING...' : '> PROCEED TO DECONSTRUCTION'}
        </BtnPrimary>
      </div>

      {/* Error display */}
      {scanError && (
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: '10px',
          color: 'var(--danger)', padding: '8px 12px',
          border: '1px solid rgba(255,0,0,0.3)',
          background: 'rgba(255,0,0,0.05)',
        }}>
          ⚠ {scanError}
        </div>
      )}
    </div>
  )
}
