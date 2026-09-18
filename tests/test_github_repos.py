"""Pruebas unitarias para las funciones de creación y visualización de repositorios de GitHub."""

import io
import json
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

from src.github_auth import github_auth, format_github_date


class TestGitHubRepos(unittest.TestCase):
    """Pruebas de la API de repositorios de GitHub (POST y GET)."""

    def test_format_github_date(self):
        """Verifica la conversión de fechas ISO 8601 a formato legible."""
        iso = "2026-09-17T21:30:45Z"
        formatted = format_github_date(iso)
        self.assertEqual(formatted, "17/09/2026 21:30")

        self.assertEqual(format_github_date(""), "Fecha desconocida")
        self.assertEqual(format_github_date("invalid"), "invalid")

    @patch.object(github_auth, "get_active_token", return_value="gho_mock_token_12345")
    @patch("urllib.request.urlopen")
    def test_create_repository_success(self, mock_urlopen, mock_token):
        """Verifica la creación exitosa de un repositorio en GitHub vía POST /user/repos."""
        mock_resp = MagicMock()
        mock_resp.status = 201
        payload = {
            "name": "proyecto-ciencias",
            "full_name": "Alan222-coder/proyecto-ciencias",
            "clone_url": "https://github.com/Alan222-coder/proyecto-ciencias.git",
            "html_url": "https://github.com/Alan222-coder/proyecto-ciencias",
            "private": True,
        }
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        succ, msg, data = github_auth.create_repository(
            name="proyecto-ciencias",
            description="Proyecto para la feria de ciencias",
            is_private=True,
        )

        self.assertTrue(succ)
        self.assertIn("éxito", msg.lower())
        self.assertEqual(data["name"], "proyecto-ciencias")
        self.assertEqual(data["clone_url"], "https://github.com/Alan222-coder/proyecto-ciencias.git")

    @patch.object(github_auth, "get_active_token", return_value="gho_mock_token_12345")
    @patch("urllib.request.urlopen")
    def test_create_repository_already_exists(self, mock_urlopen, mock_token):
        """Verifica que el error 422 de nombre duplicado sea traducido en lenguaje claro."""
        err_body = json.dumps({
            "message": "Repository creation failed.",
            "errors": [
                {
                    "resource": "Repository",
                    "code": "custom",
                    "field": "name",
                    "message": "name already exists on this account",
                }
            ],
        }).encode("utf-8")

        http_err = urllib.error.HTTPError(
            url="https://api.github.com/user/repos",
            code=422,
            msg="Unprocessable Entity",
            hdrs=None,
            fp=io.BytesIO(err_body),
        )
        mock_urlopen.side_effect = http_err

        succ, msg, data = github_auth.create_repository(
            name="proyecto-existente",
            description="",
            is_private=True,
        )

        self.assertFalse(succ)
        self.assertIn("Ya tienes un repositorio llamado 'proyecto-existente'", msg)

    @patch.object(github_auth, "get_active_token", return_value="gho_mock_token_12345")
    @patch("urllib.request.urlopen")
    def test_create_repository_unauthorized(self, mock_urlopen, mock_token):
        """Verifica que el error 401 explique que la sesión expiró o faltan permisos."""
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/user/repos",
            code=401,
            msg="Bad credentials",
            hdrs=None,
            fp=io.BytesIO(b'{"message": "Bad credentials"}'),
        )
        mock_urlopen.side_effect = http_err

        succ, msg, data = github_auth.create_repository(
            name="nuevo-repo",
            description="",
            is_private=True,
        )

        self.assertFalse(succ)
        self.assertIn("sesión de GitHub ha expirado", msg)

    @patch.object(github_auth, "get_active_token", return_value="gho_mock_token_12345")
    @patch("urllib.request.urlopen")
    def test_get_all_user_repositories_pagination(self, mock_urlopen, mock_token):
        """Verifica que la consulta pagine y recopile todos los repositorios."""
        page1 = [{"name": f"repo-{i}", "clone_url": f"https://.../repo-{i}.git"} for i in range(100)]
        page2 = [{"name": "repo-100", "clone_url": "https://.../repo-100.git"}]

        resp1 = MagicMock()
        resp1.status = 200
        resp1.read.return_value = json.dumps(page1).encode("utf-8")

        resp2 = MagicMock()
        resp2.status = 200
        resp2.read.return_value = json.dumps(page2).encode("utf-8")

        # Context manager returns resp1 on first call, resp2 on second
        mock_urlopen.return_value.__enter__.side_effect = [resp1, resp2]

        succ, repos, err = github_auth.get_all_user_repositories()

        self.assertTrue(succ)
        self.assertEqual(len(repos), 101)
        self.assertEqual(repos[0]["name"], "repo-0")
        self.assertEqual(repos[100]["name"], "repo-100")


if __name__ == "__main__":
    unittest.main()
