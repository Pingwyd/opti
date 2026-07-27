@echo off
REM Launch MetaPrompt without a console window (uses venv if present).
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
) else (
  start "" pythonw "%~dp0main.py"
)
