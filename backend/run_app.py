"""
Run shim for Transformusic.

Stubs all optional audio packages so the app starts with only core deps installed.
Run from the backend/ directory: python run_app.py
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import types
from typing import Any, Callable

_logger = logging.getLogger("run_app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def _make_stub_callable(name: str) -> Callable[..., Any]:
    def _raiser(*args, **kwargs):
        raise RuntimeError(
            f"'{name}' is not installed. Install audio deps: pip install -r requirements-audio.txt"
        )
    return _raiser


class _StubModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__stub__ = True

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        return _make_stub_callable(f"{self.__name__}.{attr}")


def _stub(module_name: str, submodules: list[str] | None = None, attrs: dict | None = None):
    try:
        importlib.import_module(module_name)
        return
    except Exception:
        pass

    mod = _StubModule(module_name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[module_name] = mod

    if submodules:
        for sub in submodules:
            full = f"{module_name}.{sub}"
            sub_mod = _StubModule(full)
            sys.modules[full] = sub_mod
            setattr(mod, sub, sub_mod)


# Stub all audio deps that server.py imports at top level
_stub("numpy")
_stub("librosa", submodules=["core", "effects", "util"])
_stub("soundfile")
_stub("scipy", submodules=["signal"])
_stub("music21")
_stub("pretty_midi")
_stub("mido")
_stub("basic_pitch", submodules=["inference"])
_stub("faster_whisper")

_AUDIO_MODULES = {"numpy","librosa","soundfile","scipy","music21","pretty_midi","mido","basic_pitch","faster_whisper"}
_stubbed = [name for name, mod in sys.modules.items() if getattr(mod, "__stub__", False) and name.split(".")[0] in _AUDIO_MODULES]
if _stubbed:
    _logger.info("Stubbed %d audio modules (core-only mode). Audio endpoints will error until you install requirements-audio.txt", len(_stubbed))


def main():
    try:
        import uvicorn
    except Exception as e:
        _logger.error("uvicorn not installed: %s", e)
        raise

    host = os.environ.get("RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("RUN_PORT", os.environ.get("PORT", "8000")))
    reload = os.environ.get("RELOAD", "false").lower() in ("1", "true", "yes")

    _logger.info("Starting Transformusic API — http://%s:%d", host, port)
    uvicorn.run("server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
