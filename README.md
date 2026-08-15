# Oikos

*oikos* (οἶκος) — the ancient Greek word for the household: the home as one running
whole. This is that, in a rack of one old laptop: a self-hosted media and
retro-gaming homelab you run on a screenless PC wired to the TV, and drive entirely
from your phone.

No app to install. Open one web page — **Console Hub**, the control surface — and
tap a game cover to launch it on the TV with your phone as the gamepad, or tap a
movie and the same page becomes the remote. Behind it, a full media stack
(Jellyfin + the *arr* apps) finds, downloads and organizes everything.

The TV itself also gets its own surface: the **Home Screen**, a kiosk page that
opens on boot and browses like a streaming app (Netflix-style sidebar), driven
entirely by a d-pad sent from the phone — no remote, no keyboard on the TV.

```
        phone browser  ──►  Console Hub  (:8100, one Python file)
                                 │
          ┌──────────────────────┼───────────────────────────┐
          ▼                      ▼                            ▼
   uinput gamepad          mpv on the TV               Jellyfin / Radarr /
   → PCSX2 / RetroArch      (IPC socket)                Sonarr / Lidarr APIs
   (games on the TV)       (movies · series · music)   (catalog · search · get)

        TV kiosk browser  ──►  Home Screen  (same server, /home)
                                 │
                     d-pad + search keystrokes, streamed live
                     from the phone's Controle tab (/api/remote,
                     /api/search-query) — the TV has no input of its own
```

The hub is the surface; the homelab underneath does the work. It is not a standalone
app — it launches emulators, `mpv`, the *arr* apps and the kiosk browser itself, so
those have to be there. The setup below stands the whole thing up; the hub is one
component of it, installed along the way.

## Repo layout

| Path | What |
|------|------|
| [`hub/`](hub/) | **Console Hub** (phone, `/`) and **Home Screen** (TV, `/home`) — both served by `console-hub.py` — + the launcher scripts it shells out to |
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

- **Games** — grid of box art for PS2 (PCSX2), N64 (RetroArch) and your **Steam**
  library (launched via `steam://`). Tap to launch;
  the phone turns into a virtual gamepad (two analog sticks, d-pad with diagonals,
  L1/L2/R1/R2, turbo, a d-pad/analog swap). Two players via `?p=2`. Locks to landscape.
- **Movies / Series / Music** — posters pulled from Jellyfin as a catalog, played with
  **mpv** on the TV (not Jellyfin's own player).
- **Apps** — a grid of one-tap launchers for anything else on the box: LibreWolf,
  Jellyfin's own web UI, Navidrome, Kodi, Spotify (native client) — whatever you add to the `APPS`
  list. Launching one closes the Home Screen kiosk first (see below), so it always
  gets the full screen.
- **Busca** — search across Radarr (movies), Sonarr (series) **and Lidarr (music)**
  at once, each result showing synopsis/genres/rating pulled straight from the
  lookup, with a "＋ download" action (or "already in your library"). A tiny
  Jellyseerr, three services deep. Browsing the Music tab itself has no search box
  on purpose — see [Notes](#notes).
- **Media remote** — the same page becomes play/pause, seek, volume, audio/subtitle
  cycling and prev/next, over mpv's IPC socket. The Controle tab is **contextual**: a
  gamepad while a game runs, this media remote while something plays, or a d-pad for
  the TV's Home Screen the rest of the time — driven by `/api/status`'s `kind`. The
  now-playing cover fills the background, and subtitle/audio delay steppers fix
  lip-sync from the couch. A "✕ Close everything" button kills whatever's in the
  foreground (game, media or app) and brings the Home Screen back.
- **Continue watching** — a row of films you left partway, read from mpv's saved
  positions (matched to the library by hash, so it carries the real poster). Tap to
  resume where you stopped.
- **See the TV** — a button grabs the current TV frame (via `grim`) and shows it on
  the phone, refreshing every couple of seconds. Debugging what is on screen without
  getting up, and handy when the set is in another room.

Mouse/keyboard control of the box itself (not the TV apps) was extracted to a
sibling project: [**hyprpad**](https://github.com/harbefas/hyprpad).

### Requirements

- Linux with a **Sway or Hyprland** session on the TV (autologin on a TTY works well);
  it launches through `swaymsg` or `hyprctl` depending on which is running
- Python 3 and `python-evdev`; `mpv` for video/music; emulators you want (`pcsx2`, `retroarch`)
- For movies/series/music: the catalog/download stack on localhost — Jellyfin
  (`:8096`), Radarr (`:7878`), Sonarr (`:8989`), Lidarr (`:8686`). (The games tab
  doesn't use these, but it still needs the emulators, launchers and gamepad
  autoconfig — see [`emulators/`](emulators/).)
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
| Radarr / Sonarr / Lidarr | `http://localhost:{7878,8989,8686}` | `RADARR` / `SONARR` / `LIDARR` | — |
| Login password | *(none)* | `PASSWORD` | `OIKOS_PASSWORD` |
| Auth token | *(none)* | `TOKEN` | `OIKOS_TOKEN` |
| mpv user home | *(current user)* | — | `OIKOS_HOME` |
| Steam library | `<OIKOS_HOME>/.local/share/Steam` | `STEAM_ROOT` | `OIKOS_STEAM` |
| hyprpad instance | *(none)* | `HYPRPAD` | `OIKOS_HYPRPAD` (+ `OIKOS_HYPRPAD_TOKEN`) |

### PC tab (optional, hyprpad)

[hyprpad](https://github.com/harbefas/hyprpad) turns the phone into the mouse and
keyboard of a Wayland desktop. Set `OIKOS_HYPRPAD` to its URL
(`http://desktop:8123`) and the hub grows a **PC** tab that embeds it, so the phone
opens one page instead of two. The tab only shows while that host answers (probed
every 15s) and the frame loads on first open, not on page load.

Running hyprpad on the same box as the hub (so the phone drives the TV's own
session)? `OIKOS_HYPRPAD=http://localhost:8123` — the page rewrites `localhost` to
whatever host the phone used to reach the hub, since the frame loads on the phone,
not on the server. Point it at another machine's address to control that one instead.

Two gotchas: the browser blocks an `http://` frame inside an `https://` page — serve
both the same way (`tailscale serve` on each, or plain HTTP on both) — and hyprpad's
Voice button needs the microphone, which needs hyprpad on HTTPS. Everything else
works over plain HTTP on the LAN.

`OIKOS_HOME` only matters if the hub runs as a different user than mpv (e.g. the hub
as root, mpv as your desktop user): point it at that user's home so "continue
watching" can find mpv's saved positions and the Steam library resolves under it
(otherwise a root-run hub looks in `/root` and lists no Steam games). Set `OIKOS_STEAM`
directly if Steam lives outside that home. "See the TV" needs `grim` and reads the
Sway session on `WAYLAND_DISPLAY=wayland-1`, `XDG_RUNTIME_DIR=/run/user/1000`.

API keys are **never hardcoded** — pass them or point at a file, per service:

| Service | Direct env | Or file env | Default file |
|---------|-----------|-------------|--------------|
| Jellyfin | `OIKOS_JF_KEY` | `OIKOS_JF_KEY_FILE` | `/srv/jellyfin/console-hub.key` |
| Radarr | `OIKOS_RADARR_KEY` | `OIKOS_RADARR_KEY_FILE` | (legacy path) |
| Sonarr | `OIKOS_SONARR_KEY` | `OIKOS_SONARR_KEY_FILE` | `docker exec sonarr` fallback |
| Lidarr | `OIKOS_LIDARR_KEY` | `OIKOS_LIDARR_KEY_FILE` | `docker exec lidarr` fallback |

With the compose stack, point the `*_KEY_FILE` vars at each container's `config.xml`
(e.g. `homelab/config/radarr/config.xml`) and `OIKOS_JF_KEY_FILE` at the `jf.key`
that `stack-setup.py` / `jellyfin-setup.sh` writes.

The launchers in [`hub/scripts/`](hub/scripts/) (`run-ps2`, `run-n64`, `play-video`,
`play-audio`, `stop-game`) are what the hub shells out to. Install them on `PATH`.
They assume `XDG_RUNTIME_DIR=/run/user/1000` (uid 1000) and `WAYLAND_DISPLAY=wayland-1` —
adjust for your user. `play-video` carries the hardware-decode and audio tuning
(`LIBVA_DRIVER_NAME=iHD` for Intel iGPUs; change for AMD/NVIDIA).

`stop-game` is called before **every** launch — game, media, or an app from the
`APPS` list — and kills whatever else is currently in the foreground (emulators,
`mpv`, and any app process named in `APPS`, including the Home Screen kiosk
browser itself). Only one thing owns the screen at a time; add a new app's
process name to it if `pkill -x` doesn't find it under its own binary name.

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

## Home Screen

The TV's own surface, at `/home` on the same server — a kiosk page for whoever's
on the couch without their phone out. There's no keyboard or mouse on the TV, so
every interaction is remote:

- **Sidebar** (Início/Movies/Series/Music/Games/Search/Downloads/Apps) — hidden by
  default, slides in and pushes the content over (doesn't overlay it) when you
  press left from the leftmost card. Categories switch live while you browse the
  sidebar, no need to confirm with OK.
- **Search** spans Radarr + Sonarr + Lidarr together, same as the phone's Busca
  tab. There's no keyboard on the TV to type with — the query is typed **on the
  phone** (a text field in the Controle tab) and streamed to the TV live via
  polling (`/api/search-query`); the TV jumps to the Search screen by itself the
  moment you start typing, from anywhere. Selecting a result opens the same detail
  view as a local item, synopsis and all, with a "download" action in place of
  "play".
- **Downloads** is a read-only queue view (Radarr+Sonarr+Lidarr, reuses
  `/api/downloads`).
- **Apps** is the same `APPS` grid as the phone's Apps tab.
- The remote itself lives in the phone's existing **Controle** tab, not a
  separate one — it's contextual (`/api/status`'s `kind`): a d-pad + search field
  while the Home Screen is up, the gamepad or media remote when a game or video is
  running instead.

### How the remote works

A second virtual input device (`KBD`, a `uinput` keyboard alongside the existing
gamepad) sends `KEY_UP/DOWN/LEFT/RIGHT/ENTER/ESC` on `POST /api/remote`
`{"key": "up"|"down"|"left"|"right"|"ok"|"back"}`. Same `/dev/uinput` requirement
as the gamepad.

### Autostart

Add the kiosk to your compositor's autostart so it's there after every reboot,
not just after the hub relaunches it. Sway (`~/.config/sway/config`):

```
exec sh -c "sleep 3; librewolf --kiosk http://localhost:8100/home"
```

The `sleep` gives `console-hub.py` time to be listening before the browser
requests the page. Firefox/Librewolf don't reliably pick up the host's timezone
in kiosk mode (even with `TZ` set on a fresh process) — the clock and day/night
theme use `Intl.DateTimeFormat` with an explicit `timeZone` instead of trusting
the system one; change it in `hub/console-hub.py` if you're not in
`America/Sao_Paulo`.

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
processes on the host** (emulators, mpv, apps, the kiosk browser) on request.
Treat it accordingly.

- **`/home` (the TV's Home Screen) skips the login entirely**, on purpose — it's
  meant for a physically-present TV, not a device someone reaches over the
  network. `OIKOS_PASSWORD`/`OIKOS_TOKEN` only gate the phone's `/`.
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
- Browsing the Music tab itself has no search box on purpose — public indexers
  rarely carry music, Lidarr's browse metadata is patchy, and album covers are
  hit or miss. Fill `/media/music` yourself and let Navidrome pick it up. The
  unified Busca tab does search Lidarr (for requesting new artists), it's just
  not wired into the Music tab's own browsing.
- Legality is on you: use your own game dumps and legally obtained media.

## License

MIT. See [LICENSE](LICENSE).
