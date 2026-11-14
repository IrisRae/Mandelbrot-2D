@echo off
cd /d "%~dp0"
if exist "build\vs2026\Release\mandelbulb.exe" (
  "build\vs2026\Release\mandelbulb.exe"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build.ps1" -Run
)
if errorlevel 1 pause
