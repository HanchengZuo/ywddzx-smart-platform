"""Version checks use temporary metadata and isolated Flask routes, without a DB."""

import ast
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask, jsonify

from frontend_version import development_frontend_version


class FrontendVersionTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.package_path = Path(folder.name) / "package.json"
        self.env = {
            "APP_ENV": "development",
            "APP_FRONTEND_VERSION": "9.5.0",
            "APP_FRONTEND_PACKAGE_PATH": str(self.package_path),
        }
        self.write_package({"version": "9.8.0"})

    def write_package(self, value):
        self.package_path.write_text(json.dumps(value), encoding="utf-8")

    def test_development_metadata_overrides_stale_configuration(self):
        self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.8.0")

    def test_live_changes_do_not_require_a_backend_restart(self):
        self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.8.0")
        self.write_package({"version": "9.8.1"})
        self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.8.1")

    def test_production_always_uses_deployed_version(self):
        for environment in ("production", "staging"):
            self.env["APP_ENV"] = environment
            with patch("builtins.open", side_effect=AssertionError("must not read metadata")):
                self.assertEqual(development_frontend_version("9.7", environ=self.env), "9.7")

    def test_missing_or_invalid_metadata_uses_fallback(self):
        for value in ({}, [], {"version": 9.8}, {"version": ""}, {"version": "invalid"}):
            with self.subTest(value=value):
                self.write_package(value)
                self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.5")
        self.package_path.write_text("{", encoding="utf-8")
        self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.5")
        self.package_path.unlink()
        self.assertEqual(development_frontend_version("9.5", environ=self.env), "9.5")

    def test_version_endpoint_retains_contract_and_disables_caching(self):
        source = Path(__file__).resolve().parents[1] / "app.py"
        nodes = [node for node in ast.parse(source.read_text()).body
                 if isinstance(node, ast.FunctionDef)
                 and node.name in {"get_frontend_version", "normalize_frontend_app_version"}]
        app = Flask(__name__)
        namespace = {
            "app": app, "jsonify": jsonify, "FRONTEND_APP_VERSION": "9.5",
            "development_frontend_version": development_frontend_version,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
        with patch.dict(os.environ, self.env, clear=True):
            response = app.test_client().get("/api/version")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"version": "9.8"})
            self.assertEqual(response.headers["Cache-Control"], "no-cache, no-store, must-revalidate")
            self.assertEqual(response.headers["Pragma"], "no-cache")
            self.assertEqual(response.headers["Expires"], "0")
            self.env["APP_ENV"] = "production"
            with patch.dict(os.environ, self.env, clear=True):
                self.assertEqual(app.test_client().get("/api/version").json, {"version": "9.5"})


if __name__ == "__main__":
    unittest.main()
