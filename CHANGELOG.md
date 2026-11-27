# Changelog

All notable changes to RouteVPN for Android. The release workflow publishes the section of the
version being released as the GitHub Release notes, so every release needs a `## [x.y.z]` section
here before it is tagged (see `docs/ci-cd/release-process.md`).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.0.4]

### Changed
- Release builds now take `versionName` from `gradle.properties` and fail when the tag does not
  match it, when `versionCode` is not higher than in every earlier release tag, or when this
  changelog has no section for the version.
- Release assets now include a signed Android App Bundle (`routevpn-<version>-release.aab`),
  `SBOM.spdx.json`, `release.json`, this changelog section and, when a checksum signing key is
  configured, a detached signature of `SHA256SUMS.txt`. Builds carry GitHub build provenance when the
  repository supports artifact attestations.
- APK and AAB signatures and signing certificate fingerprints are verified before publishing.

### Security
- GitHub Actions are pinned to commit SHAs where the SHA could be verified, workflow permissions
  are reduced to what each job needs, and pull requests from forks no longer run on the
  self-hosted runner.

## [1.0.3]

### Added
- Support for Android 5.0 and 6.0 (`minSdk` 21, previously 24).
- Instrumented smoke tests and a manual emulator workflow (API 21, 23, 24, 26, 29, 34).

### Changed
- `versionCode` 15.

## [1.0.2]

### Changed
- Release workflow creates draft GitHub Releases; GitHub Actions moved to their Node 24 versions.

### Known issues
- Built with the same `versionCode` (14) as 1.0.1, so it does not install as an update over 1.0.1.

## [1.0.1]

### Changed
- Rebranded to RouteVPN; application ID `io.routedns.awg`.

### Fixed
- `PersistentKeepalive` values that are not an integer between 0 and 65535 are rejected when a
  configuration is imported or saved, instead of failing when the tunnel starts.
