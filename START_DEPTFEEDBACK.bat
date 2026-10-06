@echo off
title Department Feedback System - MongoDB
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv venv
  if errorlevel 1 (echo Python is not installed or not on PATH.&pause&exit /b 1)
)
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed.&pause&exit /b 1)
start "" http://127.0.0.1:5000
python app.py
pause
