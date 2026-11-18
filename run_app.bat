@echo off
REM Starts Krishi AI with the project's own Python environment (.venv),
REM so it works even when Streamlit is not installed system-wide.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment and installing requirements. This runs once...
    python -m venv .venv || goto :nopython
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :failed
)

if "%BOLNA_API_KEY%"=="" echo Note: BOLNA_API_KEY is not set, so the call button will say the assistant is not set up yet.

echo Starting Krishi AI on http://localhost:8501 ...
".venv\Scripts\python.exe" -m streamlit run server.py --server.port 8501
goto :eof

:nopython
echo Python 3.10+ was not found on PATH. Install it from https://www.python.org/downloads/ and run this again.
pause
goto :eof

:failed
echo Installing requirements failed. See the messages above.
pause
