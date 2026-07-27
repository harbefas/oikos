# Emulators (N64 + PS2)

The games tab launches RetroArch (N64) and PCSX2 (PS2), and your phone becomes the
controller. This is the part the bootstrap can only half-automate: RetroArch and its
N64 core install from the repos, but PCSX2 is AUR and the PS2 BIOS you must supply
yourself (it is copyrighted; dump it from your own console).

Bring your own **ROMs** (dump your own discs/carts) and **PS2 BIOS**. None of that
ships here.

## The virtual gamepad autoconfig (do this or nothing works)

The hub creates `uinput` gamepads in the kernel. RetroArch ignores an unknown pad
and logs `not configured` unless there is an autoconfig matching it by name/VID/PID.
[`HomelabVirtualGamepad.cfg`](HomelabVirtualGamepad.cfg) is that file, and the
button order in the hub's code depends on the indices in it. Install it:

```bash
install -Dm644 HomelabVirtualGamepad.cfg \
  ~/.config/retroarch/autoconfig/udev/HomelabVirtualGamepad.cfg
```

Two players work because the hub creates **two identical** devices (same name/VID/PID).
The autoconfig matches both; the emulator assigns ports by connection order (the
device created first, with the lower `event` number, is P1). RetroArch needs
`input_player2_joypad_index = 1`; PCSX2 maps the second pad as `[Pad2]` -> `SDL-1`.

PCSX2 needs no autoconfig: since the pad is a real kernel device, PCSX2's SDL layer
sees it as a DualShock and the mapping is already in its ini.

## RetroArch (N64)

Install: `retroarch` + an N64 core (`libretro-mupen64plus-next`). Settings that
matter (RetroArch overwrites its config on exit, so set `config_save_on_exit = false`
**first**, or edit while it is closed):

```
video_driver = "vulkan"          # needs vulkan-intel; parallel-rdp core runs on it
pause_nonactive = "false"        # or the game pauses when the window loses focus
config_save_on_exit = "false"    # or RetroArch clobbers your edits on quit
input_player2_joypad_index = "1" # second virtual pad -> player 2
```

- **Core: parallel-rdp** (Vulkan). angrylion is pure software: it took the N64 from
  34% to 325% CPU here. Pick parallel-rdp in the core options.
- N64 button map in the hub: **Z -> L2**, **C-buttons -> right analog stick**.
- Launch via `run-n64` (in [`../hub/scripts`](../hub/scripts)), which exports
  `WAYLAND_DISPLAY` so RetroArch does not open on a "null" display under Sway.

## PS2 (PCSX2)

Install `pcsx2-latest-bin` from the AUR (prebuilt binary; avoids a compile that has
failed on low-RAM boxes), or grab the official **AppImage** if you can't use the AUR
(no root needed). `run-ps2` calls `pcsx2-qt` by default; point it elsewhere with the
`PCSX2` env var, e.g. `PCSX2=~/pcsx2.AppImage` (it adds `--appimage-extract-and-run`
automatically on `.AppImage`). Then:

- **BIOS** (yours): put e.g. `scph39001.bin` (NTSC-U) in `~/.config/PCSX2/bios/`.
- **Renderer:** Vulkan (`Renderer = 14`), native 1x upscale, vsync off, in
  `~/.config/PCSX2/inis/PCSX2.ini`. There is headroom for 2x (a real game measured
  at 28% CPU / 74C here), raise it if you want.
- **Controller:** PCSX2 needs SDL pad bindings for the hub's virtual gamepad, or the
  phone does nothing. Append [`PCSX2-pad.ini`](PCSX2-pad.ini) to
  `~/.config/PCSX2/inis/PCSX2.ini` **with PCSX2 closed** (it rewrites the ini on exit):
  it enables the SDL input source and binds `Pad1 -> SDL-0`, `Pad2 -> SDL-1` (the two
  virtual pads). The pads must already exist when PCSX2 starts, so the hub launches it.
- **Fullscreen:** `run-ps2` passes `-fullscreen`.
- **Memory card:** add a `[MemoryCards]` section pointing
  `Slot1_Filename = Mcd001.ps2`, or games report "unformatted". Format it from the
  console's Browser: launch the BIOS with **no** game (`run-ps2 -bios`). Launching
  straight into a disc skips the format screen.
- Launch a game: `run-ps2 '/media/roms/ps2/game.iso'`. `run-ps2` also exports
  `QT_QPA_PLATFORM=wayland` (same null-display trap as RetroArch).

## ROMs and covers

```
/media/roms/ps2/<game>.{iso,chd,bin}
/media/roms/n64/<game>.{n64,z64,v64}
/media/roms/.covers/<system>/<rom-stem>.png
```

Fetch box art automatically from [libretro-thumbnails](https://github.com/libretro-thumbnails)
by name:

```bash
python3 fetch-covers.py   # writes /media/roms/.covers/<system>/<rom>.png
```

Titles that do not match by name print `sem capa`; drop a `<rom-stem>.png` into the
covers folder by hand for those.

## Heat

One emulator at a time. RetroArch and PCSX2 together hit 87C here (throttle at
100C); alone each sits around 57-71C. The hub's `stop-game` kills whatever is
running before launching the next, so use it (the games tab already does).
