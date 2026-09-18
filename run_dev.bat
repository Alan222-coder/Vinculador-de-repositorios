@echo off
chcp 65001 >nul
echo Iniciando Git Manager (Modo Desarrollo)...
python src\main.py
if %errorlevel% neq 0 (
    echo.
    echo Ocurrió un error al ejecutar la aplicación.
    pause
)
