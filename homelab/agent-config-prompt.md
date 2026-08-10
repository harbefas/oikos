# Agent prompt: finish configuring the homelab

Paste this to a coding agent with shell access on a fresh Arch box. `bootstrap-arch.sh`
installs deps, brings up the containerized stack, and runs `stack-setup.py` (which wires
Jellyfin + arrs + Prowlarr over the APIs). The agent only does the few interactive bits
it leaves, plus verification.

Copy everything below the line.

---

You are finishing a self-hosted media homelab on a fresh Arch machine.

## Step 0 - clone + bootstrap

```bash
git clone https://github.com/harbefas/oikos.git ~/oikos
cd ~/oikos
less homelab/bootstrap-arch.sh   # read it first
./homelab/bootstrap-arch.sh      # installs deps, `docker compose up`, runs stack-setup.py
```

Confirm the stack is up:

```bash
docker compose -f ~/oikos/homelab/docker-compose.yml ps
```

All should be running: Jellyfin `:8096`, Transmission `:9091`, Radarr `:7878`,
Sonarr `:8989`, Lidarr `:8686`, Prowlarr `:9696`, Bazarr `:6767`, Jellyseerr `:5055`,
FlareSolverr `:8191`, Navidrome `:4533`. If one is missing, check `docker logs <name>`.

Everything runs in **containers on one `/media` mount**, so paths match across
containers (no remote-path-mapping). Containers reach each other by **service name**
(`radarr`, `sonarr`, `transmission`, `prowlarr`, `flaresolverr`), not `localhost` or an
IP. `stack-setup.py` already created: Jellyfin libraries + API key (`homelab/jf.key`),
Transmission download-dir, each arr's root folder + Transmission download client
(category + remove-completed), and registered the arrs in Prowlarr.

## Rules

- **Idempotent**: `GET` a collection before `POST`; skip if it exists.
- **Discover schemas**: `GET` the `/schema` endpoint (or an existing object) before
  POSTing; mimic its exact shape, don't invent fields.
- **Verify each step** with a follow-up `GET`.
- **Ask the human** for choices/secrets: which indexers, the subtitle-provider account,
  the Tailscale login. Don't guess.
- **Never expose ports to the internet** (LAN + Tailscale only). Stop before any deletion.

## Get API keys (on disk, not to be invented)

```bash
for a in radarr sonarr lidarr prowlarr; do
  echo -n "$a: "; docker exec "$a" cat /config/config.xml | grep -oP '(?<=<ApiKey>)[^<]+'
done
```

Base URLs from the host: `http://localhost:PORT`. Radarr/Sonarr/Lidarr are API v3
(`/api/v3/...`); Prowlarr is v1 (`/api/v1/...`).

## Tasks (only what stack-setup.py leaves to you)

1. **Verify stack-setup ran.** `GET` radarr/sonarr `/api/v3/rootfolder` and
   `/api/v3/downloadclient`, and Prowlarr `/api/v1/applications` (Radarr/Sonarr/Lidarr
   should be present). If anything is missing, re-run `python homelab/stack-setup.py`
   and report the exact error.
2. **Indexers.** Ask the human which to add. Add via Prowlarr `POST /api/v1/indexer`
   (`GET /api/v1/indexer/schema` for the definition; route CloudFlare-protected ones
   through FlareSolverr at `http://flaresolverr:8191`). Shortcut for public ones:
   `python homelab/stack-setup.py thepiratebay`. Trigger `ApplicationIndexerSync` and
   verify the indexer shows up in Radarr.
3. **Bazarr** (three screens, or it silently does nothing): enable a subtitle language,
   create a Languages Profile with it, set it as the movie/series default, and add a
   provider (ask the human for the account). This repo pins Bazarr **1.5.1** on purpose.
4. **Console Hub.** `sudo systemctl start console-hub`; confirm
   `curl -s localhost:8100/api/games`, `/api/movies` and `/api/downloads` return JSON,
   and `curl -s -o /dev/null -w '%{http_code}' localhost:8100/home` is `200` (the TV
   Home Screen — no login required on that route by design). (The 1080p cap is
   automatic — the hub requests the HD-1080p profile.)
5. **Optional.** `tailscale up` for outside access; enable Jellyfin VAAPI in its
   dashboard; add the Home Screen kiosk to the compositor's autostart (ask the human
   if they want it — it's a Sway/Hyprland config line, see README.md#home-screen,
   not something to guess a path for).

## Report at the end

A short table: each piece — done / skipped-existing / failed — with one verification
line and the exact error for anything you couldn't finish. List what you asked the human.
