@echo off
chcp 65001 >nul
echo =======================================================
echo          COMPILADOR DE GIT MANAGER PORTABLE
echo =======================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

echo [1/3] Verificando e instalando dependencias necesarias...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo.
echo [2/3] Ejecutando pruebas unitarias de seguridad y lógica...
python -m unittest discover -s tests -v
if %errorlevel% neq 0 (
    echo [ERROR] Las pruebas unitarias fallaron. Corrige los errores antes de compilar.
    pause
    exit /b 1
)

echo.
echo [3/3] Compilando aplicación portable con PyInstaller...
python build_portable.py
if %errorlevel% neq 0 (
    echo [ERROR] Falló el proceso de compilación.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo  COMPILACIÓN FINALIZADA CON ÉXITO
echo  1. Archivo único portable (.exe):
echo     dist\GitManager.exe
echo  2. Carpeta lista para pendrive:
echo     dist\GitManager\
echo =======================================================
pause
