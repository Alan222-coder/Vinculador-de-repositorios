"""Punto de entrada principal para Git Manager.

Inicializa el sistema de logs, comprueba la configuración y arranca
la interfaz gráfica de usuario.
"""

import sys
import os

# Asegurar que el directorio raíz de la aplicación esté en el sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from src.logger_service import logger
from src.app_gui import start_app


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Captura excepciones no controladas y las registra en los logs de forma sanitizada."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error(f"Excepción no controlada: {exc_type.__name__}: {exc_value}")


def main() -> None:
    """Función principal."""
    sys.excepthook = handle_uncaught_exception
    logger.info("=== Iniciando Git Manager ===")
    try:
        start_app()
    except Exception as exc:
        logger.error(f"Error crítico al ejecutar la aplicación: {exc}")
        sys.exit(1)
    finally:
        logger.info("=== Git Manager cerrado ===")


if __name__ == "__main__":
    main()
