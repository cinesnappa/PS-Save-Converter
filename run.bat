@echo off
cd /d "%~dp0"
start "" pythonw app.py || python app.py
