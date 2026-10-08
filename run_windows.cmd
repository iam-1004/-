@echo off
cd /d "%~dp0"
py -3.12 main.py
if errorlevel 1 (
  echo Install Python 3.12 with Tcl/Tk support, then run this file again.
  pause
)
