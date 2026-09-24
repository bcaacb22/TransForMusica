// src/components/AudioPlayer.jsx — compact neon audio player for stems/originals

export default function AudioPlayer({ src, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '10px',
      border: '1px solid rgba(0,255,136,0.2)',
      background: 'rgba(0,255,136,0.03)',
      padding: '6px 10px',
    }}>
      <span style={{
        fontFamily: 'JetBrains Mono', fontSize: '9px',
        color: 'var(--neon)', letterSpacing: '0.1em', flexShrink: 0,
      }}>
        ▶ {label}
      </span>
      <audio
        controls
        preload="none"
        src={src}
        style={{ width: '100%', height: '28px', filter: 'invert(1) hue-rotate(90deg)' }}
      />
    </div>
  )
}
