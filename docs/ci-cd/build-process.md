# Build process

## Requirements for local builds

JDK 17, the Android SDK (`ANDROID_HOME`), and network access; Gradle downloads the NDK
(`26.1.10909125`) and CMake. The native `libwg-go` build downloads Go 1.24.2 and, because `go.mod`
requires Go 1.25, needs automatic Go toolchain download: do not set `GOTOOLCHAIN=local`.

```sh
git clone --recurse-submodules https://github.com/RouteTechnologies/amneziawg-android
cd amneziawg-android
./gradlew :tunnel:testDebugUnitTest          # unit tests
./gradlew :ui:assembleDebug                  # debug APK (io.routedns.awg.debug)
./gradlew :ui:bundleRelease                  # unsigned release AAB (all ABIs)
./gradlew -PamneziawgSplitAbi=true :ui:assembleRelease   # unsigned per-ABI + universal APKs
./gradlew :ui:writeReleaseDependencies       # ui/build/sbom/release-dependencies.txt
./gradlew :ui:lintRelease                    # lint report (not run in CI by default)
python3 scripts/ci/test_release_tool.py      # release tooling tests
```

On memory-constrained machines add `--max-workers=2 -Dorg.gradle.parallel=false` (CI does).

## Variants

| Build type | Application ID | Notes |
|---|---|---|
| `debug` | `io.routedns.awg.debug` | `versionName` suffix `-debug` |
| `release` | `io.routedns.awg` | R8 + resource shrinking; unsigned (signed by `release.yml`) |
| `googleplay` | `io.routedns.awg` | `initWith(release)`; no own sources, currently identical to `release` and unused by the workflows |

There are no product flavors. The Play AAB is built from `release`.

## ABIs and outputs

Every build contains `arm64-v8a`, `armeabi-v7a`, `x86` and `x86_64`. With `-PamneziawgSplitAbi=true`
`assembleRelease` produces `ui-<abi>-release-unsigned.apk` for each ABI plus
`ui-universal-release-unsigned.apk`; the release workflow renames them to
`routevpn-<version>-<abi>.apk` / `routevpn-<version>-universal.apk` after signing. All split APKs
share the same `versionCode` (they are distributed through GitHub, where users pick one; Google
Play uses the AAB instead).

Minimum Android version: `minSdk` in `settings.gradle.kts` (21 = Android 5.0); target and compile
SDK 36. Native libraries are aligned to 16 KB pages (`zipalign -P 16`, NDK linker flag
`max-page-size=16384`).

## Versions

`gradle.properties`:

| Property | Meaning |
|---|---|
| `amneziawgVersionName` | `versionName`; the release tag must be `v` + this value |
| `amneziawgVersionCode` | `versionCode`; must increase with every release, never reused |
| `amneziawgPackageName` | `applicationId` (`io.routedns.awg`); never change it for a released app |

`versionCode` is not derived from `versionName`. Use the next integer after the highest released
one; `python3 scripts/ci/release_tool.py check-version --tag v<version>` prints it as
`highest_previous_version_code` and fails if the new code is not higher.
