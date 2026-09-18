"""Traductor de errores de Git a lenguaje amigable para estudiantes.

Analiza las salidas crudas de error de Git (stderr/stdout) y las traduce
a explicaciones sencillas en español con soluciones claras, preservando
el detalle técnico para inspección bajo demanda.
"""

from typing import Dict, Any, Optional


class ErrorTranslator:
    """Traduce mensajes de error técnicos de Git a español comprensible."""

    @staticmethod
    def translate(
        stderr: str,
        stdout: str = "",
        context_cmd: str = "",
        returncode: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Analiza la salida de Git y devuelve un diagnóstico amigable con causa y acción sugerida."""
        raw_text = f"{stderr}\n{stdout}".strip()
        lower = raw_text.lower()
        code_str = f" (Código de salida: {returncode})" if returncode is not None else ""

        # 1. Identidad de Git no configurada (user.name / user.email)
        if any(keyword in lower for keyword in [
            "please tell me who you are",
            "unable to auto-detect email address",
            "author identity unknown",
            "empty ident name",
            "no name was given",
            "committer identity unknown",
        ]):
            return {
                "title": f"⚠️ Identidad de Git no configurada{code_str}",
                "message": (
                    "Git no sabe quién está realizando los cambios porque no tienes "
                    "configurado tu nombre ni tu correo electrónico en esta computadora.\n\n"
                    "Es necesario para que tus compañeros y profesores sepan quién hizo cada aporte."
                ),
                "severity": "warning",
                "cause": "missing_identity",
                "suggested_action": "Haz clic en 'Identidad Git y Ajustes' o ingresa tu nombre y correo para continuar.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 2. Archivo index.lock trabado o archivo bloqueado por Windows
        if any(keyword in lower for keyword in [
            "index.lock",
            "another git process seems to be running",
            "unable to create",
            "unable to unlink",
            "device or resource busy",
            "another process is using the file",
        ]) or ("permission denied" in lower and "index" in lower):
            return {
                "title": f"⚠️ Archivo de Git bloqueado por Windows (index.lock){code_str}",
                "message": (
                    "Git no puede guardar porque hay un archivo de bloqueo temporal activo (.git/index.lock).\n\n"
                    "Esto suele ocurrir si otra operación de Git anterior fue interrumpida bruscamente "
                    "o si un editor (como VS Code) o antivirus está inspeccionando la carpeta."
                ),
                "severity": "warning",
                "cause": "locked_file",
                "suggested_action": "Cierra editores o programas que usen la carpeta. Si el bloqueo persiste, puedes presionar 'Limpiar Bloqueo index.lock'.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 3. Merge o Rebase a medias / inconcluso
        if any(keyword in lower for keyword in [
            "you have not concluded your merge",
            "merge_head exists",
            "cannot do a partial commit during a merge",
            "rebase in progress",
            "cherry-pick in progress",
            "you need to resolve your current index first",
            "rebase-apply",
            "rebase-merge",
        ]):
            return {
                "title": f"⚠️ Fusión (Merge) o actualización pendiente sin terminar{code_str}",
                "message": (
                    "Hay una operación de integración de cambios que quedó a mitad de camino.\n\n"
                    "Git necesita que termines de confirmar la fusión o que canceles la operación "
                    "inconclusa para poder volver al estado seguro anterior."
                ),
                "severity": "warning",
                "cause": "merge_in_progress",
                "suggested_action": "Haz clic en 'Cancelar Fusión Inconclusa' para volver al estado anterior o resuelve los archivos pendientes.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 4. Conflictos sin resolver en archivos (unmerged)
        if any(keyword in lower for keyword in [
            "fix conflicts and then commit",
            "unmerged paths",
            "you have unmerged paths",
            "unmerged files",
            "conflict (content)",
            "automatic merge failed",
            "merge conflict in",
        ]):
            return {
                "title": f"⚠️ Conflicto entre versiones{code_str}",
                "message": (
                    "Git detectó que tú y otro compañero modificaron las mismas líneas del mismo archivo.\n\n"
                    "Tus archivos NO fueron eliminados. Tienen marcas '<<<<<<<' que deben revisarse antes de poder guardar."
                ),
                "severity": "warning",
                "cause": "unresolved_conflicts",
                "suggested_action": "Abre los archivos indicados en tu editor, elige qué código conservar, guárdalos e inténtalo de nuevo.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 5. Falta de conexión a Internet / DNS
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
                "title": f"🔴 Sin conexión con GitHub{code_str}",
                "message": (
                    "No se pudo conectar con los servidores de GitHub.\n\n"
                    "Comprueba que la computadora escolar tenga acceso a Internet (WiFi o cable de red)."
                ),
                "severity": "error",
                "cause": "network_error",
                "suggested_action": "Verifica tu conexión a Internet y vuelve a intentar.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 6. Autenticación fallida / Permiso denegado
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
                "title": f"🔴 GitHub no conectado o sin permiso{code_str}",
                "message": (
                    "No se pudo validar tu cuenta de GitHub o no tienes permisos de escritura "
                    "en este repositorio escolar.\n\n"
                    "Haz clic en 'Iniciar sesión' o comprueba que tu usuario tenga acceso de colaborador."
                ),
                "severity": "error",
                "cause": "auth_error",
                "suggested_action": "Haz clic en 'Iniciar sesión' o comprueba que seas colaborador del repositorio en GitHub.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 7. Push rechazado porque hay cambios remotos (non-fast-forward)
        if any(keyword in lower for keyword in [
            "failed to push some refs",
            "updates were rejected because the remote contains work",
            "fetch first",
            "[rejected]",
            "non-fast-forward",
        ]):
            return {
                "title": f"⚠️ Cambios nuevos en GitHub{code_str}",
                "message": (
                    "GitHub rechazó el envío porque un compañero de equipo subió cambios antes.\n\n"
                    "Tus cambios locales están completamente a salvo.\n"
                    "Primero haz clic en [ 📥 TRAER CAMBIOS ] para incorporar su trabajo y luego vuelve a crear el backup."
                ),
                "severity": "warning",
                "cause": "push_rejected_remote_work",
                "suggested_action": "Presiona [ 📥 TRAER CAMBIOS ] para integrar el trabajo del equipo antes de enviar el tuyo.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 8. Cambios locales que impiden checkout o pull
        if any(keyword in lower for keyword in [
            "your local changes to the following files would be overwritten",
            "please commit your changes or stash them before you switch branches",
            "please commit your changes or stash them before you merge",
        ]):
            return {
                "title": f"⚠️ Tienes cambios locales sin guardar{code_str}",
                "message": (
                    "Tienes archivos modificados en tu proyecto que entrarían en conflicto si traes cambios o cambias de rama.\n\n"
                    "Para no perder nada, primero haz clic en [ 📤 CREAR BACKUP ] o crea una rama nueva de respaldo."
                ),
                "severity": "warning",
                "cause": "local_changes_blocking",
                "suggested_action": "Crea un backup o crea una rama nueva con tus archivos antes de continuar.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 9. No hay cambios para guardar
        if any(keyword in lower for keyword in [
            "nothing to commit",
            "working tree clean",
        ]):
            return {
                "title": f"ℹ️ Sin cambios pendientes{code_str}",
                "message": "No hay archivos modificados ni nuevos para guardar en el backup.",
                "severity": "info",
                "cause": "clean_working_tree",
                "suggested_action": "Modifica o agrega archivos en tu proyecto antes de crear un nuevo backup.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # 10. Repositorio no encontrado o no es repositorio git
        if "not a git repository" in lower:
            return {
                "title": f"⚠️ Carpeta no es un repositorio Git{code_str}",
                "message": (
                    "La carpeta seleccionada no contiene un proyecto Git válido (.git).\n\n"
                    "Selecciona la carpeta correcta de tu proyecto escolar o pulsa 'Vincular con GitHub'."
                ),
                "severity": "warning",
                "cause": "not_a_repo",
                "suggested_action": "Selecciona una carpeta válida o usa el asistente de vinculación.",
                "exit_code": returncode,
                "stderr": stderr,
                "stdout": stdout,
                "raw": raw_text,
                "command": context_cmd,
            }

        # Fallback para otros errores no catalogados
        return {
            "title": f"⚠️ Error en la operación de Git{code_str}",
            "message": (
                "La operación de Git no pudo completarse satisfactoriamente.\n"
                "Revisa el detalle técnico para ver la causa exacta reportada por Git."
            ),
            "severity": "error",
            "cause": "unknown",
            "suggested_action": "Consulta el mensaje de error de Git (stderr) y el código de salida detallado en pantalla.",
            "exit_code": returncode,
            "stderr": stderr,
            "stdout": stdout,
            "raw": raw_text if raw_text else "No hubo mensaje de salida.",
            "command": context_cmd,
        }
