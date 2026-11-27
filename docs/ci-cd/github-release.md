# GitHub Release

Created by `release.yml` as a **draft** named `RouteVPN <version>`; a maintainer publishes it.

## Assets

| File | Description |
|---|---|
| `routevpn-<v>-arm64-v8a.apk` | Most phones (64-bit ARM) |
| `routevpn-<v>-armeabi-v7a.apk` | Older 32-bit ARM phones |
| `routevpn-<v>-x86.apk`, `routevpn-<v>-x86_64.apk` | Emulators, some tablets and Chromebooks |
| `routevpn-<v>-universal.apk` | All ABIs in one file |
| `routevpn-<v>-release.aab` | Signed Android App Bundle for Google Play (not installable directly) |
| `SHA256SUMS.txt` | SHA-256 of the 5 APKs and the AAB |
| `SHA256SUMS.txt.sig`, `routevpn-checksums-signing-key.asc` | Only when checksum signing is configured |
| `SBOM.spdx.json` | Software bill of materials ([sbom-and-provenance.md](sbom-and-provenance.md)) |
| `release.json` | Release metadata (below) |
| `CHANGELOG-v<v>.md` | The changelog section for this version |

GitHub adds the source code archives itself. Keystores, passwords and private keys are never
uploaded; the workflow refuses to publish if key files appear among the assets.

Release notes = the `CHANGELOG.md` section plus a "Verification" block with the APK certificate
fingerprint and the checksum-signature and provenance status.

## release.json

Generated from the verified build (`aapt2` output), `gradle.properties`, `settings.gradle.kts` and
Git metadata. Example:

```json
{
  "app": "RouteVPN",
  "application_id": "io.routedns.awg",
  "version": "1.0.4",
  "version_code": 16,
  "tag": "v1.0.4",
  "commit": "<sha>",
  "release_date": "2026-11-26",
  "minimum_android": 21,
  "minimum_android_release": "5.0",
  "prerelease": false,
  "latest": true,
  "mandatory_update": false,
  "distribution": {"github": true, "google_play": false},
  "release_url": "https://github.com/<owner>/<repo>/releases/tag/v1.0.4",
  "changelog_url": "https://github.com/<owner>/<repo>/blob/v1.0.4/CHANGELOG.md",
  "signing": {"apk_certificate_sha256": "<hex>", "aab_certificate_sha256": "<hex>", "checksums_signed": false},
  "provenance": {"github_attestation": true, "workflow_run_url": "https://github.com/<owner>/<repo>/actions/runs/<id>"},
  "artifacts": [{"name": "routevpn-1.0.4-arm64-v8a.apk", "sha256": "<hex>", "size": 6827304}]
}
```

* `minimum_android` is the API level (`minSdk`).
* `latest` is `false` for pre-release tags. It describes the release once published; a draft is not
  visible to users.
* `mandatory_update` comes from the repository variable `RELEASE_MANDATORY_UPDATE` (`true`/unset).
* `distribution.google_play` is always `false` when the release is built; publishing to Play
  happens later and does not rewrite `release.json`.
* `release_date` is the UTC build date.
