---
title: "Safe Container Updates on a Personal Docker Host"
date: 2024-01-22
lastmod: 2026-08-01
reviewed_at: 2026-08-01
maintenance_status: replacement
replaces_url: "/blog/2024-01-22-harnessing-the-power-of-watchtower-for-docker-automated-updates-made-simple.html"
author: Yoonsoo Park
description: "A controlled update workflow for Docker and Synology hosts using pinned versions, notifications, backups, health checks, and rollback instead of blind latest-tag updates."
categories:
  - Docker
  - DevOps
tags:
  - Docker
  - Container Updates
  - Security
  - Reliability
---

Automatic container replacement looks like maintenance, but it is also an unattended production deployment. Pulling a mutable `latest` tag and restarting several stateful services can introduce a breaking application or database migration with no reviewed change, tested backup, or rollback artifact.

For a personal Docker or Synology host, the practical goal is not “never automate.” It is to separate **discovery** from **deployment** and make each update observable and recoverable.

> **Review note (2026-10-21):** The August version used `containrrr/watchtower:1.7.1` as the monitor. That project is no longer maintained. Its maintainers [announced the archive](https://github.com/containrrr/watchtower/discussions/2135) on December 17, 2025, and the repository is now read-only. Separately, [Docker Engine 29.0 raised the daemon's minimum API version to v1.44](https://docs.docker.com/engine/release-notes/29/#2900), and Watchtower 1.7.1 failed against it with `client version 1.25 is too old` ([issue #2124](https://github.com/containrrr/watchtower/issues/2124)). [Docker Engine 29.3.0 lowered that minimum to v1.40](https://docs.docker.com/engine/release-notes/29/#2930) (March 5, 2026). That is still above the v1.25 client version in that error. The minimum depends on the exact Engine release, so check your own daemon with `docker version` (read-only; the Server section prints `API version: ... (minimum version ...)`). The example now uses a maintained notify-only monitor, and the checklist adds that Docker API check. The update procedure itself is unchanged.

## The current mental model

Use automation to detect new images and notify you. Promote a specific version or digest during a maintenance window after reviewing release notes. Back up persistent data, update one dependency group at a time, verify health and user workflows, then retain the previous image until the rollback window closes.

Do not start new setups on `containrrr/watchtower`. Upstream is archived, so it will not get fixes for Docker Engine changes or security issues. The maintainers also declined to vouch for any fork and asked users to assess forks themselves. If you already run it, check whether it can still talk to your daemon before trusting its silence (see the checklist).

For discovery, a notify-only tool is enough. [Diun](https://crazymax.dev/diun/) checks the images your containers use against the registry and reports what it finds. It never recreates containers. What it checks depends on its labels, and it sends notifications only after you configure a notifier (see below). If your Compose files live in Git, [Renovate](https://docs.renovatebot.com/docker/) can open a pull request with the new tag or digest instead, which leaves a review trail. Either way, any monitor that mounts `/var/run/docker.sock` has powerful control over the Docker daemon, which is effectively a host-level trust boundary. Run only a pinned, trusted image, limit what it observes, and do not expose it publicly.

## Pin the deployment

```yaml
services:
  app:
    image: ghcr.io/example/app:2.4.1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
    volumes:
      - app-data:/var/lib/app
    labels:
      - "diun.enable=true"
      - "diun.watch_repo=true"
      - "diun.sort_tags=semver"
      - "diun.max_tags=10"
      - 'diun.include_tags=^2\.[0-9]+\.[0-9]+$$'

  diun:
    image: crazymax/diun:4.33.0
    command: serve
    environment:
      TZ: "UTC"
      DIUN_WATCH_SCHEDULE: "30 8 * * 1"
      DIUN_PROVIDERS_DOCKER: "true"
    volumes:
      - diun-data:/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped

volumes:
  app-data:
  diun-data:
```

Diun uses a standard five-field cron expression, so `30 8 * * 1` means Monday at 08:30 in the container's `TZ` (UTC here; set your own). Leave `DIUN_PROVIDERS_DOCKER_WATCHBYDEFAULT` at its default (`false`). Diun then checks only containers labeled `diun.enable=true`, here just `app`. Diun reports and never redeploys, so the `:ro` mount is a reminder of intent, not a security boundary: read access to the Docker socket is still powerful.

The labels decide which question Diun answers. They are easy to get wrong:

- **Same tag only (the default).** With `diun.enable=true` alone, [`diun.watch_repo` defaults to `false`](https://crazymax.dev/diun/providers/docker/#docker-labels). Diun then compares the tag you run, `2.4.1`, with the registry. It can tell you that the image behind `2.4.1` changed, for example after a republished tag. It will not discover that `2.4.2` exists.
- **New tags in your version line.** `diun.watch_repo=true` makes Diun fetch the repository's tags. `diun.include_tags` then narrows them with a regular expression, here plain `2.x.y` releases (no `-rc` or `latest`). `diun.sort_tags=semver` orders them by semantic version, and `diun.max_tags` caps how many it tracks. The doubled `$$` is Compose's [escape for a literal `$`](https://docs.docker.com/reference/compose-file/interpolation/), so Diun receives `...[0-9]+$`. Widen or narrow the pattern to match your upgrade policy, for example `^2\.4\.` for patch releases only.

These are two different signals. "The deployed `2.4.1` image changed" is a reproducibility question; pinning by digest avoids it. "A `2.4.2` tag exists" is an upgrade candidate for the maintenance window below. If your Compose files live in Git, you can leave Diun on same-tag watching and let Renovate propose new tags as pull requests instead.

Diun's first scan records what it sees without notifying ([`firstCheckNotif`](https://crazymax.dev/diun/config/watch/#firstchecknotif) defaults to `false`). Later scans report changes. Nothing reaches you until you configure a notifier (mail, ntfy, Slack, and others; see [Diun notifications](https://crazymax.dev/diun/config/notif/)). Until then, results appear only in Diun's logs.

This example follows the Diun documentation, but I have not run it. After you deploy it, check the logs to confirm that Diun found `app` and lists the tags you expect, then send a test notification. A file that parses is not proof of detection. `4.33.0` was the current Diun release when this was reviewed. Pin whatever release you verified, the same way you pin the app.

## Maintenance-window procedure

1. Read application and image release notes, including required intermediate upgrades and schema changes.
2. Record the current image reference and Compose configuration.
3. Stop application writes if the product requires a consistent backup.
4. Back up volumes and external databases, then perform a restore test periodically. A successful archive command is not proof of recoverability.
5. Change the image to a specific version or immutable digest and pull it.
6. Recreate the affected service without deleting dependencies or volumes.
7. Wait for the health check, then test login, reads, writes, scheduled jobs, and dependent services.
8. Watch logs and resource use through the rollback window.

If the new version fails before a one-way data migration, restore the previous image reference. If it migrated data incompatibly, follow the application's documented downgrade path or restore the pre-update backup. Simply starting the old image against a newer schema can make damage worse.

## Tradeoffs

Full automatic updates reduce patch delay but accept unreviewed breaking changes. Monitor-only automation needs human time but preserves a decision gate. A registry digest is immutable and ideal for reproducibility, while a version tag is more readable but depends on publisher tag discipline. Renovate or Dependabot can propose Compose changes in Git and provide a review trail; that is valuable when the host configuration is managed as code.

For disposable stateless services, auto-update plus strong health and rollback automation may be reasonable. For databases, media indexes, identity services, or anything with irreplaceable state, require a maintenance gate.

Do not confuse a container's `healthy` status with application acceptance. A health endpoint can succeed while authentication, background jobs, storage permissions, or integrations are broken. Keep a short smoke-test list for the services you actually use. On Synology, also verify Container Manager still points to the intended project, volume paths retain their permissions, and reverse-proxy routes reach the recreated container.

## Migration checklist

- Replace `latest` with a version or digest.
- If an existing host still runs `containrrr/watchtower`, check it first. Running `docker version` is read-only: compare the server's `API version ... (minimum version ...)` line with what the monitor uses, and read the monitor's logs for `client version ... is too old`. A monitor that cannot connect does not notify you, and its silence looks like "no updates".
- Replace the archived Watchtower with a notify-only monitor or a Git-based update PR flow before changing deployment policy.
- Confirm the monitor's cron syntax and timezone, then trigger one test notification.
- Add real health checks and notifications.
- Inventory volumes, databases, configuration, and secrets; document backup and restore.
- Test one service group, dependency ordering, and rollback.
- Remove unused images only after the rollback period.
- Review Docker socket access and keep the management UI private.

Verified on **2026-10-21**.

## Primary sources

- [Goodbye containrrr/watchtower (archive announcement)](https://github.com/containrrr/watchtower/discussions/2135)
- [Docker Engine 29 release notes (minimum API version)](https://docs.docker.com/engine/release-notes/29/)
- [Diun Docker installation](https://crazymax.dev/diun/install/docker/) and [Docker provider](https://crazymax.dev/diun/providers/docker/)
- [Docker Compose healthcheck reference](https://docs.docker.com/reference/compose-file/services/#healthcheck)
- [Docker image digests](https://docs.docker.com/dhi/core-concepts/digests/)
