# Architecture

```
 pull request / push to master          git tag vX.Y.Z (= amneziawgVersionName)
            |                                        |
            v                                        v
         ci.yml                                release.yml  (environment: github-release)
  unit tests, debug APK,                             |
  release tooling tests,              1. validate tag, versionName, versionCode, changelog
  SBOM dry run                        2. Gradle: :ui:bundleRelease + assembleRelease (ABI splits)
                                         -- no secrets available --
                                      3. verify outputs with aapt2 (package, versionCode,
                                         versionName, minSdk, ABIs) and the AAB contents
                                      4. decode keys -> zipalign + apksigner (APKs),
                                         jarsigner (AAB) -> verify signatures and certificate
                                         fingerprints -> delete keys
                                      5. SHA256SUMS.txt (+ optional OpenPGP signature)
                                      6. SBOM.spdx.json, build provenance attestation,
                                         release.json, release notes from CHANGELOG.md
                                      7. draft GitHub Release with all assets
                                                     |
                                       maintainer reviews and publishes the draft
                                                     |
                                                     v  (manual, disabled by default)
                                           play-publish.yml  (environment: google-play)
                                  download AAB from the published release, verify checksum,
                                  versionCode > Play, upload to a track (dry run by default)
```

`build.yml` (manual unsigned validation builds) and `emulator.yml` (manual instrumented tests on
API 21–34 emulators) sit beside this flow. All jobs run on the self-hosted runner
`[self-hosted, docker-runner]`; the shared setup is the composite action
`.github/actions/android-env`.

## Design decisions

**Signing happens in the workflow, not in Gradle.** The build has no `signingConfig`; Gradle
produces unsigned outputs and the release job signs them afterwards. Keys are decoded only after
the Gradle build has finished and are deleted at the end of the signing step, so the build (and
any third-party Gradle plugin or dependency) never runs with key material on disk or in its
environment. This also keeps local builds free of signing setup.

**One release job, two Gradle invocations.** `:ui:bundleRelease` builds the AAB (all ABIs in one
bundle); `assembleRelease -PamneziawgSplitAbi=true` then packages the per-ABI and universal APKs,
reusing the already compiled native code and dex. The ABI split property is not passed to the
bundle build, because it only affects APK packaging. A single job avoids passing unsigned
artifacts between jobs and fits the memory-constrained runner pool.

**The tag must match `gradle.properties`.** `amneziawgVersionName` is the single source of truth;
the tag is checked against it, and `versionCode` must be greater than in every other `v*` tag
(`scripts/ci/release_tool.py check-version`). Previously the tag overrode `versionName`, which let
`gradle.properties` drift and let two releases ship with the same `versionCode`.

**Draft first.** Releases are always created as drafts. A person reviews the assets and publishes;
nothing reaches users automatically.

**Google Play is a separate, manual, gated workflow.** It reuses the AAB from a *published* GitHub
Release instead of rebuilding, so the file on Play is byte-identical to the one in the release and
its checksum is verified against `SHA256SUMS.txt`. It needs a repository variable, a protected
environment and a manual dispatch, and defaults to a dry run.

**No new build dependencies.** The SBOM uses a small Gradle task built on Gradle's dependency
resolution plus a Python standard-library script; Play publishing uses the Android Publisher REST
API directly. No Gradle plugin or third-party publishing action was added.
