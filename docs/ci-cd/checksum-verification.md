# Verifying a download

A checksum proves the file was not corrupted or changed **relative to `SHA256SUMS.txt`**. It does
not prove who made it: anyone who can change the file can change the checksum list too. Authenticity
comes from the APK signature, the optional OpenPGP signature of the checksums, and build provenance.

## 1. Checksums

Download the APK (or AAB) and `SHA256SUMS.txt` from the same release into one directory:

```sh
sha256sum -c SHA256SUMS.txt --ignore-missing
# routevpn-1.0.4-arm64-v8a.apk: OK
```

macOS: `shasum -a 256 -c SHA256SUMS.txt --ignore-missing`.
Windows PowerShell: `Get-FileHash routevpn-1.0.4-arm64-v8a.apk -Algorithm SHA256` and compare
with the line in `SHA256SUMS.txt`.

## 2. Signature of the checksums (when published)

If the release has `SHA256SUMS.txt.sig`, verify it with the RouteVPN checksum key. Get the key's
fingerprint from a source other than the release (README or website), then:

```sh
gpg --import routevpn-checksums-signing-key.asc
gpg --fingerprint            # compare with the published fingerprint
gpg --verify SHA256SUMS.txt.sig SHA256SUMS.txt
# gpg: Good signature from "RouteVPN release checksums ..."
```

## 3. APK signing certificate

With Android build-tools:

```sh
apksigner verify --print-certs routevpn-1.0.4-arm64-v8a.apk | grep 'SHA-256'
```

The digest must equal the "APK signing certificate SHA-256" in the release notes and
`signing.apk_certificate_sha256` in `release.json`, and must stay the same across releases.
Android itself refuses an update signed with a different certificate.

For the AAB: `keytool -printcert -jarfile routevpn-1.0.4-release.aab`.

## 4. Build provenance

See [sbom-and-provenance.md](sbom-and-provenance.md#verifying-provenance).
