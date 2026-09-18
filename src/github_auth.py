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
def format_github_date(iso_str: str) -> str:
    """Convierte fechas ISO 8601 de GitHub (ej. '2026-09-17T21:30:00Z') a formato DD/MM/AAAA HH:MM."""
    if not iso_str:
        return "Fecha desconocida"
    try:
        clean = iso_str.replace("Z", "")
        if "T" in clean:
            date_part, time_part = clean.split("T", 1)
            parts = date_part.split("-")
            if len(parts) == 3:
                y, m, d = parts
                hh_mm = time_part[:5]
                return f"{d}/{m}/{y} {hh_mm}"
        return iso_str
    except Exception:
        return iso_str[:10]


# Estructura CREDENTIAL para la API Win32 CredReadW
class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)


def _read_win_credential(target: str) -> Optional[str]:
    """Lee el blob de credencial de Windows Credential Manager usando advapi32.dll."""
    if sys.platform != "win32":
        return None
    try:
        cred_read = ctypes.windll.advapi32.CredReadW
        cred_read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_PCREDENTIAL)]
        cred_read.restype = wintypes.BOOL
        cred_free = ctypes.windll.advapi32.CredFree

        pcred = _PCREDENTIAL()
        # CRED_TYPE_GENERIC = 1
        if cred_read(target, 1, 0, ctypes.byref(pcred)) and pcred:
            cred = pcred.contents
            if cred.CredentialBlob and cred.CredentialBlobSize > 0:
                raw_bytes = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                cred_free(pcred)
                # 1. Comprobar prefijos conocidos de tokens de GitHub (OAuth, PAT, User, Server)
                for enc in ("utf-8", "utf-16le"):
                    try:
                        decoded = raw_bytes.decode(enc).strip()
                        if decoded.startswith(("gho_", "ghp_", "ghu_", "ghs_", "github_pat_")):
                            return decoded
                    except Exception:
                        pass
                # 2. Fallback: string ASCII sin bytes nulos y longitud suficiente
                for enc in ("utf-8", "utf-16le"):
                    try:
                        decoded = raw_bytes.decode(enc).strip()
                        if decoded.isascii() and len(decoded) >= 20 and "\x00" not in decoded:
                            return decoded
                    except Exception:
                        pass
            else:
                cred_free(pcred)
    except Exception as exc:
        logger.debug(f"CredReadW para {target} falló: {exc}")
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

    def get_active_token(self) -> Optional[str]:
        """Obtiene el token activo de GitHub buscando en sesión DPAPI o Windows Credential Manager."""
        if self._cached_token:
            return self._cached_token

        # 1. Sesión cifrada en session.dat
        token = self._load_saved_token()
        if token:
            return token

        # 2. Windows Credential Manager (GCM oficial)
        if sys.platform == "win32":
            # Si conocemos el usuario, probar su target específico primero
            user = self._cached_user_info.get("login") if self._cached_user_info else None
            targets = []
            if user:
                targets.append(f"GitHub - https://api.github.com/{user}")
            targets.extend([
                "git:https://github.com",
            ])

            # Consultar cuentas listadas por GCM
            if git_service.is_git_available():
                succ, stdout, _ = git_service.run_command(["credential-manager", "github", "list"], timeout=5)
                if succ and stdout.strip():
                    for acc in stdout.splitlines():
                        acc = acc.strip()
                        if acc:
                            targets.insert(0, f"GitHub - https://api.github.com/{acc}")

            for target in targets:
                token = _read_win_credential(target)
                if token:
                    self._cached_token = token
                    return token

        return None

    def get_auth_status(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Comprueba el estado de la cuenta de GitHub."""
        # 1. Comprobar si tenemos token activo y podemos verificarlo contra la API
        token = self.get_active_token()
        if token:
            user_data = self._fetch_github_user_via_token(token)
            if user_data:
                return {
                    "is_authenticated": True,
                    "username": user_data.get("login", ""),
                    "public_name": user_data.get("name") or user_data.get("login", ""),
                    "email": user_data.get("email") or "",
                    "source": "GitHub Official API (Token)",
                    "status_label": "🟢 GitHub conectado",
                }

        # 2. Comprobar Git Credential Manager oficial
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

    def create_repository(
        self,
        name: str,
        description: str = "",
        is_private: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Crea un nuevo repositorio en la cuenta autenticada vía API (POST /user/repos).

        Retorna:
            (éxito, mensaje_explicativo, datos_del_repositorio)
        """
        clean_name = name.strip()
        if not clean_name:
            return False, "El nombre del repositorio no puede estar vacío.", {}

        token = self.get_active_token()
        if not token:
            return False, "No se encontró una sesión activa de GitHub con token. Por favor inicia sesión.", {}

        url = "https://api.github.com/user/repos"
        payload = {
            "name": clean_name,
            "description": description.strip(),
            "private": bool(is_private),
            "auto_init": False,
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "GitManager-App",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 201):
                    repo_data = json.loads(resp.read().decode("utf-8"))
                    logger.info(f"Repositorio creado con éxito: {repo_data.get('full_name')}")
                    return True, "¡Repositorio creado con éxito en GitHub!", repo_data
                return False, f"GitHub respondió con código inesperado: {resp.status}", {}
        except urllib.error.HTTPError as http_err:
            raw_err = ""
            try:
                raw_err = http_err.read().decode("utf-8")
                err_json = json.loads(raw_err)
                msg = err_json.get("message", "")
                errors = err_json.get("errors", [])

                if http_err.code == 422:
                    for err_item in errors:
                        err_msg = err_item.get("message", "") if isinstance(err_item, dict) else str(err_item)
                        if "already exists" in err_msg.lower() or "already exists" in msg.lower():
                            return (
                                False,
                                f"Ya tienes un repositorio llamado '{clean_name}' en tu cuenta de GitHub.\n\n"
                                "Por favor elige un nombre diferente.",
                                {},
                            )
                    if msg:
                        return False, f"GitHub no pudo crear el repositorio: {msg}", {}
                elif http_err.code == 401:
                    return (
                        False,
                        "Tu sesión de GitHub ha expirado o no tiene permisos de creación de repositorios.\n"
                        "Inicia sesión nuevamente en la aplicación.",
                        {},
                    )
                elif http_err.code == 403:
                    return False, f"Permisos insuficientes o límite de peticiones alcanzado: {msg}", {}
                return False, f"Error de GitHub ({http_err.code}): {msg or http_err.reason}", {}
            except Exception:
                return False, f"Error de GitHub ({http_err.code}): {raw_err or http_err.reason}", {}
        except urllib.error.URLError as url_err:
            return False, f"No se pudo conectar con GitHub. Comprueba tu conexión a Internet:\n{url_err.reason}", {}
        except Exception as exc:
            return False, f"Error inesperado al crear repositorio: {exc}", {}

    def get_all_user_repositories(self) -> Tuple[bool, List[Dict[str, Any]], str]:
        """Obtiene TODOS los repositorios del usuario autenticado vía API (GET /user/repos) paginando."""
        token = self.get_active_token()
        if not token:
            return False, [], "No se encontró un token de autenticación activo para consultar tus repositorios."

        all_repos: List[Dict[str, Any]] = []
        page = 1
        per_page = 100

        while True:
            url = f"https://api.github.com/user/repos?sort=updated&per_page={per_page}&page={page}&type=all"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GitManager-App",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        items = json.loads(resp.read().decode("utf-8"))
                        if not items:
                            break
                        for item in items:
                            all_repos.append({
                                "name": item.get("name", ""),
                                "full_name": item.get("full_name", ""),
                                "clone_url": item.get("clone_url", ""),
                                "html_url": item.get("html_url", ""),
                                "default_branch": item.get("default_branch", "main"),
                                "is_private": item.get("private", False),
                                "description": item.get("description") or "",
                                "updated_at": item.get("updated_at", ""),
                            })
                        if len(items) < per_page:
                            break
                        page += 1
                        if page > 10:  # Límite de seguridad
                            break
                    else:
                        return False, all_repos, f"GitHub devolvió el código de estado: {resp.status}"
            except urllib.error.HTTPError as http_err:
                if http_err.code == 401:
                    return False, all_repos, "Tu sesión de GitHub expiró. Por favor vuelve a iniciar sesión."
                return False, all_repos, f"Error al consultar GitHub ({http_err.code}): {http_err.reason}"
            except urllib.error.URLError as url_err:
                return False, all_repos, f"No se pudo conectar a GitHub:\n{url_err.reason}"
            except Exception as exc:
                return False, all_repos, f"Error inesperado al obtener repositorios: {exc}"

        return True, all_repos, ""

    def get_user_repositories(self, repo_path: Optional[str] = None) -> List[Dict[str, str]]:
        """Obtiene la lista de repositorios del usuario (compatibilidad con llamadas previas)."""
        succ, repos, _ = self.get_all_user_repositories()
        if succ:
            return repos
        return []

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
