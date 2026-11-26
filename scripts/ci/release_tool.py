#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Release helpers for the RouteVPN CI/CD workflows (Python standard library only).

Subcommands:
  check-version   Validate a release tag against gradle.properties, settings.gradle.kts, the
                  changelog and the versionCode of every other v* tag. Prints key=value lines
                  suitable for $GITHUB_OUTPUT.
  changelog       Extract the section of CHANGELOG.md for one version.
  sbom            Write an SPDX 2.3 JSON SBOM.
  validate-sbom   Structural validation of an SPDX 2.3 JSON document.
  release-json    Write release.json (release metadata).

See docs/ci-cd/ for how the workflows use these.
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid

TAG_RE = re.compile(r"^v(?P<version>(?P<core>\d+\.\d+\.\d+)(?:-(?P<pre>(?:alpha|beta|rc)\.\d+))?)$")
APP_NAME = "RouteVPN"

# Android API level -> platform release, for human-readable metadata.
ANDROID_RELEASES = {
    21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9",
    29: "10", 30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15", 36: "16",
}


class ReleaseError(Exception):
    pass


# --------------------------------------------------------------------------- parsing helpers

def read_properties(path):
    props = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(("#", "!")) or "=" not in line:
                continue
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def parse_properties_text(text):
    props = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")) and "=" in line:
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def read_min_sdk(settings_path):
    with open(settings_path, encoding="utf-8") as fh:
        match = re.search(r"^\s*minSdk\s*=\s*(\d+)\s*$", fh.read(), re.MULTILINE)
    if not match:
        raise ReleaseError(f"minSdk not found in {settings_path}")
    return int(match.group(1))


def app_version(props):
    try:
        name = props["amneziawgVersionName"]
        code = int(props["amneziawgVersionCode"])
        package = props["amneziawgPackageName"]
    except KeyError as exc:
        raise ReleaseError(f"gradle.properties is missing {exc.args[0]}") from None
    except ValueError:
        raise ReleaseError("amneziawgVersionCode is not an integer") from None
    if code <= 0:
        raise ReleaseError("amneziawgVersionCode must be a positive integer")
    return name, code, package


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def version_codes_of_other_tags(repo, current_tag):
    """{tag: versionCode} for every v* tag except current_tag whose gradle.properties has one."""
    codes = {}
    for tag in git(repo, "tag", "--list", "v*").split():
        if tag == current_tag:
            continue
        try:
            text = git(repo, "show", f"{tag}:gradle.properties")
        except subprocess.CalledProcessError:
            continue  # very old tags may not have gradle.properties
        value = parse_properties_text(text).get("amneziawgVersionCode")
        if value and value.isdigit():
            codes[tag] = int(value)
    return codes


def changelog_section(changelog_path, version):
    """Body of the '## [version]' (or '## version') section, without the heading."""
    with open(changelog_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    heading = re.compile(r"^##\s+\[?" + re.escape(version) + r"\]?(\s|$)")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise ReleaseError(f"{changelog_path} has no '## [{version}]' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = "\n".join(lines[start + 1:end]).strip()
    if not body:
        raise ReleaseError(f"the '## [{version}]' section of {changelog_path} is empty")
    return body


# --------------------------------------------------------------------------- check-version

def check_version(tag, props_path, settings_path, changelog_path, repo):
    match = TAG_RE.match(tag)
    if not match:
        raise ReleaseError(
            f"tag '{tag}' is not a release tag; expected vMAJOR.MINOR.PATCH or "
            "vMAJOR.MINOR.PATCH-(alpha|beta|rc).N, e.g. v1.0.4 or v1.1.0-rc.1")
    version = match.group("version")
    name, code, package = app_version(read_properties(props_path))
    if name != version:
        raise ReleaseError(
            f"tag {tag} does not match amneziawgVersionName={name} in {props_path}. "
            f"Set amneziawgVersionName={version} (and increase amneziawgVersionCode), commit, and tag that commit.")
    others = version_codes_of_other_tags(repo, tag)
    if others:
        highest_tag = max(others, key=others.get)
        if code <= others[highest_tag]:
            raise ReleaseError(
                f"amneziawgVersionCode={code} must be greater than every released versionCode; "
                f"{highest_tag} already uses {others[highest_tag]}. Android rejects updates whose "
                f"versionCode is not higher than the installed one.")
    changelog_section(changelog_path, version)  # raises when missing
    return {
        "version": version,
        "version_code": code,
        "application_id": package,
        "min_sdk": read_min_sdk(settings_path),
        "prerelease": "true" if match.group("pre") else "false",
        "highest_previous_version_code": max(others.values()) if others else 0,
    }


# --------------------------------------------------------------------------- SBOM

def spdx_id(*parts):
    raw = "-".join(str(p) for p in parts)
    return "SPDXRef-" + re.sub(r"[^A-Za-z0-9.-]+", "-", raw).strip("-")


def parse_gradle_dependencies(path):
    deps = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3 or not all(parts):
                raise ReleaseError(f"unexpected dependency line in {path}: {line!r}")
            deps.append(tuple(parts))
    return sorted(set(deps))


def parse_go_mod(path):
    """(module_path, go_version, [(module, version, indirect)])"""
    module, go_version, requires = None, None, []
    in_block = False
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("//", 1)[0].strip()
            indirect = "// indirect" in raw
            if in_block:
                if line == ")":
                    in_block = False
                elif line:
                    mod, ver = line.split()[:2]
                    requires.append((mod, ver, indirect))
                continue
            if line.startswith("module "):
                module = line.split()[1]
            elif line.startswith("go "):
                go_version = line.split()[1]
            elif line.startswith("require ("):
                in_block = True
            elif line.startswith("require "):
                mod, ver = line.split()[1:3]
                requires.append((mod, ver, indirect))
    return module, go_version, requires


def parse_gitmodules(path):
    """.gitmodules -> {submodule path: url}"""
    urls, current = {}, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("path"):
                current = line.split("=", 1)[1].strip()
            elif line.startswith("url") and current:
                urls[current] = line.split("=", 1)[1].strip()
    return urls


def parse_submodules(path):
    """Output of 'git submodule status' -> [(path, sha)]"""
    result = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            sha, sub_path = line.lstrip("-+U ").split()[:2]
            result.append((sub_path, sha))
    return result


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(spdxid, name, version, purl=None, download="NOASSERTION", comment=None, checksums=None):
    pkg = {
        "SPDXID": spdxid,
        "name": name,
        "versionInfo": version,
        "downloadLocation": download,
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "supplier": "NOASSERTION",
    }
    if purl:
        pkg["externalRefs"] = [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl",
                                "referenceLocator": purl}]
    if checksums:
        pkg["checksums"] = checksums
    if comment:
        pkg["comment"] = comment
    return pkg


def build_sbom(args):
    root_id = "SPDXRef-Package-RouteVPN"
    repo_url = f"{args.server_url}/{args.repository}"
    packages = [package(root_id, APP_NAME, args.version, download=f"git+{repo_url}@{args.commit}",
                        comment=f"Android application {args.application_id}, built from tag {args.tag}")]
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
                      "relatedSpdxElement": root_id}]

    def depends(pkg, rel="DEPENDS_ON"):
        packages.append(pkg)
        if rel == "DEPENDS_ON":
            relationships.append({"spdxElementId": root_id, "relationshipType": "DEPENDS_ON",
                                  "relatedSpdxElement": pkg["SPDXID"]})
        else:  # BUILD_DEPENDENCY_OF: <tool> is a build dependency of the app
            relationships.append({"spdxElementId": pkg["SPDXID"], "relationshipType": rel,
                                  "relatedSpdxElement": root_id})

    for group, name, version in parse_gradle_dependencies(args.gradle_deps):
        depends(package(spdx_id("Maven", group, name, version), f"{group}:{name}", version,
                        purl=f"pkg:maven/{group}/{name}@{version}"))

    _, go_version, requires = parse_go_mod(args.go_mod)
    for module, version, indirect in requires:
        depends(package(spdx_id("Go", module, version), module, version, purl=f"pkg:golang/{module}@{version}",
                        comment="Go module compiled into libwg-go.so" + (" (indirect)" if indirect else "")))

    submodule_urls = parse_gitmodules(args.gitmodules) if args.gitmodules else {}
    for sub_path, sha in parse_submodules(args.submodules):
        url = submodule_urls.get(sub_path, "NOASSERTION")
        name = sub_path.rsplit("/", 1)[-1]
        purl = None
        gh = re.match(r"https://github\.com/([^/]+)/([^/.]+)", url)
        if gh:
            purl = f"pkg:github/{gh.group(1)}/{gh.group(2)}@{sha}"
        pkg = package(spdx_id("Submodule", name, sha[:12]), name, sha,
                      purl=purl, download=f"git+{url}@{sha}" if url != "NOASSERTION" else "NOASSERTION",
                      comment=f"git submodule {sub_path}")
        depends(pkg, "BUILD_DEPENDENCY_OF" if name in args.build_only_submodule else "DEPENDS_ON")

    tools = [("gradle", args.gradle_version), ("android-gradle-plugin", args.agp_version),
             ("kotlin", args.kotlin_version), ("android-ndk", args.ndk_version),
             ("android-build-tools", args.build_tools_version), ("go", go_version)]
    for name, version in tools:
        if version:
            depends(package(spdx_id("Tool", name, version), name, version), "BUILD_DEPENDENCY_OF")

    for path in args.artifact:
        file_name = os.path.basename(path)
        art_id = spdx_id("Artifact", file_name)
        packages.append(package(art_id, file_name, args.version,
                                checksums=[{"algorithm": "SHA256", "checksumValue": sha256_file(path)}],
                                comment="release artifact"))
        relationships.append({"spdxElementId": art_id, "relationshipType": "GENERATED_FROM",
                              "relatedSpdxElement": root_id})

    created = args.created or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{APP_NAME}-{args.version}",
        "documentNamespace": f"{repo_url}/releases/tag/{args.tag}/sbom/{uuid.uuid4()}",
        "creationInfo": {"created": created, "creators": ["Tool: routevpn-release-tool",
                                                         f"Organization: {args.repository.split('/')[0]}"]},
        "packages": packages,
        "relationships": relationships,
    }


def validate_sbom(doc):
    errors = []
    for key in ("spdxVersion", "dataLicense", "SPDXID", "name", "documentNamespace", "creationInfo", "packages"):
        if key not in doc:
            errors.append(f"missing top-level field {key}")
    if doc.get("spdxVersion") != "SPDX-2.3":
        errors.append("spdxVersion must be SPDX-2.3")
    if doc.get("dataLicense") != "CC0-1.0":
        errors.append("dataLicense must be CC0-1.0")
    if not re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", doc.get("creationInfo", {}).get("created", "")):
        errors.append("creationInfo.created must be YYYY-MM-DDThh:mm:ssZ")
    if not doc.get("creationInfo", {}).get("creators"):
        errors.append("creationInfo.creators is empty")
    ids = {"SPDXRef-DOCUMENT"}
    for pkg in doc.get("packages", []):
        pid = pkg.get("SPDXID", "")
        if not re.match(r"^SPDXRef-[A-Za-z0-9.-]+$", pid):
            errors.append(f"invalid SPDXID {pid!r}")
        if pid in ids:
            errors.append(f"duplicate SPDXID {pid}")
        ids.add(pid)
        for key in ("name", "downloadLocation", "versionInfo"):
            if not pkg.get(key):
                errors.append(f"package {pid} has no {key}")
        for checksum in pkg.get("checksums", []):
            if checksum.get("algorithm") == "SHA256" and not re.match(r"^[0-9a-f]{64}$", checksum.get("checksumValue", "")):
                errors.append(f"package {pid} has an invalid SHA256")
    for rel in doc.get("relationships", []):
        for key in ("spdxElementId", "relatedSpdxElement"):
            if rel.get(key) not in ids:
                errors.append(f"relationship refers to unknown element {rel.get(key)}")
    if not any(r.get("relationshipType") == "DESCRIBES" for r in doc.get("relationships", [])):
        errors.append("no DESCRIBES relationship")
    return errors


# --------------------------------------------------------------------------- release.json

def build_release_json(args):
    repo_url = f"{args.server_url}/{args.repository}"
    artifacts = [{"name": os.path.basename(p), "sha256": sha256_file(p), "size": os.path.getsize(p)}
                 for p in sorted(args.artifact)]
    prerelease = args.prerelease == "true"
    return {
        "app": APP_NAME,
        "application_id": args.application_id,
        "version": args.version,
        "version_code": args.version_code,
        "tag": args.tag,
        "commit": args.commit,
        "release_date": args.release_date or _dt.datetime.now(_dt.timezone.utc).date().isoformat(),
        "minimum_android": args.min_sdk,
        "minimum_android_release": ANDROID_RELEASES.get(args.min_sdk),
        "prerelease": prerelease,
        "latest": not prerelease,
        "mandatory_update": args.mandatory_update == "true",
        "distribution": {"github": True, "google_play": args.google_play == "true"},
        "release_url": f"{repo_url}/releases/tag/{args.tag}",
        "changelog_url": f"{repo_url}/blob/{args.tag}/CHANGELOG.md",
        "signing": {
            "apk_certificate_sha256": args.apk_cert_sha256,
            "aab_certificate_sha256": args.aab_cert_sha256,
            "checksums_signed": args.checksums_signed == "true",
        },
        "provenance": {
            "github_attestation": args.attestation == "true",
            "workflow_run_url": args.workflow_run_url,
        },
        "artifacts": artifacts,
    }


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-version")
    p.add_argument("--tag", required=True)
    p.add_argument("--gradle-properties", default="gradle.properties")
    p.add_argument("--settings", default="settings.gradle.kts")
    p.add_argument("--changelog", default="CHANGELOG.md")
    p.add_argument("--repo", default=".")

    p = sub.add_parser("changelog")
    p.add_argument("--version", required=True)
    p.add_argument("--changelog", default="CHANGELOG.md")
    p.add_argument("--out", required=True)

    p = sub.add_parser("sbom")
    for name in ("version", "tag", "commit", "application_id", "repository", "out", "gradle_deps", "go_mod", "submodules"):
        p.add_argument("--" + name.replace("_", "-"), dest=name, required=True)
    p.add_argument("--server-url", default="https://github.com")
    p.add_argument("--gitmodules", default=".gitmodules")
    p.add_argument("--build-only-submodule", action="append", default=[], help="submodule name used only to build")
    for name in ("gradle_version", "agp_version", "kotlin_version", "ndk_version", "build_tools_version", "created"):
        p.add_argument("--" + name.replace("_", "-"), dest=name)
    p.add_argument("--artifact", action="append", default=[])

    p = sub.add_parser("validate-sbom")
    p.add_argument("path")

    p = sub.add_parser("release-json")
    for name in ("version", "tag", "commit", "application_id", "repository", "out", "workflow_run_url"):
        p.add_argument("--" + name.replace("_", "-"), dest=name, required=True)
    p.add_argument("--version-code", type=int, required=True)
    p.add_argument("--min-sdk", type=int, required=True)
    p.add_argument("--server-url", default="https://github.com")
    p.add_argument("--release-date")
    p.add_argument("--prerelease", choices=("true", "false"), default="false")
    p.add_argument("--mandatory-update", choices=("true", "false"), default="false")
    p.add_argument("--google-play", choices=("true", "false"), default="false")
    p.add_argument("--apk-cert-sha256", required=True)
    p.add_argument("--aab-cert-sha256", required=True)
    p.add_argument("--checksums-signed", choices=("true", "false"), default="false")
    p.add_argument("--attestation", choices=("true", "false"), default="false")
    p.add_argument("--artifact", action="append", default=[])

    args = parser.parse_args(argv)
    try:
        if args.command == "check-version":
            for key, value in check_version(args.tag, args.gradle_properties, args.settings,
                                            args.changelog, args.repo).items():
                print(f"{key}={value}")
        elif args.command == "changelog":
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(changelog_section(args.changelog, args.version) + "\n")
        elif args.command == "sbom":
            doc = build_sbom(args)
            errors = validate_sbom(doc)
            if errors:
                raise ReleaseError("generated SBOM is invalid: " + "; ".join(errors))
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2)
                fh.write("\n")
        elif args.command == "validate-sbom":
            with open(args.path, encoding="utf-8") as fh:
                errors = validate_sbom(json.load(fh))
            if errors:
                raise ReleaseError("; ".join(errors))
            print(f"{args.path}: valid SPDX 2.3 structure")
        elif args.command == "release-json":
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(build_release_json(args), fh, indent=2)
                fh.write("\n")
    except (ReleaseError, OSError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
