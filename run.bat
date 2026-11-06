@echo off
REM Starts the Moonshine service on port 9240 (syncs .venv with uv on each run). The first start downloads the weights (about 250 MB).
REM LABEL: Moonshine Service
REM DESCRIPTION: Shared HTTP service that runs Moonshine on the CPU for every project.

cd /d "%~dp0"

uv sync
if errorlevel 1 (
    echo uv sync failed. Install uv: winget install astral-sh.uv
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

python src/app.py
pause
