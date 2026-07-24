# Agent prompt: configure the homelab after bootstrap

Paste this to a coding agent (Claude Code, etc.) that has **shell access on the
homelab machine** and permission to run `docker`, `curl`, and edit files. It does
the wiring that `bootstrap-arch.sh` deliberately leaves manual: linking the arr
stack, setting quality caps, Jellyfin libraries, and Bazarr.

Copy everything below the line.

---

You are configuring a self-hosted media homelab. `bootstrap-arch.sh` already ran:
Docker is up and these containers are running on the host — Jellyfin (`:8096`),
Radarr (`:7878`), Sonarr (`:8989`), Lidarr (`:8686`), Prowlarr (`:9696`),
Bazarr (`:6767`), Jellyseerr (`:5055`), FlareSolverr (`:8191`), Navidrome (`:4533`).
Transmission runs on the host at `:9091`. Media lives under `/media`
(`/media/{filmes,series,musica,downloads}`, downloads split into
`filmes/series/musica` categories).

## Rules

- **Idempotent.** Before creating anything, `GET` the collection and skip if it
  already exists. Never create duplicates.
- **Discover schemas, don't assume them.** The arr APIs change. For any object you
  POST, first `GET` an existing example (or the `/schema` endpoint) and mimic its
  exact shape. Do not invent fields.
- **Verify every step** with a follow-up `GET` and report pass/fail before moving on.
- **Containers talk to each other and to Transmission via `172.17.0.1`**, never
  `localhost` (inside a container localhost is itself). The host's LAN IP changes
  with DHCP; `172.17.0.1` (docker0 gateway) does not.
- **Ask the human** for anything interactive or secret: indexer URLs/credentials,
  Tailscale login, preferred language. Do not guess these.
- **Never expose ports to the internet.** Access is LAN + Tailscale only.
- Stop before any deletion and show what you would remove.

## Get the API keys (they are on disk, not to be invented)

```bash
for a in radarr sonarr lidarr prowlarr; do
  echo -n "$a: "; docker exec "$a" cat /config/config.xml | grep -oP '(?<=<ApiKey>)[^<]+'
done
```

Use each as the `X-Api-Key` header. Base URLs from the host: `http://localhost:PORT`.
Radarr/Sonarr/Lidarr are API v3 (`/api/v3/...`); Prowlarr is v1 (`/api/v1/...`).

## Tasks, in order

1. **Root folders.** In Radarr add `/media/filmes`, Sonarr `/media/series`,
   Lidarr `/media/musica` (`POST /api/v3/rootfolder`). Verify with a `GET`.

2. **Download client.** In Radarr, Sonarr, Lidarr add Transmission
   (`POST /api/v3/downloadclient`): host `172.17.0.1`, port `9091`, and the right
   category (`filmes`/`series`/`musica`). GET the downloadclient `/schema` for
   the Transmission implementation to get field names right. Test with the
   client's `/test` action before saving.

3. **Remote path mapping.** In Radarr and Sonarr add
   (`POST /api/v3/remotepathmapping`) host `172.17.0.1`, remote `/media/`,
   local `/media/`. (Both sides are `/media/` here because the single mount is
   symmetric — confirm by checking an existing import path.) Without this, imports
   fail with `No files found are eligible for import`.

4. **Quality cap = 1080p.** Pick or edit a profile so 2160p and Remux are
   **disabled** and the cutoff is a 1080p tier (`/api/v3/qualityprofile`). GET the
   existing profiles, find the 1080p one, and make sure the big tiers are
   unchecked. Set it as each root folder's default. 4K on a TV costs 4-10x for no
   visible gain.

5. **Prowlarr -> arrs.** In Prowlarr, add each arr as an Application
   (`POST /api/v1/applications`) with its API key and the `172.17.0.1` address, so
   indexers sync automatically. Then ask the human which indexers to add and add
   them (`/api/v1/indexer`), routing CloudFlare-protected ones through FlareSolverr
   at `172.17.0.1:8191`. Trigger a sync and verify the indexers appear in Radarr.

6. **removeCompletedDownloads.** In Radarr/Sonarr/Lidarr media-management settings,
   enable "remove completed downloads" (hardlinks between the split mounts are
   cross-device, so this avoids double disk use). Verify via the config GET.

7. **Jellyfin libraries.** Add a Movies library pointing at `/media/filmes` and a
   Shows library at `/media/series`. Enable VAAPI hardware transcoding (the
   container already has `/dev/dri`). Do this via the Jellyfin API with an API key,
   or tell the human the two clicks if the API path is unclear. Verify a scan runs.

8. **Bazarr (three screens, or it silently does nothing).** Enable a subtitle
   language, create a Languages Profile with it, and apply that profile to
   movies/series (`profileId` on the items). Add at least one subtitle provider.
   With a provider but no language it neither searches nor errors. If the API is
   awkward, stop the container, edit `config.yaml`
   (`enabled_languages`, `*_default_profile`) and `bazarr.db`, restart. The
   container overwrites config on exit, so it must be stopped first.

9. **Console Hub.** Ensure `/opt/console-hub/console-hub.py` has the correct paths
   and that the Jellyfin/Radarr/Sonarr keys are where it reads them (see its
   constants). `sudo systemctl start console-hub`, then confirm
   `curl -s localhost:8100/api/games` and `/api/movies` return JSON.

## Report at the end

A short table: each service, configured or skipped-existing, and one verification
line (e.g. "Radarr: root folder + Transmission client + 1080p profile OK, 3
indexers synced"). List anything you asked the human for and any step you could
not complete, with the exact error.
