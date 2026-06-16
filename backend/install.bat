@echo off
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

echo.
echo Installing audio dependencies...
pip install -r requirements-audio.txt
if %errorlevel% neq 0 (
    echo ERROR: Audio install failed
    exit /b 1
)

echo.
echo Installing basic-pitch (ONNX backend on Windows/Python 3.11)...
echo Installing basic-pitch runtime deps (avoids heavy TensorFlow)...
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
echo Run: .venv\Scripts\activate
echo Then: python run_app.py
