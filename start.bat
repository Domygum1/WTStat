@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv --without-pip .venv
  if errorlevel 1 goto :fail
)
if not exist ".venv\Scripts\uvicorn.exe" (
  set "TEMP=%CD%\work"
  set "TMP=%CD%\work"
  if not exist work mkdir work
  python -m pip --python .venv install -r requirements.txt
  if errorlevel 1 goto :fail
)
if not exist "bin\wtstat_results.exe" (
  echo Missing bin\wtstat_results.exe. See README.md for build instructions.
  goto :fail
)
echo WTStat: http://127.0.0.1:8766
start "" "http://127.0.0.1:8766"
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8766
exit /b %errorlevel%
:fail
echo Setup failed. Check README.md.
pause
exit /b 1
