# backend/morph_engine.py
"""Gateway 03 — Morph Engine.

Deterministic DSP morphing of the instrumental stems produced by Gateway 02.
Every transformation is a calculable operation on extracted source atoms
(Derivative Origin): time-stretch and pitch-shift on stem audio, tempo and
pitch scaling on stem MIDI. No generation, no ML, no randomness.

Pure functions only — no FastAPI/motor imports. server.py wires this module
into endpoints and background tasks (same pattern as style_engine.py).
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional heavy imports (audio/ML). If missing, set flags and gracefully degrade
# (same style as server.py).
HAS_NUMPY = HAS_LIBROSA = HAS_SOUNDFILE = HAS_PRETTYMIDI = False
try:
    import numpy as np
    HAS_NUMPY = True
except Exception as e:
    logger.warning(f"numpy not available: {e}")

try:
    import librosa
    HAS_LIBROSA = True
except Exception as e:
    logger.warning(f"librosa not available: {e}")

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except Exception as e:
    logger.warning(f"soundfile not available: {e}")

try:
    import pretty_midi
    HAS_PRETTYMIDI = True
except Exception as e:
    logger.warning(f"pretty_midi not available: {e}")

KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Instrumental stems that get morphed. Vocals are NEVER morphed — the doctrine's
# exit product is a cleared instrumental, pitch-shifted source vocals are
# audible-weird, and Gateway 05 replaces them anyway.
MORPH_STEMS = ["drums", "bass", "other"]

# Phase-vocoder artifact ceiling: stretching beyond this range sounds broken.
TEMPO_RATE_MIN = 0.80
TEMPO_RATE_MAX = 1.25
# Tritone = max perceptual pitch distance.
MAX_PITCH_SEMITONES = 7

# Similarity weights — tuned once against smoke measurements: on real material
# chroma cosine has a high floor (0.989 measured at +5 semitones on a full
# track — dense harmonic content barely moves under rotation), so it carries
# little discriminative weight; key distance is the honest discriminator.
W_CHROMA = 0.15
W_KEY = 0.50
W_TEMPO = 0.35


class MorphPlanError(ValueError):
    """Raised when the requested morph parameters cannot be satisfied."""


def analyze_audio(y, sr) -> dict:
    """Detect BPM, key index and mean chroma vector — same detectors as legal_scan."""
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # librosa >=0.10 returns tempo as a 1-element array, not a scalar
    bpm = round(float(np.squeeze(tempo)), 1)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_idx = int(np.argmax(chroma_mean))
    return {
        "bpm": bpm,
        "key_idx": key_idx,
        "key_name": KEY_NAMES[key_idx],
        "chroma_mean": chroma_mean,
    }


def plan_morph(similarity_target: int, key_idx_orig: int, bpm_orig: float,
               key_target=None, bpm_target=None) -> dict:
    """Map a similarity target (0-79, % similarity to source) to concrete DSP params.

    Deviation D = 100 - target is split deterministically across two axes:
      pitch: P = round(7 * D/100) semitones, clamped |P| <= 7, applied upward
      tempo: rate = 1 + 0.15 * D/100, clamped [0.80, 1.25]
    Explicit key_target (chroma name) or bpm_target override their axis.
    """
    if not 0 <= similarity_target <= 79:
        raise MorphPlanError(f"similarity_target must be 0-79, got {similarity_target}")
    deviation = 100 - similarity_target

    pitch = min(round(MAX_PITCH_SEMITONES * deviation / 100), MAX_PITCH_SEMITONES)
    rate = 1.0 + 0.15 * deviation / 100
    rate = min(max(rate, TEMPO_RATE_MIN), TEMPO_RATE_MAX)

    if key_target is not None:
        names_upper = {k.upper(): i for i, k in enumerate(KEY_NAMES)}
        kt = str(key_target).strip().upper()
        if kt not in names_upper:
            raise MorphPlanError(f"Invalid key_target '{key_target}' — use a chroma name like 'F#'")
        target_idx = names_upper[kt]
        # signed circular distance, mapped to -6..+5
        pitch = (target_idx - key_idx_orig + 6) % 12 - 6

    if bpm_target is not None:
        if bpm_orig <= 0:
            raise MorphPlanError("Cannot honor bpm_target: original BPM could not be detected")
        wanted = float(bpm_target) / bpm_orig
        if not TEMPO_RATE_MIN <= wanted <= TEMPO_RATE_MAX:
            raise MorphPlanError(
                f"bpm_target {bpm_target} needs tempo rate {wanted:.2f}, "
                f"outside safe range [{TEMPO_RATE_MIN}, {TEMPO_RATE_MAX}]")
        rate = wanted

    return {
        "tempo_rate": round(rate, 4),
        "pitch_semitones": int(pitch),
        # Pitch-shifting a drum kit produces hollow artifacts and pitch is
        # meaningless there — drums get time_stretch only.
        "drum_pitch_semitones": 0,
    }


def morph_stem(wav_in: Path, wav_out: Path, tempo_rate: float, pitch_semitones: int) -> None:
    """Time-stretch then pitch-shift one stem, per channel, PCM_16 out.

    Order matters: time_stretch first, then pitch_shift (pitch_shift internally
    resamples+stretches; stretching once first avoids double phase-vocoder
    smearing).
    """
    data, sr = sf.read(str(wav_in), dtype="float32", always_2d=True)
    channels = []
    for ch in range(data.shape[1]):
        y = data[:, ch]
        if abs(tempo_rate - 1.0) > 1e-6:
            y = librosa.effects.time_stretch(y=y, rate=tempo_rate)
        if pitch_semitones != 0:
            y = librosa.effects.pitch_shift(y=y, sr=sr, n_steps=pitch_semitones)
        channels.append(y)
    frames = max(c.shape[0] for c in channels)
    out = np.zeros((frames, len(channels)), dtype=np.float32)
    for i, c in enumerate(channels):
        out[:c.shape[0], i] = c
    sf.write(str(wav_out), out, sr, subtype="PCM_16")


def morph_midi(mid_in: Path, mid_out: Path, tempo_rate: float, pitch_semitones: int) -> bool:
    """Scale note times by 1/rate and transpose non-drum instruments. False on failure."""
    if not HAS_PRETTYMIDI:
        return False
    try:
        midi = pretty_midi.PrettyMIDI(str(mid_in))
        for instrument in midi.instruments:
            if instrument.is_drum:
                continue
            for note in instrument.notes:
                note.start /= tempo_rate
                note.end /= tempo_rate
                note.pitch = int(min(max(note.pitch + pitch_semitones, 0), 127))
        midi.write(str(mid_out))
        return True
    except Exception as e:
        logger.warning(f"MIDI morph failed for {mid_in.name}: {e}")
        return False


def remix_instrumental(morph_dir: Path, stem_names=MORPH_STEMS):
    """Sum the morphed stems into morph_dir/instrumental.wav (clone of _mix_instrumental)."""
    tracks, sr = [], None
    for name in stem_names:
        p = morph_dir / f"{name}.wav"
        if p.exists():
            data, rate = sf.read(str(p), dtype="float32", always_2d=True)
            tracks.append(data)
            sr = rate
    if not tracks:
        return None
    frames = max(t.shape[0] for t in tracks)
    mixed = np.zeros((frames, tracks[0].shape[1]), dtype=np.float32)
    for t in tracks:
        mixed[:t.shape[0]] += t
    out_path = morph_dir / "instrumental.wav"
    sf.write(str(out_path), mixed, sr, subtype="PCM_16")
    return out_path


def encode_mp3(wav_path: Path, mp3_path: Path, bitrate: int = 320) -> None:
    """Encode a wav to mp3 with lameenc (local copy of server.py's recipe —
    importing from server.py would be circular)."""
    import lameenc
    pcm, sr = sf.read(str(wav_path), dtype="int16", always_2d=True)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(sr)
    encoder.set_channels(pcm.shape[1])
    encoder.set_quality(2)
    encoder.silence()
    mp3 = encoder.encode(pcm.tobytes()) + encoder.flush()
    mp3_path.write_bytes(mp3)


def _fold_tempo_ratio(r: float) -> float:
    """Fold a bpm ratio by x2^k into [0.80, 1.25] to absorb beat-tracker octave errors."""
    while r < TEMPO_RATE_MIN:
        r *= 2
    while r > TEMPO_RATE_MAX:
        r /= 2
    return r


def measure_similarity(y_orig, sr_orig, morph_wav: Path) -> dict:
    """Honest similarity: re-analyze BOTH signals with the same detectors.

    Returns the three raw components plus achieved/deviation percentages.
    The achieved value will not equal the target exactly — the UI shows
    target vs. achieved and the user re-adjusts (doctrine: preview and
    re-adjust before committing).
    """
    orig = analyze_audio(y_orig, sr_orig)
    y_m, sr_m = librosa.load(str(morph_wav), sr=None, mono=True, duration=60)
    morphed = analyze_audio(y_m, sr_m)

    # Chroma cosine (harmonic content)
    a = np.asarray(orig["chroma_mean"], dtype=np.float64)
    b = np.asarray(morphed["chroma_mean"], dtype=np.float64)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    chroma_sim = float(np.dot(a, b) / denom) if denom > 0 else 0.0
    chroma_sim = min(max(chroma_sim, 0.0), 1.0)

    # Key distance (circular semitones, max meaningful distance 6)
    key_dist = min(abs(morphed["key_idx"] - orig["key_idx"]),
                   12 - abs(morphed["key_idx"] - orig["key_idx"]))
    key_sim = 1.0 - min(key_dist, 6) / 6.0

    # Tempo distance (folded ratio)
    if orig["bpm"] > 0 and morphed["bpm"] > 0:
        r = _fold_tempo_ratio(morphed["bpm"] / orig["bpm"])
        tempo_sim = min(max(1.0 - abs(r - 1.0) / 0.25, 0.0), 1.0)
    else:
        tempo_sim = 1.0  # undetectable tempo on either side: don't penalize

    similarity_achieved = round(100 * (W_CHROMA * chroma_sim + W_KEY * key_sim + W_TEMPO * tempo_sim))
    return {
        "similarity_achieved": int(similarity_achieved),
        "deviation_achieved": int(100 - similarity_achieved),
        "bpm_original": orig["bpm"],
        "bpm_morphed": morphed["bpm"],
        "key_original": orig["key_name"],
        "key_morphed": morphed["key_name"],
        "chroma_similarity": round(chroma_sim, 3),
        "key_similarity": round(key_sim, 3),
        "tempo_similarity": round(tempo_sim, 3),
    }


def _load_original_instrumental(stems_dir: Path):
    """Load the pre-morph instrumental for baseline analysis: instrumental.wav
    if present, else an in-memory sum of the original stems."""
    inst = stems_dir / "instrumental.wav"
    if inst.exists():
        return librosa.load(str(inst), sr=None, mono=True, duration=60)
    tracks, sr = [], None
    for name in MORPH_STEMS:
        p = stems_dir / f"{name}.wav"
        if p.exists():
            data, rate = sf.read(str(p), dtype="float32", always_2d=True)
            tracks.append(data.mean(axis=1))
            sr = rate
    if not tracks:
        return None, None
    frames = max(t.shape[0] for t in tracks)
    mixed = np.zeros(frames, dtype=np.float32)
    for t in tracks:
        mixed[:t.shape[0]] += t
    return mixed, sr


def run_morph_pipeline(stems_dir, morph_dir, params: dict, progress_cb=None) -> dict:
    """Orchestrate the full morph. Runs in a worker thread (sync DSP).

    Returns {'success': True, 'plan': {...}, 'result': {...}, 'files': [...]}
    or {'success': False, 'error': str} — same contract as
    extract_stems_and_convert_to_midi.
    """
    def prog(stage, pct, detail=""):
        if progress_cb:
            try:
                progress_cb(stage, pct, detail)
            except Exception:
                pass

    try:
        if not (HAS_NUMPY and HAS_LIBROSA and HAS_SOUNDFILE):
            return {"success": False,
                    "error": "Audio libraries unavailable (numpy/librosa/soundfile) — cannot morph"}

        stems_dir = Path(stems_dir)
        morph_dir = Path(morph_dir)

        source_stems = [n for n in MORPH_STEMS if (stems_dir / f"{n}.wav").exists()]
        if not source_stems:
            return {"success": False,
                    "error": "No instrumental stems found — run deconstruction (Gateway 02) first"}

        prog("analyze", 8, "Detecting key & tempo")
        y_orig, sr_orig = _load_original_instrumental(stems_dir)
        if y_orig is None:
            return {"success": False, "error": "No instrumental audio found for baseline analysis"}
        baseline = analyze_audio(y_orig, sr_orig)

        try:
            plan = plan_morph(
                similarity_target=int(params.get("similarity_target", 35)),
                key_idx_orig=baseline["key_idx"],
                bpm_orig=baseline["bpm"],
                key_target=params.get("key_target"),
                bpm_target=params.get("bpm_target"),
            )
        except MorphPlanError as e:
            return {"success": False, "error": str(e)}

        morph_dir.mkdir(parents=True, exist_ok=True)
        rate = plan["tempo_rate"]
        files = []

        # Morph stems — audio failures are fatal (audio is the deliverable)
        stage_pcts = {"drums": 20, "bass": 35, "other": 50}
        morphed_stems = []
        for name in source_stems:
            prog("morph_stems", stage_pcts.get(name, 50), f"Time-stretching / pitch-shifting: {name}")
            pitch = plan["drum_pitch_semitones"] if name == "drums" else plan["pitch_semitones"]
            morph_stem(stems_dir / f"{name}.wav", morph_dir / f"{name}.wav", rate, pitch)
            morphed_stems.append(name)
            files.append(f"{name}.wav")

        prog("remix", 60, "Remixing instrumental")
        inst_wav = remix_instrumental(morph_dir, morphed_stems)
        if inst_wav is None:
            return {"success": False, "error": "Remix produced no audio"}
        files.append("instrumental.wav")

        # MIDI morph — tolerated failures (notation belongs to the GW02 package)
        prog("morph_midi", 70, "Scaling MIDI tempo & pitch")
        for name in morphed_stems:
            mid_in = stems_dir / f"{name}.mid"
            if mid_in.exists():
                pitch = plan["drum_pitch_semitones"] if name == "drums" else plan["pitch_semitones"]
                if morph_midi(mid_in, morph_dir / f"{name}.mid", rate, pitch):
                    files.append(f"{name}.mid")

        prog("measure", 85, "Measuring achieved similarity")
        result = measure_similarity(y_orig, sr_orig, inst_wav)
        result.update({
            "pitch_semitones": plan["pitch_semitones"],
            "tempo_rate": rate,
            "tempo_shift_pct": round((rate - 1.0) * 100, 1),
        })

        prog("encode", 92, "Encoding MP3")
        try:
            encode_mp3(inst_wav, morph_dir / "instrumental.mp3")
            files.append("instrumental.mp3")
        except Exception as e:
            logger.warning(f"MP3 encode failed (wav still available): {e}")

        prog("done", 100, "Morph complete")
        return {"success": True, "plan": plan, "result": result, "files": files}
    except Exception as e:
        logger.error(f"Morph pipeline failed: {e}")
        return {"success": False, "error": str(e)}
