@echo off
cd /d "%~dp0"
python -m sim.ui
if errorlevel 1 pause
