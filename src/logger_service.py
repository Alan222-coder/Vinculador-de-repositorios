"""Servicio de registro (logging) local para Git Manager.

Registra operaciones de forma sanitizada en logs/app.log.
Elimina tokens, contraseñas y credenciales de cualquier mensaje antes de guardarlo.
"""

import os
import re
import sys
import logging
from datetime import datetime
from typing import Optional


def get_base_dir() -> str:
    """Obtiene el directorio base de la aplicación de manera portable.

    Funciona tanto al ejecutarse como script de Python como al compilarse en .exe.
    """
    if getattr(sys, "frozen", False):
        # Ejecutable compilado con PyInstaller
        return os.path.dirname(sys.executable)
    # Ejecutándose como script en desarrollo
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Expresiones regulares para censurar credenciales y datos sensibles
_PATTERNS_TO_MASK = [
    # Tokens de GitHub (clásicos y de grano fino)
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"), "[GITHUB_TOKEN_OCULTO]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{50,255}"), "[GITHUB_PAT_OCULTO]"),
    # URLs con usuario:contraseña embebidos (https://usuario:token@github.com/...)
    (re.compile(r"https?://([^:\s]+):([^@\s]+)@"), r"https://\1:[OCULTO]@"),
    # Cabeceras de autorización
    (re.compile(r"(Authorization:\s*(Bearer|token)\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE), r"\1[TOKEN_OCULTO]"),
    # Argumentos típicos de contraseña
    (re.compile(r"(--password[=\s]+)(\S+)", re.IGNORECASE), r"\1[PASS_OCULTO]"),
]


def sanitize_text(text: str) -> str:
    """Elimina tokens, contraseñas o URLs con credenciales de una cadena de texto."""
    if not text:
        return ""
    sanitized = str(text)
    for pattern, replacement in _PATTERNS_TO_MASK:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class SafeFormatter(logging.Formatter):
    """Formateador de logs que sanitiza automáticamente cada registro."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return sanitize_text(original)


class AppLogger:
    """Gestor de logging centralizado para la aplicación."""

    _instance: Optional["AppLogger"] = None

    def __init__(self) -> None:
        self.base_dir = get_base_dir()
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file = os.path.join(self.logs_dir, "app.log")

        self.logger = logging.getLogger("GitManager")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()

        # Manejador de archivo rotativo o append estándar
        try:
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8", mode="a")
            file_handler.setLevel(logging.INFO)
            formatter = SafeFormatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as exc:
            # Si el pendrive o carpeta fuese de solo lectura, continuar sin fallar
            sys.stderr.write(f"No se pudo inicializar log en archivo: {exc}\n")

    @classmethod
    def get(cls) -> "AppLogger":
        if cls._instance is None:
            cls._instance = AppLogger()
        return cls._instance

    def info(self, message: str) -> None:
        self.logger.info(sanitize_text(message))

    def warning(self, message: str) -> None:
        self.logger.warning(sanitize_text(message))

    def error(self, message: str) -> None:
        self.logger.error(sanitize_text(message))

    def log_operation(self, operation: str, result: str, details: str = "") -> None:
        """Registra una operación en el formato estándar requerido."""
        msg = f"Operación: {operation} | Resultado: {result}"
        if details:
            msg += f" | Detalles: {details}"
        self.info(msg)


logger = AppLogger.get()
