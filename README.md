# RouteVPN for Android

RouteVPN is an Android client built on the [AmneziaWG](https://amnezia.org/learn-more/31_amneziawg) protocol.
It is a derivative of the open-source [amnezia-vpn/amneziawg-android](https://github.com/amnezia-vpn/amneziawg-android)
project, which itself builds on the WireGuard Android GUI. See [COPYING](COPYING) for the license.

## Requirements

Android 5.0 (API 21) or newer. Release APKs are built for `arm64-v8a`, `armeabi-v7a`, `x86` and `x86_64`, plus a universal APK.

## Building

```
$ git clone --recurse-submodules https://github.com/rtlbd/routevpn-android
$ cd routevpn-android
$ ./gradlew assembleRelease
```

macOS users may need [flock(1)](https://github.com/discoteq/flock).

Requires JDK 17, Go (version from `tunnel/tools/libwg-go/go.mod`) and the Android SDK/NDK; Gradle downloads the NDK on demand.

## Releasing

Releases are built, signed and published as a draft GitHub Release by `.github/workflows/release.yml`
when a tag such as `v1.0.5` is pushed. The tag must equal `amneziawgVersionName` in
`gradle.properties`, `amneziawgVersionCode` must be higher than in every earlier release, and
`CHANGELOG.md` needs a section for the version. Assets: per-ABI and universal APKs, a signed AAB,
`SHA256SUMS.txt`, an SPDX SBOM, `release.json` and the changelog section.

CI/CD documentation, including the release procedure, signing, download verification and the
(disabled) Google Play integration: [docs/ci-cd/](docs/ci-cd/README.md).

## Application id

The installed application id is `io.routedns.awg` (`amneziawgPackageName` in `gradle.properties`).
The Kotlin/Java source package and the `R`/`BuildConfig` namespace remain `org.amnezia.awg` on purpose,
which keeps merging upstream changes simple.
