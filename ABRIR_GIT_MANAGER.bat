@echo off
:: Lanzador directo de 1 clic para Git Manager
cd /d "%~dp0"
if exist "dist\GitManager\GitManager.exe" (
    start "" "dist\GitManager\GitManager.exe"
) else (
    python src\main.py
)
