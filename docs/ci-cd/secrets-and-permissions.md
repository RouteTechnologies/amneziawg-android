# Secrets, variables, environments and permissions

## Secrets

| Secret | Required | Scope (recommended) | Used by |
|---|---|---|---|
| `ANDROID_KEYSTORE_BASE64` | yes | environment `github-release` | release |
| `ANDROID_KEYSTORE_PASSWORD` | yes | `github-release` | release |
| `ANDROID_KEY_ALIAS` | yes | `github-release` | release |
| `ANDROID_KEY_PASSWORD` | no (defaults to keystore password) | `github-release` | release |
| `PLAY_UPLOAD_KEYSTORE_BASE64`, `PLAY_UPLOAD_KEYSTORE_PASSWORD`, `PLAY_UPLOAD_KEY_ALIAS`, `PLAY_UPLOAD_KEY_PASSWORD` | no | `github-release` | release (AAB) |
| `CHECKSUMS_GPG_PRIVATE_KEY`, `CHECKSUMS_GPG_PASSPHRASE` | no | `github-release` | release |
| `PLAY_SERVICE_ACCOUNT_JSON` | only for Play | environment `google-play` | play-publish |

The existing signing secrets are repository-level and keep working. Moving them into the
`github-release` environment (Settings → Environments → `github-release` → secrets) makes them
available only to that job; then restrict the environment's deployment to tags `v*`.

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `RELEASE_CERT_SHA256` | unset (warning) | Expected APK signing certificate SHA-256; releases fail on mismatch. **Set it.** |
| `PLAY_UPLOAD_CERT_SHA256` | unset | Expected upload certificate when a separate upload key is used |
| `CHECKSUMS_GPG_FINGERPRINT` | unset | Expected OpenPGP key for checksum signatures |
| `RELEASE_MANDATORY_UPDATE` | unset (`false`) | `mandatory_update` in `release.json` |
| `PLAY_PUBLISHING_ENABLED` | unset (disabled) | `true` enables `play-publish.yml` |

## Environments

| Environment | Used by | Recommended protection |
|---|---|---|
| `github-release` | `release.yml` | Deployment: tags `v*` only; holds signing secrets |
| `google-play` | `play-publish.yml` | Required reviewers; deployment: `master`; holds `PLAY_SERVICE_ACCOUNT_JSON` |

GitHub creates an environment without protection the first time a job uses it, so configure them
before relying on them.

## Repository settings

* Settings → Actions → General → Workflow permissions: **Read repository contents** (workflows
  request more per job where needed).
* Fork pull request workflows: require approval for all outside collaborators.
* Rules → Rulesets: a tag ruleset for `v*` restricting creation/deletion to maintainers, so only
  they can trigger releases.
* Branch protection on `master`: require the CI check.

## Permissions per job

| Job | Permissions |
|---|---|
| ci / build / emulator | `contents: read` |
| release | `contents: write` (release + assets), `id-token: write` + `attestations: write` (provenance) |
| play-publish | `contents: read` |

Workflow-level defaults are `{}` (release, play-publish) or `contents: read`. Checkouts use
`persist-credentials: false`. Secrets are passed only to the steps that need them, as environment
variables, and never echoed. Signing passwords reach `apksigner`/`jarsigner` through `env:`
indirection, not the command line.

## Action pinning

| Action | Reference |
|---|---|
| `actions/checkout` | `fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09` (v5) |
| `actions/setup-java` | `b6effb05e454b25005698d916606bdc6ffcbf961` (v5) |
| `actions/setup-go` | `924ae3a1cded613372ab5595356fb5720e22ba16` (v6) |
| `gradle/actions/setup-gradle` | `0723195856401067f7a2779048b490ace7a47d7c` (v5) |
| `android-actions/setup-android` | `9fc6c4e9069bf8d3d10b2204b1fb8f6ef7065407` (v3) |
| `actions/upload-artifact` | `330a01c490aca151604b8cf639adc76d48f6c5d4` (v5) |
| `reactivecircus/android-emulator-runner` | `a421e43855164a8197daf9d8d40fe71c6996bb0d` (v2) |
| `softprops/action-gh-release` | **`@v2` (tag, not pinned)** |
| `actions/attest-build-provenance` | **`@v2` (tag, not pinned)** |

The SHAs are the commits the runner resolved for those tags in earlier runs of this repository
("Download action repository ... (SHA:...)" in the job log). The two tag references could not be
resolved from the environment where this was written. To pin them, take the SHA from the
"Set up job" log of the next release run and replace `@v2` with `@<sha> # v2`. Update pins
deliberately (for example with Dependabot for GitHub Actions), not by editing tags blindly.

## Cache and artifacts

* Gradle cache: written only on `master` (CI) and read-only elsewhere, so pull requests and tags
  cannot poison it. The Gradle wrapper JAR is validated by `setup-gradle`.
* Workflow artifacts (debug APKs, unsigned validation builds, reports) are kept for 7 days. Signed
  release files are not uploaded as workflow artifacts, only to the release.
