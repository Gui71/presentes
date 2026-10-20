import os
from pathlib import Path
import secrets
import subprocess
import sys
from unittest import TestCase


class ConfigurationTests(TestCase):
    def run_settings(self, **changes):
        environment = dict(os.environ)
        environment.update(APP_ENV="production", DEBUG="false", SECRET_KEY=secrets.token_urlsafe(64),
                           ALLOWED_HOSTS="example.invalid", CSRF_TRUSTED_ORIGINS="https://example.invalid",
                           SECURE_HSTS_SECONDS="31536000", SECURE_HSTS_INCLUDE_SUBDOMAINS="true", SECURE_HSTS_PRELOAD="true")
        environment.update(changes)
        return subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level=WARNING"],
                              cwd=Path(__file__).resolve().parents[2], env=environment, capture_output=True, text=True)

    def test_production_secure_settings_pass_deploy_checks(self):
        result = self.run_settings()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_placeholder_weak_secret_debug_hosts_and_origins_are_rejected(self):
        for invalid in ({"SECRET_KEY": ""}, {"SECRET_KEY": "CHANGE-ME-example"}, {"SECRET_KEY": "short"},
                        {"DEBUG": "true"}, {"DEBUG": "not-a-boolean"}, {"ALLOWED_HOSTS": "*"},
                        {"ALLOWED_HOSTS": ""}, {"CSRF_TRUSTED_ORIGINS": "http://example.invalid"},
                        {"CSRF_TRUSTED_ORIGINS": ""}):
            with self.subTest(fields=list(invalid)):
                result = self.run_settings(**invalid)
                self.assertNotEqual(result.returncode, 0)
