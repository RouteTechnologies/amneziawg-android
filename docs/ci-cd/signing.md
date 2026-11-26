# Signing

## Keys

| Key | Signs | Where it lives |
|---|---|---|
| **Release key** | All APKs on GitHub; the AAB when no upload key is configured | Secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` (optional) |
| **Play upload key** (optional, future) | The AAB uploaded to Google Play | Secrets `PLAY_UPLOAD_KEYSTORE_BASE64`, `PLAY_UPLOAD_KEYSTORE_PASSWORD`, `PLAY_UPLOAD_KEY_ALIAS`, `PLAY_UPLOAD_KEY_PASSWORD` |
| **Play app signing key** | What Google Play delivers to devices | Held by Google (Play App Signing) |
| **Checksum key** (optional) | `SHA256SUMS.txt.sig` (OpenPGP) | Secrets `CHECKSUMS_GPG_PRIVATE_KEY`, `CHECKSUMS_GPG_PASSPHRASE` |

Android only installs an update if it is signed by the same certificate as the installed app.
Users who installed from GitHub can update from Google Play only if the Play app signing key is
**the same key as the GitHub release key**. To keep both channels compatible, when enrolling in
Play App Signing choose *use my own app signing key* and upload the release key (Play Console →
App integrity → "Export and upload a key"), then register a **separate upload key** and store it
in the `PLAY_UPLOAD_*` secrets. If you instead let Google generate the app signing key, GitHub and
Play installs can never update each other.

> **The key currently configured is a test key** whose password was shared in a chat. It must be
> replaced with a newly generated key before any public distribution. Releases signed with it cannot
> be updated by releases signed with the real key; users would have to uninstall.

## What the workflow does

`release.yml`, step "Sign and verify APKs and AAB" (runs only after the Gradle build):

1. Decodes the keystores into `$RUNNER_TEMP/keys` (mode 600); a `trap` deletes them when the step
   ends, success or failure.
2. APKs: `zipalign -P 16 4` then `apksigner sign` (v1 + v2 + v3 schemes; v1 is needed for
   Android 5–6). Passwords are passed through environment variables, never on the command line.
3. Verifies each APK (`apksigner verify --print-certs`, v2 required, exactly one signer) and that all
   APKs carry the same certificate. If the variable `RELEASE_CERT_SHA256` is set, the certificate
   must match it; otherwise the job warns and prints the fingerprint.
4. AAB: `jarsigner` with the upload key if configured, else the release key; verified with
   `jarsigner -verify`. Signed with the release key, its certificate must equal the APK
   certificate; signed with the upload key, it must equal `PLAY_UPLOAD_CERT_SHA256` when that is set.
5. Missing signing secrets fail the job. Nothing is ever published unsigned. Unsigned builds exist
   only in `build.yml` and are named `*-UNSIGNED.*`.

The workflow never creates, rotates or replaces a signing key.

## Creating the release key (once)

On a trusted machine, not on the runner:

```sh
keytool -genkeypair -v -alias routevpn-release -keyalg RSA -keysize 4096 -validity 10000 \
  -storetype PKCS12 -keystore routevpn-release.p12
keytool -list -v -keystore routevpn-release.p12 | grep 'SHA256:'     # certificate fingerprint
base64 -w0 routevpn-release.p12 > routevpn-release.p12.b64
```

Store `routevpn-release.p12` and its password in at least two offline, encrypted places (password
manager vault plus an encrypted offline copy). Then set the secrets (environment `github-release`
preferred, see [secrets-and-permissions.md](secrets-and-permissions.md)) and set the variable
`RELEASE_CERT_SHA256` to the fingerprint so a wrong key can never sign a release. Delete the `.b64`
file afterwards. A PKCS12 store uses one password for store and key; leave `ANDROID_KEY_PASSWORD`
empty in that case.

The upload key is created the same way (alias `routevpn-upload`) and registered in Play Console;
set `PLAY_UPLOAD_CERT_SHA256` to its fingerprint.

## Checksum signing key (optional)

```sh
gpg --quick-gen-key "RouteVPN release checksums <security@your-domain>" rsa4096 sign 5y
gpg --armor --export-secret-keys <FINGERPRINT>     # -> secret CHECKSUMS_GPG_PRIVATE_KEY
```

Set `CHECKSUMS_GPG_PASSPHRASE` and the variable `CHECKSUMS_GPG_FINGERPRINT`, and publish the
fingerprint somewhere users can check independently of the release (README, website). This key is
separate from the APK signing key on purpose.

## Recovery

See [disaster-recovery.md](disaster-recovery.md) for lost or leaked keys.
