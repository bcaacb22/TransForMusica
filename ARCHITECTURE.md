# Transformusic — Architecture

## Purpose

Transformusic is a 5-gateway beat deconstruction and lyric generation pipeline. Upload any audio (beat, instrumental, full track) and move it through:

1. **Legal Diagnostic** — AuDD.io fingerprint scan, similarity score, violation risk
2. **Deconstruction** — Demucs stem separation → MIDI (Basic Pitch) → MusicXML (music21)
3. **Morph Engine** — deterministic DSP reshaping: time-stretch + pitch-shift driven by a similarity target (or explicit key/BPM), with measured achieved similarity
4. **Lyric Rebuild** — local LLM generation with style fingerprinting; CADENCE (keep original structure) vs FRESH (new structure) modes
5. **Voice Clone** — TTS-server voice cloning onto generated lyrics (requires `VOICE_CLONE_URL`)

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11), async via uvicorn |
| Database | MongoDB (motor async driver) |
| Stem Separation | Demucs `htdemucs` — remote GPU server or local CPU fallback |
| Audio-to-MIDI | Basic Pitch (Spotify) |
| Morph DSP | librosa `time_stretch`/`pitch_shift`, pretty_midi (`morph_engine.py`) |
| Notation | music21, pretty_midi, mido |
| Transcription | faster-whisper (tiny, GPU or CPU) — runs on remote Demucs server |
| Music Recognition | AuDD.io API (legal scan) |
| Voice Clone | XTTS-v2 or F5-TTS via standalone server (`xtts_server.py` / `f5tts_server.py`, port 8500) |
| Style Engine | Custom heuristic + LLM hybrid (`style_engine.py`) |
| Task Bounding | `task_manager.py` — global `asyncio.Semaphore(10)`, strong-ref background tasks |
| Frontend | React 19, Vite 8, Tailwind CSS, per-gateway components, resilient fetch client |
| Transport | REST (fetch + retry/backoff), multipart file uploads, Vite `/api` proxy |

## Directory Structure

```
Transformusic/
├── ARCHITECTURE.md
├── SETUP.md
├── CEREMONIES.md          # V2 product vision / gateway ceremony spec
├── STYLE.md
├── README.md
├── memory/
│   ├── PRD.md             # Product requirements
│   └── test_credentials.md
├── backend/
│   ├── server.py          # All FastAPI endpoints, models, pipeline logic (~2100 lines)
│   ├── morph_engine.py    # Gateway 03 — deterministic DSP morph + similarity measurement
│   ├── style_engine.py    # Lyric fingerprinting (heuristic + LLM hybrid)
│   ├── task_manager.py    # Bounded background tasks (semaphore 10, strong refs)
│   ├── run_app.py         # Launcher — stubs basic_pitch if not installed
│   ├── demucs_server.py   # Standalone Demucs + Whisper server (run on Windows GPU)
│   ├── xtts_server.py     # Standalone XTTS-v2 clone server (/health + /clone, :8500)
│   ├── f5tts_server.py    # Standalone F5-TTS clone server (/health + /clone, :8500)
│   ├── requirements-core.txt   # API-only deps
│   ├── requirements-audio.txt  # Full audio pipeline deps
│   ├── .env               # MongoDB, LLM, AuDD.io, Demucs/Voice URLs
│   ├── install.bat        # Windows venv + dep installer
│   ├── tests/backend_test.py   # Live-server pytest suite (REACT_APP_BACKEND_URL)
│   └── uploads/           # Runtime — audio files, stems, MIDI, morphs (gitignored)
└── frontend/
    ├── src/
    │   ├── App.jsx         # SPA shell — 3-pane gateway state machine
    │   ├── main.jsx
    │   ├── components/gateways/  # Gateway01Legal, 02Deconstruction, 03Morph, 04LyricRebuild, 05VoiceClone
    │   ├── components/ErrorBoundary.jsx  # per-gateway boundary
    │   ├── lib/apiClient.js      # fetch + retry/backoff + toasts
    │   ├── components/ui/  # shadcn/ui primitives (unused by current UI)
    │   ├── hooks/use-toast.js
    │   └── lib/utils.js
    ├── package.json
    ├── vite.config.js      # /api proxy → VITE_BACKEND_URL
    ├── tailwind.config.js
    └── .env                # VITE_DEV_PORT, VITE_BACKEND_URL
```

## Data Model (MongoDB)

| Collection | Key Fields | Purpose |
|------------|-----------|---------|
| `projects` | id, name, original_file, lyrics, style, legal_scan, transform_status, stems_directory, midi_files, musicxml_files, morph_status, morph_params, morph_result, morph_directory, voice_sample_file, voice_clone_status, voice_clone_file | One document per uploaded track — every gateway checkpoint persisted (True Isolation) |
| `user_styles` | id, name, description, sample_lyrics, text_samples, audio_sample_transcripts | Named lyric style presets |
| `profiles` | id (`"default"`), corpus[], fingerprint, fingerprint_bias, llm_theme_summary | Global learned writing voice |
| `status_checks` | id, client_name, timestamp | Health check log |

## API Endpoints (36 routes)

### Core
- `GET /api/` — health check
- `POST /api/status` / `GET /api/status` — status check log

### Projects
- `POST /api/projects` — create
- `GET /api/projects` — list
- `GET /api/projects/{id}` — get
- `POST /api/projects/{id}/upload` — upload audio (MP3/WAV/FLAC/OGG)
- `POST /api/projects/{id}/legal-scan` — AuDD.io fingerprint scan *(Gateway 01)*
- `POST /api/projects/{id}/transform` — stem separation + MIDI *(Gateway 02)*
- `GET /api/projects/{id}/transform-status` — poll transform progress (carries detected bpm/key)
- `GET /api/projects/{id}/transcription` — vocal transcription text
- `GET /api/projects/{id}/stem-audio/{stem}` — stream a stem for in-app playback
- `GET /api/projects/{id}/download-stems` — download DAW package as ZIP
- `GET /api/projects/{id}/download-beat` — download the Cleared Beat (morphed instrumental if GW03 complete, else deconstructed instrumental)
- `POST /api/projects/{id}/morph` — trigger morph `{similarity_target?, key_target?, bpm_target?}` *(Gateway 03)*
- `GET /api/projects/{id}/morph-status` — poll morph progress/result
- `GET /api/projects/{id}/morph-preview` — stream the morphed instrumental
- `POST /api/projects/{id}/generate-lyrics` — LLM lyric generation *(Gateway 04)*
- `GET /api/projects/{id}/export` — export project JSON
- `GET /api/projects/{id}/download-lyrics` — download lyrics as text
- `POST /api/projects/{id}/voice-sample` — upload voice reference *(Gateway 05)*
- `POST /api/projects/{id}/voice-clone` — trigger voice clone *(Gateway 05)*
- `GET /api/projects/{id}/voice-clone-status` — poll clone status
- `GET /api/projects/{id}/download-vocal` — download cloned vocal

### User Styles
- `POST /api/user-styles` — create
- `GET /api/user-styles` — list
- `DELETE /api/user-styles/{id}` — delete
- `POST /api/user-styles/{id}/text-sample` — add text sample
- `POST /api/user-styles/{id}/audio-sample` — add audio sample (Whisper transcribed)

### Profile (Learned Style)
- `GET /api/profile` — get profile + corpus + fingerprint
- `POST /api/profile/corpus` — add text to corpus
- `POST /api/profile/corpus/audio` — add audio (transcribed first)
- `DELETE /api/profile/corpus/{item_id}` — remove corpus item
- `PUT /api/profile/bias` — set fingerprint bias slider (0.0=heuristic, 1.0=LLM)
- `POST /api/profile/fingerprint/compute` — recompute fingerprint from corpus

### Utilities
- `POST /api/transcribe` — transcribe audio via Whisper
- `GET /api/files/{filename}` — serve uploaded files (path-traversal safe)
- `GET /api/ollama/config` — get LLM connection info
- `POST /api/ollama/test` — test LLM connectivity + list models

## External Services

| Service | Port / URL | Purpose | Required |
|---------|-----------|---------|----------|
| MongoDB | localhost:27017 | Database | Yes |
| LM Studio / Ollama | localhost:1234 | Lyric LLM generation | Yes |
| AuDD.io | api.audd.io | Music recognition (legal scan) | Gateway 01 |
| Demucs server | `DEMUCS_URL`:8600 | GPU stem separation | No (falls back to CPU) |
| Whisper (via Demucs server) | `DEMUCS_URL`/transcribe | Audio transcription | No (runs local on fallback) |
| Voice Clone server | `VOICE_CLONE_URL`:8500 | F5-TTS voice cloning | Gateway 05 only |

## Demucs Server (`demucs_server.py`)

Standalone FastAPI server meant to run on the Windows RTX 3080 machine. Exposes:

- `GET /health` — returns device (cuda/cpu) + demucs install status
- `POST /separate` — takes audio file, returns ZIP of 4 stems (drums, bass, vocals, other) as WAV
- `POST /transcribe` — takes audio file, returns Whisper transcription text

Uses `demucs.audio.AudioFile` and `demucs.audio.save_audio` for I/O (no torchaudio dependency). Whisper via `faster-whisper`.

## Style Engine (`style_engine.py`)

Fingerprints the user's lyric writing voice from a corpus. Produces a style prompt for the LLM.

**Hybrid approach:**
- **Heuristic** (no LLM): rhyme density, syllable cadence, lexical diversity, structural patterns
- **LLM theme pass** (optional): Ollama call to summarize thematic/tonal qualities
- **Bias slider** (0.0–1.0): user-controlled blend weight

**Lyric generation modes:**

| Mode | Behavior |
|------|----------|
| Preset | Built-in genre templates (trap, boom bap, drill, conscious, etc.) |
| Defined | User-created named style with explicit samples |
| Learned | Fingerprint-based from profile corpus |
| Blend | Defined + Learned at user-set weight |
| Custom | Free-form prompt |

## Frontend

React 19 SPA (Vite 8). `App.jsx` is the shell: 3-pane layout (INPUT / FUSION MATRIX /
SOVEREIGN OUTPUT), string state machine, cosmetic telemetry + spectrogram. Each gateway
lives in `components/gateways/` wrapped in a `GatewayErrorBoundary`; all HTTP goes
through `lib/apiClient.js` (fetch, 3 retries, 1s/2s/4s backoff on 5xx/429/network,
sonner toasts). Dev proxy forwards `/api` to `VITE_BACKEND_URL`.

State machine drives the 5-gateway flow:
```
idle → ingesting → gateway_01 → deconstructing → gateway_02
     → morphing → gateway_03 → rebuilding_lyrics → gateway_04
     → planting → gateway_05
```

Processing phases are short fixed-timer telemetry animations; the real work is
triggered and polled inside each gateway component (GW02/GW03/GW05 poll every 3s).

Dark theme per STYLE.md, neon green accent (`--neon: #00ff88`), JetBrains Mono.

## Gateway Status

| Gateway | Name | Backend | Frontend |
|---------|------|---------|----------|
| 01 | Legal Diagnostic | Live (AuDD.io) | Live |
| 02 | Deconstruction | **Live** (Demucs + Basic Pitch + music21) | **Live** |
| 03 | Morph Engine | **Live** (`morph_engine.py` — DSP morph + measured similarity) | **Live** (target slider, preview, re-morph) |
| 04 | Lyric Rebuild | **Live** (LLM + style engine + structure modes) | **Live** |
| 05 | Voice Clone | Live (TTS-server client); needs `VOICE_CLONE_URL` provisioned | **Live** (upload → clone → poll → download) |

## Morph Engine (`morph_engine.py`)

Gateway 03 — deterministic DSP per the Derivative-Origin rule (every output is a
calculable operation on GW02's extracted stems; no generation):

- **Plan**: similarity target S ∈ [0,79] → deviation D = 100−S → pitch +round(7·D/100)
  semitones (≤7), tempo rate 1+0.15·D/100 clamped [0.80,1.25]. Explicit `key_target`
  (signed circular semitone distance) or `bpm_target` override their axis.
- **Apply**: per-channel `librosa.effects.time_stretch` then `pitch_shift` on
  drums/bass/other (vocals never morphed; drums time-stretch only). MIDI: note
  times ×(1/rate), non-drum pitches +n. Remix → `instrumental.wav` + lameenc MP3
  in `uploads/{id}_morph/`.
- **Measure**: tempo axis from full mixes (beat tracker), chroma+key axes from the
  harmonic submix (bass+other) — drum transients dominate full-mix chroma and would
  mask real key movement (measured cos 0.99 despite bass/other moving G→C).
  `similarity_achieved = 100·(0.15·chroma + 0.50·key + 0.35·tempo)`, monotonic in the
  target within a source (verified live: same track target 20→18% and 50→40%;
  a different real track target 35→43% and 60→63%).
- Status/claim/recovery semantics identical to the transform pipeline (atomic DB
  claim, `_MORPH_PROGRESS` dict, stale-processing recovery, startup orphan reset).

## Known Issues / Next Work

- Key detection is major-only chroma argmax (no minor-mode profiling) — shared by
  legal scan and morph; consistent on both sides of the similarity measurement
- Voice clone has never completed a real run — needs a provisioned TTS server
- No authentication — single global "default" profile
- server.py is ~2100 lines on one router — split into modules planned
