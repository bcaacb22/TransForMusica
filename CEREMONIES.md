# TRANSFORMUSIC V2 — Ceremonies & Pipeline Architecture

## The Doctrine

> "Ease is Earned."

When the software is designed with absolute structural certainty, the user isn't trapped in a rigid, anxious loop. The infrastructure handles heavy complexity upstream so that at every single gateway — whether checking the legal cutoff line, pulling raw MIDI trackouts, or committing to an AI beat reconstruction — the system remains quiet, stable, and completely neutral. The user owns the stream. The app is the flawless executor of their choice.

---

## Core Purpose

Transform any song — copyrighted, published, or otherwise — into an original, publishable version with as little adjustment as the user chooses. The pipeline is the path. The exits are the product.

---

## The Five Sovereign Exit Points

| Gateway | Stage | Upstream System Action | Earned Product |
|---------|-------|----------------------|----------------|
| **01** | INGESTION & SCAN | Runs audio + lyric telemetry against public records. Sets the hard similarity cutoff line. | **Legal Diagnostic Report** — User knows exactly where their raw audio sits legally before spending a second changing it. |
| **02** | DECONSTRUCTION | Splits track into frequency-based Audio Stems, MIDI sequences, and MusicXML notation. | **The DAW Package** — Asset bundle zipped and downloadable. User leaves the app and rebuilds manually in external DAW. |
| **03** | MORPH ENGINE | Takes user input on similarity scale. Reshapes beat skeleton into a new original instrumental. | **The Cleared Beat** — A completely original, cleared instrumental stem. Ready for standalone export or external licensing. |
| **04** | LYRIC REBUILD | Executes the 3-choice engine (Placeholder Cadence vs. Fresh Deconstruction). | **The Cleared Lyric Canvas** — Fully structured, high-density phonetic text built around savable style presets. |
| **05** | THE RE-PLANT | Clones user's voice. Prints vocal stem cleanly back into the master mix. | **The Final Master** — Completely original, self-contained, cleared track ready for public release. |

---

## Pipeline Detail

### Gateway 01 — Ingestion & Scan

**Input:** Any audio file (song with vocals OR instrumental only)

**System Actions:**
- Ingest audio
- Run against public records — audio fingerprint + lyric matching
- Apply consistent similarity cutoff threshold (same threshold across ALL uploads)
- Surface results: similarity score, matched source, violation risk

**User Decision:** Proceed or exit with Legal Diagnostic Report

**Exit Product:** Legal Diagnostic Report

---

### Gateway 02 — Deconstruction

**Input:** Cleared or accepted audio (user chose to proceed)

**System Actions:**
- Separate into actual audio stems (bass, melody, percussion, harmony, kick)
- Convert to MIDI stems via Basic Pitch
- Generate MusicXML notation
- Bundle into downloadable DAW package

**User Controls:**
- Download individual stems or full bundle
- View similarity position on scale
- Adjust similarity target for next phase
- Option to refresh similarity assessment at any time

**Exit Product:** The DAW Package (zip of all stems, MIDI, MusicXML)

---

### Gateway 03 — Morph Engine

**Input:** Deconstruction complete, user wants to modify the music

**User Input:**
- Similarity scale target (how close to / far from original)
- Specific adjustment parameters (rhythm, key, tempo, feel)
- Optional: natural language creative brief

**System Actions:**
- AI reconstructs beat skeleton based on user input + similarity target
- Preserves structural DNA proportional to similarity target
- User can preview and re-adjust before committing

**Exit Product:** The Cleared Beat — original instrumental, exportable

---

### Gateway 04 — Lyric Rebuild

**Three-Choice Engine (expanded from V1):**

| Mode | Description |
|------|-------------|
| **Preset** | Genre-based style selection |
| **Defined** | Hand-crafted style profile (saveable, reusable) |
| **Learned** | AI-trained on user's own voice/corpus |

**User Input:**
- Style selection (from saved profiles or new)
- Topic / creative direction
- Structural preference: Placeholder Cadence (match original lyric structure) OR Fresh Deconstruction (new structure from final beat)

**System Actions:**
- If Placeholder Cadence: preserve original bar/rhyme structure, rewrite content
- If Fresh Deconstruction: build new phonetic architecture from beat output
- Generate lyrics with thinking mode (quality over speed)

**Exit Product:** The Cleared Lyric Canvas — structured text file, downloadable

---

### Gateway 05 — The Re-Plant

**Input:** Final beat + final lyrics confirmed

**System Actions:**
- Clone user's voice from provided vocal sample
- Synthesize vocal performance from lyrics
- Plant vocal stem back into master mix
- Replace model voice or original artist voice entirely

**Exit Product:** The Final Master — original track, cleared, ready for public release

---

## Architectural Rule: Derivative Origin

**Every modification must trace back to the original song. No exceptions.**

All transformations are mathematical operations performed on extracted source material:
- Pitch shift on an actual stem
- Tempo/timing adjustment on an actual MIDI sequence
- Instrument replacement on an actual MusicXML voice
- Melody variation derived from the original melodic contour
- Harmonic restructuring from the original chord data

The AI does not generate from nothing. It operates on the atoms of the source track. Every parameter has a calculable relationship to the input. Nothing is by chance. There are no unknowns. Everything is calculated and has an origin.

**The chain of provenance is never broken.**

This applies at every gateway — the cleared beat at Gateway 03, the lyric structure at Gateway 04, the vocal stem at Gateway 05. Each output must be traceable to a specific source element from the deconstruction at Gateway 02.

---

## Architectural Rule: True Isolation

Each gateway is an independent, asynchronous state. Gateways do not depend on each other completing. The database preserves exact structural checkpoints at each gateway in the `projects` collection without throwing errors or hanging the async event loop.

**Rules:**
- A user can download at Gateway 02 and close the browser. Project state is preserved.
- A user can return days later and resume from any saved checkpoint.
- No gateway can block or fail another gateway.
- Similarity factor can be refreshed and reassessed at any gateway, at any time.
- The system never demands a decision. It waits.

---

## Similarity System

**The Line:**
- One consistent cutoff threshold across all uploads
- Applied at Gateway 01 (initial scan)
- Refreshable at any subsequent gateway
- Displayed as a visual scale — current position vs. target position vs. violation line

**User Control:**
- Rigid framework (the line doesn't move)
- Moldable within it (user slides their target anywhere below the line)
- System adjusts output to match the target, not the other way around

---

## The Doctrine in Motion

The app doesn't demand the user finish the journey. It sits back, mirrors their pace, and serves the files when requested. No anxiety. No rush. No demand. Calm and stable through every decision. The user reflects that same energy back.

**Effortless Metaphor in practice.**
