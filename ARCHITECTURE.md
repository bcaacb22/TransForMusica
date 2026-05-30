# Transformusic — Architecture

## Purpose

Transformusic is a 5-gateway beat deconstruction and lyric generation pipeline. Upload any audio (beat, instrumental, full track) and move it through:

1. **Legal Diagnostic** — AuDD.io fingerprint scan, similarity score, violation risk
2. **Deconstruction** — Demucs stem separation → MIDI (Basic Pitch) → MusicXML (music21)
3. **Morph Engine** — BPM/key reshaping UI *(backend not yet implemented)*
4. **Lyric Rebuild** — local LLM generation with style fingerprinting
5. **Voice Clone** — F5-TTS voice cloning onto generated lyrics

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11), async via uvicorn |
| Database | MongoDB (motor async driver) |
| LLM | LM Studio / Ollama (OpenAI-compatible API, default port 1234) |
| Stem Separation | Demucs `htdemucs` — remote GPU server or local CPU fallback |
| Audio-to-MIDI | Basic Pitch (Spotify) |
| Notation | music21, pretty_midi, mido |
| Transcription | faster-whisper (tiny, GPU or CPU) — runs on remote Demucs server |
| Music Recognition | AuDD.io API (legal scan) |
| Voice Clone | F5-TTS or XTTS — remote server or local |
| Style Engine | Custom heuristic + LLM hybrid (`style_engine.py`) |
| Frontend | React 19, Vite, Tailwind CSS, shadcn/ui (48 components), Lucide icons |
| Transport | REST (fetch), multipart file uploads |

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
│   ├── server.py          # All FastAPI endpoints, models, pipeline logic
│   ├── style_engine.py    # Lyric fingerprinting (heuristic + LLM hybrid)
│   ├── run_app.py         # Launcher — stubs basic_pitch if not installed
│   ├── demucs_server.py   # Standalone Demucs + Whisper server (run on Windows GPU)
│   ├── requirements-core.txt   # API-only deps
│   ├── requirements-audio.txt  # Full audio pipeline deps
│   ├── .env               # MongoDB, LLM, AuDD.io, Demucs/Voice URLs
│   ├── install.bat        # Windows venv + dep installer
│   └── uploads/           # Runtime — audio files, stems, MIDI (gitignored)
└── frontend/
    ├── src/
    │   ├── App.jsx         # Single-file SPA (~2,000 lines) — all 5 gateways
    │   ├── main.jsx
    │   ├── components/ui/  # shadcn/ui primitives (48 components)
    │   ├── hooks/use-toast.js
    │   └── lib/utils.js
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── .env                # REACT_APP_BACKEND_URL
```

## Data Model (MongoDB)

| Collection | Key Fields | Purpose |
|------------|-----------|---------|
| `projects` | id, name, original_file, transformed_file, lyrics, style, legal_scan_result, voice_clone_status | One document per uploaded track |
| `user_styles` | id, name, description, sample_lyrics, text_samples, audio_sample_transcripts | Named lyric style presets |
| `profiles` | id (`"default"`), corpus[], fingerprint, fingerprint_bias, llm_theme_summary | Global learned writing voice |
| `status_checks` | id, client_name, timestamp | Health check log |

## API Endpoints (34 total)

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
- `GET /api/projects/{id}/transform-status` — poll transform progress
- `GET /api/projects/{id}/download-stems` — download stems + MIDI as ZIP
- `GET /api/projects/{id}/download-beat` — download instrumental
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

## Frontend (`App.jsx`)

Single-file React SPA (~2,000 lines). Three views: **Home**, **Studio**, **Settings**.

State machine drives the 5-gateway flow:
```
idle → ingesting → gateway_01 → deconstructing → gateway_02
     → morphing → gateway_03 → rebuilding_lyrics → gateway_04
     → planting → gateway_05
```

Each gateway has animated telemetry feed (status lines), spectrogram visualization, and a "PROCEED" button to advance.

No external state library — all useState/useRef local state.  
Dark gradient theme (slate-900 → purple-900), neon green accent (`--neon: #00ff88`).

## Gateway Status

| Gateway | Name | Backend | Frontend |
|---------|------|---------|----------|
| 01 | Legal Diagnostic | Live (AuDD.io) | Live |
| 02 | Deconstruction | **Live** (Demucs + Basic Pitch + music21) | **Live** |
| 03 | Morph Engine | Not implemented | UI only (mock) |
| 04 | Lyric Rebuild | **Live** (LLM + style engine) | **Live** |
| 05 | Voice Clone | Partial (endpoints + F5-TTS code present) | Partial |

## Known Issues / Next Work

- Gateway 03 (beat morphing) has no backend — pitch/tempo/key reshape not implemented
- Voice clone (Gateway 05) has server code but is untested end-to-end
- MIDI conversion in `extract_stems_and_convert_to_midi()` runs synchronously in async context — should move to `asyncio.to_thread`
- No authentication — single global "default" profile
