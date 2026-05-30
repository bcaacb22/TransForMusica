"""
Applio TTS Server — run this from C:\\applio using Applio's own venv.

  env\\Scripts\\python applio_server.py

Exposes POST /tts  →  returns WAV audio
"""

import os
import sys
import tempfile
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse

# Must be run from C:\applio so core.py is importable
sys.path.insert(0, str(Path(__file__).parent))

from core import run_tts_script  # noqa: E402

app = FastAPI()

MODEL_NAME = os.environ.get("APPLIO_MODEL", "mute_spin-v2")
TTS_VOICE   = os.environ.get("APPLIO_VOICE", "en-US-AndrewMultilingualNeural")

APPLIO_DIR = Path(__file__).parent
MODEL_PTH   = str(APPLIO_DIR / "logs" / MODEL_NAME / f"{MODEL_NAME}.pth")
INDEX_PATH  = ""

# Find index file if present
index_candidates = list((APPLIO_DIR / "logs" / MODEL_NAME).glob("*.index")) if (APPLIO_DIR / "logs" / MODEL_NAME).exists() else []
if index_candidates:
    INDEX_PATH = str(index_candidates[0])


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "voice": TTS_VOICE}


@app.post("/tts")
async def tts(text: str = Form(...)):
    tts_out = tempfile.mktemp(suffix="_tts.wav")
    rvc_out  = tempfile.mktemp(suffix="_rvc.wav")

    result = run_tts_script(
        tts_text=text,
        tts_voice=TTS_VOICE,
        tts_rate=0,
        pitch=0,
        filter_radius=3,
        index_rate=0.75,
        volume_envelope=1,
        protect=0.5,
        hop_length=128,
        f0_method="rmvpe",
        output_tts_path=tts_out,
        output_rvc_path=rvc_out,
        pth_path=MODEL_PTH,
        index_path=INDEX_PATH,
        split_audio=False,
        autotune=False,
        clean_audio=True,
        clean_strength=0.7,
        export_format="WAV",
        upscale_audio=False,
        f0_autotune_strength=1.0,
        formant_shift=False,
        formant_qfrency=1.0,
        formant_timbre=1.0,
        post_process=False,
        reverb=False,
        pitch_shift=False,
        limiter=False,
        gain=False,
        distortion=False,
        chorus=False,
        bitcrush=False,
        clipping=False,
        compressor=False,
        delay=False,
        reverb_room_size=0.5,
        reverb_damping=0.5,
        reverb_wet_gain=0.33,
        reverb_dry_gain=0.4,
        reverb_width=1.0,
        reverb_freeze_mode=0.0,
        pitch_shift_semitones=0,
        limiter_threshold=-6.0,
        limiter_release_time=0.01,
        gain_db=0.0,
        distortion_gain=25,
        chorus_rate=1.5,
        chorus_depth=0.1,
        chorus_center_delay=0.0,
        chorus_feedback=0.25,
        chorus_mix=0.5,
        bitcrush_bit_depth=8,
        clipping_threshold=-6.0,
        compressor_threshold=0.0,
        compressor_ratio=4,
        compressor_attack=1.0,
        compressor_release=100.0,
        delay_seconds=0.5,
        delay_feedback=0.5,
        delay_mix=0.5,
    )

    output_file = rvc_out if Path(rvc_out).exists() else tts_out
    return FileResponse(output_file, media_type="audio/wav", filename="vocal.wav")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8500))
    uvicorn.run(app, host="0.0.0.0", port=port)
