# Workflows

All workflows run on `[self-hosted, docker-runner]` and use the composite action
[`.github/actions/android-env`](../../.github/actions/android-env/action.yml) for JDK 17, Go (from
`tunnel/tools/libwg-go/go.mod`), Gradle, the Android SDK, python3 and a container memory check.

| Workflow | Trigger | Permissions | Secrets | Purpose |
|---|---|---|---|---|
| `ci.yml` | pull request (same repository only), push to `master`, manual | `contents: read` | none | Unit tests, debug APK, release tooling tests, SBOM dry run |
| `release.yml` | push of a `v*` tag | `contents: write`, `id-token: write`, `attestations: write` (job level) | signing keys, optional checksum key | Signed APKs + AAB, checksums, SBOM, provenance, `release.json`, draft release |
| `build.yml` | manual | `contents: read` | none | Unsigned validation builds of any ref, optional lint |
| `emulator.yml` | manual | `contents: read` | none | Instrumented smoke tests on emulators (API 21, 23, 24, 26, 29, 34) |
| `play-publish.yml` | manual, only if `PLAY_PUBLISHING_ENABLED=true` | `contents: read` | Play service account | Upload a released AAB to Google Play (dry run by default) |

## ci.yml

Runs `scripts/ci/test_release_tool.py` and `scripts/ci/test_play_publish.py`, then
`:tunnel:testDebugUnitTest :ui:assembleDebug :ui:writeReleaseDependencies`, then generates and
validates an SBOM with the debug APK as a stand-in artifact, so the release SBOM path is exercised
on every pull request. Pull requests from forks are skipped so that untrusted code never runs on
the self-hosted runner. Only `master` writes the Gradle cache.

## release.yml

See [release-process.md](release-process.md) for the steps and [architecture.md](architecture.md)
for the reasoning. Fails without publishing when the tag, version, changelog, outputs, signatures or
certificate fingerprints do not check out, or when signing secrets are missing. The build
provenance step is allowed to fail (artifact attestations need a public repository or GitHub
Enterprise Cloud); `release.json` and the release notes record whether it succeeded.

## build.yml

Inputs: `target` (`release_unsigned` or `debug_apk`), `ref`, `lint`. Release outputs are renamed
`routevpn-<version>-<abi>-UNSIGNED.apk` / `routevpn-<version>-release-UNSIGNED.aab` and kept for
7 days. It previously produced a signed AAB from any ref; that path moved to `release.yml` so that
signing secrets are used only for version tags.

## emulator.yml

Inputs: `api-levels` (a JSON array) and `mode` (`tests`, `screenshots` or `both`). `screenshots` runs
`scripts/ci/emulator-run.sh`, which installs the debug APK, starts the app and saves real screenshots
(start page, add-tunnel sheet, tunnel editor) as the artifact `screenshots-api-<N>`. Jobs run one at
a time (`max-parallel: 1`, `concurrency`), need `/dev/kvm` and at least 3 GiB of container memory
(4 GiB is recommended; 3.95 GiB is the largest limit tested with the smoke tests), and install the
emulator's X11/GL libraries with `apt-get` ([self-hosted-runner.md](self-hosted-runner.md)). Before the
emulator starts they delete the system images of other API levels and fail early when less than
6 GiB of disk is free; the AVD is removed afterwards.

## play-publish.yml

Inputs: `tag`, `track` (`internal`, `alpha`, `beta`, `production`), `status` (`draft`,
`completed`), `dry-run` (default `true`). See [google-play.md](google-play.md).

## Scripts

| Script | Used by | Purpose |
|---|---|---|
| `scripts/ci/release_tool.py` | release, ci | `check-version`, `changelog`, `sbom`, `validate-sbom`, `release-json` |
| `scripts/ci/play_publish.py` | play-publish | Download/verify the release AAB; upload it to Google Play |
| `scripts/ci/test_*.py` | ci | Unit tests (`python3 scripts/ci/test_release_tool.py`) |

The Gradle task `:ui:writeReleaseDependencies` (in `ui/build.gradle.kts`) writes the resolved
release dependencies to `ui/build/sbom/release-dependencies.txt`.
