#!/usr/bin/env python3
"""
Comprehensive in-process test for the Beat Maker backend.

This script runs the FastAPI app inside a TestClient (no external server required)
and exercises multiple endpoints end-to-end using the in-memory DB fallback.

Checks performed:
- Status endpoints: POST /api/status, GET /api/status
- User styles: create, list, add text sample, delete
- Profile corpus: add text, fetch profile
- Fingerprint compute: POST /api/profile/fingerprint/compute
- Project lifecycle: create project, upload audio file, attempt transform (expected controlled failure if advanced deps are stubbed)
- Project export/download endpoints (basic checks)

Usage:
    cd <repo root>/app
    python backend/full_test.py

Notes:
- The script forces the server to use the in-memory DB fallback so tests run
  reliably without a running Mongo instance.
- The script inserts lightweight stubs for heavy optional modules (basic_pitch,
  music21, pretty_midi, mido) so importing the server succeeds in constrained
  environments. Endpoints that require those features will return predictable
  errors.
"""
from __future__ import annotations

import os
import sys
import json
import traceback
import tempfile
from pathlib import Path
from typing import Any, Dict

# Ensure project 'app' root is on sys.path so we can load backend.server by path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force in-memory DB fallback in server (makes tests hermetic)
# By clearing MONGO_URL the server will choose the in-memory DB implemented in server.py
os.environ["MONGO_URL"] = ""
os.environ.setdefault("DB_NAME", "beat_maker_test")
os.environ.setdefault("CORS_ORIGINS", "*")
# Keep Ollama defaults (not required for this smoke test)
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "llama3.2")
os.environ.setdefault("WHISPER_MODEL", "tiny.en")

# Install lightweight stubs for heavy optional modules if not importable.
# These stubs ensure importing backend.server does not fail.
def _make_stub_module(name: str, attrs: Dict[str, Any] | None = None):
    import types

    mod = types.ModuleType(name)
    mod.__dict__.setdefault("__stub__", True)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


# basic_pitch.inference.predict -> raises clear error if invoked
def _predict_stub(*args, **kwargs):
    raise RuntimeError(
        "basic_pitch.inference.predict is not available in this environment. "
        "Install `basic-pitch` to enable audio->MIDI endpoints."
    )


if "basic_pitch" not in sys.modules:
    try:
        __import__("basic_pitch")
    except Exception:
        bp_inference_stub = _make_stub_module("basic_pitch.inference", {"predict": _predict_stub})
        bp_stub = _make_stub_module("basic_pitch", {"inference": bp_inference_stub})
        sys.modules["basic_pitch"] = bp_stub
        sys.modules["basic_pitch.inference"] = bp_inference_stub

# stub music21/pretty_midi/mido if they are missing (advanced features)
for _m in ("music21", "pretty_midi", "mido"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except Exception:
            sys.modules[_m] = _make_stub_module(_m)


# Import the server module by path (robust)
import importlib.util

server_path = ROOT / "backend" / "server.py"
if not server_path.exists():
    print("ERROR: backend/server.py not found at", server_path)
    raise SystemExit(2)

spec = importlib.util.spec_from_file_location("backend.server", str(server_path))
backend_server = importlib.util.module_from_spec(spec)
# Register the module before executing so internal relative imports work
sys.modules["backend.server"] = backend_server
try:
    spec.loader.exec_module(backend_server)  # type: ignore
except Exception:
    print("ERROR importing backend.server:")
    traceback.print_exc()
    raise SystemExit(1)

# Obtain FastAPI app and TestClient
try:
    app = getattr(backend_server, "app")
except Exception:
    print("backend.server does not expose `app`")
    raise SystemExit(1)

from fastapi.testclient import TestClient

# Use raise_server_exceptions=False to capture HTTP-level responses rather than
# letting exceptions propagate out of the TestClient. That yields stable outputs.
client = TestClient(app, raise_server_exceptions=False)


def pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)


def check(method: str, path: str, **kwargs):
    """
    Perform request and print a concise report with response status and body (JSON/text).
    Returns response object.
    """
    print(f"\n--- {method} {path} ---")
    try:
        func = getattr(client, method.lower())
        resp = func(path, **kwargs)
    except Exception:
        print("Request raised exception:")
        traceback.print_exc()
        return None

    print(f"Status: {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            print("JSON:", pretty(resp.json()))
        except Exception:
            print("Body (raw):", resp.text[:2000])
    else:
        text = resp.text or ""
        print("Body (text):", text[:2000] + ("...(truncated)" if len(text) > 2000 else ""))
    return resp


def run_all_tests():
    results = {}

    # 1) Health / status endpoints
    r = check("GET", "/api/")
    results["health"] = r.status_code if r else None

    # POST status check
    payload = {"client_name": "full_test_runner"}
    r = check("POST", "/api/status", json=payload)
    results["status_create"] = r.json() if r and r.status_code < 400 else None

    # GET status checks
    r = check("GET", "/api/status")
    results["status_list"] = r.json() if r and r.status_code < 400 else None

    # 2) User-style management
    usr = {"name": "TestStyle", "description": "A test style", "sample_lyrics": "sample lyric text"}
    r = check("POST", "/api/user-styles", json=usr)
    style_obj = r.json() if r and r.status_code < 400 else None
    style_id = style_obj.get("id") if style_obj else None
    results["style_created"] = style_obj

    # List styles
    r = check("GET", "/api/user-styles")
    results["styles_list"] = r.json() if r and r.status_code < 400 else None

    # Add a text sample to the style
    if style_id:
        sample_payload = {"text": "This is a new sample added by full_test"}
        r = check("POST", f"/api/user-styles/{style_id}/text-sample", json=sample_payload)
        results["style_after_text_sample"] = r.json() if r and r.status_code < 400 else None

    # 3) Profile corpus - add text and check profile updates
    corpus_payload = {"text": "These are some lyrics for the profile corpus.", "title": "Test Corpus", "source": "manual"}
    r = check("POST", "/api/profile/corpus", json=corpus_payload)
    r = check("GET", "/api/profile")
    profile = r.json() if r and r.status_code < 400 else None
    results["profile_after_corpus"] = profile

    # 4) Compute fingerprint (heuristic) - should work without Ollama
    fp_body = {"use_llm_theme": False}
    r = check("POST", "/api/profile/fingerprint/compute", json=fp_body)
    results["fingerprint_compute"] = r.json() if r and r.status_code < 400 else {"status": r.status_code if r else None}

    # 5) Create a project, upload a small fake WAV file, then attempt transform
    proj_payload = {"name": "Full Test Project"}
    r = check("POST", "/api/projects", json=proj_payload)
    project = r.json() if r and r.status_code < 400 else None
    results["project_created"] = project

    project_id = project.get("id") if project else None

    # Prepare a tiny WAV-like payload (valid WAV header is complex; server currently only saves bytes)
    # We'll craft a minimal valid WAV header for 1-channel, 8-bit PCM, 1 sample (this may not be playable,
    # but the upload endpoint just writes file bytes and updates DB; advanced processing will fail gracefully).
    def make_min_wav_bytes():
        # 44-byte WAV header with zeroed data (not guaranteed playable)
        # But acceptable for a file upload test.
        header = bytearray(44)
        # RIFF header
        header[0:4] = b"RIFF"
        # file size placeholder
        header[4:8] = (36).to_bytes(4, "little")
        header[8:12] = b"WAVE"
        # fmt chunk
        header[12:16] = b"fmt "
        header[16:20] = (16).to_bytes(4, "little")  # fmt chunk size
        header[20:22] = (1).to_bytes(2, "little")  # PCM
        header[22:24] = (1).to_bytes(2, "little")  # channels
        header[24:28] = (44100).to_bytes(4, "little")  # sample rate
        header[28:32] = (44100).to_bytes(4, "little")  # byte rate (approx)
        header[32:34] = (1).to_bytes(2, "little")  # block align
        header[34:36] = (8).to_bytes(2, "little")  # bits per sample
        # data chunk
        header[36:40] = b"data"
        header[40:44] = (0).to_bytes(4, "little")
        return bytes(header)

    if project_id:
        wav_bytes = make_min_wav_bytes()
        files = {"file": ("test.wav", wav_bytes, "audio/wav")}
        r = check("POST", f"/api/projects/{project_id}/upload", files=files)
        results["upload_result"] = r.json() if r and r.status_code < 400 else {"status": r.status_code if r else None}

        # Try transform - expected to return 500 or 400 depending on missing dependencies / validation.
        r = check("POST", f"/api/projects/{project_id}/transform")
        # capture the status and body
        results["transform_result"] = {"status": r.status_code, "body": (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)}

    else:
        print("Project creation failed; skipping upload/transform tests")
        results["transform_result"] = None

    # 6) Export and download endpoints basic checks (if project exists)
    if project_id:
        r = check("GET", f"/api/projects/{project_id}/export")
        results["export"] = r.json() if r and r.status_code < 400 else None

        # Download lyrics (will 404 because no lyrics)
        r = check("GET", f"/api/projects/{project_id}/download-lyrics")
        results["download_lyrics"] = {"status": r.status_code}

    # 7) Cleanup: delete style if created
    if style_id:
        r = check("DELETE", f"/api/user-styles/{style_id}")
        results["style_deleted"] = r.status_code if r else None

    # Final summary
    print("\n\n=== TEST SUMMARY ===")
    print(pretty(results))
    return results


if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception:
        print("Unhandled exception during tests:")
        traceback.print_exc()
