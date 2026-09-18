"""Pruebas unitarias para SecurityChecker."""

import unittest
from src.security_checker import SecurityChecker


class TestSecurityChecker(unittest.TestCase):
    """Verifica la correcta detección y bloqueo de archivos sensibles."""

    def test_blocks_env_files(self):
        env_files = [
            ".env",
            ".env.local",
            ".env.production",
            ".env.test",
            "frontend/.env",
            "backend/.env.development",
        ]
        for f in env_files:
            self.assertTrue(
                SecurityChecker.is_sensitive_filename(f),
                f"El archivo '{f}' debería ser clasificado como sensible."
            )

    def test_blocks_keys_and_certificates(self):
        key_files = [
            "id_rsa",
            "id_ed25519",
            "server.key",
            "cert.pem",
            "keystore.pfx",
            "auth.kdbx",
        ]
        for f in key_files:
            self.assertTrue(
                SecurityChecker.is_sensitive_filename(f),
                f"La clave/certificado '{f}' debería ser clasificado como sensible."
            )

    def test_blocks_credentials_and_secrets(self):
        secret_files = [
            "credentials.json",
            "client_secret_xyz.json",
            "service_account.json",
            "passwords.txt",
            "mis_contraseñas.txt",
            "api_token.json",
        ]
        for f in secret_files:
            self.assertTrue(
                SecurityChecker.is_sensitive_filename(f),
                f"El archivo de credenciales '{f}' debería ser sensible."
            )

    def test_allows_safe_project_files(self):
        safe_files = [
            "index.html",
            "style.css",
            "script.js",
            "README.md",
            "app.py",
            "package.json",
            "requirements.txt",
            "logo.png",
            "login_form.html",
            "token_parser_helper.py", # Código fuente que menciona token en el nombre no es archivo de secretos
        ]
        for f in safe_files:
            self.assertFalse(
                SecurityChecker.is_sensitive_filename(f),
                f"El archivo normal '{f}' no debería ser bloqueado."
            )

    def test_inspect_changed_files(self):
        porcelain_output = [
            " M src/main.py",
            "?? .env",
            "A  README.md",
        ]
        is_safe, dangerous = SecurityChecker.inspect_changed_files(porcelain_output)
        self.assertFalse(is_safe)
        self.assertIn(".env", dangerous)

        clean_output = [
            " M src/main.py",
            "?? assets/logo.png",
            "A  README.md",
        ]
        is_safe, dangerous = SecurityChecker.inspect_changed_files(clean_output)
        self.assertTrue(is_safe)
        self.assertEqual(len(dangerous), 0)


if __name__ == "__main__":
    unittest.main()
