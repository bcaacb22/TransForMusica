# TRANSFORMUSIC V2 — Style Aesthetic Document

## Philosophy

The app is the metaphor. The UI does not describe transformation — it undergoes it.
The interface begins as a raw schematic and resolves into doctrine as the user works.
Every visual state is earned by completing the phase before it.

---

## Typography Stack

Sourced from effortlessmetaphor.org. Non-negotiable.

| Role | Font | Weight | Usage |
|------|------|--------|-------|
| Phase 1 / Terminal / Labels | JetBrains Mono | 400, 500 | Node headers, status lines, telemetry readouts |
| Phase 3 / Brand / Output | Unbounded | 700, 900 | Logo final state, output panel headers, doctrine text |
| UI Body / Inputs | Inter | 600 | Buttons, field labels, secondary UI |
| Body Copy | Outfit | 300, 400, 600 | Descriptions, metadata, helper text |

---

## Color System

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#000000` | Global background |
| `--bg-surface` | `#0a0a0a` | Pane backgrounds |
| `--bg-surface-2` | `#111111` | Card / input backgrounds |
| `--border-dim` | `rgba(255,255,255,0.08)` | Inactive pane borders |
| `--border-active` | `#00ff88` | Active pane bounding box |
| `--text-primary` | `#ffffff` | Primary text |
| `--text-secondary` | `rgba(255,255,255,0.45)` | Dim labels, inactive states |
| `--text-terminal` | `rgba(255,255,255,0.75)` | Monospace telemetry text |
| `--neon` | `#00ff88` | Neon green — buttons, active borders, signal bars, status line |
| `--neon-dim` | `rgba(0,255,136,0.15)` | Neon glow fill, spectrogram background |
| `--neon-glow` | `0 0 12px rgba(0,255,136,0.6)` | Box shadow for active elements |
| `--danger` | `#ff3b3b` | Error states |
| `--warning` | `#ffaa00` | Processing warnings |

---

## Three-Phase Visual System

### Phase 1 — The Schematic
*Triggered: App load / no project active*

- Background: `#000000`
- Logo: Wireframe only. JetBrains Mono, thin stroke, no fill. Renders as `TRANSFORMUSIC // NODE_07`
- Pane borders: `1px solid rgba(255,255,255,0.08)` — barely visible structural lines
- Text: All white monospace, low opacity (`0.45–0.75`)
- Buttons: Hollow. `1px solid #00ff88`, transparent fill, neon green text
- Accents: None. No glow, no color bleeding
- Feel: Architect's desk. Uncompiled. Structural geometry only.

### Phase 2 — Signal Overdrive
*Triggered: Audio ingested, backend processing active*

- Logo: Text locked in place. Center fractures into vertical neon green signal bars / waveform eruption. Glow: `--neon-glow`
- Active pane border: Solid `#00ff88` bounding box, `box-shadow: --neon-glow`
- Inactive panes: Drop to `opacity: 0.35`, borders remain dim
- Spectrogram: Pixel-precise neon green bars, hardware diagnostic aesthetic, flickering in real-time
- Buttons: Solid `#00ff88` fill, black text — `> PROCESSING...`
- Telemetry lines animate: `SUB_BASS: ISOLATED`, `HIGH_MIDS: CALCULATED`, etc.
- Feel: System under load. Signal erupting. Controlled chaos.

### Phase 3 — Doctrine Lock
*Triggered: Processing complete, output ready*

- Logo: Resolves to full Unbounded 900 weight. Solid white. Underlined by sharp neon green status bar.
- All three panes: Return to full opacity. Active pane border dims back to `rgba(255,255,255,0.15)`
- Output pane: Hard-lined cells. Metrics lock in: `BPM: 71`, `STEMS: 04`, `ANCHORS: 00`
- Lyrics display: Crisp, clean, zero filler. Unbounded or Inter depending on content density
- Export button: Solid `#00ff88`, Unbounded font, `> EXPORT PACKAGE`
- Feel: Permanent. Immovable. System anchor. Work is done.

---

## Three-Pane Architecture

All three panes visible at all times. Active pane is lit. Inactive panes are dimmed but present — the pipeline is always legible.

```
+------------------+------------------+------------------+
| // INPUT         | // PROCESSING    | // OUTPUT        |
| NODE_07_A        | NODE_07_B        | NODE_07_C        |
|                  |                  |                  |
| RAW INGESTION    | FREQUENCY        | DOCTRINE-GRADE   |
| UNIT             | DECONSTRUCTION   | CANVAS           |
+------------------+------------------+------------------+
```

### Pane 1 — Ingestion Module (Left)
- Dark container, thin border
- White monospace upload telemetry
- Drop zone: dashed `#00ff88` border
- Primary CTA: Solid flat neon green block — `> INGEST AUDIO` — black text, JetBrains Mono
- File name, duration, format display as terminal readout once loaded

### Pane 2 — Fusion Matrix (Center)
- Inactive: dim structural shell, placeholder spectrogram grid
- Active: neon green bounding box, live spectrogram, animated telemetry lines
- Status lines: `SUB_BASS: ISOLATED`, `HIGH_MIDS: CALCULATED`, `STEMS: SEPARATING...`
- No colorful wave art. Pixel-precise. Hardware diagnostic console only.

### Pane 3 — Sovereign Output (Right)
- Resolves last. Dim until processing completes.
- Left half: Generated lyrics, clean type, no filler
- Right half: Metric cells — `BPM`, `STEMS`, `KEY`, `ANCHORS`, `STYLE`
- Export CTA: `> EXPORT PACKAGE` — Unbounded, solid neon green

---

## Component Rules

- **No rounded corners** anywhere in the interface. Everything is rectilinear.
- **No gradients** in Phase 1. Gradients are Phase 2 only (neon bleed/glow).
- **No shadows** except `--neon-glow` on active elements.
- **No colored text** except neon green for active states and status indicators.
- **No icons** unless functional. No decorative iconography.
- **Borders are structural** — they define space, not decoration.
- **Spacing** is generous. Panes breathe. Terminal aesthetic requires negative space.
- **Animations**: Phase transitions use a mechanical, step-based easing — not smooth curves. Stagger reveals, not fades.

---

## Logo States

| Phase | Rendering |
|-------|-----------|
| Schematic | `TRANSFORMUSIC // NODE_07` — JetBrains Mono 500, wireframe only, no fill |
| Signal Overdrive | Text locked, center erupts with vertical neon signal bars, glow active |
| Doctrine Lock | Unbounded 900, solid white, 3px `#00ff88` underline bar beneath |

---

## Reference

- Typography source: `https://www.effortlessmetaphor.org`
- Brand fonts loaded via Google Fonts: `Unbounded`, `JetBrains Mono`, `Inter`, `Outfit`
- Color anchor: effortlessmetaphor.org cyberpunk system (`neon green on black`)
- Design language owner: Thomas Parks Edwards IV (OGTommyP)
