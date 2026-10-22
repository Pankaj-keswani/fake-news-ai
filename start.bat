@echo off
title Fake News Detector
cd /d "%~dp0backend"

if not exist venv\Scripts\python.exe (
  echo Creating virtual environment...
  python -m venv venv || (echo Python not found. Install Python 3.10+ first. & pause & exit /b 1)
)
call venv\Scripts\activate.bat

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo  Add your GROQ_API_KEY to backend\.env, then run start.bat again.
  notepad .env
  pause
  exit /b 1
)

echo Installing / updating packages...
python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo Package install failed. & pause & exit /b 1)

echo.
echo  Fake News Detector is starting at http://127.0.0.1:5000
echo  Keep this window open. Press Ctrl+C to stop the server.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
python app.py
pause
