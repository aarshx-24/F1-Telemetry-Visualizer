@echo off
cd /d "%~dp0"
code .
if errorlevel 1 (
  echo VS Code command "code" was not found in PATH.
  echo Open VS Code manually, then use File ^> Open Folder and choose:
  echo %cd%
  pause
)
