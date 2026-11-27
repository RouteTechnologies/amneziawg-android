#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Upload a signed AAB from a GitHub Release to Google Play (Android Publisher API v3).

Used only by .github/workflows/play-publish.yml, which is disabled unless the repository variable
PLAY_PUBLISHING_ENABLED is 'true' and runs in the protected 'google-play' environment.

  download  Fetch release.json, SHA256SUMS.txt and the AAB of a published GitHub Release and check
            the AAB checksum and the package name / versionCode in release.json.
  publish   Authenticate with the service account in $PLAY_SERVICE_ACCOUNT_JSON, check that the
            versionCode is higher than every versionCode on Play, and (unless --dry-run) upload the
            bundle and assign it to a track. With --dry-run the edit is deleted without changes.

Standard library only; the JWT is signed with the openssl CLI. Secrets are never printed.
See docs/ci-cd/google-play.md.
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
UPLOAD_API = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
TRACKS = ("internal", "alpha", "beta", "production")


class PublishError(Exception):
    pass


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwt(service_account, now=None):
    """RS256 JWT for the OAuth 2.0 JWT bearer flow, signed with `openssl dgst -sha256 -sign`."""
    now = int(now if now is not None else time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({
        "iss": service_account["client_email"],
        "scope": SCOPE,
        "aud": service_account.get("token_uri", "https://oauth2.googleapis.com/token"),
        "iat": now,
        "exp": now + 3600,
    }).encode())
    signing_input = f"{header}.{claims}".encode()
    with tempfile.NamedTemporaryFile("w", delete=False, dir=os.environ.get("RUNNER_TEMP")) as key_file:
        os.chmod(key_file.name, 0o600)
        key_file.write(service_account["private_key"])
    try:
        signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_file.name],
                                   input=signing_input, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        raise PublishError("could not sign the JWT with the service account key") from None
    finally:
        os.unlink(key_file.name)
    return f"{header}.{claims}.{b64url(signature)}"


def max_version_code(tracks_response):
    """Highest versionCode in any release of any track of an edits.tracks.list response."""
    codes = [int(code)
             for track in tracks_response.get("tracks", [])
             for release in track.get("releases", [])
             for code in release.get("versionCodes", [])]
    return max(codes) if codes else 0


def request(method, url, token=None, body=None, data=None, content_type=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:2000]
        raise PublishError(f"{method} {url.split('?')[0]} failed: HTTP {exc.code}: {detail}") from None
    return json.loads(payload) if payload else {}


def access_token(service_account):
    form = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": make_jwt(service_account),
    }).encode()
    token_uri = service_account.get("token_uri", "https://oauth2.googleapis.com/token")
    return request("POST", token_uri, data=form, content_type="application/x-www-form-urlencoded")["access_token"]


def publish(args):
    raw = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise PublishError("PLAY_SERVICE_ACCOUNT_JSON is not set")
    try:
        service_account = json.loads(raw)
        service_account["client_email"], service_account["private_key"]
    except (ValueError, KeyError):
        raise PublishError("PLAY_SERVICE_ACCOUNT_JSON is not a service account JSON key") from None

    token = access_token(service_account)
    base = f"{API}/{args.package}/edits"
    edit_id = request("POST", base, token, body={})["id"]
    committed = False
    try:
        on_play = max_version_code(request("GET", f"{base}/{edit_id}/tracks", token))
        print(f"highest versionCode on Google Play: {on_play}; this release: {args.version_code}")
        if args.version_code <= on_play:
            raise PublishError(f"versionCode {args.version_code} is not higher than {on_play} already on Google Play")
        if args.dry_run:
            print("dry run: credentials, package and versionCode are valid; nothing was uploaded")
            return
        with open(args.aab, "rb") as fh:
            bundle = request("POST", f"{UPLOAD_API}/{args.package}/edits/{edit_id}/bundles?uploadType=media",
                             token, data=fh.read(), content_type="application/octet-stream")
        if int(bundle.get("versionCode", -1)) != args.version_code:
            raise PublishError(f"Google Play read versionCode {bundle.get('versionCode')} from the bundle, "
                               f"expected {args.version_code}")
        release = {"name": args.release_name, "versionCodes": [str(args.version_code)], "status": args.status}
        request("PUT", f"{base}/{edit_id}/tracks/{args.track}", token,
                body={"track": args.track, "releases": [release]})
        request("POST", f"{base}/{edit_id}:commit", token)
        committed = True
        print(f"uploaded versionCode {args.version_code} to the {args.track} track with status {args.status}")
    finally:
        if not committed:
            try:
                request("DELETE", f"{base}/{edit_id}", token)
            except PublishError as exc:
                print(f"::warning::could not delete edit {edit_id}: {exc}", file=sys.stderr)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def github_download(url, token, dest):
    """Download a release asset. The API answers with a redirect to signed storage, which must be
    fetched without the GitHub Authorization header."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream",
                                               "Authorization": f"Bearer {token}"})
    try:
        resp = opener.open(req, timeout=600)
        data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise PublishError(f"downloading {url} failed: HTTP {exc.code}") from None
        with urllib.request.urlopen(exc.headers["Location"], timeout=600) as resp:
            data = resp.read()
    with open(dest, "wb") as fh:
        fh.write(data)


def download(args):
    token = os.environ.get("GITHUB_TOKEN", "")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    url = f"{api}/repos/{args.repository}/releases/tags/{urllib.parse.quote(args.tag)}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            release = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise PublishError(f"no published GitHub Release for {args.tag} (HTTP {exc.code}); "
                           "publish the draft release first") from None
    assets = {a["name"]: a["url"] for a in release.get("assets", [])}
    version = args.tag[1:] if args.tag.startswith("v") else args.tag
    aab_name = f"routevpn-{version}-release.aab"
    for name in ("release.json", "SHA256SUMS.txt", aab_name):
        if name not in assets:
            raise PublishError(f"release {args.tag} has no asset {name}")
        github_download(assets[name], token, os.path.join(args.out, name))

    with open(os.path.join(args.out, "release.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    if meta.get("tag") != args.tag or meta.get("version") != version:
        raise PublishError("release.json does not describe this tag")
    sums = {}
    with open(os.path.join(args.out, "SHA256SUMS.txt"), encoding="utf-8") as fh:
        for line in fh:
            digest, name = line.split()
            sums[name.lstrip("*")] = digest
    with open(os.path.join(args.out, aab_name), "rb") as fh:
        actual = hashlib.sha256(fh.read()).hexdigest()
    if sums.get(aab_name) != actual:
        raise PublishError(f"{aab_name} does not match SHA256SUMS.txt")
    print(f"{aab_name}: checksum ok, {meta['application_id']} versionCode {meta['version_code']}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"aab={os.path.join(args.out, aab_name)}\n")
            fh.write(f"package={meta['application_id']}\n")
            fh.write(f"version_code={meta['version_code']}\n")
            fh.write(f"version={meta['version']}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("download")
    p.add_argument("--repository", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--package", required=True)
    p.add_argument("--aab", required=True)
    p.add_argument("--version-code", type=int, required=True)
    p.add_argument("--release-name", required=True)
    p.add_argument("--track", choices=TRACKS, default="internal")
    p.add_argument("--status", choices=("draft", "completed"), default="draft")
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        download(args) if args.command == "download" else publish(args)
    except PublishError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
