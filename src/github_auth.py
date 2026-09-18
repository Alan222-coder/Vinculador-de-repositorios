"""Servicio de autenticación y API de GitHub para Git Manager.

Independiente de Git local. Utiliza Windows DPAPI para almacenamiento cifrado
de credenciales a nivel de sistema operativo y se integra con Git Credential
Manager y la API oficial de GitHub (api.github.com).
"""

import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from src.logger_service import get_base_dir, logger
from src.git_service import git_service


# Estructura DATA_BLOB para la API Win32 CryptProtectData (DPAPI)
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def dpapi_encrypt(data_bytes: bytes) -> Optional[bytes]:
    """Cifra bytes utilizando las credenciales del usuario de Windows actual."""
    if sys.platform != "win32":
        return data_bytes

    try:
        blob_in = _DATA_BLOB(
            len(data_bytes),
            ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _DATA_BLOB()
        if ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "GitManagerAuthToken",
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            cb = int(blob_out.cbData)
            pb = blob_out.pbData
            buf = ctypes.string_at(pb, cb)
            ctypes.windll.kernel32.LocalFree(pb)
            return buf
    except Exception as exc:
        logger.error(f"Error al cifrar con Windows DPAPI: {exc}")
    return None


def dpapi_decrypt(cipher_bytes: bytes) -> Optional[bytes]:
    """Descifra bytes utilizando Windows DPAPI."""
    if sys.platform != "win32":
        return cipher_bytes

    try:
        blob_in = _DATA_BLOB(
            len(cipher_bytes),
            ctypes.cast(ctypes.create_string_buffer(cipher_bytes), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            cb = int(blob_out.cbData)
            pb = blob_out.pbData
            buf = ctypes.string_at(pb, cb)
            ctypes.windll.kernel32.LocalFree(pb)
            return buf
    except Exception as exc:
        logger.error(f"Error al descifrar con Windows DPAPI: {exc}")
    return None


class GitHubAuthService:
    """Gestiona el estado de autenticación y la interacción con la API de GitHub."""

    def __init__(self) -> None:
        self.base_dir = get_base_dir()
        self.auth_file = os.path.join(self.base_dir, "config", "session.dat")
        self._cached_token: Optional[str] = None
        self._cached_user_info: Optional[Dict[str, Any]] = None

    def _load_saved_token(self) -> Optional[str]:
        """Carga y descifra el token seguro desde config/session.dat."""
        if self._cached_token:
            return self._cached_token

        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, "rb") as f:
                    encrypted = f.read()
                decrypted = dpapi_decrypt(encrypted)
                if decrypted:
                    self._cached_token = decrypted.decode("utf-8").strip()
                    return self._cached_token
            except Exception as exc:
                logger.warning(f"No se pudo cargar token de session.dat: {exc}")
        return None

    def _save_token(self, token: str) -> bool:
        """Cifra y almacena el token usando Windows DPAPI."""
        clean = token.strip()
        if not clean:
            return False
        encrypted = dpapi_encrypt(clean.encode("utf-8"))
        if not encrypted:
            return False
        try:
            with open(self.auth_file, "wb") as f:
                f.write(encrypted)
            self._cached_token = clean
            return True
        except Exception as exc:
            logger.error(f"Error al escribir session.dat: {exc}")
            return False

    def get_auth_status(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Comprueba el estado de la cuenta de GitHub."""
        # 1. Comprobar Git Credential Manager oficial
        if git_service.is_git_available():
            gcm_cmd = ["credential-manager", "github", "list"]
            success, stdout, _ = git_service.run_command(gcm_cmd, cwd=repo_path, timeout=10)
            if success and stdout.strip():
                accounts = [acc.strip() for acc in stdout.splitlines() if acc.strip()]
                if accounts:
                    user = accounts[0]
                    return {
                        "is_authenticated": True,
                        "username": user,
                        "public_name": user,
                        "email": "",
                        "source": "Git Credential Manager",
                        "status_label": "🟢 GitHub conectado",
                    }

        # 2. Comprobar sesión guardada en DPAPI con la API de GitHub
        token = self._load_saved_token()
        if token:
            user_data = self._fetch_github_user_via_token(token)
            if user_data:
                return {
                    "is_authenticated": True,
                    "username": user_data.get("login", ""),
                    "public_name": user_data.get("name") or user_data.get("login", ""),
                    "email": user_data.get("email") or "",
                    "source": "Windows DPAPI (API Token)",
                    "status_label": "🟢 GitHub conectado",
                }

        # 3. Fallback a configuración de Git user.name si existe
        if git_service.is_git_available():
            succ, uname, _ = git_service.run_command(["config", "user.name"], cwd=repo_path, timeout=5)
            if succ and uname.strip():
                return {
                    "is_authenticated": True,
                    "username": uname.strip(),
                    "public_name": uname.strip(),
                    "email": "",
                    "source": "Git Config Local",
                    "status_label": "🟢 Conectado (Git Local)",
                }

        # No hay autenticación
        return {
            "is_authenticated": False,
            "username": "",
            "public_name": "",
            "email": "",
            "source": "None",
            "status_label": "🔴 GitHub no conectado en esta computadora",
        }

    def _fetch_github_user_via_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Consulta la API de GitHub (GET /user) con el token seguro."""
        url = "https://api.github.com/user"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitManager-App",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._cached_user_info = data
                    return data
        except Exception as exc:
            logger.warning(f"Error al consultar API de GitHub /user: {exc}")
        return None

    def get_user_repositories(self, repo_path: Optional[str] = None) -> List[Dict[str, str]]:
        """Obtiene la lista de repositorios del usuario autenticado vía API."""
        repos = []
        token = self._load_saved_token()

        if token:
            url = "https://api.github.com/user/repos?sort=updated&per_page=100&type=all"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GitManager-App",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        items = json.loads(resp.read().decode("utf-8"))
                        for item in items:
                            repos.append({
                                "name": item.get("name", ""),
                                "full_name": item.get("full_name", ""),
                                "clone_url": item.get("clone_url", ""),
                                "default_branch": item.get("default_branch", "main"),
                                "is_private": item.get("private", False),
                            })
                        return repos
            except Exception as exc:
                logger.warning(f"Error al obtener repositorios vía API: {exc}")

        # Si no hay token de API directo pero hay repos conocidos o URLs guardadas
        return repos

    def launch_official_login(self) -> Dict[str, Any]:
        """Inicia el proceso oficial de login de GitHub (GCM en navegador)."""
        logger.info("Iniciando login oficial de GitHub...")
        if not git_service.is_git_available():
            return {
                "success": False,
                "message": "Git no está disponible en esta computadora.",
            }

        try:
            cmd = [git_service._git_executable, "credential-manager", "github", "login"]
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=creationflags,
            )

            status = self.get_auth_status()
            if status["is_authenticated"]:
                logger.log_operation("github_login", "correcto", f"Usuario: {status['username']}")
                return {
                    "success": True,
                    "message": f"¡Sesión iniciada con éxito! Usuario: {status['username']}",
                    "username": status["username"],
                    "public_name": status.get("public_name", status["username"]),
                    "email": status.get("email", ""),
                }
            return {
                "success": False,
                "message": "No se completó el inicio de sesión en el navegador.",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "El inicio de sesión expiró por inactividad."}
        except Exception as exc:
            return {"success": False, "message": f"Error al abrir login: {exc}"}

    def verify_manual_hint_against_login(self, hint: str, actual_username: str, actual_email: str = "") -> Tuple[bool, str]:
        """Compara la sugerencia ingresada manualmente por el alumno con el usuario autenticado real.

        Retorna:
            (coincide, mensaje_o_advertencia)
        """
        clean_hint = hint.strip().lower()
        clean_user = actual_username.strip().lower()
        clean_email = actual_email.strip().lower()

        if not clean_hint:
            return True, ""

        if clean_hint == clean_user or (clean_email and clean_hint == clean_email):
            return True, "La cuenta coincide exactamente con la indicada."

        # Difieren: preparar advertencia clara
        msg = (
            f"Iniciaste sesión como '{actual_username}', pero habías indicado '{hint}'.\n\n"
            "¿Deseas continuar utilizando la cuenta conectada?"
        )
        return False, msg


github_auth = GitHubAuthService()
