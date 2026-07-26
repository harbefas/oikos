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
  sway retroarch grim \
  tailscale
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
sudo mkdir -p "$MEDIA"/{downloads/{incomplete,movies,series,music},movies,series,music,roms/{ps2,n64},roms/.covers}
sudo chown -R "$USER_NAME:$USER_NAME" "$MEDIA"
sudo find "$MEDIA" -type d -exec chmod 2775 {} +   # setgid: new files inherit group

# --- 4. media stack --------------------------------------------------------
say "Bringing up the media stack (docker compose)"
cd "$REPO_DIR/homelab"
PUID="$PUID" PGID="$PGID" TZ="$TZ" docker compose up -d
# note: Jellyfin needs /dev/dri; if the box has no iGPU, remove that block.

# (Transmission runs in the compose now -- no host setup needed.)

# --- 5. wire the stack (Jellyfin wizard, arrs, download client, Prowlarr) ---
say "Configuring the stack via API (stack-setup.py)"
python "$REPO_DIR/homelab/stack-setup.py" || \
  warn "stack-setup.py failed (containers still starting?). Re-run it, or paste agent-config-prompt.md to an agent."

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
Environment=OIKOS_JF_KEY_FILE=$REPO_DIR/homelab/jf.key
Environment=OIKOS_RADARR_KEY_FILE=$REPO_DIR/homelab/config/radarr/config.xml
Environment=OIKOS_SONARR_KEY_FILE=$REPO_DIR/homelab/config/sonarr/config.xml
Environment=OIKOS_HOME=/home/$USER_NAME
ExecStart=/usr/bin/python3 /opt/console-hub/console-hub.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable console-hub || warn "start console-hub after configuring paths in console-hub.py"

# --- done ------------------------------------------------------------------
IP="$(ip -4 addr show scope global | grep -oP '(?<=inet )[\d.]+' | head -1)"
say "Base install done. stack-setup.py already wired Jellyfin + arrs + Prowlarr."
cat <<EOF

  Left to do by hand:
  1. Log out/in (or 'newgrp docker') so the docker group applies.
  2. tailscale up          # interactive login, for access outside the LAN
  3. Prowlarr (http://$IP:9696): add your indexers (public: re-run
       python homelab/stack-setup.py thepiratebay). They sync to the arrs automatically.
  4. Bazarr (http://$IP:6767): enable a language + profile + a subtitle provider
     (needs your provider account). Three screens, or it silently does nothing.
  5. Jellyfin VAAPI: hardware transcoding is optional; enable it in the dashboard.
  6. Start the hub:  sudo systemctl start console-hub   (open http://$IP:8100)
  7. Gamepad: add yourself to the 'input' group + a udev rule for /dev/uinput,
     or the phone pad stays disabled (media/mouse/keyboard still work).
  8. Emulators: PS2 = pcsx2-latest-bin (AUR) + your own BIOS; see emulators/README.md.
     Games work without the arr stack.

EOF
