"""Servicio de ejecución segura de comandos Git para Git Manager.

Garantiza la ejecución controlada de procesos mediante argumentos separados,
sin shell interactivo, con tiempos límite (timeout), sanitización de salidas,
detección de ejecutables de Git portables o del sistema y prevención de bloqueos.
Soporta inicialización de carpetas sin .git, vinculación a GitHub y clonación.
"""

import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Any, Callable

from src.logger_service import get_base_dir, logger, sanitize_text
from src.security_checker import SecurityChecker
from src.error_translator import ErrorTranslator


class GitService:
    """Administra y ejecuta todas las operaciones de Git de forma segura."""

    def __init__(self) -> None:
        self.base_dir = get_base_dir()
        self._git_executable: Optional[str] = None
        self.detect_git_binary()

    def detect_git_binary(self) -> Optional[str]:
        """Detecta la ubicación de Git (portable en el directorio de la app o en el sistema)."""
        # 1. Buscar Git portable local en el pendrive / carpeta de la aplicación
        candidate_paths = [
            os.path.join(self.base_dir, "git", "cmd", "git.exe"),
            os.path.join(self.base_dir, "git", "bin", "git.exe"),
            os.path.join(self.base_dir, "runtime", "git", "cmd", "git.exe"),
            os.path.join(self.base_dir, "runtime", "git", "bin", "git.exe"),
        ]

        for path in candidate_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                self._git_executable = os.path.normpath(path)
                logger.info(f"Git portable detectado en: {self._git_executable}")
                return self._git_executable

        # 2. Buscar Git en el PATH del sistema
        system_git = shutil.which("git") or shutil.which("git.exe")
        if system_git:
            self._git_executable = os.path.normpath(system_git)
            logger.info(f"Git del sistema detectado en: {self._git_executable}")
            return self._git_executable

        self._git_executable = None
        logger.warning("No se encontró ningún ejecutable de Git (ni portable ni en PATH).")
        return None

    def is_git_available(self) -> bool:
        """Indica si hay un binario de Git listo para usarse."""
        if not self._git_executable or not os.path.isfile(self._git_executable):
            self.detect_git_binary()
        return self._git_executable is not None

    def get_git_version(self) -> str:
        """Devuelve la versión instalada de Git parseada a partir de 'git --version'."""
        if not self.is_git_available():
            return "No disponible"
        success, stdout, _ = self.run_command(["--version"])
        if success and stdout:
            # Ejemplo: "git version 2.53.0.windows.3" -> "Git 2.53.0"
            match = re.search(r"git\s+version\s+([0-9]+\.[0-9]+(\.[0-9]+)?)", stdout, re.IGNORECASE)
            if match:
                return f"Git {match.group(1)}"
            return stdout.strip()
        return "No disponible"

    def run_command(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        timeout: int = 45,
    ) -> Tuple[bool, str, str]:
        """Ejecuta un comando Git mediante lista de argumentos segura.

        Retorna:
            (éxito, stdout, stderr)
        """
        if not self.is_git_available():
            return False, "", "Git no está instalado o no se encontró el ejecutable."

        full_cmd = [self._git_executable] + args

        # Entorno seguro sin prompts en consola que congelen la interfaz
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"

        # Ocultar ventana de consola en Windows
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        # Censurar argumentos para log
        log_args = [sanitize_text(a) for a in args]
        logger.info(f"Ejecutando: git {' '.join(log_args)} en cwd={cwd or os.getcwd()}")

        try:
            process = subprocess.run(
                full_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                creationflags=creationflags,
            )

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            success = process.returncode == 0

            if not success:
                logger.warning(
                    f"Git falló (código {process.returncode}): {sanitize_text(stderr or stdout)}"
                )
            return success, stdout, stderr

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout al ejecutar: git {' '.join(log_args)}")
            return False, "", "La operación tardó demasiado tiempo y se canceló por seguridad."
        except Exception as exc:
            logger.error(f"Error del sistema al ejecutar git: {exc}")
            return False, "", f"Error del sistema al ejecutar Git: {exc}"

    def is_git_repository(self, path: str) -> bool:
        """Comprueba si una carpeta es la raíz de un repositorio Git."""
        if not path or not os.path.isdir(path):
            return False
        git_dir = os.path.join(path, ".git")
        return os.path.exists(git_dir)

    def count_folder_contents(self, path: str) -> Tuple[int, int]:
        """Cuenta la cantidad de archivos y subcarpetas en una carpeta (omitiendo .git)."""
        if not path or not os.path.isdir(path):
            return 0, 0

        file_count = 0
        dir_count = 0
        try:
            for root, dirs, files in os.walk(path):
                if ".git" in dirs:
                    dirs.remove(".git")
                file_count += len(files)
                dir_count += len(dirs)
        except Exception as exc:
            logger.warning(f"Error al contar contenido de {path}: {exc}")

        return file_count, dir_count

    def get_repo_info(self, repo_path: str) -> Dict[str, Any]:
        """Extrae la información fundamental del repositorio."""
        if not self.is_git_repository(repo_path):
            return {
                "is_repo": False,
                "name": os.path.basename(repo_path) if repo_path else "Sin seleccionar",
                "remote_url": "No configurado",
                "branch": "N/A",
                "is_clean": True,
                "has_remote": False,
            }

        # 1. Rama actual
        success, branch, _ = self.run_command(["branch", "--show-current"], cwd=repo_path)
        if not success or not branch:
            _, branch, _ = self.run_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        branch = branch.strip() if branch else "main"

        # 2. URL remota origin
        success, remote_url, _ = self.run_command(["remote", "get-url", "origin"], cwd=repo_path)
        remote_url = remote_url.strip() if success else ""

        # 3. Nombre del repositorio
        repo_name = os.path.basename(os.path.normpath(repo_path))
        if remote_url:
            clean_url = remote_url.rstrip("/").removesuffix(".git")
            repo_name = clean_url.split("/")[-1] or repo_name

        # 4. Estado de cambios locales
        success, status_out, _ = self.run_command(["status", "--porcelain"], cwd=repo_path)
        is_clean = len(status_out.strip()) == 0

        return {
            "is_repo": True,
            "name": repo_name,
            "remote_url": remote_url or "Sin remoto configurado",
            "branch": branch,
            "is_clean": is_clean,
            "has_remote": bool(remote_url),
        }

    def get_git_identity(self, repo_path: Optional[str] = None) -> Tuple[str, str]:
        """Obtiene la identidad local o global de Git (user.name, user.email)."""
        name = ""
        email = ""

        succ_name, out_name, _ = self.run_command(["config", "user.name"], cwd=repo_path)
        if succ_name and out_name:
            name = out_name.strip()

        succ_email, out_email, _ = self.run_command(["config", "user.email"], cwd=repo_path)
        if succ_email and out_email:
            email = out_email.strip()

        return name, email

    def set_git_identity(
        self,
        name: str,
        email: str,
        repo_path: Optional[str] = None,
        is_global: bool = False,
    ) -> Tuple[bool, str]:
        """Configura user.name y user.email en Git."""
        clean_name = name.strip()
        clean_email = email.strip()
        if not clean_name or not clean_email:
            return False, "Nombre y correo son requeridos."

        scope_arg = ["--global"] if is_global else []
        cmd_name = ["config"] + scope_arg + ["user.name", clean_name]
        cmd_email = ["config"] + scope_arg + ["user.email", clean_email]

        succ1, _, err1 = self.run_command(cmd_name, cwd=repo_path)
        succ2, _, err2 = self.run_command(cmd_email, cwd=repo_path)

        if succ1 and succ2:
            logger.info(f"Identidad Git configurada: {clean_name} <{clean_email}> (global={is_global})")
            return True, "Identidad de Git configurada correctamente."
        return False, f"Error al configurar identidad: {err1 or err2}"

    def init_repository(self, path: str) -> Tuple[bool, str]:
        """Inicializa un nuevo repositorio Git en una carpeta común."""
        if not os.path.isdir(path):
            return False, "La ruta no es una carpeta válida."
        success, stdout, stderr = self.run_command(["init"], cwd=path)
        if success:
            logger.info(f"Repositorio Git inicializado en: {path}")
            return True, "Repositorio Git inicializado."
        return False, f"No se pudo inicializar Git: {stderr or stdout}"

    def add_remote(self, path: str, remote_url: str, name: str = "origin") -> Tuple[bool, str]:
        """Agrega o actualiza el remoto origin."""
        clean_url = remote_url.strip()
        # Verificar si origin ya existe
        succ, stdout, _ = self.run_command(["remote", "get-url", name], cwd=path)
        if succ:
            # Ya existe, actualizarlo con set-url
            succ_set, _, err_set = self.run_command(["remote", "set-url", name, clean_url], cwd=path)
            return succ_set, err_set or "Remoto actualizado."
        else:
            # No existe, agregarlo
            succ_add, _, err_add = self.run_command(["remote", "add", name, clean_url], cwd=path)
            return succ_add, err_add or "Remoto agregado."

    def verify_remote(self, path: str, name: str = "origin") -> Tuple[bool, str]:
        """Verifica que el remoto esté configurado correctamente con git remote -v."""
        success, stdout, stderr = self.run_command(["remote", "-v"], cwd=path)
        if success and name in stdout:
            return True, stdout
        return False, stderr or "El remoto no está configurado."

    def clone_repository(
        self,
        remote_url: str,
        dest_folder: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Clona de forma segura un repositorio de GitHub hacia una carpeta."""
        clean_url = remote_url.strip()
        if not clean_url:
            return False, "URL del repositorio requerida.", {}

        if progress_callback:
            progress_callback("Descargando repositorio desde GitHub...", 0.4)

        success, stdout, stderr = self.run_command(["clone", clean_url, dest_folder], timeout=90)
        if success:
            logger.log_operation("clone", "correcto", f"URL: {clean_url}")
            if progress_callback:
                progress_callback("Proyecto clonado con éxito.", 1.0)
            return True, "Repositorio clonado correctamente.", {"raw": stdout}

        diag = ErrorTranslator.translate(stderr, stdout, f"git clone {clean_url}")
        logger.log_operation("clone", "error", diag["title"])
        return False, diag["message"], diag

    def link_folder_to_github(
        self,
        folder_path: str,
        remote_url: str,
        commit_message: str = "Primer backup del proyecto",
        branch_name: str = "main",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Vincula una carpeta normal existente a un repositorio de GitHub:

        1. git init (si no existe .git)
        2. Configurar origin
        3. Configurar rama principal (main)
        4. Verificar seguridad de archivos existentes (.env, etc.)
        5. git add . y commit inicial
        6. git push -u origin main
        """
        if not os.path.isdir(folder_path):
            return False, "La carpeta seleccionada no existe.", {}

        # Paso 1: Inicializar si no es repo
        if progress_callback:
            progress_callback("Inicializando Git en la carpeta...", 0.15)

        if not self.is_git_repository(folder_path):
            succ_init, msg_init = self.init_repository(folder_path)
            if not succ_init:
                return False, msg_init, {}

        # Paso 2: Configurar rama principal estándar
        self.run_command(["branch", "-M", branch_name], cwd=folder_path)

        # Paso 3: Configurar y verificar remoto origin
        if progress_callback:
            progress_callback("Configurando conexión con GitHub (origin)...", 0.30)

        succ_rem, msg_rem = self.add_remote(folder_path, remote_url, "origin")
        if not succ_rem:
            return False, f"No se pudo configurar el remoto: {msg_rem}", {}

        # Validar con git remote -v
        succ_v, _ = self.verify_remote(folder_path, "origin")
        if not succ_v:
            return False, "Error en la verificación de git remote -v.", {}

        # Paso 4: Comprobar archivos locales
        if progress_callback:
            progress_callback("Analizando archivos locales...", 0.45)

        has_changes, changes = self.has_local_changes(folder_path)
        if has_changes:
            # Inspección de seguridad
            is_safe, dangerous = SecurityChecker.inspect_changed_files(changes)
            if not is_safe:
                alert = SecurityChecker.format_security_alert(dangerous)
                return False, alert["message"], alert

            # git add .
            if progress_callback:
                progress_callback("Preparando archivos para el primer backup...", 0.60)
            succ_add, stdout_add, stderr_add = self.run_command(["add", "."], cwd=folder_path)
            if not succ_add:
                diag = ErrorTranslator.translate(stderr_add, stdout_add, "git add .")
                return False, diag["message"], diag

            # git commit
            if progress_callback:
                progress_callback("Creando punto de guardado inicial...", 0.75)
            succ_commit, stdout_com, stderr_com = self.run_command(
                ["commit", "-m", commit_message],
                cwd=folder_path,
            )
            if not succ_commit and "nothing to commit" not in (stdout_com + stderr_com).lower():
                diag = ErrorTranslator.translate(stderr_com, stdout_com, "git commit")
                return False, diag["message"], diag

        # Paso 5: Push al remoto con vinculación upstream (-u)
        if progress_callback:
            progress_callback("Sincronizando con GitHub...", 0.90)

        succ_push, stdout_p, stderr_p = self.run_command(
            ["push", "-u", "origin", branch_name],
            cwd=folder_path,
            timeout=60,
        )

        if not succ_push:
            diag = ErrorTranslator.translate(stderr_p, stdout_p, f"git push -u origin {branch_name}")
            return False, diag["message"], diag

        if progress_callback:
            progress_callback("¡Proyecto vinculado con éxito!", 1.0)

        logger.log_operation("link_project", "correcto", f"Carpeta: {folder_path} -> {remote_url}")
        return True, "Proyecto vinculado y sincronizado exitosamente con GitHub.", {
            "title": "✅ PROYECTO CONFIGURADO",
            "branch": branch_name,
            "remote": remote_url,
        }

    def get_status_porcelain(self, repo_path: str) -> List[str]:
        """Obtiene las líneas de archivos modificados/nuevos."""
        success, stdout, _ = self.run_command(["status", "--porcelain"], cwd=repo_path)
        if not success or not stdout:
            return []
        return [line for line in stdout.splitlines() if line.strip()]

    def has_local_changes(self, repo_path: str) -> Tuple[bool, List[str]]:
        """Comprueba si hay cambios locales sin guardar."""
        lines = self.get_status_porcelain(repo_path)
        return len(lines) > 0, lines

    def get_branches(self, repo_path: str) -> Tuple[List[str], str]:
        """Obtiene la lista de ramas locales y la rama actual."""
        branches: List[str] = []
        current_branch = "main"

        success, stdout, _ = self.run_command(["branch", "--format=%(refname:short)|%(HEAD)"], cwd=repo_path)
        if success and stdout:
            for line in stdout.splitlines():
                parts = line.strip().split("|")
                if len(parts) >= 1:
                    b_name = parts[0].strip()
                    if b_name:
                        branches.append(b_name)
                    if len(parts) >= 2 and parts[1].strip() == "*":
                        current_branch = b_name

        if not branches:
            branches = ["main"]

        return branches, current_branch

    def checkout_branch(self, repo_path: str, target_branch: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Cambia de rama de forma segura, verificando antes si hay cambios pendientes."""
        has_changes, changes = self.has_local_changes(repo_path)
        if has_changes:
            return False, "Tienes cambios locales sin guardar.", {
                "title": "⚠️ Cambios sin guardar",
                "message": (
                    "No se puede cambiar de rama porque tienes archivos modificados.\n\n"
                    "Crea un backup de tu trabajo antes de cambiar de rama para evitar pérdidas."
                ),
                "severity": "warning",
                "raw": "\n".join(changes),
                "command": f"git checkout {target_branch}",
            }

        success, stdout, stderr = self.run_command(["checkout", target_branch], cwd=repo_path)
        if success:
            logger.log_operation("checkout_branch", "correcto", f"Rama: {target_branch}")
            return True, f"Cambiado a la rama '{target_branch}' con éxito.", {}

        diag = ErrorTranslator.translate(stderr, stdout, f"git checkout {target_branch}")
        logger.log_operation("checkout_branch", "error", diag["title"])
        return False, diag["message"], diag

    def pull(self, repo_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Trae los cambios remotos de GitHub de forma segura."""
        success, stdout, stderr = self.run_command(["pull"], cwd=repo_path)
        if success:
            logger.log_operation("git pull", "correcto", stdout)
            msg = "Los cambios más recientes de GitHub fueron incorporados a tu computadora."
            if "Already up to date." in stdout or "Ya está actualizado" in stdout:
                msg = "Tu proyecto ya está completamente al día. No había cambios nuevos."
            return True, msg, {"raw": stdout}

        diag = ErrorTranslator.translate(stderr, stdout, "git pull")
        logger.log_operation("git pull", "error", diag["title"])
        return False, diag["message"], diag

    def create_backup(
        self,
        repo_path: str,
        message: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Ejecuta el flujo completo de creación de backup:

        1. Verifica cambios
        2. Inspecciona archivos sensibles (.env, etc.)
        3. git add .
        4. git commit -m <message>
        5. git push
        """
        clean_msg = message.strip()
        if not clean_msg:
            return False, "El mensaje del backup no puede estar vacío.", {
                "title": "⚠️ Mensaje requerido",
                "message": "Debes escribir una breve descripción de los cambios que realizaste.",
                "severity": "warning",
                "raw": "",
                "command": "",
            }

        if progress_callback:
            progress_callback("Analizando cambios...", 0.15)

        # Paso 1: Comprobar si hay cambios
        has_changes, changes = self.has_local_changes(repo_path)
        if not has_changes:
            return False, "No hay cambios nuevos para guardar.", {
                "title": "ℹ️ Sin cambios",
                "message": "No hay archivos modificados ni nuevos para guardar en este momento.",
                "severity": "info",
                "raw": "",
                "command": "",
            }

        # Paso 2: Análisis de seguridad (archivos sensibles)
        if progress_callback:
            progress_callback("Comprobando seguridad...", 0.30)

        is_safe, dangerous_files = SecurityChecker.inspect_changed_files(changes)
        if not is_safe:
            alert = SecurityChecker.format_security_alert(dangerous_files)
            logger.warning(f"Backup bloqueado por archivos sensibles: {dangerous_files}")
            return False, alert["message"], alert

        # Paso 3: git add .
        if progress_callback:
            progress_callback("Preparando archivos...", 0.50)

        success, stdout, stderr = self.run_command(["add", "."], cwd=repo_path)
        if not success:
            diag = ErrorTranslator.translate(stderr, stdout, "git add .")
            logger.log_operation("git add .", "error", diag["title"])
            return False, diag["message"], diag

        # Paso 4: git commit -m <clean_msg>
        if progress_callback:
            progress_callback("Creando punto de guardado (commit)...", 0.70)

        success, stdout, stderr = self.run_command(["commit", "-m", clean_msg], cwd=repo_path)
        if not success:
            diag = ErrorTranslator.translate(stderr, stdout, "git commit")
            logger.log_operation("git commit", "error", diag["title"])
            return False, diag["message"], diag

        # Paso 5: git push
        if progress_callback:
            progress_callback("Subiendo a GitHub...", 0.90)

        info = self.get_repo_info(repo_path)
        current_branch = info.get("branch", "main")
        push_args = ["push", "origin", current_branch] if info.get("has_remote") else ["push"]

        success, stdout, stderr = self.run_command(push_args, cwd=repo_path)
        if not success:
            diag = ErrorTranslator.translate(stderr, stdout, f"git {' '.join(push_args)}")
            logger.log_operation("git push", "error", diag["title"])
            return False, diag["message"], diag

        if progress_callback:
            progress_callback("¡Backup completado!", 1.0)

        logger.log_operation("create_backup", "correcto", f"Mensaje: {clean_msg}")
        return True, "Los cambios fueron enviados correctamente a GitHub.", {
            "title": "✅ BACKUP CREADO",
            "message": "Los cambios fueron enviados correctamente a GitHub.",
            "branch": current_branch,
            "commit_message": clean_msg,
            "raw": stdout,
        }

    def get_commit_history(self, repo_path: str, limit: int = 15) -> List[Dict[str, str]]:
        """Obtiene la lista de los últimos commits para el historial escolar."""
        if not self.is_git_repository(repo_path):
            return []

        fmt = "%h|%an|%cr|%s"
        success, stdout, _ = self.run_command(
            ["log", f"-n{limit}", f"--format={fmt}"],
            cwd=repo_path,
        )

        if not success or not stdout:
            return []

        commits = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0].strip(),
                    "author": parts[1].strip(),
                    "time_ago": parts[2].strip(),
                    "message": parts[3].strip(),
                })
        return commits


git_service = GitService()
