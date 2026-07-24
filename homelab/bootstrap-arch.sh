#!/usr/bin/env bash
# Homelab bootstrap for Arch Linux: installs deps, brings the media stack up,
# installs Console Hub + launchers. Idempotent - safe to re-run.
#
# What it does NOT do (needs a human, by design):
#   - Tailscale login (interactive), Sway autologin, emulator install (AUR)
#   - arr API keys / indexers / quality profiles (set in each web UI)
#   - Jellyfin libraries, Bazarr languages (3 screens)
# A checklist for all of that prints at the end.
#
# Untested end to end (the author's box is already set up). Reads defensively;
# review before running on a machine you care about. Run as your normal user
# (it uses sudo where needed), NOT as root.
set -euo pipefail

# --- config (override via env) --------------------------------------------
MEDIA="${MEDIA:-/media}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
PUID="$(id -u "$USER_NAME")"
PGID="$(id -g "$USER_NAME")"
TZ="$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] && { warn "run as your normal user, not root"; exit 1; }
command -v pacman >/dev/null || { warn "this script is for Arch (pacman)"; exit 1; }

# --- 1. packages -----------------------------------------------------------
say "Installing packages"
sudo pacman -Syu --needed --noconfirm \
  git python python-evdev mpv \
  docker docker-compose \
  intel-media-driver libva-utils vulkan-intel \
  sway retroarch \
  transmission-cli tailscale
# retroarch cores come separately:
sudo pacman -S --needed --noconfirm libretro-mupen64plus-next 2>/dev/null || \
  warn "install an N64 core manually (e.g. libretro-mupen64plus-next from AUR)"

# virtual-gamepad autoconfig for RetroArch (without it the phone pad does NOTHING)
install -Dm644 "$REPO_DIR/emulators/HomelabVirtualGamepad.cfg" \
  "$HOME/.config/retroarch/autoconfig/udev/HomelabVirtualGamepad.cfg"
# (repo layout: the hub itself lives in hub/, the media stack here in homelab/)

# --- 2. docker -------------------------------------------------------------
say "Enabling Docker"
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER_NAME"   # takes effect on next login

# --- 3. media dirs (setgid + shared group so arrs can hardlink) -----------
say "Creating $MEDIA (setgid, group $USER_NAME)"
sudo mkdir -p "$MEDIA"/{downloads/{incomplete,filmes,series,musica},filmes,series,musica,roms/{ps2,n64},roms/.covers}
sudo chown -R "$USER_NAME:$USER_NAME" "$MEDIA"
sudo find "$MEDIA" -type d -exec chmod 2775 {} +   # setgid: new files inherit group

# --- 4. media stack --------------------------------------------------------
say "Bringing up the media stack (docker compose)"
cd "$REPO_DIR/homelab"
PUID="$PUID" PGID="$PGID" TZ="$TZ" docker compose up -d
# note: Jellyfin needs /dev/dri; if the box has no iGPU, remove that block.

# --- 5. transmission on the host (not Docker) -----------------------------
say "Configuring Transmission (host, umask 002 so arrs can hardlink imports)"
sudo mkdir -p /etc/systemd/system/transmission.service.d
sudo tee /etc/systemd/system/transmission.service.d/override.conf >/dev/null <<EOF
[Service]
UMask=0002
EOF
sudo systemctl enable transmission || warn "enable transmission manually"
warn "Set Transmission download dir to $MEDIA/downloads and categories filmes/series/musica in its config, then: sudo systemctl restart transmission"

# --- 6. Console Hub + launchers -------------------------------------------
say "Installing Console Hub + launchers"
sudo install -m755 "$REPO_DIR"/hub/scripts/* /usr/local/bin/
sudo install -Dm755 "$REPO_DIR/hub/console-hub.py" /opt/console-hub/console-hub.py
sudo tee /etc/systemd/system/console-hub.service >/dev/null <<EOF
[Unit]
Description=Console Hub
After=graphical.target

[Service]
User=$USER_NAME
ExecStart=/usr/bin/python3 /opt/console-hub/console-hub.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable console-hub || warn "start console-hub after configuring paths in console-hub.py"

# --- done ------------------------------------------------------------------
IP="$(ip -4 addr show scope global | grep -oP '(?<=inet )[\d.]+' | head -1)"
say "Base install done. Manual steps left:"
warn "Steps 3-9 below can be done for you: paste homelab/agent-config-prompt.md to a coding agent with shell access on this box."
cat <<EOF

  1. Log out/in (or 'newgrp docker') so the docker group applies.
  2. tailscale up          # interactive login, for access outside the LAN
  3. Point Prowlarr (http://$IP:9696) at your indexers, then link Radarr/Sonarr/Lidarr.
     Inside containers, reach each other + Transmission via 172.17.0.1 (NOT localhost).
  4. In Radarr/Sonarr: add download client Transmission (172.17.0.1:9091),
     set a 1080p quality profile, add remote path map /media/ -> /downloads/.
  5. Jellyfin (http://$IP:8096): add libraries /media/filmes and /media/series,
     enable VAAPI hardware transcoding.
  6. Bazarr: enable a language + create a profile + apply it (three screens).
  7. Edit /opt/console-hub/console-hub.py if your paths/ports differ, put the
     Jellyfin/Radarr/Sonarr API keys where it reads them, then:
       sudo systemctl start console-hub
     Open http://$IP:8100 on your phone.
  8. Emulators: N64 (RetroArch) deps installed above. For PS2 install pcsx2-latest-bin
     from the AUR and supply your own BIOS. Full config (parallel-rdp core, memory
     card, quality flags) in emulators/README.md. Games work without the arr stack.

EOF
