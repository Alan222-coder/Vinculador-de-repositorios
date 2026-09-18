"""Inspector de seguridad de archivos sensibles para Git Manager.

Previene que estudiantes suban accidentalmente archivos .env, contraseñas,
claves privadas o tokens a repositorios públicos o compartidos de GitHub.
"""

import os
import re
from typing import List, Tuple, Dict, Any


# Patrones de nombres de archivo sensibles y peligrosos
SENSITIVE_FILENAME_PATTERNS = [
    # Archivos de entorno
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r".*\.env$", re.IGNORECASE),
    # Claves SSH y certificados privados
    re.compile(r"^id_(rsa|dsa|ecdsa|ed25519).*$", re.IGNORECASE),
    re.compile(r".*\.(pem|key|pkcs12|pfx|p12|keystore|kdbx)$", re.IGNORECASE),
    # Credenciales de servicios en la nube / APIs
    re.compile(r"^credentials(\..+)?\.json$", re.IGNORECASE),
    re.compile(r"^service[-_]?account.*\.json$", re.IGNORECASE),
    re.compile(r"^client[-_]?secret.*\.json$", re.IGNORECASE),
    # Archivos explícitos de contraseñas o tokens
    re.compile(r".*(password|contrase[nñ]a|clave|secret|token).*\.(txt|json|yml|yaml|ini|env|cfg)$", re.IGNORECASE),
]


class SecurityChecker:
    """Verifica si los archivos que van a subirse contienen datos sensibles."""

    @classmethod
    def is_sensitive_filename(cls, filename: str) -> bool:
        """Determina si un nombre de archivo o ruta coincide con un patrón sensible."""
        basename = os.path.basename(filename).strip()
        for pattern in SENSITIVE_FILENAME_PATTERNS:
            if pattern.search(basename):
                return True
        return False

    @classmethod
    def inspect_changed_files(cls, status_porcelain_lines: List[str]) -> Tuple[bool, List[str]]:
        """Analiza la salida de 'git status --porcelain' y detecta archivos de riesgo.

        Retorna:
            (es_seguro, lista_de_archivos_peligrosos)
        """
        dangerous_files = []
        for line in status_porcelain_lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue

            # El formato porcelain es XY PATH o XY "PATH"
            # O en caso de renombrado: R  ORIGINAL -> NEW
            file_part = line[2:].strip()
            if " -> " in file_part:
                # Caso de renombrado
                _, file_part = file_part.split(" -> ", 1)

            file_part = file_part.strip('"\'')
            if cls.is_sensitive_filename(file_part):
                dangerous_files.append(file_part)

        is_safe = len(dangerous_files) == 0
        return is_safe, dangerous_files

    @classmethod
    def format_security_alert(cls, dangerous_files: List[str]) -> Dict[str, Any]:
        """Genera un mensaje de alerta comprensible para el usuario."""
        file_list_str = "\n".join([f"  • {f}" for f in dangerous_files])
        message = (
            "⚠️ ¡ATENCIÓN: ARCHIVO PRIVADO DETECTADO!\n\n"
            "La aplicación detectó archivos que comúnmente contienen contraseñas, "
            "claves de bases de datos o secretos privados:\n\n"
            f"{file_list_str}\n\n"
            "POR SEGURIDAD, EL BACKUP SE HA DETENIDO.\n\n"
            "Tus archivos NO han sido eliminados.\n"
            "Te recomendamos agregarlos al archivo '.gitignore' para no subirlos a GitHub."
        )
        return {
            "title": "⚠️ Alerta de Seguridad - Datos Privados",
            "message": message,
            "dangerous_files": dangerous_files,
        }
