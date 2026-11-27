# Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `tag vX does not match amneziawgVersionName=Y` | Tag and `gradle.properties` differ | Set `amneziawgVersionName` (and bump `amneziawgVersionCode`) on `master`, then tag that commit |
| `amneziawgVersionCode=N must be greater than every released versionCode; vX already uses M` | `versionCode` not increased | Set `amneziawgVersionCode` above `M` |
| `CHANGELOG.md has no '## [X]' section` / `is empty` | Missing release notes | Add the section, merge, re-tag |
| `tag 'X' is not a release tag` | Tag format | Use `v1.2.3` or `v1.2.3-rc.1` |
| `Runner container ... is limited to N MiB` | Runner container memory too small | Raise the limit ([self-hosted-runner.md](self-hosted-runner.md)) or re-run on another runner |
| `Gradle build daemon disappeared unexpectedly` | OOM kill; check `oom_kill` in "Container resources (after build)" | Same as above |
| `go.mod requires go >= 1.25.0 (running go 1.24.2; GOTOOLCHAIN=local)` | Something set `GOTOOLCHAIN=local` after the shared setup | The `android-env` action sets `GOTOOLCHAIN=auto`; do not override it |
| `missing ui/build/outputs/apk/release/ui-<abi>-release-unsigned.apk` / `expected 5 APKs` | ABI split configuration or AGP output naming changed | Check `splits` in `ui/build.gradle.kts` and the files in `apk/release` |
| `package/versionCode/versionName do not match` | Build did not use `gradle.properties` values | Look for `-P` overrides or edits to `defaultConfig` |
| `Signing secrets ... are not set` | Secrets missing or not available to the `github-release` environment | Add them ([secrets-and-permissions.md](secrets-and-permissions.md)) |
| `APK signing certificate ... does not match RELEASE_CERT_SHA256` | Wrong keystore configured | Restore the correct keystore secret; never "fix" this by changing the variable unless the key change is intended |
| `AAB and APKs are not signed with the same certificate` | Inconsistent keys | Check `ANDROID_*` secrets |
| `checksum signing key ... does not match CHECKSUMS_GPG_FINGERPRINT` | Wrong GPG key in secrets | Restore the correct key |
| Release notes say "No GitHub build provenance attestation" | Attestations unavailable (private repo without Enterprise Cloud) or `id-token` blocked | Expected on such plans; otherwise see the step log |
| `The runner has received a shutdown signal` | Runner container restarted during the job | Re-run the job |
| Emulator: `libX11.so.6: cannot open shared object file` | Image lacks emulator libraries | Installed by `emulator.yml`; check that `apt-get` works |
| Emulator: `/dev/kvm is missing` | Container started without `--device /dev/kvm` | Recreate the runner container with it |
| Emulator: `Your device does not have enough disk space to run avd` / `Free space left: 0 MB` / `Only N MiB ... are free` | Runner disk full | Free disk on the runner host (`df -h`, `docker system prune`, old work directories) |
| Emulator disappears during boot, `oom_kill` > 0 | Memory below ~3 GiB (or too little headroom: 4 GiB is recommended) | Raise the container limit |
| Play: `no published GitHub Release for vX` | Release still a draft | Publish it first |
| Play: `versionCode N is not higher than M already on Google Play` | Version already uploaded | Release a new version |

## Re-running

* "Re-run failed jobs" re-uses the same commit and workflow file; it does not pick up fixes.
* For a release whose draft was never published: delete the draft, move the tag to the fixed commit
  (see [release-process.md](release-process.md#if-something-fails)).
