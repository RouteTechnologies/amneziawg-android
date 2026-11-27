# Release process

## 1. Prepare (pull request)

1. In `gradle.properties` set `amneziawgVersionName` to the new version (`1.0.5`, or
   `1.1.0-rc.1` for a pre-release) and `amneziawgVersionCode` to the next integer above every
   released one.
2. In `CHANGELOG.md` move the relevant `## [Unreleased]` entries into a new `## [1.0.5]` section.
   That section becomes the release notes; the release fails if it is missing or empty.
3. Open a pull request, wait for CI, merge.

You can check the version before tagging:

```sh
python3 scripts/ci/release_tool.py check-version --tag v1.0.5
```

## 2. Tag

```sh
git checkout master && git pull
git tag v1.0.5            # or: git tag -a v1.0.5 -m "RouteVPN 1.0.5"
git push origin v1.0.5
```

Accepted tags: `vMAJOR.MINOR.PATCH` and `vMAJOR.MINOR.PATCH-(alpha|beta|rc).N`. Pre-release tags
create a GitHub pre-release with `"latest": false` in `release.json`. Do not create the release in
the GitHub UI first; the workflow creates it.

## 3. What `release.yml` does

| Step | Fails when |
|---|---|
| Validate tag, version and changelog | bad tag format; tag ≠ `amneziawgVersionName`; `versionCode` ≤ any other `v*` tag's; no changelog section |
| Build AAB and APKs (unsigned) | Gradle fails; container memory below 1.2 GiB |
| Verify build outputs | an APK is missing or extra; `aapt2` reports a different package, `versionCode`, `versionName`, `minSdk` or ABI set; the AAB lacks native libraries for an ABI |
| Sign and verify APKs and AAB | signing secrets missing; a signature does not verify; APKs signed by different certificates; certificate ≠ `RELEASE_CERT_SHA256` (when set); AAB certificate mismatch |
| Checksums | any checksum does not verify |
| Sign checksums | key configured but import/sign/verify fails, or fingerprint ≠ `CHECKSUMS_GPG_FINGERPRINT` |
| SBOM | dependency list missing or SBOM structurally invalid |
| Build provenance attestation | never fails the release; recorded in `release.json` and the notes |
| Release metadata and notes, publish | key material found among the assets; upload fails |

## 4. Review and publish

Open the draft on the *Releases* page and check:

* assets: 5 APKs, the AAB, `SHA256SUMS.txt`, `SBOM.spdx.json`, `release.json`, `CHANGELOG-v1.0.5.md`
  (and `SHA256SUMS.txt.sig` + `routevpn-checksums-signing-key.asc` when checksum signing is set up);
* the APK certificate SHA-256 in the notes is your release certificate;
* the job summary of the workflow run.

Install the APK for your device on a test phone, then **Publish release**. Publishing marks it as
latest (unless it is a pre-release).

## 5. Google Play (optional, later)

After publishing, run `play-publish.yml` ([google-play.md](google-play.md)).

## If something fails

Fix the cause on `master`, then either tag a new version or move the tag (the workflow uses the
workflow file and code of the tagged commit):

```sh
git push origin :refs/tags/v1.0.5 && git tag -f v1.0.5 origin/master && git push origin v1.0.5
```

Only move a tag whose release was never published. Delete the leftover draft release first. See
[troubleshooting.md](troubleshooting.md).

## Not yet verified

The following have been checked only statically or locally, not in a real run on GitHub:

* the whole `release.yml` (first real test is the next tag), including `aapt2` output parsing,
  `apksigner` output parsing and the ABI split file names of AGP 8.13;
* the Gradle task `:ui:writeReleaseDependencies` (first run is the next CI run);
* OpenPGP checksum signing (only the "no key configured" path was exercised locally);
* `actions/attest-build-provenance` on this repository (availability depends on plan/visibility);
* everything in `play-publish.yml` that talks to Google or GitHub APIs.
