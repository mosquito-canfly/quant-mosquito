@echo off
cd /d "%~dp0"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%i

call venv\Scripts\activate.bat
python run_agent.py >> logs\run_%TIMESTAMP%.log 2>&1
