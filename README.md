# RouteVPN for Android

RouteVPN is an Android client built on the [AmneziaWG](https://amnezia.org/learn-more/31_amneziawg) protocol.
It is a derivative of the open-source [amnezia-vpn/amneziawg-android](https://github.com/amnezia-vpn/amneziawg-android)
project, which itself builds on the WireGuard Android GUI. See [COPYING](COPYING) for the license.

## Building

```
$ git clone --recurse-submodules https://github.com/RouteTechnologies/amneziawg-android
$ cd amneziawg-android
$ ./gradlew assembleRelease
```

macOS users may need [flock(1)](https://github.com/discoteq/flock).

Requires JDK 17, Go (version from `tunnel/tools/libwg-go/go.mod`) and the Android SDK/NDK; Gradle downloads the NDK on demand.

## Releasing

Pushing a tag such as `v3.1.5` runs `.github/workflows/release.yml` on the self-hosted `docker-runner`.
It builds signed APKs (universal plus one per ABI) and attaches them with `SHA256SUMS.txt` to a GitHub Release.
The tag sets `versionName`; bump `amneziawgVersionCode` in `gradle.properties` for every release.

Required repository secrets: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`
and optionally `ANDROID_KEY_PASSWORD`.

## Application id

The installed application id is `io.routedns.awg` (`amneziawgPackageName` in `gradle.properties`).
The Kotlin/Java source package and the `R`/`BuildConfig` namespace remain `org.amnezia.awg` on purpose,
which keeps merging upstream changes simple.
