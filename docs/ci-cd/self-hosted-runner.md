# Self-hosted runner

All workflows use runners with the labels `self-hosted` and `docker-runner` (group
`docker-runners`). GitHub-hosted runners are not used or required.

## Requirements

| Requirement | Why |
|---|---|
| Linux x86_64 container, `bash`, `git`, `curl`, `unzip` | Workflow steps and SDK setup |
| Root or password-less `sudo` with `apt-get` | python3, gnupg and emulator libraries are installed on demand when missing |
| Container memory limit ≥ 1.2 GiB (CI, builds, release); ≥ 3.5 GiB (emulator); 4 GiB+ recommended | Enforced by the "Check runner resources" step; below ~1.4 GiB Gradle gets OOM-killed |
| `/dev/kvm` passed into the container (emulator only) | Hardware-accelerated emulators |
| Disk: about 20 GB free | Android SDK, NDK, system images, Gradle and Go caches |
| Outbound HTTPS to GitHub, `dl.google.com`, `maven.google.com`, Maven Central, Gradle plugin portal, `proxy.golang.org`, `go.dev`, `storage.googleapis.com`, Ubuntu mirrors | Dependencies and toolchains |

Example (adapt to how your runners are started):

```sh
docker run -d --name runner-1 --restart unless-stopped \
  --memory=4g --memory-swap=8g --shm-size=1g --device /dev/kvm \
  <runner-image> ...

# raise the limit of a running container
docker update --memory=4g --memory-swap=8g runner-1

# show the limits of all runner containers
for c in $(docker ps --format '{{.Names}}' | grep -i runner); do
  echo "$c $(docker inspect "$c" --format '{{.HostConfig.Memory}} {{.HostConfig.ShmSize}}')"
done
```

Each job prints the runner name, `free -m` and the container cgroup `memory.max`, `memory.current`
and `memory.events` (`oom_kill > 0` means the kernel killed a process).

## Known problems (observed November 2026)

* **Memory limits differ between jobs**: `memory.max` of about 808 MiB, 1.35 GiB and 3.95 GiB were
  seen on containers with the same name. Jobs on the small containers failed with "Gradle build
  daemon disappeared unexpectedly" and `oom_kill 1`. Give every runner container a fixed limit and
  make sure the host has enough memory for all runners at once (the host has 11.8 GiB).
* `/dev/shm` is 64 MB. It did not cause failures, but `--shm-size=1g` is safer for the emulator.
* The image lacks the emulator's X11/GL/audio libraries; `emulator.yml` installs them each run.
  Baking them into the image (see the package list in `emulator.yml`) saves about a minute per job.
* Runner containers are recreated (names reused, runner IDs change). A job running during a
  restart fails with "The runner has received a shutdown signal"; re-run it.

## Isolation

* Pull requests from forks are not run (`ci.yml` job condition). Also set *Settings → Actions →
  General → Fork pull request workflows* to require approval.
* Signing keys are written under `$RUNNER_TEMP/keys` (mode 700) only during the signing step and
  removed afterwards and again in an `always()` step. If a runner dies mid-job, `$RUNNER_TEMP` is
  cleared when the next job starts; containers that are destroyed lose it entirely.
* The release job starts by deleting `$RUNNER_TEMP/dist` and `$RUNNER_TEMP/keys` from earlier runs.
* Prefer separate runner containers (or labels) for release jobs if untrusted contributors can open
  pull requests in this repository.
