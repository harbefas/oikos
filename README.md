# Oikos

*oikos* (οἶκος) — the ancient Greek word for the household: the home as one running
whole. This is that, in a rack of one old laptop: a self-hosted media and
retro-gaming homelab you run on a screenless PC wired to the TV, and drive entirely
from your phone.

No app to install. Open one web page — **Console Hub**, the control surface — and
tap a game cover to launch it on the TV with your phone as the gamepad, or tap a
movie and the same page becomes the remote. Behind it, a full media stack
(Jellyfin + the *arr* apps) finds, downloads and organizes everything.

```
        phone browser  ──►  Console Hub  (:8100, one Python file)
                                 │
          ┌──────────────────────┼───────────────────────────┐
          ▼                      ▼                            ▼
   uinput gamepad          mpv on the TV               Jellyfin / Radarr /
   → PCSX2 / RetroArch      (IPC socket)                Sonarr / Lidarr APIs
   (games on the TV)       (movies · series · music)   (catalog · search · get)
```

The hub is the surface; the homelab underneath does the work. It is not a standalone
app — it launches emulators, `mpv` and the *arr* apps, so those have to be there. The
setup below stands the whole thing up; the hub is one component of it, installed along
the way.

## Repo layout

| Path | What |
|------|------|
| [`hub/`](hub/) | **Console Hub** — the phone control surface (`console-hub.py`) + the launcher scripts it shells out to |
| [`homelab/`](homelab/) | The stack: Arch `bootstrap-arch.sh`, `docker-compose.yml`, and an agent prompt that wires it all |
| [`emulators/`](emulators/) | Retro gaming: the virtual-gamepad autoconfig, RetroArch/PCSX2 setup, cover fetcher |

## Get started

On Arch, the bootstrap stands up the whole household — deps, media stack, emulators
config, and the hub as a service:

```bash
git clone https://github.com/harbefas/oikos.git ~/oikos
cd ~/oikos
./homelab/bootstrap-arch.sh          # read it first; installs packages + Docker
```

Then finish the wiring (indexers, quality caps, Jellyfin libraries, Bazarr) from the
printed checklist by hand, or let an agent do it — see [Homelab stack](#homelab-stack).

On another distro, adapt [`homelab/docker-compose.yml`](homelab/docker-compose.yml)
for the media stack, install the launchers and hub as the bootstrap does
(`sudo install -m755 hub/scripts/* /usr/local/bin/`, run `hub/console-hub.py` as a
service), and set up the emulators — see the sections below.

Once it is up, open `http://<server-ip>:8100` on your phone (same LAN, or over
Tailscale). Player 2: append `?p=2`.

---

## Console Hub

The single web page you drive everything from. One Python file, standard library
plus [`python-evdev`](https://pypi.org/project/evdev/). No app, no HTTPS required
(it uses the Fullscreen API, which works over plain HTTP on Android).

- **Games** — grid of box art for PS2 (PCSX2) and N64 (RetroArch). Tap to launch;
  the phone turns into a virtual gamepad. Two players via `?p=2` (two identical
  `uinput` devices, so an emulator autoconfig binds both).
- **Movies / Series** — posters pulled from Jellyfin as a catalog, played with
  **mpv** on the TV (not Jellyfin's own player). Built-in search adds titles to
  Radarr/Sonarr and shows live download progress (a tiny Jellyseerr).
- **Music** — albums from a folder, played as an mpv playlist.
- **Media remote** — the same page becomes play/pause, seek, volume, audio/subtitle
  cycling and prev/next, over mpv's IPC socket. It switches between gamepad and
  remote automatically based on what is running.

### Requirements

- Linux with a **Sway** session on the TV (autologin on a TTY works well)
- Python 3 and `python-evdev`; `mpv` for video/music; emulators you want (`pcsx2`, `retroarch`)
- For movies/series: the catalog/download stack on localhost — Jellyfin (`:8096`),
  Radarr (`:7878`), Sonarr (`:8989`). (The games tab doesn't use these, but it still
  needs the emulators, launchers and gamepad autoconfig — see
  [`emulators/`](emulators/).)
- Runs as a user in the `input` group (to create `uinput` devices)

### Configuration

Constants at the top of `hub/console-hub.py`. The paths also read from environment
variables, so you can override them in the systemd unit without editing code:

| What | Default | Constant | Env override |
|------|---------|----------|--------------|
| Media root | `/media` | `MEDIA` | `OIKOS_MEDIA` |
| ROMs | `<media>/roms/{ps2,n64}` | `ROMS` | `OIKOS_ROMS` |
| Game covers | `<roms>/.covers/<system>/<rom>.png` | `COVERS` | — |
| Music | `<media>/music/<album>/` | `MUSIC` | `OIKOS_MUSIC` |
| mpv IPC socket | `/tmp/mpv.sock` | `MPV_SOCK` | — |
| Port | `8100` | `PORT` | — |
| Jellyfin | `http://localhost:8096` | `JF` | — |
| Radarr / Sonarr | `http://localhost:{7878,8989}` | `RADARR` / `SONARR` | — |
| Auth token | *(none)* | `TOKEN` | `OIKOS_TOKEN` |

API keys are **read from disk at runtime**, never hardcoded: Jellyfin from
`/srv/jellyfin/console-hub.key`, Radarr/Sonarr from each container's `config.xml`.
Point these at your own paths.

The launchers in [`hub/scripts/`](hub/scripts/) (`run-ps2`, `run-n64`, `play-video`,
`play-audio`, `stop-game`) are what the hub shells out to. Install them on `PATH`.
They assume `XDG_RUNTIME_DIR=/run/user/1000` (uid 1000) and `WAYLAND_DISPLAY=wayland-1` —
adjust for your user. `play-video` carries the hardware-decode and audio tuning
(`LIBVA_DRIVER_NAME=iHD` for Intel iGPUs; change for AMD/NVIDIA).

### Run as a service

```ini
# /etc/systemd/system/console-hub.service
[Unit]
Description=Console Hub
After=graphical.target

[Service]
User=youruser
ExecStart=/usr/bin/python3 /opt/console-hub/console-hub.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now console-hub
```

---

## Homelab stack

[`homelab/bootstrap-arch.sh`](homelab/bootstrap-arch.sh) stands up everything under
the hub. It installs deps, creates `/media` with the permissions hardlinks need,
brings up the media stack ([`homelab/docker-compose.yml`](homelab/docker-compose.yml):
Jellyfin, Radarr, Sonarr, Lidarr, Prowlarr, Bazarr, Jellyseerr, FlareSolverr,
Navidrome), installs the hub + launchers as a service, and prints a checklist for
the parts that can't be scripted (Tailscale login, indexers, quality profiles,
Jellyfin libraries, Bazarr languages). It is idempotent; review it before running.

That checklist is also written as an **agent prompt**:
[`homelab/agent-config-prompt.md`](homelab/agent-config-prompt.md). Paste it to a
coding agent with shell access on a fresh Arch box and it does the whole thing end
to end — clones the repo, runs the bootstrap, then wires the arr stack, quality
caps, Jellyfin and Bazarr through their APIs (asking you for indexer credentials
and the Tailscale login).

<details>
<summary><b>The full agent prompt</b> (click to expand — copy from here)</summary>

You are setting up a self-hosted media homelab on a fresh Arch Linux machine, end
to end. Work in order, verifying as you go.

### Step 0 - install and run the bootstrap

Clone the repo and run the bootstrap as the normal user (it uses sudo internally;
do not run it as root):

```bash
git clone https://github.com/harbefas/oikos.git ~/oikos
cd ~/oikos
less homelab/bootstrap-arch.sh   # read it first; it installs packages and Docker
./homelab/bootstrap-arch.sh
```

Read the script before running it. When it finishes, confirm the containers are up
before continuing:

```bash
docker compose -f ~/oikos/homelab/docker-compose.yml ps
```

Every container below should be running: Jellyfin (`:8096`), Radarr (`:7878`),
Sonarr (`:8989`), Lidarr (`:8686`), Prowlarr (`:9696`), Bazarr (`:6767`),
Jellyseerr (`:5055`), FlareSolverr (`:8191`), Navidrome (`:4533`). Transmission
runs on the host at `:9091`. Media lives under `/media`
(`/media/{movies,series,music,downloads}`, downloads split into
`movies/series/music` categories). If a container is missing, fix that (check
`docker logs <name>`) before moving on.

### Rules

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

### Get the API keys (they are on disk, not to be invented)

```bash
for a in radarr sonarr lidarr prowlarr; do
  echo -n "$a: "; docker exec "$a" cat /config/config.xml | grep -oP '(?<=<ApiKey>)[^<]+'
done
```

Use each as the `X-Api-Key` header. Base URLs from the host: `http://localhost:PORT`.
Radarr/Sonarr/Lidarr are API v3 (`/api/v3/...`); Prowlarr is v1 (`/api/v1/...`).

### Tasks, in order

1. **Root folders.** In Radarr add `/media/movies`, Sonarr `/media/series`,
   Lidarr `/media/music` (`POST /api/v3/rootfolder`). Verify with a `GET`.

2. **Download client.** In Radarr, Sonarr, Lidarr add Transmission
   (`POST /api/v3/downloadclient`): host `172.17.0.1`, port `9091`, and the right
   category (`movies`/`series`/`music`). GET the downloadclient `/schema` for
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

7. **Jellyfin libraries.** Add a Movies library pointing at `/media/movies` and a
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

### Report at the end

A short table: each service, configured or skipped-existing, and one verification
line (e.g. "Radarr: root folder + Transmission client + 1080p profile OK, 3
indexers synced"). List anything you asked the human for and any step you could
not complete, with the exact error.

</details>

---

## Emulators

Game launching (N64 via RetroArch, PS2 via PCSX2) and the two-player virtual
gamepad have their own setup — the RetroArch autoconfig the phone pad needs, the
parallel-rdp core, PS2 BIOS/memory card, and cover fetching. See
[`emulators/README.md`](emulators/README.md). Bring your own ROMs and PS2 BIOS.

## Security

Be honest with yourself about what this is: a web server that **launches and kills
processes on the host** (emulators, mpv) on request. Treat it accordingly.

- **Trust boundary is the network.** Run it on your LAN, and reach it from outside
  over Tailscale (or another VPN). **Never** port-forward `:8100` to the internet or
  put it behind a public reverse proxy. There is no sandbox around what it can start.
- **Optional shared token.** Set `OIKOS_TOKEN` (env var) and every request must carry
  it. First visit with `http://<host>:8100/?t=<token>` sets a cookie; after that the
  phone just works. Unset (the default) means no auth — fine on a LAN you control,
  handy when you share a Tailscale node with someone you don't want launching games.
  It is a single shared secret over HTTP, not real user auth — a speed bump, not a wall.
- **No TLS by itself.** Plain HTTP. If you want encryption end to end, front it with
  `tailscale serve` (Tailscale-issued cert) rather than exposing it.

## Notes

- Game covers come from [libretro-thumbnails](https://github.com/libretro-thumbnails)
  via [`emulators/fetch-covers.py`](emulators/fetch-covers.py); drop a `<rom-name>.png`
  into the covers folder if a title does not match.
- Music has no search on purpose — public indexers rarely carry music and Lidarr's
  metadata is poor. Fill `/media/music` yourself.
- Legality is on you: use your own game dumps and legally obtained media.

## License

MIT. See [LICENSE](LICENSE).
