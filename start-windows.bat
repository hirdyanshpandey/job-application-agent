@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 exit /b 1
if not exist ".venv\ready" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
  echo ready > ".venv\ready"
)
".venv\Scripts\python.exe" -m streamlit run dashboard.py --server.address 127.0.0.1
pause
