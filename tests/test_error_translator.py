"""Pruebas unitarias para ErrorTranslator."""

import unittest
from src.error_translator import ErrorTranslator


class TestErrorTranslator(unittest.TestCase):
    """Verifica que los mensajes de Git se traduzcan correctamente al español comprensible."""

    def test_translate_no_internet(self):
        stderr = "fatal: unable to access 'https://github.com/org/repo.git/': Could not resolve host: github.com"
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git push")
        self.assertIn("Sin conexión con GitHub", res["title"])
        self.assertIn("Internet", res["message"])
        self.assertEqual(res["severity"], "error")

    def test_translate_rejected_push_non_fast_forward(self):
        stderr = (
            "To https://github.com/org/repo.git\n"
            " ! [rejected]        main -> main (fetch first)\n"
            "error: failed to push some refs to 'https://github.com/org/repo.git'\n"
            "hint: Updates were rejected because the remote contains work that you do not have locally."
        )
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git push origin main")
        self.assertIn("Cambios nuevos en GitHub", res["title"])
        self.assertIn("TRAER CAMBIOS", res["message"])
        self.assertEqual(res["severity"], "warning")

    def test_translate_merge_conflict(self):
        stderr = (
            "Auto-merging index.html\n"
            "CONFLICT (content): Merge conflict in index.html\n"
            "Automatic merge failed; fix conflicts and then commit the result."
        )
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git pull")
        self.assertIn("Conflicto entre versiones", res["title"])
        self.assertIn("NO fueron eliminados", res["message"])
        self.assertEqual(res["severity"], "warning")

    def test_translate_auth_failure(self):
        stderr = "fatal: Authentication failed for 'https://github.com/org/repo.git/'"
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git push")
        self.assertIn("GitHub no conectado", res["title"])
        self.assertIn("Iniciar sesión", res["message"])
        self.assertEqual(res["severity"], "error")

    def test_translate_local_changes_blocking(self):
        stderr = (
            "error: Your local changes to the following files would be overwritten by checkout:\n"
            "        app.js\n"
            "Please commit your changes or stash them before you switch branches."
        )
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git checkout desarrollo")
        self.assertIn("cambios locales sin guardar", res["title"])
        self.assertIn("CREAR BACKUP", res["message"])
        self.assertEqual(res["severity"], "warning")


    def test_translate_missing_identity(self):
        stderr = (
            "Author identity unknown\n\n"
            "*** Please tell me who you are.\n\n"
            "Run\n\n"
            "  git config --global user.email \"you@example.com\"\n"
            "  git config --global user.name \"Your Name\"\n\n"
            "fatal: unable to auto-detect email address (got 'User@PC.(none)')"
        )
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git commit", returncode=128)
        self.assertIn("Identidad de Git no configurada", res["title"])
        self.assertEqual(res["cause"], "missing_identity")
        self.assertEqual(res["exit_code"], 128)
        self.assertIn("Identidad Git y Ajustes", res["suggested_action"])

    def test_translate_index_lock(self):
        stderr = (
            "fatal: Unable to create 'C:/project/.git/index.lock': File exists.\n"
            "Another git process seems to be running in this repository"
        )
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git add .", returncode=128)
        self.assertIn("index.lock", res["title"])
        self.assertEqual(res["cause"], "locked_file")
        self.assertIn("Limpiar Bloqueo", res["suggested_action"])

    def test_translate_merge_in_progress(self):
        stderr = "fatal: cannot do a partial commit during a merge.\nMerge_head exists."
        res = ErrorTranslator.translate(stderr=stderr, context_cmd="git commit", returncode=1)
        self.assertIn("Fusión (Merge)", res["title"])
        self.assertEqual(res["cause"], "merge_in_progress")
        self.assertIn("Cancelar Fusión", res["suggested_action"])


if __name__ == "__main__":
    unittest.main()
