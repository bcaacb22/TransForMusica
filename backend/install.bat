@echo off
setlocal EnableDelayedExpansion
echo === Transformusic Backend Installer ===
echo.

where py >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python launcher 'py' not found. Install Python 3.11 from python.org
    exit /b 1
)

echo Creating virtual environment with Python 3.11...
py -3.11 -m venv .venv
if %errorlevel% neq 0 (
    echo ERROR: Python 3.11 not found. Install it from python.org
    echo Your installed versions:
    py -0
    exit /b 1
)

call .venv\Scripts\activate

echo.
echo Installing core dependencies...
pip install -r requirements-core.txt
if %errorlevel% neq 0 (
    echo ERROR: Core install failed
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM PyTorch backend selection (affects demucs stem separation speed)
REM   - Auto: uses NVIDIA GPU if one is detected, otherwise CPU
REM   - Override: set TORCH_BACKEND=cuda  or  TORCH_BACKEND=cpu  before running
REM ---------------------------------------------------------------------------
echo.
echo === PyTorch backend selection ===
set "TORCH_CHOICE=cpu"
if defined TORCH_BACKEND set "TORCH_CHOICE=%TORCH_BACKEND%"
if not defined TORCH_BACKEND (
    nvidia-smi >nul 2>&1
    if !errorlevel! equ 0 set "TORCH_CHOICE=cuda"
)

if "!TORCH_CHOICE!"=="cuda" (
    echo Detected NVIDIA GPU - installing CUDA-enabled PyTorch.
    pip install torch --index-url https://download.pytorch.org/whl/cu126
) else (
    echo Installing CPU-only PyTorch.
    pip install torch --index-url https://download.pytorch.org/whl/cpu
)
if !errorlevel! neq 0 (
    echo WARNING: PyTorch install failed. Demucs stem separation may not work.
)

echo.
echo Installing audio dependencies (demucs, librosa, basic-pitch support)...
pip install -r requirements-audio.txt
if %errorlevel% neq 0 (
    echo ERROR: Audio install failed
    exit /b 1
)

echo.
echo Installing basic-pitch (ONNX backend on Windows/Python 3.11)...
pip install onnxruntime "mir_eval>=0.6" "resampy>=0.2.2,<0.4.3" typing-extensions
if %errorlevel% neq 0 (
    echo WARNING: basic-pitch deps failed. Transform/MIDI feature will be stubbed.
    goto done
)
pip install basic-pitch --no-deps
if %errorlevel% neq 0 (
    echo WARNING: basic-pitch failed. Transform/MIDI feature will be stubbed.
)

:done
echo.
echo === Install complete ===
echo PyTorch backend: !TORCH_CHOICE!
echo Run: .venv\Scripts\activate
echo Then: python run_app.py
endlocal
