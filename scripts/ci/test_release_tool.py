#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for release_tool.py: python3 scripts/ci/test_release_tool.py"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import release_tool as rt  # noqa: E402

CHANGELOG = """# Changelog

## [Unreleased]

## [1.0.4]

### Changed
- Something.

## [1.0.3]
- Older.
"""

SETTINGS = "configure<SettingsExtension> {\n    compileSdk = 36\n    minSdk = 21\n}\n"


def props(name, code, pkg="io.routedns.awg"):
    return f"amneziawgVersionCode={code}\namneziawgVersionName={name}\namneziawgPackageName={pkg}\n"


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        self.write("settings.gradle.kts", SETTINGS)
        self.write("CHANGELOG.md", CHANGELOG)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True)

    def write(self, name, text):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def commit_tag(self, name, code, tag):
        self.write("gradle.properties", props(name, code))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", tag or "wip")
        if tag:
            self.git("tag", tag)

    def check(self, tag):
        return rt.check_version(tag, os.path.join(self.repo, "gradle.properties"),
                                os.path.join(self.repo, "settings.gradle.kts"),
                                os.path.join(self.repo, "CHANGELOG.md"), self.repo)


class CheckVersionTest(RepoTestCase):
    def test_valid_release(self):
        self.commit_tag("1.0.3", 15, "v1.0.3")
        self.commit_tag("1.0.4", 16, None)
        out = self.check("v1.0.4")
        self.assertEqual(out["version"], "1.0.4")
        self.assertEqual(out["version_code"], 16)
        self.assertEqual(out["min_sdk"], 21)
        self.assertEqual(out["application_id"], "io.routedns.awg")
        self.assertEqual(out["prerelease"], "false")
        self.assertEqual(out["highest_previous_version_code"], 15)

    def test_current_tag_is_excluded(self):
        self.commit_tag("1.0.4", 16, "v1.0.4")
        self.assertEqual(self.check("v1.0.4")["version_code"], 16)

    def test_tag_must_match_version_name(self):
        self.commit_tag("1.0.4", 16, None)
        with self.assertRaisesRegex(rt.ReleaseError, "does not match amneziawgVersionName"):
            self.check("v1.0.5")

    def test_version_code_must_increase(self):
        self.commit_tag("1.0.3", 15, "v1.0.3")
        self.commit_tag("1.0.4", 15, None)
        with self.assertRaisesRegex(rt.ReleaseError, "must be greater"):
            self.check("v1.0.4")

    def test_version_code_compared_with_highest_tag_not_latest(self):
        self.commit_tag("3.1.5", 40, "v3.1.5")    # e.g. an upstream tag with a high code
        self.commit_tag("1.0.4", 16, None)
        with self.assertRaisesRegex(rt.ReleaseError, "v3.1.5 already uses 40"):
            self.check("v1.0.4")

    def test_bad_tag_format(self):
        self.commit_tag("1.0.4", 16, None)
        for tag in ("1.0.4", "v1.0", "v1.0.4.1", "v1.0.4-beta", "v1.0.4+build"):
            with self.assertRaisesRegex(rt.ReleaseError, "not a release tag"):
                self.check(tag)

    def test_prerelease_tag(self):
        self.commit_tag("1.1.0-rc.1", 17, None)
        self.write("CHANGELOG.md", CHANGELOG + "\n## [1.1.0-rc.1]\n- RC.\n")
        self.assertEqual(self.check("v1.1.0-rc.1")["prerelease"], "true")

    def test_changelog_section_required(self):
        self.commit_tag("1.0.9", 20, None)
        with self.assertRaisesRegex(rt.ReleaseError, r"no '## \[1.0.9\]' section"):
            self.check("v1.0.9")


class ChangelogTest(RepoTestCase):
    def test_extracts_only_one_section(self):
        body = rt.changelog_section(os.path.join(self.repo, "CHANGELOG.md"), "1.0.4")
        self.assertEqual(body, "### Changed\n- Something.")

    def test_empty_section_rejected(self):
        with self.assertRaisesRegex(rt.ReleaseError, "is empty"):
            rt.changelog_section(os.path.join(self.repo, "CHANGELOG.md"), "Unreleased")

    def test_version_prefix_does_not_match_longer_version(self):
        self.write("CHANGELOG.md", "## [1.0.40]\n- other\n")
        with self.assertRaises(rt.ReleaseError):
            rt.changelog_section(os.path.join(self.repo, "CHANGELOG.md"), "1.0.4")


class SbomAndMetadataTest(RepoTestCase):
    def files(self):
        deps = os.path.join(self.repo, "deps.txt")
        self.write("deps.txt", "androidx.core:core:1.12.0\ncom.google.android.material:material:1.11.0\n"
                               "androidx.core:core:1.12.0\n")
        self.write("go.mod", "module example.com/m\n\ngo 1.25.0\n\nrequire golang.org/x/sys v0.36.0\n\n"
                             "require (\n\tgithub.com/a/b/v3 v3.1.0\n\tgolang.org/x/net v0.44.0 // indirect\n)\n")
        self.write("submodules.txt", " ee0f0a9aa34ff0a0da4b3433b9512781cfe02843 tunnel/tools/amneziawg-tools (v1)\n"
                                     "-7efc05090675ec6161b7def862728086a26c3b1f tunnel/tools/elf-cleaner\n")
        self.write(".gitmodules", '[submodule "a"]\n\tpath = tunnel/tools/amneziawg-tools\n'
                                  "\turl = https://github.com/amnezia-vpn/amneziawg-tools\n"
                                  '[submodule "b"]\n\tpath = tunnel/tools/elf-cleaner\n'
                                  "\turl = https://github.com/termux/termux-elf-cleaner\n")
        apk = os.path.join(self.repo, "routevpn-1.0.4-universal.apk")
        with open(apk, "wb") as fh:
            fh.write(b"apk")
        return deps, apk

    def sbom_args(self, deps, apk):
        return ["sbom", "--version", "1.0.4", "--tag", "v1.0.4", "--commit", "abc123",
                "--application-id", "io.routedns.awg", "--repository", "Org/repo",
                "--out", os.path.join(self.repo, "SBOM.spdx.json"), "--gradle-deps", deps,
                "--go-mod", os.path.join(self.repo, "go.mod"),
                "--submodules", os.path.join(self.repo, "submodules.txt"),
                "--gitmodules", os.path.join(self.repo, ".gitmodules"),
                "--build-only-submodule", "elf-cleaner", "--gradle-version", "8.13",
                "--agp-version", "8.13.0", "--ndk-version", "26.1.10909125", "--artifact", apk]

    def test_sbom(self):
        deps, apk = self.files()
        self.assertEqual(rt.main(self.sbom_args(deps, apk)), 0)
        with open(os.path.join(self.repo, "SBOM.spdx.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(rt.validate_sbom(doc), [])
        names = {p["name"]: p for p in doc["packages"]}
        self.assertIn("androidx.core:core", names)
        self.assertEqual(sum(1 for p in doc["packages"] if p["name"] == "androidx.core:core"), 1)
        self.assertEqual(names["golang.org/x/net"]["externalRefs"][0]["referenceLocator"],
                         "pkg:golang/golang.org/x/net@v0.44.0")
        self.assertIn("(indirect)", names["golang.org/x/net"]["comment"])
        self.assertEqual(names["amneziawg-tools"]["externalRefs"][0]["referenceLocator"],
                         "pkg:github/amnezia-vpn/amneziawg-tools@ee0f0a9aa34ff0a0da4b3433b9512781cfe02843")
        self.assertEqual(names["go"]["versionInfo"], "1.25.0")
        rel = {(r["spdxElementId"], r["relationshipType"], r["relatedSpdxElement"]) for r in doc["relationships"]}
        elf = names["termux-elf-cleaner" if "termux-elf-cleaner" in names else "elf-cleaner"]["SPDXID"]
        self.assertIn((elf, "BUILD_DEPENDENCY_OF", "SPDXRef-Package-RouteVPN"), rel)
        art = names["routevpn-1.0.4-universal.apk"]
        self.assertEqual(art["checksums"][0]["checksumValue"], rt.sha256_file(apk))

    def test_validate_sbom_catches_errors(self):
        doc = {"spdxVersion": "SPDX-2.2", "packages": [{"SPDXID": "bad id"}],
               "relationships": [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
                                  "relatedSpdxElement": "SPDXRef-missing"}]}
        errors = rt.validate_sbom(doc)
        self.assertTrue(any("spdxVersion" in e for e in errors))
        self.assertTrue(any("invalid SPDXID" in e for e in errors))
        self.assertTrue(any("unknown element" in e for e in errors))

    def test_bad_dependency_line(self):
        deps, apk = self.files()
        self.write("deps.txt", "not-a-coordinate\n")
        self.assertEqual(rt.main(self.sbom_args(deps, apk)), 1)

    def test_release_json(self):
        _, apk = self.files()
        out = os.path.join(self.repo, "release.json")
        code = rt.main(["release-json", "--version", "1.0.4", "--tag", "v1.0.4", "--commit", "abc123",
                        "--application-id", "io.routedns.awg", "--repository", "Org/repo", "--out", out,
                        "--workflow-run-url", "https://github.com/Org/repo/actions/runs/1",
                        "--version-code", "16", "--min-sdk", "21", "--release-date", "2026-11-26",
                        "--apk-cert-sha256", "aa", "--aab-cert-sha256", "aa", "--artifact", apk])
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as fh:
            meta = json.load(fh)
        self.assertEqual(meta["version_code"], 16)
        self.assertEqual(meta["minimum_android"], 21)
        self.assertEqual(meta["minimum_android_release"], "5.0")
        self.assertTrue(meta["latest"])
        self.assertFalse(meta["mandatory_update"])
        self.assertEqual(meta["distribution"], {"github": True, "google_play": False})
        self.assertEqual(meta["release_url"], "https://github.com/Org/repo/releases/tag/v1.0.4")
        self.assertEqual(meta["changelog_url"], "https://github.com/Org/repo/blob/v1.0.4/CHANGELOG.md")
        self.assertEqual(meta["artifacts"][0]["sha256"], rt.sha256_file(apk))


if __name__ == "__main__":
    unittest.main(verbosity=2)
