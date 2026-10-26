@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0games\bullet_pet\start_3d.ps1"
if errorlevel 1 pause
