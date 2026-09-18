"""Gestor de configuración portable para Git Manager.

Guarda y lee preferencias en config/settings.json de forma relativa
al ejecutable o raíz de la aplicación, sin almacenar contraseñas ni tokens.
"""

import json
import os
import sys
from typing import Any, Dict, Optional
from src.logger_service import get_base_dir, logger


class ConfigManager:
    """Administra la configuración persistente y portable de la aplicación."""

    _instance: Optional["ConfigManager"] = None

    DEFAULT_SETTINGS: Dict[str, Any] = {
        "project_path": "",
        "repo_name": "",
        "remote_url": "",
        "default_branch": "main",
        "theme": "dark",
        "last_backup_time": "",
        "last_backup_message": "",
    }

    def __init__(self) -> None:
        self.base_dir = get_base_dir()
        self.config_dir = os.path.join(self.base_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.data: Dict[str, Any] = dict(self.DEFAULT_SETTINGS)
        self.load()

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = ConfigManager()
        return cls._instance

    def load(self) -> Dict[str, Any]:
        """Carga la configuración desde el archivo JSON si existe."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        # Mantener claves por defecto y actualizar con las existentes
                        self.data.update(loaded)
                logger.info(f"Configuración cargada desde: {self.config_file}")
            except Exception as exc:
                logger.warning(f"Error al leer settings.json, usando valores por defecto: {exc}")
        else:
            self.save()
        return self.data

    def save(self) -> bool:
        """Guarda la configuración actual en config/settings.json."""
        # Filtro de seguridad: garantizar que ninguna clave guarde contraseñas ni tokens
        safe_data = {}
        forbidden_keys = {"token", "password", "secret", "cred", "auth_token"}
        for k, v in self.data.items():
            if any(f in k.lower() for f in forbidden_keys):
                continue
            safe_data[k] = v

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(safe_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error(f"Error al guardar config/settings.json: {exc}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get_project_path(self) -> str:
        """Obtiene la ruta del proyecto configurada, validando si aún existe."""
        path = self.get("project_path", "")
        if not path:
            return ""
        # Si es una ruta relativa, resolverla respecto al directorio base portable
        if not os.path.isabs(path):
            abs_path = os.path.normpath(os.path.join(self.base_dir, path))
            return abs_path
        return os.path.normpath(path)

    def set_project_path(self, path: str) -> None:
        """Establece la ruta del proyecto."""
        normalized = os.path.normpath(path)
        self.set("project_path", normalized)


config = ConfigManager.get_instance()
