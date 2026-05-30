#!/usr/bin/env python3
"""
Smoke-test backend with robust import of backend.server by file path.

This script attempts to import the FastAPI app from `backend/server.py` in a
robust way:

- It first ensures minimal environment variables are present so the module can
  import without KeyError.
- It installs lightweight stubs for optional heavy modules (e.g. `basic_pitch`)
  so the import won't fail when those packages are missing.
- It tries a normal package import (`import backend.server`). If that fails it
  will load the `server.py` file directly using importlib.util.spec_from_file_location
  after ensuring the backend directory is on sys.path so sibling imports
  (like `style_engine`) resolve.
- Uses FastAPI's TestClient to exercise a few endpoints and prints structured
  responses.

Run this from the repository's `app` directory:
    python backend/smoke_test.py
"""
from __future__ import annotations

import json
import os
import sys
import types
import traceback
from pathlib import Path
from typing import Any, Dict

# ---- 1) Environment configuration ------------------------------------------------
# Provide minimal env vars before importing backend.server (it reads them at import time)
# Force in-memory DB for smoke tests by ensuring the Mongo URL is empty.
# This causes the backend to fall back to the in-memory DB implementation.
os.environ["MONGO_URL"] = ""
os.environ.setdefault("DB_NAME", "beat_maker")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "llama3.2")
os.environ.setdefault("WHISPER_MODEL", "tiny.en")

# ---- 2) Lightweight stubs for heavy optional modules -----------------------------
# If packages like basic_pitch aren't installed, create small runtime stubs so
# importing server.py won't fail. Endpoints that call stubbed features will
# raise clear RuntimeError when executed.
def _make_stub_module(name: str, attrs: Dict[str, Any] | None = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.setdefault("__stub__", True)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


def _predict_stub(*args, **kwargs):
    raise RuntimeError(
        "basic_pitch.inference.predict is not available in this environment. "
        "Install `basic-pitch` and its dependencies to enable audio->MIDI endpoints."
    )


# Insert stubs if import would otherwise fail
if "basic_pitch" not in sys.modules:
    try:
        __import__("basic_pitch")
    except Exception:
        bp_inference = _make_stub_module("basic_pitch.inference", {"predict": _predict_stub})
        bp_mod = _make_stub_module("basic_pitch", {"inference": bp_inference})
        sys.modules["basic_pitch"] = bp_mod
        sys.modules["basic_pitch.inference"] = bp_inference

# Also ensure music21/pretty_midi/mido exist as stubs if missing (not exercised here)
for mod_name in ("music21", "pretty_midi", "mido"):
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except Exception:
            sys.modules[mod_name] = _make_stub_module(mod_name)

# ---- 3) Robust import of backend.server -----------------------------------------
# The smoke_test script lives in: <repo>/app/backend/smoke_test.py
# The server path we want to import is: <repo>/app/backend/server.py

backend_dir = Path(__file__).resolve().parent
server_path = backend_dir / "server.py"

# Ensure the backend directory is on sys.path so sibling imports (style_engine, etc.)
# can be resolved when server.py is executed directly.
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

backend_server = None
import importlib
import importlib.util

# Try normal package import first
try:
    backend_server = importlib.import_module("backend.server")
except Exception:
    # If that fails, try loading server.py by file path into a module named 'backend.server'
    try:
        if not server_path.exists():
            raise FileNotFoundError(f"Expected server.py at {server_path} not found")
        spec = importlib.util.spec_from_file_location("backend.server", str(server_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create import spec for {server_path}")
        module = importlib.util.module_from_spec(spec)
        # Register under the package name so internal imports that expect that name work
        sys.modules["backend.server"] = module
        # Also ensure plain 'server' name doesn't conflict but is available
        sys.modules["server"] = module
        spec.loader.exec_module(module)  # type: ignore
        backend_server = module
    except Exception as e:
        print("ERROR: Failed to import backend.server via both package import and file load.")
        traceback.print_exc()
        raise SystemExit(1)

# If we got here, backend_server should be set
if backend_server is None:
    print("ERROR: backend_server module not loaded for unknown reasons.")
    raise SystemExit(1)

# ---- 4) Use TestClient to exercise some endpoints -------------------------------
from fastapi.testclient import TestClient

# The server module defines `app` at module-level
if not hasattr(backend_server, "app"):
    print("ERROR: imported module backend.server does not expose `app` variable.")
    raise SystemExit(1)

app = getattr(backend_server, "app")
client = TestClient(app, raise_server_exceptions=True)


def _pretty_resp(resp):
    """Return a JSON-serializable summary of the response."""
    out: Dict[str, Any] = {"status_code": resp.status_code}
    try:
        out["json"] = resp.json()
    except Exception:
        text = resp.text or ""
        out["text"] = text if len(text) < 2000 else text[:2000] + "...(truncated)"
    # include a few headers relevant for CORS / content negotiation
    headers_of_interest = ["content-type", "content-disposition", "access-control-allow-origin"]
    out["headers"] = {k: v for k, v in resp.headers.items() if k.lower() in headers_of_interest}
    return out


def run_smoke_tests():
    print("Running smoke tests against the in-process FastAPI app...\n")

    # 1) Root
    try:
        r = client.get("/api/")
        print("GET /api/ ->")
        print(json.dumps(_pretty_resp(r), indent=2, default=str))
    except Exception:
        print("GET /api/ raised an exception:")
        traceback.print_exc()

    # 2) Ollama config (harmless if Ollama not running)
    try:
        r = client.get("/api/ollama/config")
        print("\nGET /api/ollama/config ->")
        print(json.dumps(_pretty_resp(r), indent=2, default=str))
    except Exception:
        print("GET /api/ollama/config raised an exception:")
        traceback.print_exc()

    # 3) Profile (this will create a default profile document if possible)
    try:
        r = client.get("/api/profile", timeout=15)
        print("\nGET /api/profile ->")
        print(json.dumps(_pretty_resp(r), indent=2, default=str))
    except Exception:
        print("GET /api/profile raised an exception:")
        traceback.print_exc()

    # 4) Create a project
    proj_payload = {"name": "smoke-test-project"}
    try:
        r = client.post("/api/projects", json=proj_payload, timeout=15)
        print("\nPOST /api/projects ->")
        print(json.dumps(_pretty_resp(r), indent=2, default=str))
        created = None
        try:
            created = r.json()
        except Exception:
            created = None
    except Exception:
        print("POST /api/projects raised an exception:")
        traceback.print_exc()
        created = None

    # 5) List projects
    try:
        r = client.get("/api/projects", timeout=15)
        print("\nGET /api/projects ->")
        print(json.dumps(_pretty_resp(r), indent=2, default=str))
    except Exception:
        print("GET /api/projects raised an exception:")
        traceback.print_exc()

    # 6) If project created, try transform endpoint (expected to error when basic-pitch not installed)
    if created and isinstance(created, dict) and created.get("id"):
        pid = created["id"]
        try:
            r = client.post(f"/api/projects/{pid}/transform", timeout=30)
            print(f"\nPOST /api/projects/{pid}/transform ->")
            print(json.dumps(_pretty_resp(r), indent=2, default=str))
        except Exception:
            print(f"POST /api/projects/{pid}/transform raised an exception:")
            traceback.print_exc()
    else:
        print("\nNote: project creation failed or returned unexpected payload; skipping transform test.")

    print("\nSmoke tests complete.")


if __name__ == "__main__":
    run_smoke_tests()
