# Disaster recovery

## A bad release

* **Still a draft**: delete the draft release (and the tag if it will be reused). Nothing reached
  users.
* **Published on GitHub**: edit the release to mark it as a pre-release or delete it, and publish a
  fixed version with a **higher `versionCode`**. Never reuse a `versionCode`: devices that installed
  the bad build will not "downgrade" to a build with the same or a lower code. Do not move a tag of a
  published release; the checksums, SBOM and provenance refer to the original files.
* **On Google Play**: halt the rollout in Play Console (Release → Halt), then upload a fixed version
  with a higher `versionCode`. Play does not allow re-using a `versionCode` either.

## Release key lost

APK updates signed with a new key will not install over existing installs. Users must uninstall
and reinstall (losing their tunnel configurations unless exported). If the app is on Google Play
with Play App Signing, Google holds the app signing key; a lost **upload** key can be reset through
Play Console support, but GitHub APKs still cannot be updated. Prevent this with offline encrypted
backups of the keystore and password ([signing.md](signing.md)).

## Release key leaked

1. Remove the secret and restrict access to the repository and environments.
2. Anyone with the key can publish updates that Android accepts as genuine. Tell users, and publish
   the new certificate fingerprint through an independent channel.
3. Generate a new key. Existing installs cannot move to it without reinstalling (APK Signature
   Scheme v3 key rotation could provide a path; it is not implemented in these workflows and must
   be planned separately).
4. On Google Play, request an upload key reset; for the app signing key, follow Play's key upgrade
   process.

## Checksum signing key leaked or lost

Revoke it (`gpg --gen-revoke`), create a new key, update `CHECKSUMS_GPG_PRIVATE_KEY`,
`CHECKSUMS_GPG_PASSPHRASE` and `CHECKSUMS_GPG_FINGERPRINT`, and publish the new fingerprint.
Existing APK signatures are unaffected.

## Play service account key leaked

Delete the key in Google Cloud, create a new one, update `PLAY_SERVICE_ACCOUNT_JSON`, and review
Play Console's release history for uploads you did not make.

## Runner lost

The workflows need only a runner with the labels `self-hosted` and `docker-runner` that meets
[self-hosted-runner.md](self-hosted-runner.md); no state lives on the runner except caches. Register
a new runner container with the same labels. Caches are rebuilt on the next run.

## Secrets lost from GitHub

Restore them from your offline copies (keystore + password, GPG key, service account JSON). The
workflows contain no key material, and nothing in the repository can recreate a key.

## After transferring or renaming the repository

The repository moved from `RouteTechnologies/amneziawg-android` to `rtlbd/routevpn-android`
(2026-11-27). Old URLs redirect, workflows use `GITHUB_REPOSITORY` so they follow the new name, and
`release.json` links are generated from it. Check the following after any transfer:

* **Runners** are registered per organization or repository. A runner group of the old organization
  is not available to the new one: re-register the runners or give the new repository access to a
  runner group with the labels `self-hosted` and `docker-runner`. Queued runs are cancelled by the
  transfer and must be started again.
* **Secrets and variables**: repository and environment secrets/variables normally move with the
  repository; organization-level ones do not. Verify `ANDROID_KEYSTORE_*`, `RELEASE_CERT_SHA256` and
  the other entries in [secrets-and-permissions.md](secrets-and-permissions.md).
* **Environments** (`github-release`, `google-play`), **rulesets** and branch protection: confirm
  they still exist and still restrict tags and reviewers.
* **Build provenance** attestations name the repository they were built in; releases attested before
  a rename must be verified against the old name (`gh attestation verify ... --repo <old name>`).
* Update remotes (`git remote set-url origin https://github.com/rtlbd/routevpn-android`), links in
  documentation and any Google Play listing or website that points to the repository.
