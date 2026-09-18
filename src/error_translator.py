"""Traductor de errores de Git a lenguaje amigable para estudiantes.

Analiza las salidas crudas de error de Git (stderr/stdout) y las traduce
a explicaciones sencillas en español con soluciones claras, preservando
el detalle técnico para inspección bajo demanda.
"""

from typing import Dict, Any


class ErrorTranslator:
    """Traduce mensajes de error técnicos de Git a español comprensible."""

    @staticmethod
    def translate(stderr: str, stdout: str = "", context_cmd: str = "") -> Dict[str, Any]:
        """Analiza la salida de Git y devuelve un diagnóstico amigable."""
        raw_text = f"{stderr}\n{stdout}".strip()
        lower = raw_text.lower()

        # 1. Falta de conexión a Internet / DNS
        if any(keyword in lower for keyword in [
            "could not resolve host",
            "unable to access",
            "failed to connect",
            "network is unreachable",
            "connection timed out",
            "operation timed out",
            "connection refused",
        ]):
            return {
                "title": "🔴 Sin conexión con GitHub",
                "message": (
                    "No se pudo conectar con GitHub.\n\n"
                    "Comprueba que la computadora esté conectada a Internet "
                    "(WiFi o cable de red) e inténtalo nuevamente."
                ),
                "severity": "error",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 2. Autenticación fallida / Permiso denegado
        if any(keyword in lower for keyword in [
            "authentication failed",
            "could not read username",
            "permission to",
            "denied to",
            "invalid username or password",
            "403",
            "401",
            "terminal prompts disabled",
        ]):
            return {
                "title": "🔴 GitHub no conectado o sin permiso",
                "message": (
                    "No se pudo validar tu cuenta de GitHub o no tienes permisos de escritura "
                    "en este repositorio escolar.\n\n"
                    "Haz clic en 'Iniciar sesión' o comprueba que tu usuario tenga acceso de colaborador."
                ),
                "severity": "error",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 3. Push rechazado porque hay cambios remotos (non-fast-forward)
        if any(keyword in lower for keyword in [
            "failed to push some refs",
            "updates were rejected because the remote contains work",
            "fetch first",
            "[rejected]",
            "non-fast-forward",
        ]):
            return {
                "title": "⚠️ Cambios nuevos en GitHub",
                "message": (
                    "GitHub rechazó el backup porque un compañero de equipo subió cambios nuevos.\n\n"
                    "Tus cambios locales están completamente a salvo.\n"
                    "Primero haz clic en [ 📥 TRAER CAMBIOS ] para incorporar su trabajo y luego vuelve a crear el backup."
                ),
                "severity": "warning",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 4. Conflicto de fusión (Merge conflict)
        if any(keyword in lower for keyword in [
            "conflict (content)",
            "automatic merge failed",
            "fix conflicts and then commit",
            "merge conflict in",
            "unmerged files",
        ]):
            return {
                "title": "⚠️ Conflicto entre versiones",
                "message": (
                    "Git detectó que tú y otro compañero modificaron las mismas líneas del mismo archivo.\n\n"
                    "Tus archivos NO fueron eliminados ni modificados destructivamente.\n"
                    "Abre los archivos marcados con conflicto en tu editor de código para elegir qué cambios conservar."
                ),
                "severity": "warning",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 5. Cambios locales que impiden checkout o pull
        if any(keyword in lower for keyword in [
            "your local changes to the following files would be overwritten",
            "please commit your changes or stash them before you switch branches",
            "please commit your changes or stash them before you merge",
        ]):
            return {
                "title": "⚠️ Tienes cambios locales sin guardar",
                "message": (
                    "Tienes archivos modificados en tu proyecto que entrarían en conflicto si traes cambios o cambias de rama.\n\n"
                    "Para no perder nada, primero haz clic en [ 📤 CREAR BACKUP ] para guardar tu trabajo actual."
                ),
                "severity": "warning",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 6. Archivos bloqueados en Windows (lstat / file lock)
        if any(keyword in lower for keyword in [
            "unable to unlink",
            "permission denied",
            "unlink failed",
            "device or resource busy",
            "another process is using the file",
        ]):
            return {
                "title": "⚠️ Archivo bloqueado en Windows",
                "message": (
                    "Un archivo del proyecto está abierto o bloqueado por otra aplicación (como VS Code, Word, Excel o un servidor local en ejecución).\n\n"
                    "Cierra o detén la aplicación que lo esté usando e inténtalo de nuevo."
                ),
                "severity": "warning",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 7. No hay cambios para guardar
        if any(keyword in lower for keyword in [
            "nothing to commit",
            "working tree clean",
        ]):
            return {
                "title": "ℹ️ Sin cambios pendientes",
                "message": "No hay archivos modificados ni nuevos para guardar en el backup.",
                "severity": "info",
                "raw": raw_text,
                "command": context_cmd,
            }

        # 8. Repositorio no encontrado o no es repositorio git
        if "not a git repository" in lower:
            return {
                "title": "⚠️ Carpeta no es un repositorio Git",
                "message": (
                    "La carpeta seleccionada no contiene un proyecto Git válido (.git).\n\n"
                    "Selecciona la carpeta correcta de tu proyecto escolar en Configuración."
                ),
                "severity": "warning",
                "raw": raw_text,
                "command": context_cmd,
            }

        # Fallback genérico para otros errores
        return {
            "title": "⚠️ Error en la operación",
            "message": (
                "La operación de Git no pudo completarse satisfactoriamente.\n"
                "Puedes consultar los detalles técnicos para más información."
            ),
            "severity": "error",
            "raw": raw_text if raw_text else "No hubo mensaje de salida.",
            "command": context_cmd,
        }
