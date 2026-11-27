# RouteVPN Android CI/CD

GitHub Releases are the distribution channel today. Google Play support is prepared but
**disabled** until it is explicitly configured ([google-play.md](google-play.md)).

| Document | Contents |
|---|---|
| [audit-report.md](audit-report.md) | State of CI/CD before this work, and what was fixed |
| [architecture.md](architecture.md) | How the pieces fit together, and why |
| [workflows.md](workflows.md) | Every workflow: trigger, permissions, what it does |
| [self-hosted-runner.md](self-hosted-runner.md) | Runner requirements and known runner problems |
| [build-process.md](build-process.md) | Local builds, variants, ABIs, versions |
| [release-process.md](release-process.md) | How to cut a release, step by step |
| [signing.md](signing.md) | Signing keys, Play App Signing, key setup and recovery |
| [checksum-verification.md](checksum-verification.md) | How users verify downloads |
| [sbom-and-provenance.md](sbom-and-provenance.md) | SBOM contents and build provenance |
| [github-release.md](github-release.md) | Release assets and `release.json` |
| [google-play.md](google-play.md) | Enabling Google Play publishing |
| [secrets-and-permissions.md](secrets-and-permissions.md) | Secrets, variables, environments, permissions, action pinning |
| [troubleshooting.md](troubleshooting.md) | Common failures and fixes |
| [disaster-recovery.md](disaster-recovery.md) | Bad releases, lost or leaked keys, broken runners |

## Quick reference

Release (details in [release-process.md](release-process.md)):

```sh
# 1. in a PR: bump amneziawgVersionName / amneziawgVersionCode in gradle.properties
#    and add a "## [1.0.5]" section to CHANGELOG.md; merge it
# 2. tag the merged commit
git tag v1.0.5 && git push origin v1.0.5
# 3. review the draft release on GitHub, then publish it
```

Verify a download (details in [checksum-verification.md](checksum-verification.md)):

```sh
sha256sum -c SHA256SUMS.txt --ignore-missing
apksigner verify --print-certs routevpn-1.0.5-arm64-v8a.apk
```

## Status of this setup

The workflows were statically checked (YAML, `bash -n` on every script, unit tests for the
scripts, and local runs of the signing/checksum step scripts with a test keystore). They have **not
yet run on GitHub**; the first CI run and the first release tag are the end-to-end test. See the
"Not yet verified" list in [release-process.md](release-process.md#not-yet-verified).
