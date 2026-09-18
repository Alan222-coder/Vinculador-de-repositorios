"""Script de compilación y empaquetado portable para Git Manager.

Utiliza PyInstaller para generar una distribución autónoma en dist/GitManager/
lista para copiar directamente a cualquier pendrive o computadora Windows.
"""

import os
import shutil
import subprocess
import sys
import customtkinter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOMTKINTER_PATH = os.path.dirname(customtkinter.__file__)


def build() -> bool:
    print("====================================================")
    print("Iniciando compilación de Git Manager Portable...")
    print("====================================================")

    dist_dir = os.path.join(BASE_DIR, "dist")
    build_dir = os.path.join(BASE_DIR, "build")
    output_app_dir = os.path.join(dist_dir, "GitManager")

    # Comando PyInstaller
    # Incluimos los datos de customtkinter explícitamente (--add-data)
    separator = ";" if sys.platform == "win32" else ":"
    ctk_data_arg = f"{CUSTOMTKINTER_PATH}{separator}customtkinter"

    icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")
    icon_arg = f"--icon={icon_path}" if os.path.exists(icon_path) else ""

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=GitManager",
        f"--add-data={ctk_data_arg}",
        "--clean",
    ]

    if icon_arg:
        cmd.append(icon_arg)

    if os.path.exists(os.path.join(BASE_DIR, "assets")):
        cmd.append(f"--add-data={os.path.join(BASE_DIR, 'assets')}{separator}assets")

    # Script principal
    main_script = os.path.join(BASE_DIR, "src", "main.py")
    cmd.append(main_script)

    print(f"Ejecutando: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, cwd=BASE_DIR)
    if proc.returncode != 0:
        print("\n[ERROR] Fallo durante la compilacion con PyInstaller.")
        return False

    print("\n[OK] Binarios compilados correctamente en:", output_app_dir)

    # Crear carpetas esenciales dentro de dist/GitManager para asegurar portabilidad
    target_config = os.path.join(output_app_dir, "config")
    target_logs = os.path.join(output_app_dir, "logs")
    target_git = os.path.join(output_app_dir, "git")

    os.makedirs(target_config, exist_ok=True)
    os.makedirs(target_logs, exist_ok=True)
    os.makedirs(target_git, exist_ok=True)

    # Copiar plantilla de configuracion si existe
    src_config = os.path.join(BASE_DIR, "config", "settings.json")
    if os.path.exists(src_config):
        shutil.copy2(src_config, os.path.join(target_config, "settings.json"))

    # Crear archivo explicativo para el pendrive
    readme_pendrive = os.path.join(output_app_dir, "LEEME_PENDRIVE.txt")
    with open(readme_pendrive, "w", encoding="utf-8") as f:
        f.write(
            "GIT MANAGER - VERSION PORTABLE\n"
            "==============================\n\n"
            "Esta carpeta contiene la aplicacion completa para llevar en un pendrive.\n\n"
            "INSTRUCCIONES:\n"
            "1. Haz doble clic en 'GitManager.exe' para abrir el programa.\n"
            "2. No necesitas instalar Python ni librerias.\n"
            "3. Puedes mover esta carpeta a cualquier PC (Escritorio, Documentos o Pendrive).\n\n"
            "NOTA SOBRE GIT:\n"
            "- Si la computadora de la escuela ya tiene Git instalado, el programa lo usara automaticamente.\n"
            "- Si la computadora no tiene Git ni conexion a Internet para instalarlo, puedes descargar 'MinGit'\n"
            "  (la version portable oficial de Git para Windows) y extraer su contenido dentro de la carpeta 'git/'.\n"
        )

    print("[OK] Estructura de carpetas portables (config/, logs/, git/) preparada.")
    print("====================================================")
    print("Compilacion completada exitosamente.")
    print(f"Ubicacion final: {output_app_dir}")
    print("====================================================")
    return True


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
