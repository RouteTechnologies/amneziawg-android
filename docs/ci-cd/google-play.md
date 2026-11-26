# Google Play (prepared, disabled)

`play-publish.yml` uploads the signed AAB of a **published** GitHub Release to Google Play. It is
disabled: with `PLAY_PUBLISHING_ENABLED` unset it only prints a notice. Tags never trigger it.

> Not yet exercised: the Google Play API calls and the GitHub asset download have never run against
> real services. Start with `dry-run` on the internal track.

## How it works

1. Downloads `release.json`, `SHA256SUMS.txt` and `routevpn-<v>-release.aab` from the GitHub Release
   for the given tag (the release must be published, not a draft).
2. Checks the AAB's SHA-256 against `SHA256SUMS.txt`, that `release.json` belongs to the tag, and
   the AAB signature (`jarsigner -verify`).
3. Authenticates with the service account (OAuth 2.0 JWT bearer, signed with `openssl`), opens an
   edit, and checks that the release's `versionCode` is higher than every `versionCode` on any track.
4. `dry-run: true` (default): deletes the edit and stops. Otherwise uploads the bundle, checks that
   Play read the expected `versionCode`, assigns it to the track with the chosen status, and commits.

Implementation: `scripts/ci/play_publish.py` (standard library only, Android Publisher API v3).

## Activation

1. **Play Console**: create the app with package `io.routedns.awg`; enrol in Play App Signing using
   the existing release key and a separate upload key ([signing.md](signing.md)). The first upload
   of a new app may have to be done by hand in Play Console.
2. **Service account**: in Google Cloud create a service account, enable the *Google Play Android
   Developer API*, create a JSON key; in Play Console → Users and permissions, invite the service
   account with release permissions for this app only.
3. **GitHub environment `google-play`** (Settings → Environments): required reviewers, deployment
   branches limited to `master`; add the secret `PLAY_SERVICE_ACCOUNT_JSON` (whole JSON key) to this
   environment only.
4. **Upload key** (optional but recommended): secrets `PLAY_UPLOAD_KEYSTORE_BASE64`,
   `PLAY_UPLOAD_KEYSTORE_PASSWORD`, `PLAY_UPLOAD_KEY_ALIAS` (+ `PLAY_UPLOAD_KEY_PASSWORD`) and variable
   `PLAY_UPLOAD_CERT_SHA256` in `github-release`; the next release's AAB is then signed with it.
5. **Enable**: repository variable `PLAY_PUBLISHING_ENABLED=true`.
6. **Dry run**: Actions → *Google Play publish* → tag `v1.0.x`, track `internal`, `dry-run` on. A
   reviewer approves the environment; the log shows the highest `versionCode` on Play.
7. **First upload**: same with `dry-run` off, status `draft`; finish the release in Play Console.

## Tracks and promotion

Use `internal` first, then `alpha` (closed testing), `beta` (open testing), `production`. Each run
uploads the bundle to one track. Promoting an existing build between tracks is done in Play Console;
running the workflow again for the same tag fails because the `versionCode` is already on Play.
Staged rollouts (`inProgress` with a user fraction) are not implemented.

## Disabling again

Delete or change `PLAY_PUBLISHING_ENABLED`, and/or remove the secret from the environment.
