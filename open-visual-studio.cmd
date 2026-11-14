@echo off
cd /d "%~dp0"
if not exist "build\vs2026\MandelbulbStudio.slnx" if not exist "build\vs2026\MandelbulbStudio.sln" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build.ps1"
  if errorlevel 1 (pause & exit /b 1)
)
if exist "build\vs2026\MandelbulbStudio.slnx" (
  start "" "build\vs2026\MandelbulbStudio.slnx"
) else (
  start "" "build\vs2026\MandelbulbStudio.sln"
)
