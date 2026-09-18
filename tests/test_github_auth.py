"""Pruebas unitarias para GitHubAuthService y almacenamiento seguro DPAPI."""

import unittest
from src.github_auth import github_auth, dpapi_encrypt, dpapi_decrypt


class TestGitHubAuth(unittest.TestCase):
    """Verifica la lógica de autenticación y validación de pistas manuales."""

    def test_dpapi_encryption_roundtrip(self):
        secret = b"token_secreto_super_seguro_github_12345"
        encrypted = dpapi_encrypt(secret)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(secret, encrypted)

        decrypted = dpapi_decrypt(encrypted)
        self.assertEqual(secret, decrypted)

    def test_manual_hint_verification_matches(self):
        # Coincidencia exacta por usuario
        matches, _ = github_auth.verify_manual_hint_against_login("Alan222-coder", "Alan222-coder", "alan@mail.com")
        self.assertTrue(matches)

        # Coincidencia insensible a mayúsculas
        matches, _ = github_auth.verify_manual_hint_against_login("alan222-coder", "Alan222-coder", "alan@mail.com")
        self.assertTrue(matches)

        # Coincidencia por correo
        matches, _ = github_auth.verify_manual_hint_against_login("alan@mail.com", "Alan222-coder", "alan@mail.com")
        self.assertTrue(matches)

    def test_manual_hint_verification_mismatch_warns(self):
        matches, msg = github_auth.verify_manual_hint_against_login("otro-usuario", "Alan222-coder", "alan@mail.com")
        self.assertFalse(matches)
        self.assertIn("otro-usuario", msg)
        self.assertIn("Alan222-coder", msg)


if __name__ == "__main__":
    unittest.main()
