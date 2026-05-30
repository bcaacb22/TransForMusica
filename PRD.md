# Transformusic — Product Requirements

## Problem Statement

Musicians need a tool that takes any uploaded instrumental and transforms it into a copyrightable original composition. The pipeline deconstructs audio into stems, converts to MIDI/MusicXML for DAW import, generates original lyrics in the user's learned style, and clones their voice onto the result.

## User Personas

- **Independent rapper/producer** — uploads beats, needs original lyrics in their voice/style, wants DAW-ready MIDI stems
- **Songwriter** — trains the system on their writing corpus, generates lyrics that match their voice
- **Beat maker** — uploads instrumentals, gets stem separation + MIDI for remixing

## Core Requirements

1. Upload audio (MP3/WAV/FLAC/OGG) and create a project
2. Legal scan — fingerprint against public databases, assess copyright risk
3. Deconstruct — separate stems (drums, bass, vocals, other) + convert to MIDI/MusicXML
4. Morph — reshape BPM/key/tempo to create transformative derivative
5. Generate lyrics — LLM-powered, style-aware (presets, user-defined, learned fingerprint)
6. Voice clone — apply user's voice to generated lyrics

## What's Implemented

- [x] Project CRUD (create, list, get, delete)
- [x] Audio upload (MP3/WAV/FLAC/OGG, multipart)
- [x] Gateway 01: Legal Diagnostic (AuDD.io fingerprint scan)
- [x] Gateway 02: Deconstruction (Demucs stems + Basic Pitch MIDI + music21 MusicXML)
- [x] Gateway 04: Lyric Rebuild (LLM generation with 5 style modes)
- [x] Style Engine (heuristic fingerprint + LLM theme pass + bias slider)
- [x] User Styles (named presets with text/audio samples)
- [x] Profile/Corpus (learned writing voice from uploaded samples)
- [x] Transcription (faster-whisper via Demucs server)
- [x] LLM settings UI (provider selector, test connection, model picker)
- [x] Download stems as ZIP, download lyrics as text, export project JSON
- [ ] Gateway 03: Morph Engine (UI exists, no backend)
- [ ] Gateway 05: Voice Clone (endpoints exist, F5-TTS integration untested)

## Prioritized Backlog

### P0 — Working
- Upload + legal scan + deconstruction + lyric generation pipeline end-to-end

### P1 — Next
- Gateway 03 backend (BPM/key/tempo morphing with pitch-shift algorithms)
- Gateway 05 end-to-end testing (F5-TTS voice clone)
- Refactor server.py into routers/services modules (currently 1700+ lines)
- Move synchronous MIDI conversion to asyncio.to_thread

### P2 — Backlog
- User authentication (JWT, per-user profiles)
- Batch processing (multiple tracks)
- DAW plugin export (VST/AU metadata)
- Persist LLM settings server-side per user
- Upload validation by magic bytes

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI, Python 3.11, uvicorn |
| Database | MongoDB (motor async) |
| LLM | LM Studio / Ollama (OpenAI-compatible, port 1234) |
| Stem Separation | Demucs (htdemucs, remote GPU or local CPU) |
| Audio-to-MIDI | Basic Pitch (Spotify) |
| Notation | music21, pretty_midi, mido |
| Transcription | faster-whisper |
| Music Recognition | AuDD.io API |
| Voice Clone | F5-TTS / XTTS |
| Frontend | React 19, Vite, Tailwind, shadcn/ui |

## Next Tasks

1. Implement Gateway 03 morph backend (pitch-shift, tempo-stretch, key detection)
2. End-to-end test Gateway 05 voice clone with F5-TTS server
3. Split server.py into route modules
4. Add error recovery for failed transforms (retry mechanism)
