#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline unit tests for play_publish.py: python3 scripts/ci/test_play_publish.py
(The Google Play and GitHub API calls are not exercised here.)"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import play_publish as pp  # noqa: E402


def unb64(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class JwtTest(unittest.TestCase):
    def test_jwt_is_valid_rs256(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = os.path.join(tmp, "key.pem")
            pub = os.path.join(tmp, "pub.pem")
            subprocess.run(["openssl", "genrsa", "-out", key, "2048"], check=True, capture_output=True)
            subprocess.run(["openssl", "rsa", "-in", key, "-pubout", "-out", pub], check=True, capture_output=True)
            with open(key, encoding="utf-8") as fh:
                account = {"client_email": "ci@example.iam.gserviceaccount.com", "private_key": fh.read(),
                           "token_uri": "https://oauth2.googleapis.com/token"}
            token = pp.make_jwt(account, now=1_700_000_000)
            header, claims, signature = token.split(".")
            self.assertEqual(json.loads(unb64(header)), {"alg": "RS256", "typ": "JWT"})
            body = json.loads(unb64(claims))
            self.assertEqual(body["iss"], account["client_email"])
            self.assertEqual(body["scope"], pp.SCOPE)
            self.assertEqual(body["exp"] - body["iat"], 3600)
            with open(os.path.join(tmp, "sig"), "wb") as fh:
                fh.write(unb64(signature))
            with open(os.path.join(tmp, "data"), "wb") as fh:
                fh.write(f"{header}.{claims}".encode())
            verify = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pub, "-signature",
                                     os.path.join(tmp, "sig"), os.path.join(tmp, "data")],
                                    capture_output=True, text=True)
            self.assertEqual(verify.stdout.strip(), "Verified OK")
            self.assertEqual([f for f in os.listdir(tempfile.gettempdir()) if f == "key.pem"], [])

    def test_bad_key_raises(self):
        with self.assertRaises(pp.PublishError):
            pp.make_jwt({"client_email": "x", "private_key": "not a key"})


class VersionCodeTest(unittest.TestCase):
    def test_max_version_code(self):
        tracks = {"tracks": [
            {"track": "internal", "releases": [{"versionCodes": ["15"]}, {"versionCodes": ["14", "9"]}]},
            {"track": "production", "releases": [{"status": "completed"}]},
        ]}
        self.assertEqual(pp.max_version_code(tracks), 15)
        self.assertEqual(pp.max_version_code({}), 0)

    def test_missing_credentials(self):
        os.environ.pop("PLAY_SERVICE_ACCOUNT_JSON", None)
        code = pp.main(["publish", "--package", "io.routedns.awg", "--aab", "x.aab", "--version-code", "16",
                        "--release-name", "1.0.4", "--dry-run"])
        self.assertEqual(code, 1)

    def test_malformed_credentials(self):
        os.environ["PLAY_SERVICE_ACCOUNT_JSON"] = "{}"
        try:
            code = pp.main(["publish", "--package", "io.routedns.awg", "--aab", "x.aab", "--version-code", "16",
                            "--release-name", "1.0.4"])
        finally:
            del os.environ["PLAY_SERVICE_ACCOUNT_JSON"]
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
