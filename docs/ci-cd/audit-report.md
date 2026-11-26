# CI/CD audit report (2026-11-26)

Audit of the repository state at `master` = `bb6845c` (tag `v1.0.3`), done before the production
release work described in the rest of `docs/ci-cd/`. Findings marked **[fixed]** are addressed by
that work; the others are still open.

## 1. Build system

| Item | Finding |
|---|---|
| Gradle | Kotlin DSL (`*.gradle.kts`), wrapper 8.13, version catalog `gradle/libs.versions.toml` (AGP 8.13.0, Kotlin 2.2.20). The wrapper has no `distributionSha256Sum`; the wrapper JAR is validated by `gradle/actions/setup-gradle`. |
| SDK levels | `settings.gradle.kts`: `compileSdk 36`, `minSdk 21`, build-tools `36.0.0`, NDK `26.1.10909125`. `targetSdk 36` in `ui/build.gradle.kts`. |
| Modules | `:ui` (application), `:tunnel` (library with CMake/NDK + Go `libwg-go`). |
| Application ID | `io.routedns.awg` (`amneziawgPackageName`), `.debug` suffix for debug. Source namespace stays `org.amnezia.awg`. |
| Build types | `debug`, `release` (R8 + resource shrinking), `googleplay` (`initWith(release)`; no source set and no code references, so identical to `release`). No product flavors. |
| ABIs | No `abiFilters`: every build contains `armeabi-v7a`, `arm64-v8a`, `x86`, `x86_64`. `-PamneziawgSplitAbi` turns on ABI splits plus a universal APK. |
| Native/Go | `libwg-go` is built by the NDK CMake step with Go 1.24.2 (Makefile) while `go.mod` requires Go 1.25.0, which only works through automatic toolchain download (`GOTOOLCHAIN=auto`). |
| Signing | No `signingConfig` in Gradle. Release artifacts are built unsigned and signed by the workflows (`apksigner` for APKs in `release.yml`, `jarsigner` for the AAB in `build.yml`). No keystore is committed (`*.jks` is in `.gitignore`). |

## 2. Version management

| Item | Finding |
|---|---|
| Source | `gradle.properties`: `amneziawgVersionCode=15`, `amneziawgVersionName=3.1.5`. |
| Release behaviour | `release.yml` overrides `versionName` with the tag (`-PamneziawgVersionName`), so `gradle.properties` no longer matches what is shipped (`3.1.5` vs. `1.0.x`). **[fixed]**: the tag must now equal `amneziawgVersionName`. |
| versionCode monotonicity | Not checked. `v1.0.1` and `v1.0.2` were both built with `versionCode 14`, so 1.0.2 cannot be installed as an update over 1.0.1. `v1.0.3` uses 15. **[fixed]**: the release fails unless `versionCode` is greater than in every other `v*` tag. |
| Tags | `v1.0.0` (failed run), `v1.0.1`, `v1.0.2`, `v1.0.3` (RouteVPN), plus upstream AmneziaWG tags (`v3.1.x`, `v2.x`, ...). |

## 3. Existing workflows

| Workflow | Trigger | What it does | Assessment |
|---|---|---|---|
| `ci.yml` | PR, push to `master`, manual | Unit tests (`:tunnel:testDebugUnitTest`) and debug APK; memory diagnostics | Keep. Runs fork PRs on the self-hosted runner **[fixed: fork PRs skipped]**; actions not pinned **[fixed]**. |
| `release.yml` | `v*` tag | Signed per-ABI + universal APKs, `SHA256SUMS.txt`, draft GitHub Release | Keep and extend. Missing: AAB, version checks, signature fingerprint check, SBOM, provenance, release metadata, changelog. Keystore decoded before the Gradle build (build code ran with the keystore on disk) **[fixed]**. `contents: write` for the whole workflow **[fixed: job-level]**. |
| `build.yml` | manual | Signed release AAB (`jarsigner`) or debug APK | Its signed-AAB path duplicates what the release needs, signs from any ref chosen at dispatch time and uploads the signed AAB as a 90-day artifact. **[fixed]**: turned into an unsigned validation build; the signed AAB now comes from `release.yml`. |
| `emulator.yml` | manual | Instrumented smoke tests on API 21–34 emulators | Keep. Actions not pinned **[fixed]**. |

No reusable workflows or composite actions existed; the JDK/Go/Gradle/SDK setup was repeated in all
four workflows **[fixed: `.github/actions/android-env`]**. No release scripts, no `docs/`, no
changelog existed.

## 4. Security findings

| Finding | Status |
|---|---|
| Actions referenced by mutable tags (`@v5`, `@v3`, ...) | **[fixed]** for 7 of 9 actions, pinned to the commit SHAs the runner resolved in earlier runs. `softprops/action-gh-release@v2` and `actions/attest-build-provenance@v2` remain on tags (SHA not verifiable from this environment). |
| Fork pull requests execute on the self-hosted runner | **[fixed]** CI job skipped for PRs from forks. |
| Signing secrets reachable from any ref via `build.yml` dispatch | **[fixed]** `build.yml` no longer uses secrets. |
| Keystore present on disk while Gradle (third-party build code) ran | **[fixed]** keys are decoded after the build and removed right after signing. |
| No check that artifacts are signed with the intended certificate | **[fixed]** certificate fingerprints verified (enforced when `RELEASE_CERT_SHA256` is set). |
| Release secrets are repository-wide | Open: move them to the `github-release` environment (see `secrets-and-permissions.md`). |
| No tag protection | Open: add a tag ruleset for `v*`. |

## 5. Self-hosted runner findings

* Containers labelled `[self-hosted, docker-runner]`, Ubuntu image (git 2.43), root user.
* **Memory limits differ between jobs and containers**: cgroup `memory.max` of about 808 MiB,
  1.35 GiB and 3.95 GiB were observed. Android builds were OOM-killed (`oom_kill > 0`, "Gradle build
  daemon disappeared") below about 1.4 GiB. This is the most frequent cause of failed runs.
* `/dev/kvm` is available; `/dev/shm` is 64 MB; X11/GL libraries for the emulator are not installed.
* Runner containers are recreated (names reused, runner IDs change); a job was cancelled once by a
  runner shutdown.

## 6. Distribution findings

* GitHub Releases: draft releases with APKs and `SHA256SUMS.txt` only; release notes were generated
  by GitHub (no changelog). Checksums were not signed.
* Google Play: no AAB in releases, no Play integration, no documentation.
* The release signing key currently configured is a test key whose password was shared in a chat;
  it must be replaced with a real key before public distribution (see `signing.md`).
