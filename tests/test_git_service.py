"""Pruebas unitarias para GitService."""

import unittest
import os
import tempfile
import subprocess
from src.git_service import GitService


class TestGitService(unittest.TestCase):
    """Verifica la ejecución segura de Git y manejo de repositorios."""

    def setUp(self):
        self.service = GitService()

    def test_git_availability(self):
        self.assertTrue(self.service.is_git_available())
        version = self.service.get_git_version()
        self.assertTrue("git" in version.lower())

    def test_count_folder_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Crear 3 archivos y 2 subcarpetas
            os.makedirs(os.path.join(temp_dir, "carpeta1", "subcarpeta"))
            os.makedirs(os.path.join(temp_dir, "carpeta2"))
            with open(os.path.join(temp_dir, "archivo1.txt"), "w") as f:
                f.write("a")
            with open(os.path.join(temp_dir, "carpeta1", "archivo2.txt"), "w") as f:
                f.write("b")
            with open(os.path.join(temp_dir, "carpeta1", "subcarpeta", "archivo3.txt"), "w") as f:
                f.write("c")

            files, dirs = self.service.count_folder_contents(temp_dir)
            self.assertEqual(files, 3)
            self.assertEqual(dirs, 3)

    def test_init_and_configure_normal_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Comprobar que inicialmente NO es repositorio
            self.assertFalse(self.service.is_git_repository(temp_dir))

            # 2. Inicializar
            succ_init, msg_init = self.service.init_repository(temp_dir)
            self.assertTrue(succ_init)
            self.assertTrue(self.service.is_git_repository(temp_dir))

            # 3. Configurar remoto
            remote_url = "https://github.com/UsuarioColegio/ProyectoTest.git"
            succ_rem, msg_rem = self.service.add_remote(temp_dir, remote_url, "origin")
            self.assertTrue(succ_rem)

            # 4. Verificar remoto con git remote -v
            succ_v, out_v = self.service.verify_remote(temp_dir, "origin")
            self.assertTrue(succ_v)
            self.assertIn("ProyectoTest.git", out_v)

            # 5. Configurar identidad local
            succ_id, _ = self.service.set_git_identity("Estudiante A", "estudiante@escuela.edu", temp_dir, is_global=False)
            self.assertTrue(succ_id)

            name, email = self.service.get_git_identity(temp_dir)
            self.assertEqual(name, "Estudiante A")
            self.assertEqual(email, "estudiante@escuela.edu")

    def test_special_characters_in_commit_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Alumno Test"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "alumno@colegio.edu"], cwd=temp_dir, check=True)

            test_file = os.path.join(temp_dir, "archivo.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("contenido de prueba")

            tricky_message = 'Prueba "con comillas", tildes: áéíóú ñ, símbolos: $VAR & | ; `dir` && echo 123'
            success, msg, diag = self.service.create_backup(temp_dir, tricky_message)

            success_log, log_out, _ = self.service.run_command(["log", "-1", "--format=%s"], cwd=temp_dir)
            self.assertTrue(success_log)
    def test_internal_log_filtering(self):
        """Verifica que archivos de log de la aplicación no se consideren cambios de código del proyecto."""
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Alumno Test"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "alumno@colegio.edu"], cwd=temp_dir, check=True)

            # Crear un archivo de log interno
            logs_dir = os.path.join(temp_dir, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            with open(os.path.join(logs_dir, "app.log"), "w", encoding="utf-8") as f:
                f.write("2026-09-17 [INFO] Operacion interna\n")

            # get_status_porcelain y has_local_changes no deben reportar el app.log
            has_changes, changes = self.service.has_local_changes(temp_dir)
            self.assertFalse(has_changes)
            self.assertEqual(len(changes), 0)

            # Si ahora agregamos un archivo real de código del proyecto
            with open(os.path.join(temp_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write("<h1>Hola</h1>")

            has_changes2, changes2 = self.service.has_local_changes(temp_dir)
            self.assertTrue(has_changes2)
            self.assertEqual(len(changes2), 1)
            self.assertIn("index.html", changes2[0])

    def test_create_branch(self):
        """Verifica la creación y cambio de rama sin perder cambios locales."""
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Alumno Test"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "alumno@colegio.edu"], cwd=temp_dir, check=True)

            # Primer commit inicial
            with open(os.path.join(temp_dir, "archivo1.txt"), "w", encoding="utf-8") as f:
                f.write("contenido inicial")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Commit inicial"], cwd=temp_dir, check=True)

            # Crear rama nueva
            succ, msg, diag = self.service.create_branch(temp_dir, "nueva-rama-test", checkout=True)
            self.assertTrue(succ)
            self.assertEqual(diag["branch"], "nueva-rama-test")

            # Verificar que la rama activa sea la nueva
            branches, current = self.service.get_branches(temp_dir)
            self.assertEqual(current, "nueva-rama-test")
            self.assertIn("nueva-rama-test", branches)

    def test_cleanup_index_lock(self):
        """Verifica la eliminación de un index.lock atascado."""
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
            git_dir = os.path.join(temp_dir, ".git")
            lock_file = os.path.join(git_dir, "index.lock")
            with open(lock_file, "w") as f:
                f.write("bloqueo simulado")

            self.assertTrue(os.path.exists(lock_file))
            succ, msg = self.service.cleanup_index_lock(temp_dir)
            self.assertTrue(succ)
            self.assertFalse(os.path.exists(lock_file))


if __name__ == "__main__":
    unittest.main()
