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
  the phone turns into a virtual gamepad (two analog sticks, d-pad with diagonals,
  L1/L2/R1/R2, turbo, a d-pad/analog swap). Two players via `?p=2`. Locks to landscape.
- **Desktop** — use the phone as a real **mouse + keyboard** for the box (uinput):
  a trackpad, the phone's native keyboard, modifier keys for shortcuts, and an
  on-demand live screen view (`grim`). Split left/right in landscape, stacked in portrait.
- **Movies / Series** — posters pulled from Jellyfin as a catalog, played with
  **mpv** on the TV (not Jellyfin's own player). Built-in search adds titles to
  Radarr/Sonarr and shows live download progress (a tiny Jellyseerr).
- **Music** — albums from a folder, played as an mpv playlist.
- **Media remote** — the same page becomes play/pause, seek, volume, audio/subtitle
  cycling and prev/next, over mpv's IPC socket. It switches between gamepad and
  remote automatically based on what is running. The now-playing cover fills the
  background, and subtitle/audio delay steppers fix lip-sync from the couch.
- **Continue watching** — a row of films you left partway, read from mpv's saved
  positions (matched to the library by hash, so it carries the real poster). Tap to
  resume where you stopped.
- **See the TV** — a button grabs the current TV frame (via `grim`) and shows it on
  the phone, refreshing every couple of seconds. Debugging what is on screen without
  getting up, and handy when the set is in another room.

### Requirements

- Linux with a **Sway or Hyprland** session on the TV (autologin on a TTY works well);
  it launches through `swaymsg` or `hyprctl` depending on which is running
- Python 3 and `python-evdev`; `mpv` for video/music; emulators you want (`pcsx2`, `retroarch`)
- For movies/series: the catalog/download stack on localhost — Jellyfin (`:8096`),
  Radarr (`:7878`), Sonarr (`:8989`). (The games tab doesn't use these, but it still
  needs the emulators, launchers and gamepad autoconfig — see
  [`emulators/`](emulators/).)
- For the gamepad, the user needs access to `/dev/uinput` (be in the `input` group
  with a udev rule granting it). Without it the hub still runs, just with the gamepad
  disabled, so you can develop the media side on any desktop.

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
| Login password | *(none)* | `PASSWORD` | `OIKOS_PASSWORD` |
| Auth token | *(none)* | `TOKEN` | `OIKOS_TOKEN` |
| mpv user home | *(current user)* | — | `OIKOS_HOME` |

`OIKOS_HOME` only matters if the hub runs as a different user than mpv (e.g. the hub
as root, mpv as your desktop user): point it at that user's home so "continue
watching" can find mpv's saved positions. "See the TV" needs `grim` and reads the
Sway session on `WAYLAND_DISPLAY=wayland-1`, `XDG_RUNTIME_DIR=/run/user/1000`.

API keys are **never hardcoded** — pass them or point at a file, per service:

| Service | Direct env | Or file env | Default file |
|---------|-----------|-------------|--------------|
| Jellyfin | `OIKOS_JF_KEY` | `OIKOS_JF_KEY_FILE` | `/srv/jellyfin/console-hub.key` |
| Radarr | `OIKOS_RADARR_KEY` | `OIKOS_RADARR_KEY_FILE` | (legacy path) |
| Sonarr | `OIKOS_SONARR_KEY` | `OIKOS_SONARR_KEY_FILE` | `docker exec sonarr` fallback |

With the compose stack, point the `*_KEY_FILE` vars at each container's `config.xml`
(e.g. `homelab/config/radarr/config.xml`) and `OIKOS_JF_KEY_FILE` at the `jf.key`
that `stack-setup.py` / `jellyfin-setup.sh` writes.

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
Jellyfin, Transmission, Radarr, Sonarr, Lidarr, Prowlarr, Bazarr, Jellyseerr,
FlareSolverr, Navidrome — **all in containers**, one shared `/media` mount so imports
hardlink without remote-path-mapping), then runs
[`homelab/stack-setup.py`](homelab/stack-setup.py) to wire it, and installs the hub +
launchers as a service. It is idempotent; review it before running.

**`stack-setup.py`** does the wiring deterministically over the APIs: the Jellyfin
setup wizard + Movies/Shows libraries + an API key, Transmission's download-dir,
each arr's root folder and Transmission download client (right category,
remove-completed), and registers the arrs in Prowlarr. It leaves your choices to you
(indexers — pass names like `stack-setup.py thepiratebay`; Bazarr provider account).
[`jellyfin-setup.sh`](homelab/jellyfin-setup.sh) does just the Jellyfin part standalone.
The 1080p cap is enforced by the hub (it requests the HD-1080p profile).

Prefer a coding agent? [`homelab/agent-config-prompt.md`](homelab/agent-config-prompt.md)
is a ready prompt: paste it to an agent with shell access and it clones the repo, runs
the bootstrap (which runs `stack-setup.py`), then finishes the interactive bits —
indexers and Bazarr — asking you for the choices, and verifies.


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
- **Optional login.** Set `OIKOS_PASSWORD` and the hub shows a **login screen** — a
  password field; the right password sets a long-lived cookie so the phone stays in.
  Prefer this for anything shared. Or set `OIKOS_TOKEN` for a formless URL token
  (`http://<host>:8100/?t=<token>`) good for a bookmark. Set both, either works.
  Unset (the default) means no auth — fine on a LAN you fully control.
- **What the login is and isn't.** One shared password over plain HTTP; the cookie
  holds its SHA-256, not the password. It keeps casual devices on your network (or a
  shared Tailscale node) out. It is **not** per-user auth and, without TLS, not proof
  against someone sniffing your wire — a lock on the door, not a vault.
- **No TLS by itself.** Plain HTTP. For encryption end to end, front it with
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
