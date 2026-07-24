# Console Hub

Turn any old PC into a couch console you drive from your phone. One web page,
no app to install: tap a game cover and it launches on the TV and your phone
becomes the gamepad; tap a movie and the same page becomes a media remote.

Built for a screenless laptop running a Sway session on the TV over HDMI, wired
into an [arr](https://wiki.servarr.com/) media stack (Jellyfin + Radarr + Sonarr).

## What it does

- **Games** — grid of box art for PS2 (PCSX2) and N64 (RetroArch). Tap to launch;
  the phone turns into a virtual gamepad. Two players via `?p=2` (two identical
  `uinput` devices, so an emulator autoconfig binds both).
- **Movies / Series** — posters pulled from Jellyfin as a catalog, played with
  **mpv** on the TV (not Jellyfin's own player). Built-in search adds titles to
  Radarr/Sonarr and shows live download progress (a tiny Jellyseerr).
- **Music** — albums from a folder, played as an mpv playlist.
- **Media remote** — the same page becomes play/pause, seek, volume, audio/subtitle
  cycling and prev/next, talking to mpv over its IPC socket. It switches between
  gamepad and remote automatically based on what is running.

No app, no HTTPS required (uses the Fullscreen API, which works over plain HTTP on
Android). Single Python file, standard library plus `python-evdev`.

## Requirements

- Linux with a **Sway** session on the TV (autologin on a TTY works well)
- Python 3 and [`python-evdev`](https://pypi.org/project/evdev/)
- `mpv` for video/music, and emulators you want: `pcsx2-qt`, `retroarch`
- Optional catalog/download stack, each on localhost: Jellyfin (`:8096`),
  Radarr (`:7878`), Sonarr (`:8989`). The games-only mode needs none of them.
- Runs as a user in the `input` group (to create `uinput` devices)

## Layout it expects

Everything is a constant at the top of `console-hub.py` — edit to taste:

| What | Default | Constant |
|------|---------|----------|
| ROMs | `/media/roms/{ps2,n64}` | `ROMS` |
| Game covers | `/media/roms/.covers/<system>/<rom>.png` | `COVERS` |
| Music | `/media/musica/<album>/` | `MUSIC` |
| mpv IPC socket | `/tmp/mpv.sock` | `MPV_SOCK` |
| Port | `8100` | `PORT` |
| Jellyfin | `http://localhost:8096` | `JF` |
| Radarr / Sonarr | `http://localhost:{7878,8989}` | `RADARR` / `SONARR` |

API keys are **read from disk at runtime**, never hardcoded: Jellyfin from
`/srv/jellyfin/console-hub.key`, Radarr/Sonarr from each container's `config.xml`.
Point these at your own paths in the code.

The scripts in [`scripts/`](scripts/) are the launchers the hub shells out to
(`run-ps2`, `run-n64`, `filme`, `musica`, `stop-game`). Install them on `PATH`.
They assume `XDG_RUNTIME_DIR=/run/user/1000` (uid 1000) and `WAYLAND_DISPLAY=wayland-1` —
adjust for your user. `filme` carries the hardware-decode and audio tuning
(`LIBVA_DRIVER_NAME=iHD` for Intel iGPUs; change for AMD/NVIDIA).

## Run

```bash
sudo install -m755 scripts/* /usr/local/bin/
python3 console-hub.py
```

Then open `http://<server-ip>:8100` on your phone (same LAN, or over Tailscale).
Player 2: `http://<server-ip>:8100/?p=2`.

### As a service

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

## Whole-homelab bootstrap (Arch)

To stand up the full stack, not just the hub, [`homelab/`](homelab/) has an
Arch bootstrap:

```bash
./homelab/bootstrap-arch.sh
```

It installs deps, creates `/media` with the permissions hardlinks need, brings up
the media stack ([`homelab/docker-compose.yml`](homelab/docker-compose.yml):
Jellyfin, Radarr, Sonarr, Lidarr, Prowlarr, Bazarr, Jellyseerr, FlareSolverr,
Navidrome), installs the hub + launchers as a service, and prints a checklist for
the parts that can't be scripted (Tailscale login, indexers, quality profiles,
Jellyfin libraries, Bazarr languages). It is idempotent; review it before running.

## Notes

- Covers for games come from [libretro-thumbnails](https://github.com/libretro-thumbnails);
  drop `<rom-name>.png` into the covers folder if a title does not match.
- Music has no search on purpose — public indexers rarely carry music and Lidarr's
  metadata is poor. Fill `/media/musica` yourself.
- Legality is on you: use your own game dumps and legally obtained media.

## License

MIT. See [LICENSE](LICENSE).
